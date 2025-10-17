CREATE INDEX idx_files_original_file_name_prefix ON files(original_file_name text_pattern_ops);
CREATE INDEX idx_files_folder_id ON files(folder_id);
CREATE INDEX idx_user_access_files_user_id_file_id ON user_access_files(user_id, file_id);
CREATE INDEX idx_folders_parent_id ON folders(parent_id);
---- 9/4/2025----

-- Index cho tìm kiếm theo thời gian:
CREATE INDEX idx_files_upload_timestamp ON files(upload_timestamp DESC);
-- Index cho quyền sở hữu/lọc:
CREATE INDEX idx_files_uploaded_by_user_id ON files(uploaded_by_user_id);
--Index trên các bảng Group liên quan:
CREATE INDEX idx_user_group_user_id ON user_groups(user_id); 
