# db_utils.py
import json
import uuid
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from core.database import app_pool
from core.logger import logger


# -------------------------------------------------------
# CONNECTION MANAGER (psycopg3 native)
# -------------------------------------------------------
@contextmanager
def get_conn(transactional=False):
    conn = None
    try:
        conn = app_pool.getconn()
        cur = conn.cursor()

        if transactional:
            with conn.transaction():
                yield cur
        else:
            yield cur

    except Exception as e:
        logger.exception("DB error: %s", e)
        raise
    finally:
        if conn:
            app_pool.putconn(conn)


# -------------------------------------------------------
# USERS
# -------------------------------------------------------
def get_or_create_user(email: str):
    sql_select = "SELECT user_id FROM users WHERE email = %s"
    sql_insert = """
        INSERT INTO users (user_id, email)
        VALUES (%s, %s)
        RETURNING user_id
    """

    with get_conn(transactional=True) as cur:
        cur.execute(sql_select, (email,))
        row = cur.fetchone()
        if row:
            return row[0]

        new_id = uuid.uuid4()
        cur.execute(sql_insert, (new_id, email))
        return cur.fetchone()[0]


# -------------------------------------------------------
# CONVERSATIONS
# -------------------------------------------------------
def create_conversation(user_id: uuid.UUID, thread_id: str):
    sql = """
        INSERT INTO conversations (conversation_id, user_id, thread_id)
        VALUES (%s, %s, %s)
        RETURNING conversation_id
    """

    new_id = uuid.uuid4()
    with get_conn(transactional=True) as cur:
        cur.execute(sql, (new_id, user_id, thread_id))
        return cur.fetchone()[0]



def get_conversation_by_thread(thread_id: str):
    sql = """
        SELECT conversation_id, user_id, thread_id, title, summary, created_at, updated_at
        FROM conversations
        WHERE thread_id = %s
    """

    with get_conn() as cur:
        cur.execute(sql, (thread_id,))
        row = cur.fetchone()

    if not row:
        return None

    return {
        "conversation_id": row[0],
        "user_id": row[1],
        "thread_id": row[2],
        "title": row[3],
        "summary": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


# -------------------------------------------------------
# MESSAGES
# -------------------------------------------------------
def add_message(conversation_id, role, content, metadata=None):
    sql_insert = """
        INSERT INTO messages (message_id, conversation_id, role, content, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING message_id
    """
    sql_update = "UPDATE conversations SET updated_at = NOW() WHERE conversation_id = %s"

    msg_id = uuid.uuid4()
    meta_json = json.dumps(metadata or {})

    with get_conn(transactional=True) as cur:
        cur.execute(sql_insert, (msg_id, conversation_id, role, content, meta_json))
        cur.execute(sql_update, (conversation_id,))
        return msg_id


# -------------------------------------------------------
# MESSAGE LISTING
# -------------------------------------------------------
def get_conversation_messages(conversation_id: uuid.UUID, limit: int = 200):
    logger.info("get_conversation_messages: cid=%s limit=%d", conversation_id, limit)

    sql = """
        SELECT message_id, role, content, metadata, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        LIMIT %s
    """

    try:
        with get_conn() as cur:
            cur.execute(sql, (conversation_id, limit))
            rows = cur.fetchall()

        msgs = []
        for r in rows:
            meta = r[3]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {"raw": meta}

            msgs.append({
                "message_id": r[0],
                "role": r[1],
                "content": r[2],
                "metadata": meta,
                "created_at": r[4],
            })

        return msgs

    except Exception as e:
        logger.exception("get_conversation_messages failed: %s", e)
        raise


# -------------------------------------------------------
# USER CONVERSATION LIST
# -------------------------------------------------------
def list_conversations_for_user(user_id: uuid.UUID, limit: int = 20, offset: int = 0):
    logger.info("list_conversations_for_user: user_id=%s limit=%d offset=%d",
                user_id, limit, offset)

    sql = """
        SELECT conversation_id, thread_id, title, summary, updated_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY updated_at DESC
        LIMIT %s OFFSET %s
    """

    try:
        with get_conn() as cur:
            cur.execute(sql, (user_id, limit, offset))
            rows = cur.fetchall()

        return [
            {
                "conversation_id": r[0],
                "thread_id": r[1],
                "title": r[2],
                "summary": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]

    except Exception as e:
        logger.exception("list_conversations_for_user failed: %s", e)
        raise
