# checkpointer.py
import json
import time
from sqlalchemy import text
from sqlalchemy.engine import Engine
from typing import Optional, Dict, Any, Iterable
from core.logger import logger


class PostgresCheckpointer:
    """
    Postgres-backed checkpointer storing JSON snapshots in `checkpoints` table.

    Notes:
      - LangGraph expects methods such as:
          - get(thread_id)
          - save(thread_id, checkpoint_obj, version=None, **kwargs)
          - delete(thread_id)
          - get_next_version(thread_id)
          - put_writes(thread_id, writes, version=None, **kwargs)
      - put_writes is used by LangGraph to atomically apply a batch of write operations;
        we implement a flexible handler that understands common shapes and delegates to save/delete.
      - If you need strict optimistic concurrency, add a 'version' column and adapt get_next_version/save accordingly.
    """

    def __init__(self, engine: Engine):
        self._engine = engine
        logger.info("PostgresCheckpointer initialized with engine=%s", engine)

    def _preview(self, data, limit: int = 300):
        """Safe preview for logging."""
        try:
            s = json.dumps(data)
            return s if len(s) <= limit else s[:limit] + "..."
        except Exception:
            return str(data)[:limit] + "..."

    # ---------------------------------------------
    # GET
    # ---------------------------------------------
    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        logger.info("Checkpoint GET requested for thread_id=%s", thread_id)
        start = time.time()

        sql = text("SELECT checkpoint FROM checkpoints WHERE thread_id = :thread_id")

        try:
            with self._engine.connect() as conn:
                row = conn.execute(sql, {"thread_id": thread_id}).fetchone()

            if not row:
                logger.info("No checkpoint found for thread_id=%s (elapsed=%.3fs)", thread_id, time.time() - start)
                return None

            raw_value = row[0]
            logger.debug("Raw checkpoint fetched (preview): %s", self._preview(raw_value))

            try:
                result = raw_value if isinstance(raw_value, dict) else json.loads(raw_value)
                logger.info("Checkpoint loaded successfully (elapsed=%.3fs)", time.time() - start)
                return result
            except Exception as e:
                logger.exception("Failed to parse checkpoint JSON for thread_id=%s: %s", thread_id, e)
                return None

        except Exception as e:
            logger.exception("Error retrieving checkpoint for thread_id=%s: %s", thread_id, e)
            return None

    # ---------------------------------------------
    # SAVE (accepts optional version param from LangGraph)
    # ---------------------------------------------
    def save(self, thread_id: str, checkpoint_obj: Dict[str, Any], version: Optional[Any] = None, **kwargs) -> None:
        """
        Save (upsert) a checkpoint. LangGraph may pass a version token — we accept it but do not
        currently enforce versioning in the DB layer. If you desire strict optimistic concurrency,
        add a 'version' column and implement conditional updates.
        """
        logger.info("Checkpoint SAVE requested for thread_id=%s version=%s", thread_id, version)
        logger.debug("Checkpoint data preview: %s", self._preview(checkpoint_obj))

        start = time.time()

        try:
            serialized = json.dumps(checkpoint_obj)
        except Exception:
            logger.exception("Failed serializing checkpoint object for thread_id=%s", thread_id)
            return

        sql = text("""
            INSERT INTO checkpoints (thread_id, checkpoint)
            VALUES (:thread_id, :checkpoint::jsonb)
            ON CONFLICT (thread_id) DO UPDATE
              SET checkpoint = EXCLUDED.checkpoint, updated_at = now()
        """)

        try:
            with self._engine.begin() as conn:
                conn.execute(sql, {"thread_id": thread_id, "checkpoint": serialized})
            logger.info("Checkpoint saved successfully (elapsed=%.3fs)", time.time() - start)
        except Exception as e:
            logger.exception("Failed saving checkpoint for thread_id=%s: %s", thread_id, e)

    # ---------------------------------------------
    # DELETE
    # ---------------------------------------------
    def delete(self, thread_id: str) -> None:
        logger.info("Checkpoint DELETE requested for thread_id=%s", thread_id)
        start = time.time()

        sql = text("DELETE FROM checkpoints WHERE thread_id = :thread_id")

        try:
            with self._engine.begin() as conn:
                conn.execute(sql, {"thread_id": thread_id})
            logger.info("Checkpoint deleted for thread_id=%s (elapsed=%.3fs)", thread_id, time.time() - start)
        except Exception as e:
            logger.exception("Failed to delete checkpoint for thread_id=%s: %s", thread_id, e)

    # ---------------------------------------------
    # LANGGRAPH: get_next_version
    # ---------------------------------------------
    def get_next_version(self, thread_id: str) -> int:
        """
        Return a fresh version token. LangGraph uses this to coordinate checkpoint versions.
        We return a monotonic millisecond timestamp as an integer token.

        This is a simple, safe implementation that satisfies LangGraph's expectation.
        If you require DB-backed version checking, change this to read/update a 'version' column.
        """
        token = int(time.time() * 1000)
        logger.debug("get_next_version for thread_id=%s -> %s", thread_id, token)
        return token

    # ---------------------------------------------
    # LANGGRAPH: put_writes
    # ---------------------------------------------
    def put_writes(self, thread_id: str, writes: Iterable, version: Optional[Any] = None, **kwargs) -> None:
        """
        Apply a batch of write operations for the given thread_id.

        Supported shapes (flexible handling):
          - writes is a list of dicts like:
              [{"op": "save", "checkpoint": {...}}, {"op": "delete"}]
          - writes is a single dict representing a checkpoint (treated as save)
          - writes is a list of raw checkpoint dicts
        Behavior:
          - For 'save' items or checkpoint dicts -> call self.save(...)
          - For 'delete' items -> call self.delete(...)
          - Unknown items are logged and skipped
        """
        logger.info("put_writes called for thread_id=%s version=%s writes_preview=%s",
                    thread_id, version, self._preview(writes))
        start = time.time()

        # Normalize to iterable
        if writes is None:
            logger.debug("No writes provided to put_writes; nothing to do.")
            return

        # If a single dict is passed, treat it as a single save
        if isinstance(writes, dict):
            try:
                # If dict looks like a write descriptor
                if writes.get("op") == "delete":
                    logger.debug("put_writes: single dict delete -> deleting checkpoint")
                    self.delete(thread_id)
                else:
                    checkpoint = writes.get("checkpoint") if "checkpoint" in writes else writes
                    logger.debug("put_writes: single dict save -> saving checkpoint (preview)")
                    self.save(thread_id, checkpoint, version=version)
            except Exception as e:
                logger.exception("put_writes single-dict handling failed: %s", e)
            return

        # If writes is an iterable (list, tuple, etc.), iterate and handle each
        try:
            for idx, item in enumerate(writes):
                try:
                    logger.debug("put_writes processing item[%d]: %s", idx, self._preview(item))
                    if item is None:
                        logger.debug("Skipping None item in writes")
                        continue

                    # If item is a dict with explicit op
                    if isinstance(item, dict) and item.get("op"):
                        op = item.get("op").lower()
                        if op == "delete":
                            logger.info("put_writes item[%d] -> delete", idx)
                            self.delete(thread_id)
                        elif op in ("save", "upsert", "write", "checkpoint"):
                            ch = item.get("checkpoint") or item.get("data") or item
                            logger.info("put_writes item[%d] -> save", idx)
                            self.save(thread_id, ch, version=version)
                        else:
                            logger.warning("put_writes item[%d] unknown op=%s; skipping", idx, op)
                    # If item looks like a raw checkpoint dict -> save
                    elif isinstance(item, dict):
                        logger.info("put_writes item[%d] looks like checkpoint dict -> save", idx)
                        self.save(thread_id, item, version=version)
                    else:
                        # Unknown shape (string / number / other) — log and skip
                        logger.warning("put_writes item[%d] has unsupported type %s; skipping", idx, type(item))
                except Exception as e:
                    logger.exception("Failed processing writes item[%d]: %s", idx, e)
        except TypeError:
            # writes not iterable (e.g., a primitive) — attempt to save as single checkpoint
            logger.warning("put_writes received non-iterable writes; attempting to save as single checkpoint")
            try:
                self.save(thread_id, writes, version=version)
            except Exception:
                logger.exception("Failed saving non-iterable writes object")
        except Exception as e:
            logger.exception("Unexpected error in put_writes: %s", e)

        logger.info("put_writes completed for thread_id=%s (elapsed=%.3fs)", thread_id, time.time() - start)
