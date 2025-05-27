from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint
import sqlite3
from uuid import uuid4
import os
import socket
import math
from extensions import limiter  # ✅ 이제 이쪽에서 가져옴
from datetime import datetime


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
        base_url = os.getenv("BASE_URL", "https://escro-1.onrender.com")  # 기본값은 로컬용
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

    cursor.execute("""
        SELECT requester_name, requester_phone, worker_name, worker_phone, password
        FROM Link WHERE code = ?
    """, (code,))
    link_row = cursor.fetchone()

    if not link_row:
        conn.close()
        return "잘못된 접근입니다.", 404

    requester_name, requester_phone, worker_name, worker_phone, password = link_row

    # ✅ 인증 로직
    if request.method == "POST" and "phone" in request.form:
        input_phone = request.form.get("phone")
        input_password = request.form.get("password")

        if input_phone not in (requester_phone, worker_phone):
            flash("🚫 등록된 전화번호가 아닙니다.", "warning")
            return render_template("home/page/access_prompt.html")

        if input_password != password:
            flash("🚫 비밀번호가 일치하지 않습니다.", "warning")
            return render_template("home/page/access_prompt.html")

        # 인증 성공 → role 추정 후 GET redirect
        role = "신청자" if input_phone == requester_phone else "작업자"
        return redirect(url_for("home.access_link", code=code, role=role))

    # ✅ 인증 완료된 GET 요청 처리
    role = request.args.get("role")
    if not role:
        return render_template("home/page/access_prompt.html")

    # detail 정보 조회
    cursor.execute("SELECT * FROM LinkDetail WHERE link_code = ?", (code,))
    detail_row = cursor.fetchone()

    if request.method == "POST" and "phone" not in request.form:
        if detail_row:
            if role == "신청자":
                wallet_address_requester = request.form.get("wallet_address_requester", "").strip()
                request_content = request.form.get("request_content", "").strip()

                if wallet_address_requester or request_content:
                    cursor.execute("""
                        UPDATE LinkDetail
                        SET wallet_address_requester = ?, request_content = ?, updated_at = ?
                        WHERE link_code = ?
                    """, (
                        wallet_address_requester or detail_row[2],
                        request_content or detail_row[4],
                        datetime.now(),
                        code
                    ))

            elif role == "작업자":
                work_history_input = request.form.get("work_history", "").strip()

                # 작업자가 작업 이력을 자유롭게 수정 가능하도록 덮어쓰기 처리
                cursor.execute("""
                    UPDATE LinkDetail
                    SET work_history = ?, updated_at = ?
                    WHERE link_code = ?
                """, (
                    work_history_input,
                    datetime.now(),
                    code
                ))

        conn.commit()
        flash("✅ 저장 완료", "success")
        return redirect(url_for("home.access_link", code=code, role=role))

    # GET 시 화면 랜더링
    wallet_address_requester = detail_row[2] if detail_row else ""
    wallet_address_worker = detail_row[3] if detail_row else ""
    request_content = detail_row[4] if detail_row else ""
    work_history = detail_row[5] if detail_row else ""

    conn.close()

    return render_template("home/page/access_result.html",
        role=role,
        requester_name=requester_name,
        requester_phone=requester_phone,
        worker_name=worker_name,
        worker_phone=worker_phone,
        wallet_address_requester=wallet_address_requester,
        wallet_address_worker=wallet_address_worker,
        request_content=request_content,
        work_history=work_history
    )


# DB 테이블 생성 쿼리
# CREATE TABLE LinkDetail (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     link_code TEXT,
#     wallet_address_requester TEXT,
#     wallet_address_worker TEXT,
#     request_content TEXT,
#     work_history TEXT,
#     created_at DATETIME,
#     updated_at DATETIME
# );

if __name__ == "__main__":
    app.run(debug=True, port=5001, host="0.0.0.0")


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
