Nếu bạn đang quản lý DB bằng tay (chưa dùng Alembic), có thể chạy lệnh SQL:

ALTER TABLE chat_settings
ADD COLUMN user_id VARCHAR(255);


Đồng thời, nếu bạn muốn mỗi user chỉ có 1 setting duy nhất, thì nên thêm constraint:

ALTER TABLE chat_settings
ADD CONSTRAINT unique_user_chatsetting UNIQUE (user_id);
-- hiện tại nó đang not null nên đổi thành null able
ALTER TABLE chat_settings
ALTER COLUMN session_id DROP NOT NULL;
---- 9/5/2025----

---- 9/6/2025----
ALTER TABLE chat_sessions
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN id TYPE uuid USING id::uuid,
    ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Chuyển cột user_id sang UUID
ALTER TABLE chat_sessions
    ALTER COLUMN user_id TYPE uuid USING user_id::uuid;
    ---- 9/6/2025----

--- 25/9/2025---
-- thêm cột apikey dùng trong trường hợp user muốn dùng api key riêng và cho phép null để k ảnh hưởng shcema hiện tại
ALTER TABLE chat_settings
ADD COLUMN api_key VARCHAR NULL;
---- 25/9/2025---