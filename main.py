import sqlite3
import os
import pandas as pd
from flask import Flask, request, render_template, session

app = Flask(__name__, static_url_path='/static')
app.secret_key = "FelixPham"


# --- HÀM LOGIC DỮ LIỆU (KHÔNG ĐẶT ROUTE Ở ĐÂY) ---
def get_html_table(search_text):
    conn = sqlite3.connect(os.path.join('db', 'hocphan.db'))

    # Lấy dữ liệu
    if search_text:
        query = "SELECT * FROM HocPhan WHERE TenHocPhan LIKE ? OR MaHocPhan LIKE ?"
        df = pd.read_sql_query(query, conn, params=(f'%{search_text}%', f'%{search_text}%'))
    else:
        df = pd.read_sql_query("SELECT * FROM HocPhan", conn)

    conn.close()

    # 1. Thay thế giá trị None bằng khoảng trắng cho đẹp
    df = df.fillna("")

    # 2. Đổi tên cột sang Tiếng Việt có dấu
    # Key là tên cột trong DB, Value là tên bạn muốn hiển thị
    df = df.rename(columns={
        'MaHocPhan': 'Mã Học Phần',
        'TenHocPhan': 'Tên Học Phần',
        'SoTinChi': 'Số Tín Chỉ',
        'GhiChu': 'Ghi Chú'
    })
    df['Chi Tiết'] = df['Mã Học Phần'].apply(
        lambda x: f'<a href="/course/{x}" class="btn btn-sm btn-primary">Xem bài học</a>'
    )
    df['Quản lý'] = df['Mã Học Phần'].apply(
        lambda x: f'<a href="/admin/course/{x}" class="btn btn-sm btn-dark">⚙️ Quản trị</a>'
    )

    return df.to_html(classes='table table-striped table-hover align-middle', index=False, escape=False, border=0)

    # Trả về bảng HTML
    return df.to_html(classes='table table-striped table-hover', index=False, border=0)


# --- CÁC ROUTE CỦA FLASK ---

@app.route('/')
def index():
    # Khi mới vào trang, hiển thị toàn bộ dữ liệu (search_text="")
    html_table = get_html_table("")
    return render_template('Search.html', search_text="", table=html_table)


@app.route('/search', methods=['GET', 'POST'])
def search_page():
    search_text = ""
    if request.method == 'POST':
        # Lấy từ ô input name="searchInput" trong form
        search_text = request.form.get('searchInput', '')

    # Gọi hàm xử lý dữ liệu
    html_table = get_html_table(search_text)

    return render_template('Search.html',
                           search_text=search_text,
                           table=html_table)


# Route hiển thị trang quản lý tài liệu của một học phần cụ thể
@app.route('/admin/course/<ma_hp>')
def admin_course_detail(ma_hp):
    conn = sqlite3.connect(os.path.join('db', 'hocphan.db'))
    conn.row_factory = sqlite3.Row

    # Lấy thông tin học phần
    course = conn.execute("SELECT * FROM HocPhan WHERE MaHocPhan = ?", (ma_hp,)).fetchone()
    # Lấy danh sách bài học
    lessons = conn.execute("SELECT * FROM BaiHoc WHERE MaHocPhan = ? ORDER BY ThuTu", (ma_hp,)).fetchall()
    conn.close()

    return render_template('AdminCourseDetail.html', course=course, lessons=lessons)


# 2. Trang quản lý tài liệu của một BÀI HỌC cụ thể
@app.route('/admin/lesson/<int:lesson_id>/manage')
def admin_manage_documents(lesson_id):
    conn = sqlite3.connect(os.path.join('db', 'hocphan.db'))
    conn.row_factory = sqlite3.Row

    # Lấy thông tin bài học và học phần liên quan
    lesson = conn.execute("""
        SELECT bh.*, hp.TenHocPhan 
        FROM BaiHoc bh 
        JOIN HocPhan hp ON bh.MaHocPhan = hp.MaHocPhan 
        WHERE bh.MaBaiHoc = ?""", (lesson_id,)).fetchone()

    # Lấy danh sách tài liệu của bài học đó
    documents = conn.execute("SELECT * FROM TaiLieuNoiDung WHERE MaBaiHoc = ?", (lesson_id,)).fetchall()
    conn.close()

    return render_template('AdminManageDocs.html', lesson=lesson, documents=documents)


@app.route('/course/<ma_hp>')
def course_detail(ma_hp):
    conn = sqlite3.connect(os.path.join('db', 'hocphan.db'))
    conn.row_factory = sqlite3.Row  # Giúp truy xuất theo tên cột

    # 1. Lấy thông tin học phần
    hoc_phan = conn.execute("SELECT * FROM HocPhan WHERE MaHocPhan = ?", (ma_hp,)).fetchone()

    # 2. Lấy danh sách bài học của học phần đó
    bai_hoc_list = conn.execute("SELECT * FROM BaiHoc WHERE MaHocPhan = ? ", (ma_hp,)).fetchall()

    conn.close()

    if not hoc_phan:
        return "Không tìm thấy học phần!", 404

    return render_template('CourseDetail.html', course=hoc_phan, lessons=bai_hoc_list)
if __name__ == '__main__':
    app.run(debug=True)