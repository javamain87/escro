from flask import Flask
from routes.home import home_bp
from extensions import limiter  # ✅ 이제 이쪽에서 가져옴
from flask_limiter.util import get_remote_address

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_super_secret_key'  # 세션 및 flash에 필요
   # ✅ limiter를 app에 바인딩
    limiter.init_app(app)

    # ✅ 전역 기본 제한 적용 (선택)
    app.config['RATELIMIT_DEFAULT'] = "100 per minute"  # 예시: 기본값
    app.register_blueprint(home_bp)
    return app  # ❗ 여기는 실행하지 않음, 앱 객체만 반환

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)  # ✅ 외부 디바이스 접속 가능
