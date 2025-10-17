-- Cho PostgreSQL, index prefix search nhanh
CREATE INDEX idx_files_original_file_name_prefix ON files(original_file_name text_pattern_ops);
CREATE INDEX idx_files_folder_id ON files(folder_id);
CREATE INDEX idx_user_access_files_user_id_file_id ON user_access_files(user_id, file_id);
CREATE INDEX idx_folders_parent_id ON folders(parent_id);



-- test
WITH RECURSIVE folder_tree AS (
    SELECT id
    FROM folders
    WHERE keyword = 'R'
    UNION ALL
    SELECT f.id
    FROM folders f
    INNER JOIN folder_tree ft ON f.parent_id = ft.id
)
SELECT fi.id, fi.original_file_name
FROM files fi
JOIN folder_tree ft ON fi.folder_id = ft.id
JOIN user_access_files uaf ON uaf.file_id = fi.id
WHERE uaf.user_id = '00d14005-00d6-4b41-9648-16978e10b822'
  AND fi.original_file_name ILIKE 'H%'
LIMIT 20;

