from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, Enum, DateTime
from sqlalchemy.orm import relationship
from database import Base
import enum
import datetime

# Enum за статуса на упражненията 
class ExerciseStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True) # "Student", "Teacher", "Expert", "Admin"
    
    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role_id = Column(Integer, ForeignKey("roles.id"))
    total_xp = Column(Integer, default=0)

    role = relationship("Role", back_populates="users")
    # Връзка към създадените стаи (ако е учител)
    classrooms_created = relationship("Classroom", back_populates="teacher")
    # Връзка към резултатите от упражнения
    results = relationship("Result", back_populates="user")

class Level(Base):
    __tablename__ = "levels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True) # e.g., "A1", "A2", "B1"

class Module(Base):
    __tablename__ = "modules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True) # e.g., "Grammar", "Speaking"

class Classroom(Base):
    __tablename__ = "classrooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    access_code = Column(String, unique=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    level_id = Column(Integer, ForeignKey("levels.id")) # Нивото на класа (както обсъдихме!)

    teacher = relationship("User", back_populates="classrooms_created")

class ClassStudent(Base):
    __tablename__ = "class_students"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    share_full_history = Column(Boolean, default=False) # GDPR consent

class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content_prompt = Column(Text)
    level_id = Column(Integer, ForeignKey("levels.id"))
    module_id = Column(Integer, ForeignKey("modules.id"))
    status = Column(Enum(ExerciseStatus), default=ExerciseStatus.PENDING)

class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    user_answer = Column(Text)
    xp_earned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="results")
    analysis = relationship("AIAnalysis", back_populates="result", uselist=False) # 1:1 връзка

class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("results.id"), unique=True) # UNIQUE прави връзката 1:1
    grammar_score = Column(Integer) # От 1 до 10
    fluency_score = Column(Integer) # От 1 до 10
    strengths = Column(Text)
    weaknesses = Column(Text)
    explanation = Column(Text)
    pronunciation_tips = Column(String, nullable=True)

    result = relationship("Result", back_populates="analysis")