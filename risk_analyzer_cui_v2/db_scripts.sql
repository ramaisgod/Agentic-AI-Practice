-- ===============================================================
--  SCHEMA FOR DURABLE CHAT + AGENT CHECKPOINTS (PostgreSQL)
-- ===============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===============================================================
-- USERS TABLE
-- ===============================================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);


-- ===============================================================
-- CONVERSATIONS TABLE
-- ===============================================================

CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    thread_id VARCHAR(255) UNIQUE NOT NULL,     -- LangGraph thread
    title VARCHAR(255),                         -- auto-generated from first message / summary
    summary TEXT,                               -- optional summary for UI
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_archived BOOLEAN DEFAULT FALSE,          -- optional archive support
    CONSTRAINT fk_conversation_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_thread ON conversations(thread_id);


-- ===============================================================
-- MESSAGES TABLE
-- ===============================================================

CREATE TABLE messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,         -- agent metadata, scores, flags, LLM tokens, etc.
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_message_conversation
        FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_created_at   ON messages(created_at);


-- ===============================================================
-- CHECKPOINTS TABLE (For LangGraph Durable Agents)
-- ===============================================================

CREATE TABLE checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id VARCHAR(255) NOT NULL,            -- same thread_id stored in conversations
    config JSONB NOT NULL,                      -- workflow config snapshot
    checkpoint JSONB NOT NULL,                  -- actual agent state snapshot
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_thread ON checkpoints(thread_id);
CREATE INDEX idx_checkpoints_created ON checkpoints(created_at);

ALTER TABLE checkpoints ADD COLUMN version bigint DEFAULT 0;

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT PRIMARY KEY,
    checkpoint JSONB NOT NULL,
    version BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    blob_id TEXT PRIMARY KEY,
    data BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_version
    ON checkpoints (version);



