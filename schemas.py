from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import enum

class Token(BaseModel):
    access_token: str
    token_type: str

class ExerciseStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"

# --- Users & Roles ---
class UserBase(BaseModel):
    username: str
    email: str
    role_id: int

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    total_xp: int
    english_level: str = "A1"
    profile_picture: Optional[str] = None
    teacher_verification_status: str = "none"
    
    class Config:
        from_attributes = True # Позволява на Pydantic да чете данни директно от SQLAlchemy моделите

# --- Classrooms ---
class ClassroomBase(BaseModel):
    name: str
    access_code: str
    level_id: int

class ClassroomCreate(ClassroomBase):
    pass

class ClassroomResponse(ClassroomBase):
    id: int
    teacher_id: int
    
    class Config:
        from_attributes = True

# --- Exercises ---
class ExerciseBase(BaseModel):
    title: str
    content_prompt: str
    level_id: int
    module_id: int

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseResponse(ExerciseBase):
    id: int
    status: ExerciseStatus
    
    class Config:
        from_attributes = True

# --- Results & AI Analysis ---
class AIAnalysisBase(BaseModel):
    grammar_score: int
    fluency_score: int
    strengths: str
    weaknesses: str
    explanation: str

class AIAnalysisResponse(AIAnalysisBase):
    id: int
    result_id: int

    class Config:
        from_attributes = True

class ResultBase(BaseModel):
    user_answer: str
    xp_earned: int

class ResultCreate(ResultBase):
    exercise_id: int

class ResultResponse(ResultBase):
    id: int
    user_id: int
    exercise_id: int
    created_at: datetime
    # Тук връщаме и AI анализа, ако има такъв (защото връзката е 1:1)
    analysis: Optional[AIAnalysisResponse] = None

    class Config:
        from_attributes = True

