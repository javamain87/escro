from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint
import sqlite3
from uuid import uuid4
import os
import socket
import math
from extensions import limiter  # ✅ 이제 이쪽에서 가져옴


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip




home_bp = Blueprint("home", __name__)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # 현재 app.py 기준
DB_PATH = os.path.join(BASE_DIR, "db", "escro.db")
print(f"[DEBUG] DB 경로: {DB_PATH}")
@home_bp.route("/")
def home():
    return render_template("home/index.html")

@home_bp.route("/home")
def home_page():
    return render_template("home/page/home.html")

@home_bp.route("/link")
def link_page():
    return render_template("home/page/link.html")

@home_bp.route("/links/create", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def link_create():
    if request.method == "POST":
        code = str(uuid4()).split('-')[0]
        password = request.form["password"]
        requester_name = request.form["requester_name"]
        requester_phone = request.form["requester_phone"]
        worker_name = request.form["worker_name"]
        worker_phone = request.form["worker_phone"]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # ✅ 중복 체크
        cursor.execute("""
            SELECT COUNT(*) FROM Link
            WHERE requester_name = ? AND requester_phone = ?
        """, (requester_name, requester_phone))
        exists = cursor.fetchone()[0]

        if exists > 0:
            conn.close()
            flash("⚠️ 이미 같은 이름과 전화번호 조합으로 생성된 링크가 있습니다.", "warning")
            return render_template(
                "home/page/link.html",
                requester_name=requester_name,
                requester_phone=requester_phone,
                worker_name=worker_name,
                worker_phone=worker_phone,
                password=password
            )

        # ✅ 생성 처리
        # ip_address = get_local_ip()
        # access_url = f"http://{ip_address}:5001/access/{code}"

            # ✅ Render용 URL 생성
        base_url = os.getenv("BASE_URL", "http://{ip_address}:5001")  # 기본값은 로컬용
        access_url = f"{base_url}/access/{code}"

        cursor.execute("""
            INSERT INTO Link (code, password, requester_name, requester_phone, worker_name, worker_phone, access_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, password, requester_name, requester_phone, worker_name, worker_phone, access_url))
        conn.commit()
        conn.close()

        flash(f"✅ 링크 생성 완료! 접속 링크: {access_url}", "success")
        return redirect(url_for("home.link_list"))

    # GET 요청 시 빈 폼
    return render_template("home/page/link.html")



if __name__ == "__main__":
    app.run(debug=True)

@home_bp.route("/access/<code>", methods=["GET", "POST"])
def access_link(code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Link WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return "❌ 유효하지 않은 링크 코드입니다.", 404

    # row: (id, code, password, requester_name, requester_phone, worker_name, worker_phone, created_at)
    link_data = {
        "code": row[1],
        "password": row[2],
        "requester_name": row[3],
        "requester_phone": row[4],
        "worker_name": row[5],
        "worker_phone": row[6],
    }

    if request.method == "POST":
        input_password = request.form.get("password")
        input_phone = request.form.get("phone")

        if input_password != link_data["password"]:
            return "❌ 비밀번호가 일치하지 않습니다.", 403

        if input_phone == link_data["requester_phone"]:
            role = "신청자"
        elif input_phone == link_data["worker_phone"]:
            role = "작업자"
        else:
            return "❌ 전화번호가 등록되지 않았습니다.", 403

        return render_template("home/page/access_result.html", role=role, **link_data)

    return render_template("home/page/access_prompt.html")
if __name__ == "__main__":
    app.run(debug=True)


@home_bp.route("/links", methods=["GET"])
def link_list():
    # 페이지 번호 및 페이지당 항목 수
    page = int(request.args.get("page", 1))
    per_page = 10  # 한 페이지에 보여줄 개수

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 전체 데이터 수 조회
    cursor.execute("SELECT COUNT(*) FROM Link")
    total_count = cursor.fetchone()[0]
    total_pages = math.ceil(total_count / per_page)

    # 페이징 처리된 데이터 조회
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT * FROM Link
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    links = cursor.fetchall()
    conn.close()

    return render_template(
        "home/page/link_list.html",
        links=links,
        page=page,
        total_pages=total_pages
    )
