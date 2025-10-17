-- insert để test 8/23/2025 : 9:35 sáng
INSERT INTO files (
    id, 
    original_file_name, 
    storage_path, 
    processing_status, 
    extracted_text
)
VALUES
('1', 'abc.pdf', '/tmp/abc.pdf', 'done', 'Đây là nội dung đã extract từ file abc.pdf'),
('2', '123.pdf', '/tmp/123.pdf', 'done', 'Đây là nội dung đã extract từ file 123.pdf');


INSERT INTO users (id, username, email)
VALUES ('u1', 'testuser', 'test@example.com');

-- insert để test http://localhost:8000/api/v1/chatbot/chat 



