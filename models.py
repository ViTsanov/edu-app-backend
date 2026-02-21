from sqlalchemy import Column, Integer, String, Boolean, Enum
import enum
from database import Base

# Дефинираме възможните роли в системата (Role-based access)
class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    EXPERT = "expert"
    ADMIN = "admin"

# Това е моделът (таблицата) за нашите потребители
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False) # Пазим паролите криптирани заради GDPR
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.STUDENT) # По подразбиране всеки нов е ученик
    is_active = Column(Boolean, default=True)
    
    # Тук в бъдеще ще добавим полета за XP, ниво (A1-C2) и др.