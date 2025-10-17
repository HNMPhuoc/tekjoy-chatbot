-- Lấy toàn bộ dữ liệu từ các bảng

SELECT * FROM access_levels;
SELECT * FROM chat_messages;
SELECT * FROM chat_sessions;
SELECT * FROM chat_settings;
SELECT * FROM chat_usage;
SELECT * FROM file_access_levels;
SELECT * FROM files;
select original_file_name,extracted_text from files
SELECT * FROM folders;
SELECT * FROM group_access_levels;
SELECT * FROM groups;
SELECT * FROM system_config;
SELECT * FROM user_groups;
SELECT * FROM users;
select * from user_access_files

SELECT * FROM folders WHERE keyword = 'G6';


WITH RECURSIVE folder_tree AS (
    -- Lấy folder gốc có keyword = 'G6E'
    SELECT id
    FROM folders
    WHERE keyword = 'G6'

    UNION ALL

    -- Lấy các folder con
    SELECT f.id
    FROM folders f
    INNER JOIN folder_tree ft ON f.parent_id = ft.id
)
SELECT fi.*
FROM files fi
JOIN folder_tree ft ON fi.folder_id = ft.id
JOIN user_access_files uaf ON uaf.file_id = fi.id
WHERE uaf.user_id = '00d14005-00d6-4b41-9648-16978e10b822';


ALTER TABLE chat_settings
ADD COLUMN user_id VARCHAR(255);

ALTER TABLE chat_settings
ALTER COLUMN user_id TYPE uuid
USING user_id::uuid;

ALTER TABLE chat_settings
ADD CONSTRAINT unique_user_chatsetting UNIQUE (user_id);

ALTER TABLE chat_settings
ALTER COLUMN session_id DROP NOT NULL;

ALTER TABLE chat_settings
ALTER COLUMN id TYPE uuid
USING id::uuid;

ALTER TABLE chat_sessions
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN id TYPE uuid USING id::uuid,
    ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Chuyển cột user_id sang UUID
ALTER TABLE chat_sessions
    ALTER COLUMN user_id TYPE uuid USING user_id::uuid;

ALTER TABLE chat_settings
ADD COLUMN api_key VARCHAR NULL;

