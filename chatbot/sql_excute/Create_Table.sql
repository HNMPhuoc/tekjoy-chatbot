-- BẢNG QUẢN LÝ NGƯỜI DÙNG & NHÓM
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    full_name VARCHAR,
    role VARCHAR NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE groups (
    id VARCHAR PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE user_groups (
    user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
    group_id VARCHAR REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

---

-- FILES & FOLDERS
CREATE TABLE folders (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    parent_id VARCHAR REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE files (
    id VARCHAR PRIMARY KEY,
    original_file_name VARCHAR NOT NULL,
    file_extension VARCHAR,
    mime_type VARCHAR,
    file_size_bytes BIGINT,
    storage_path VARCHAR NOT NULL,
    thumbnail_path VARCHAR,
    document_type VARCHAR,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by_user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    processing_status VARCHAR NOT NULL DEFAULT 'pending',
    error_message TEXT,
    project_code VARCHAR,
    project_name VARCHAR,
    document_date DATE,
    vendor_name VARCHAR,
    contract_number VARCHAR,
    total_value DECIMAL(18,2),
    currency VARCHAR,
    warranty_period_months INTEGER,
    is_template BOOLEAN DEFAULT FALSE,
    keywords TEXT[],
    folder_id VARCHAR REFERENCES folders(id) ON DELETE CASCADE,
    folder_path VARCHAR,
    extracted_text TEXT,
    ai_summary JSON,
    ai_extracted_data JSON,
    download_link VARCHAR,
    char_count INTEGER,
    word_count INTEGER
);

---

-- ACCESS CONTROL (LEVEL-BASED + ACL)
CREATE TABLE access_levels (
    id VARCHAR PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    description TEXT,
    created_by_user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE file_access_levels (
    file_id VARCHAR REFERENCES files(id) ON DELETE CASCADE,
    access_level_id VARCHAR REFERENCES access_levels(id) ON DELETE CASCADE,
    PRIMARY KEY (file_id, access_level_id)
);

CREATE TABLE group_access_levels (
    group_id VARCHAR REFERENCES groups(id) ON DELETE CASCADE,
    access_level_id VARCHAR REFERENCES access_levels(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, access_level_id)
);

CREATE TABLE user_access_levels (
    user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
    access_level_id VARCHAR REFERENCES access_levels(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, access_level_id)
);

CREATE TABLE permissions (
    id VARCHAR PRIMARY KEY,
    resource_type VARCHAR NOT NULL,
    resource_id VARCHAR NOT NULL,
    principal_type VARCHAR NOT NULL,
    principal_id VARCHAR NOT NULL,
    permission_level VARCHAR NOT NULL,
    granted_by_user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

---

-- CHAT SYSTEM
CREATE TABLE chat_sessions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR,
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP
);

CREATE TABLE chat_settings (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    model VARCHAR NOT NULL DEFAULT 'gpt-4o-mini',
    max_tokens INTEGER,
    system_prompt TEXT,
    context_files VARCHAR[],
    domain VARCHAR,
    is_history BOOLEAN DEFAULT TRUE,
    max_context_messages INTEGER DEFAULT 20,
    using_document BOOLEAN DEFAULT TRUE,
    free_chat BOOLEAN DEFAULT FALSE,
    show_sources BOOLEAN DEFAULT TRUE,
    enable_streaming BOOLEAN DEFAULT TRUE,
    response_style VARCHAR DEFAULT 'concise',
    language VARCHAR DEFAULT 'vi',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_messages (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender_type VARCHAR NOT NULL,
    sender_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    message_text TEXT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    related_file_ids VARCHAR[],
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_usage (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR REFERENCES chat_sessions(id) ON DELETE SET NULL,
    message_id VARCHAR REFERENCES chat_messages(id) ON DELETE SET NULL,
    tokens_prompt INTEGER,
    tokens_completion INTEGER,
    cost_usd DECIMAL(10,5),
    model VARCHAR,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

---

-- SYSTEM CONFIG (API KEY & GLOBAL SETTINGS)
CREATE TABLE system_config (
    id VARCHAR PRIMARY KEY,
    config_key VARCHAR UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by_user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL
);