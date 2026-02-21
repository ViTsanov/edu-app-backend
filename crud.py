from sqlalchemy.orm import Session
import models, schemas
from passlib.context import CryptContext

# Настройка за криптиране на паролите
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Функция за търсене на потребител по имейл (за да не позволим 2 еднакви регистрации)
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

# Функция за създаване на нов потребител
def create_user(db: Session, user: schemas.UserCreate):
    # Криптираме паролата
    hashed_password = pwd_context.hash(user.password)
    
    # Създаваме записа за базата данни
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
        # Ролята по подразбиране е STUDENT, както зададохме в models.py
    )
    
    # Добавяме и запазваме
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user