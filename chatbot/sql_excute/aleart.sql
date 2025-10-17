ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL;

select * from users

delete from users where id = 'u1'