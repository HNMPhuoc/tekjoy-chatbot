CREATE TABLE user_access_files (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, file_id)
);


-- index 
CREATE INDEX idx_user_access_file_user_id ON user_access_file(user_id);
CREATE INDEX idx_user_access_file_file_id ON user_access_file(file_id);
-- chưa dùng bao giờ

-- thêm keywords cho folders
ALTER TABLE folders
ADD COLUMN keyword TEXT NULL;
