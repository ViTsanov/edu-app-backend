import jwt
from datetime import datetime, timedelta

# ТАЙНИЯТ КЛЮЧ: С него сървърът "подписва" пропуските, за да не могат хакери да си ги фалшифицират.
# В реално приложение този ключ се пази в отделен скрит файл, но за сега ще го сложим тук.
SECRET_KEY = "super-secret-english-app-key" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Пропускът ще важи 1 час, след което телефонът ще иска нов

def create_access_token(data: dict):
    """
    Тази функция взима данни (напр. имейла на потребителя) 
    и ги превръща в криптиран JWT пропуск (токен).
    """
    to_encode = data.copy()
    
    # Задаваме кога изтича токенът
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Генерираме самия токен
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt