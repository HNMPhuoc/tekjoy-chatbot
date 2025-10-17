CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
----9/4/2025----
---
-- TABLE: USERS & GROUPS
---

-- BẢNG QUẢN LÝ NGƯỜI DÙNG & NHÓM
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE user_groups (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

---
-- TABLE: FILES & FOLDERS
---

CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
	keyword TEXT NULL
);

CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_file_name VARCHAR(255) NOT NULL,
    file_extension VARCHAR(20),
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    storage_path VARCHAR(255) NOT NULL,
    thumbnail_path VARCHAR(255),
    document_type VARCHAR(50),
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_modified_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    uploaded_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    project_code VARCHAR(50),
    project_name VARCHAR(255),
    document_date DATE,
    vendor_name VARCHAR(255),
    contract_number VARCHAR(100),
    total_value DECIMAL(18,2),
    currency VARCHAR(10),
    warranty_period_months INTEGER,
    is_template BOOLEAN DEFAULT FALSE,
    keywords TEXT[],
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    folder_path TEXT,
    extracted_text TEXT,
    ai_summary JSONB,
    ai_extracted_data JSONB,
    download_link VARCHAR(255),
    char_count INTEGER,
    word_count INTEGER
);

-- Function to update the `last_modified_timestamp` on file updates.
CREATE OR REPLACE FUNCTION update_files_last_modified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_timestamp = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before each update on the `files` table.
CREATE TRIGGER files_last_modified_timestamp
BEFORE UPDATE ON files
FOR EACH ROW
EXECUTE FUNCTION update_files_last_modified_timestamp();

---
-- TABLE: ACCESS CONTROL
---

CREATE TABLE access_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE file_access_levels (
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    access_level_id UUID REFERENCES access_levels(id) ON DELETE CASCADE,
    PRIMARY KEY (file_id, access_level_id)
);

CREATE TABLE group_access_levels (
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    access_level_id UUID REFERENCES access_levels(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, access_level_id)
);

---
-- TABLE: CHAT SYSTEM
---

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE chat_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    model VARCHAR(100) NOT NULL DEFAULT 'gpt-4o-mini',
    max_tokens INTEGER,
    system_prompt TEXT,
    context_files UUID[],
    domain VARCHAR(100),
    is_history BOOLEAN DEFAULT TRUE,
    max_context_messages INTEGER DEFAULT 20,
    using_document BOOLEAN DEFAULT TRUE,
    free_chat BOOLEAN DEFAULT FALSE,
    show_sources BOOLEAN DEFAULT TRUE,
    enable_streaming BOOLEAN DEFAULT TRUE,
    response_style VARCHAR(50) DEFAULT 'concise',
    language VARCHAR(10) DEFAULT 'vi',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Function to update the `updated_at` timestamp before each update.
CREATE OR REPLACE FUNCTION update_chat_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chat_settings_updated_at
BEFORE UPDATE ON chat_settings
FOR EACH ROW
EXECUTE FUNCTION update_chat_settings_updated_at();

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender_type VARCHAR(50) NOT NULL,
    sender_id UUID REFERENCES users(id) ON DELETE SET NULL,
    message_text TEXT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    related_file_ids UUID[],
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    message_id UUID REFERENCES chat_messages(id) ON DELETE SET NULL,
    tokens_prompt INTEGER,
    tokens_completion INTEGER,
    cost_usd DECIMAL(10,5),
    model VARCHAR(100),
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

---
-- TABLE: SYSTEM CONFIG
---

CREATE TABLE system_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
); 

CREATE TABLE user_access_files (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, file_id)
);
---- 9/4/2025----

