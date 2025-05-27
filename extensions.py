from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 전역 limiter 객체만 선언
limiter = Limiter(key_func=get_remote_address)