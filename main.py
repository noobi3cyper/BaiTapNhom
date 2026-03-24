from flask import Flask, request, render_template, session, redirect, url_for, flash, abort
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3
import os
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import time

app = Flask(__name__, static_url_path='/static')
app.secret_key = "FelixPham"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'png', 'jpg', 'zip'}
DB_PATH = os.path.join('db', 'hocphan.db')

# --- 1. CORE UTILITIES ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- 2. DATA LOGIC ---


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Kiểm tra xem user có đăng nhập và có role admin không
        if session.get('role') != 'admin':
            return abort(403) # Trả về HTTP 403 Forbidden
        return f(*args, **kwargs)
    return decorated_function

# --- 3. AUTHENTICATION ROUTES ---
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    admin_secret = request.form.get('admin_secret', '') # Default là chuỗi rỗng để tránh NoneType

    if not username or not password:
        flash('Vui lòng nhập đầy đủ thông tin!', 'warning')
        return redirect(request.referrer or url_for('index'))

    hashed_pw = generate_password_hash(password)
    role = 'admin' if admin_secret == app.secret_key else 'user'

    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO User (Username, Password, Role) VALUES (?, ?, ?)",
                         (username, hashed_pw, role))
            conn.commit()

            session['username'] = username
            session['role'] = role

        flash('Đăng ký tài khoản thành công!', 'success')
        return redirect(request.referrer or url_for('index'))
    except sqlite3.IntegrityError:
        flash('Tên đăng nhập đã tồn tại!', 'danger')
        return redirect(request.referrer or url_for('index'))


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    next_page = request.referrer or url_for('index')

    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM User WHERE Username = ?", (username,)).fetchone()

        if user and check_password_hash(user['Password'], password):
            session.clear()
            session['user_id'] = user['Id']
            session['username'] = user['Username']
            session['role'] = user['Role']

            # Gửi thông báo thành công (category: 'success')
            flash(f'Chào mừng trở lại, {username}!', 'success')
            return redirect(next_page)

    # Gửi thông báo lỗi (category: 'danger' để hợp với màu đỏ của Bootstrap)
    flash('Sai tài khoản hoặc mật khẩu!', 'danger')
    return redirect(next_page)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


# --- 4. MAIN INTERFACE ROUTES ---
@app.route('/', methods=['GET', 'POST'])
@app.route('/search', methods=['GET', 'POST'])
def index():
    search_text = request.form.get('searchInput', '') if request.method == 'POST' else ""
    courses = []

    with get_db_connection() as conn:
        if search_text:
            query = "SELECT MaHocPhan, TenHocPhan FROM HocPhan WHERE TenHocPhan LIKE ? OR MaHocPhan LIKE ?"
            courses = conn.execute(query, (f'%{search_text}%', f'%{search_text}%')).fetchall()
        else:
            courses = conn.execute("SELECT * FROM HocPhan").fetchall()

    # Truyền trực tiếp list các sqlite3.Row sang template
    return render_template('Search.html', search_text=search_text, courses=courses)


@app.route('/course/<ma_hp>')
def course_detail(ma_hp):
    is_admin = session.get('role') == 'admin'
    completed_lessons = []

    try:
        with get_db_connection() as conn:
            course = conn.execute("SELECT * FROM HocPhan WHERE MaHocPhan = ?", (ma_hp,)).fetchone()
            if not course:
                return "Không tìm thấy học phần", 404

            lessons = conn.execute("SELECT * FROM BaiHoc WHERE MaHocPhan = ? ORDER BY ThuTuHoc", (ma_hp,)).fetchall()
            documents = conn.execute("""
                SELECT tl.* FROM TaiLieuNoiDung tl
                JOIN BaiHoc bh ON tl.MaBaiHoc = bh.MaBaiHoc
                WHERE bh.MaHocPhan = ?
            """, (ma_hp,)).fetchall()

            if session.get('username'):
                user = conn.execute("SELECT Id FROM User WHERE Username = ?", (session['username'],)).fetchone()
                if user:
                    data = conn.execute("SELECT MaBaiHoc FROM UserProgress WHERE User_Id = ?", (user['Id'],)).fetchall()
                    completed_lessons = [item['MaBaiHoc'] for item in data]

    except Exception as e:
        return f"Lỗi truy xuất dữ liệu: {e}", 500

    return render_template('CourseDetail.html',
                           course=course, lessons=lessons, documents=documents,
                           is_admin=is_admin, completed_lessons=completed_lessons)


# --- 5. CRUD API ROUTES ---
@app.route('/update_progress', methods=['POST'])
def update_progress():
    username = session.get('username')
    if not username:
        return {"status": "error", "message": "Bạn cần đăng nhập để lưu tiến độ!"}, 401

    data = request.json
    ma_bai_hoc = data.get('ma_bai_hoc')
    is_completed = data.get('completed')

    try:
        with get_db_connection() as conn:
            user = conn.execute("SELECT Id FROM User WHERE Username = ?", (username,)).fetchone()
            if user:
                if is_completed:
                    conn.execute("INSERT OR IGNORE INTO UserProgress (User_Id, MaBaiHoc, Status) VALUES (?, ?, 1)",
                                 (user['Id'], ma_bai_hoc))
                else:
                    conn.execute("DELETE FROM UserProgress WHERE User_Id = ? AND MaBaiHoc = ?",
                                 (user['Id'], ma_bai_hoc))
                return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

    return {"status": "error", "message": "User không tồn tại"}, 404


@app.route('/update_doc_name', methods=['POST'])
@admin_required
def update_doc_name():
    """Hàm cập nhật tên hiển thị của tài liệu"""
    ma_tl = request.form.get('ma_tl')
    ten_moi = request.form.get('ten_moi')

    try:
        with get_db_connection() as conn:
            # Bước 1: Lấy Mã Học Phần để có thể redirect người dùng về đúng trang cũ
            doc_info = conn.execute("""
                SELECT bh.MaHocPhan 
                FROM TaiLieuNoiDung tl
                JOIN BaiHoc bh ON tl.MaBaiHoc = bh.MaBaiHoc
                WHERE tl.MaTaiLieu = ?
            """, (ma_tl,)).fetchone()

            if doc_info:
                # Bước 2: Cập nhật tên tài liệu (NoiDungVanBan) trong Database
                conn.execute("UPDATE TaiLieuNoiDung SET NoiDungVanBan = ? WHERE MaTaiLieu = ?", (ten_moi, ma_tl))
                return redirect(url_for('course_detail', ma_hp=doc_info['MaHocPhan']))

            return "Không tìm thấy tài liệu", 404
    except Exception as e:
        return f"Lỗi hệ thống: {e}", 500
@app.route('/add_lesson', methods=['POST'])
@admin_required # Gắn decorator ngay dưới @app.route
def add_lesson():
    ma_hp = request.form.get('ma_hp')
    ten_bai_hoc = request.form.get('ten_bai_hoc')
    thu_tu = request.form.get('thu_tu')

    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO BaiHoc (TenBaiHoc, ThuTuHoc, MaHocPhan) VALUES (?, ?, ?)",
                         (ten_bai_hoc, thu_tu, ma_hp))
        return redirect(url_for('course_detail', ma_hp=ma_hp))
    except Exception as e:
        return f"Lỗi: {e}", 500


@app.route('/delete_lesson/<int:ma_bai_hoc>')
@admin_required
def delete_lesson(ma_bai_hoc):
    try:
        with get_db_connection() as conn:
            lesson = conn.execute("SELECT MaHocPhan FROM BaiHoc WHERE MaBaiHoc = ?", (ma_bai_hoc,)).fetchone()
            if lesson:
                ma_hp = lesson['MaHocPhan']
                conn.execute("DELETE FROM TaiLieuNoiDung WHERE MaBaiHoc = ?", (ma_bai_hoc,))
                conn.execute("DELETE FROM BaiHoc WHERE MaBaiHoc = ?", (ma_bai_hoc,))
                return redirect(f'/course/{ma_hp}')
            return "Không tìm thấy bài học", 404
    except Exception as e:
        return f"Lỗi Database: {e}", 500

# Thêm Decorator kiểm tra quyền Admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return "Bạn không có quyền thực hiện hành động này", 403
        return f(*args, **kwargs)
    return decorated_function


@app.route('/delete_doc/<int:ma_tl>')
@admin_required
def delete_doc(ma_tl):
    try:
        with get_db_connection() as conn:
            # 1. Lấy thông tin file trước khi xóa
            doc_info = conn.execute("""
                SELECT tl.DuongDanFile, bh.MaHocPhan 
                FROM TaiLieuNoiDung tl
                JOIN BaiHoc bh ON tl.MaBaiHoc = bh.MaBaiHoc
                WHERE tl.MaTaiLieu = ?
            """, (ma_tl,)).fetchone()

            if not doc_info:
                return "Không tìm thấy tài liệu để xóa", 404

            # 2. Xóa file vật lý trên hệ điều hành
            # Cần map đúng thư mục gốc của project
            file_path = os.path.join(app.root_path, 'static', doc_info['DuongDanFile'])
            if os.path.exists(file_path):
                os.remove(file_path) # Xóa file

            # 3. Xóa bản ghi trong Database
            conn.execute("DELETE FROM TaiLieuNoiDung WHERE MaTaiLieu = ?", (ma_tl,))
            conn.commit()

            return redirect(url_for('course_detail', ma_hp=doc_info['MaHocPhan']))
    except Exception as e:
        return f"Lỗi hệ thống: {e}", 500


@app.route('/update_lesson_description', methods=['POST'])
@admin_required
def update_lesson_description():
    ma_bai_hoc = request.form.get('ma_bai_hoc')
    mo_ta = request.form.get('mo_ta')

    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE BaiHoc SET MoTa = ? WHERE MaBaiHoc = ?", (mo_ta, ma_bai_hoc))
            info = conn.execute("SELECT MaHocPhan FROM BaiHoc WHERE MaBaiHoc = ?", (ma_bai_hoc,)).fetchone()
            return redirect(url_for('course_detail', ma_hp=info['MaHocPhan']))
    except Exception as e:
        return f"Lỗi khi cập nhật mô tả: {e}", 500


@app.route('/edit_lesson/<int:ma_bai_hoc>', methods=['POST'])
@admin_required
def edit_lesson(ma_bai_hoc):
    """Hàm cập nhật thông tin bài học (Tên và Thứ tự)"""
    ten_bai_hoc = request.form.get('ten_bai_hoc')
    thu_tu = request.form.get('thu_tu')

    try:
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE BaiHoc 
                SET TenBaiHoc = ?, ThuTuHoc = ? 
                WHERE MaBaiHoc = ?
            """, (ten_bai_hoc, thu_tu, ma_bai_hoc))

            info = conn.execute("SELECT MaHocPhan FROM BaiHoc WHERE MaBaiHoc = ?", (ma_bai_hoc,)).fetchone()
            return redirect(url_for('course_detail', ma_hp=info['MaHocPhan']))
    except Exception as e:
        return f"Lỗi Database: {e}", 500


@app.route('/add_doc', methods=['POST'])
@admin_required  # ĐÃ BỔ SUNG BẢO MẬT
def add_doc():
    ma_bai_hoc = request.form.get('ma_bai_hoc')
    ten_tl = request.form.get('ten_tl')
    file = request.files.get('file_tai_lieu')

    if file and file.filename != '' and allowed_file(file.filename):
        # Tạo tên file Unique bằng Timestamp để chống ghi đè
        original_filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{original_filename}"

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        try:
            with get_db_connection() as conn:
                db_path_save = f'uploads/{unique_filename}'
                conn.execute(
                    "INSERT INTO TaiLieuNoiDung (NoiDungVanBan, LoaiTaiLieu, DuongDanFile, MaBaiHoc) VALUES (?, ?, ?, ?)",
                    (ten_tl, 'File', db_path_save, ma_bai_hoc))

                info = conn.execute("SELECT MaHocPhan FROM BaiHoc WHERE MaBaiHoc = ?", (ma_bai_hoc,)).fetchone()
                return redirect(url_for('course_detail', ma_hp=info['MaHocPhan']))
        except Exception as e:
            return f"Lỗi Database: {e}", 500

    return "Lỗi: Không tìm thấy file hoặc định dạng không hợp lệ", 400

if __name__ == '__main__':
    app.run(debug=True)
