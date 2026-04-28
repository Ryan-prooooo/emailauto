-- =============================================================================
-- MailLife Database Initialization Script
-- PostgreSQL 16+
-- =============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- Tables
-- =============================================================================

-- Email messages
CREATE TABLE IF NOT EXISTS emails (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id VARCHAR(500) UNIQUE NOT NULL,
    subject VARCHAR(1000),
    sender VARCHAR(500),
    recipient VARCHAR(500),
    date TIMESTAMP WITH TIME ZONE,
    body_text TEXT,
    body_html TEXT,
    category VARCHAR(50),
    is_read BOOLEAN DEFAULT FALSE,
    is_processed BOOLEAN DEFAULT FALSE,
    parsed_at TIMESTAMP WITH TIME ZONE,
    raw_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Events extracted from emails
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    event_type VARCHAR(50),
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    location VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    organizer VARCHAR(500),
    attendees TEXT,
    rsvp_status VARCHAR(20) DEFAULT 'pending',
    meeting_link VARCHAR(1000),
    calendar_event_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User settings
CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    description VARCHAR(500),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat history
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(100),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(20),
    agent_name VARCHAR(50),
    memory_type VARCHAR(20) DEFAULT 'recent',
    summary TEXT,
    meta_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category);
CREATE INDEX IF NOT EXISTS idx_emails_is_processed ON emails(is_processed);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date DESC);
CREATE INDEX IF NOT EXISTS idx_events_email_id ON events(email_id);
CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_rsvp_status ON events(rsvp_status);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_agent_name ON chat_messages(agent_name);

-- Full text search index
CREATE INDEX IF NOT EXISTS idx_emails_body_text_trgm ON emails USING gin(body_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_emails_subject_trgm ON emails USING gin(subject gin_trgm_ops);

-- =============================================================================
-- Functions
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for auto-update
DROP TRIGGER IF EXISTS update_emails_updated_at ON emails;
CREATE TRIGGER update_emails_updated_at
    BEFORE UPDATE ON emails
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_events_updated_at ON events;
CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_settings_updated_at ON settings;
CREATE TRIGGER update_settings_updated_at
    BEFORE UPDATE ON settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Initial Data
-- =============================================================================

-- Default settings
INSERT INTO settings (key, value, description) VALUES
    ('check_interval_minutes', '5', 'Email check interval in minutes'),
    ('scheduled_send_hour', '9', 'Daily digest send hour (0-23)'),
    ('scheduled_send_minute', '0', 'Daily digest send minute (0-59)'),
    ('ai_model', 'qwen-plus', 'AI model to use (阿里百炼)'),
    ('theme', 'light', 'UI theme (light/dark)')
ON CONFLICT (key) DO NOTHING;
