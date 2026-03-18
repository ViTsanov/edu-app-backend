from sqlalchemy.orm import Session
import models, schemas
from passlib.context import CryptContext

# Настройка за криптиране на паролите
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Функция за търсене на потребител по имейл
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

# Функция за създаване на нов потребител
def create_user(db: Session, user: schemas.UserCreate):
    # 1. Криптираме паролата
    hashed_password = pwd_context.hash(user.password)
    
    # 2. Създаваме записа за базата данни с новите полета
    db_user = models.User(
        username=user.username,      # Вече използваме username от схемата
        email=user.email,
        hashed_password=hashed_password,
        role_id=user.role_id,        # Записваме подаденото ID на ролята
        total_xp=0                   # Всеки нов започва с 0 точки
    )
    
    # 3. Добавяме и записваме в PostgreSQL
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

# --- ТОВА Е ЛИПСВАЩАТА ФУНКЦИЯ ---
# Тази функция сравнява въведената парола с криптираната в базата
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Вземане на всички неодобрени упражнения
def get_pending_exercises(db: Session):
    # Използваме новия статус PENDING
    return db.query(models.Exercise).filter(models.Exercise.status == models.ExerciseStatus.PENDING).all()

# Одобряване на конкретно упражнение
def approve_exercise(db: Session, exercise_id: int):
    db_exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    if db_exercise:
        # Сменяме статуса на APPROVED
        db_exercise.status = models.ExerciseStatus.APPROVED
        db.commit()
        db.refresh(db_exercise)
    return db_exercise