from pydantic import BaseModel, EmailStr
from models import UserRole

# 1. Схема за приемане на данни (когато ученик се регистрира)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

# 2. Схема за връщане на данни (какво връщаме към мобилното приложение)
# ЗАБЕЛЕЖКА: Тук НЕ включваме паролата! Това е мярка за сигурност.
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True