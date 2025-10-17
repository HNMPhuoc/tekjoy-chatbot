--add user 9/4/2025
CREATE OR REPLACE FUNCTION insert_new_user(
    p_username VARCHAR(100),
    p_email VARCHAR(255),
    p_password_hash VARCHAR(255),
    p_full_name VARCHAR(255),
    p_role VARCHAR(50) DEFAULT 'user',
    p_is_active BOOLEAN DEFAULT TRUE
)
RETURNS UUID AS $$
DECLARE
    new_user_id UUID;
BEGIN
    INSERT INTO users (
        username,
        email,
        password_hash,
        full_name,
        role,
        is_active,
        created_at  -- Trường mới đã được thêm
    )
    VALUES (
        p_username,
        p_email,
        p_password_hash,
        p_full_name,
        p_role,
        p_is_active,
        NOW()  -- Sử dụng hàm NOW() của PostgreSQL
    )
    RETURNING id INTO new_user_id;

    RETURN new_user_id;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để tìm người dùng theo email
CREATE OR REPLACE FUNCTION get_user_by_email(
    p_email VARCHAR(255)
)
RETURNS TABLE (
    id UUID,
    username VARCHAR(100),
    email VARCHAR(255),
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    role VARCHAR(50),
    is_active BOOLEAN,
    last_login TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id,
        u.username,
        u.email,
        u.password_hash,
        u.full_name,
        u.role,
        u.is_active,
        u.last_login
    FROM users u
    WHERE u.email = p_email;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để lấy tất cả người dùng
CREATE OR REPLACE FUNCTION get_all_users()
RETURNS TABLE (
    id UUID,
    username VARCHAR(100),
    email VARCHAR(255),
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    role VARCHAR(50),
    is_active BOOLEAN,
    last_login TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id,
        u.username,
        u.email,
        u.password_hash,
        u.full_name,
        u.role,
        u.is_active,
        u.last_login
    FROM users u
    ORDER BY u.username;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để lấy thông tin người dùng theo ID
CREATE OR REPLACE FUNCTION get_user_by_id(
    p_id UUID
)
RETURNS TABLE (
    id UUID,
    username VARCHAR(100),
    email VARCHAR(255),
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    role VARCHAR(50),
    is_active BOOLEAN,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id,
        u.username,
        u.email,
        u.password_hash,
        u.full_name,
        u.role,
        u.is_active,
        u.last_login,
        u.created_at
    FROM users u
    WHERE u.id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để cập nhật thông tin người dùng
CREATE OR REPLACE FUNCTION update_user(
    p_id UUID,
    p_full_name VARCHAR(255) DEFAULT NULL,
    p_role VARCHAR(50) DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE users
    SET
        full_name = COALESCE(p_full_name, full_name),
        role = COALESCE(p_role, role),
        is_active = COALESCE(p_is_active, is_active)
    WHERE
        id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để xóa người dùng theo ID
CREATE OR REPLACE FUNCTION delete_user_by_id(
    p_id UUID
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM users
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql; 

-- Hàm SQL để thêm group mới vào bảng `groups`
CREATE OR REPLACE FUNCTION insert_new_group(
    p_name VARCHAR(100),
    p_description TEXT
)
RETURNS UUID AS $$
DECLARE
    new_group_id UUID;
BEGIN
    INSERT INTO groups (name, description)
    VALUES (p_name, p_description)
    RETURNING id INTO new_group_id;

    RETURN new_group_id;

END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để tìm group theo tên
CREATE OR REPLACE FUNCTION get_group_by_name(
    p_name VARCHAR(100)
)
RETURNS TABLE (
    id UUID,
    name VARCHAR(100),
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id,
        g.name,
        g.description
    FROM groups g
    WHERE g.name = p_name;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để liệt kê tất cả các group
CREATE OR REPLACE FUNCTION list_all_groups()
RETURNS TABLE (
    id UUID,
    name VARCHAR(100),
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id,
        g.name,
        g.description
    FROM groups g
    ORDER BY g.name;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để cập nhật một group
CREATE OR REPLACE FUNCTION update_group(
    p_id UUID,
    p_name VARCHAR(100),
    p_description TEXT
)
RETURNS VOID AS $$
BEGIN
    UPDATE groups
    SET
        name = p_name,
        description = p_description
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Hàm SQL để xóa một group
CREATE OR REPLACE FUNCTION delete_group(
    p_id UUID
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM groups
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;
--Hàm này lấy group theo id
CREATE OR REPLACE FUNCTION get_group_by_id(p_id UUID)
RETURNS TABLE (
    id UUID,
    name VARCHAR(100),
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT g.id, g.name, g.description
    FROM groups g
    WHERE g.id = p_id;
END;
$$ LANGUAGE plpgsql;
----9/4/2025----