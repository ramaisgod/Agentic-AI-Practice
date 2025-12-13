# core/database.py
from psycopg_pool import ConnectionPool
from psycopg import Connection
from langgraph.checkpoint.postgres import PostgresSaver

RAW_DSN = "postgresql://postgres:postgres@localhost:5433/icertis"

# ----------------------------------------------------
# 1) Application DB Pool (for users, conversations, messages)
# ----------------------------------------------------
app_pool = ConnectionPool(
    RAW_DSN,
    min_size=1,
    max_size=8,
)

# ----------------------------------------------------
# 2) LangGraph Checkpointer (MUST NOT use pool)
# ----------------------------------------------------
def init_checkpointer() -> PostgresSaver:
    """
    LangGraph requires a *single psycopg Connection* or ConnectionPool,
    BUT ConnectionPool causes cursor rollback conflicts with app queries.

    So we create a dedicated psycopg Connection
    exclusively for LangGraph state storage.
    """
    conn = Connection.connect(RAW_DSN, autocommit=True)

    checkpointer = PostgresSaver(conn)
    checkpointer.setup()   # run table migrations once

    return checkpointer


# Create a module-level checkpointer instance
checkpointer = init_checkpointer()
