import sqlite3
import os
from werkzeug.security import generate_password_hash

# Đường dẫn tới file DB của bạn
DB_PATH = os.path.join('db', 'hocphan.db')


def create_new_admin(username, password):
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Chèn user mới với Role là 'admin'
        cursor.execute("INSERT INTO User (Username, Password, Role) VALUES (?, ?, ?)",
                       (username, hashed_pw, 'admin'))

        conn.commit()
        conn.close()
        print(f"--- THÀNH CÔNG ---")
        print(f"Đã tạo admin: {username}")
    except sqlite3.IntegrityError:
        print(f"--- LỖI ---")
        print(f"Tên đăng nhập '{username}' đã tồn tại trong Database!")
    except Exception as e:
        print(f"Lỗi: {e}")


if __name__ == "__main__":
    # Bạn có thể đổi tên và mật khẩu ở đây
    create_new_admin('admin_test', '123456')