import jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer # ТОВА ЛИПСВАШЕ
from jose import JWTError, jwt as jose_jwt # ТОВА Е ЗА РАЗКОДИРАНЕ

# ТАЙНИЯТ КЛЮЧ
SECRET_KEY = "super-secret-english-app-key" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Казваме на FastAPI къде се намира маршрутът за вход
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jose_jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        # Използваме jose_jwt за разкодиране
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except Exception:
        return None