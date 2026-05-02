from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, Enum, DateTime
from sqlalchemy.orm import relationship
from database import Base
import enum
import datetime
from sqlalchemy.orm import relationship

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
    english_level = Column(String, default="A1")
    profile_picture = Column(String, nullable=True)
    teacher_verification_status = Column(String, default="none")
    fcm_token = Column(String, nullable=True)

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

class TeacherExercise(Base):
    """Exercises created and owned by a teacher — saved to their personal library."""
    __tablename__ = "teacher_exercises"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, index=True)
    content_prompt = Column(Text)          # same JSON format as Exercise
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    level_id = Column(Integer, ForeignKey("levels.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("User")
    module = relationship("Module")
    level = relationship("Level")


class Test(Base):
    """A timed test created by a teacher, assigned to one classroom."""
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    time_limit_minutes = Column(Integer, default=0)   # 0 = no limit
    is_active = Column(Boolean, default=False)
    opens_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("User", foreign_keys=[teacher_id])
    classroom = relationship("Classroom")
    exercises = relationship("TestExercise", back_populates="test", cascade="all, delete-orphan")
    attempts = relationship("TestAttempt", back_populates="test", cascade="all, delete-orphan")


class TestExercise(Base):
    """
    Many-to-many join between Test and an exercise.
    Supports both approved exercises (exercise_id) and
    teacher's own exercises (teacher_exercise_id).
    Exactly one of the two FK fields must be set.
    """
    __tablename__ = "test_exercises"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=True)
    teacher_exercise_id = Column(Integer, ForeignKey("teacher_exercises.id"), nullable=True)
    order_index = Column(Integer, default=0)

    test = relationship("Test", back_populates="exercises")
    exercise = relationship("Exercise")
    teacher_exercise = relationship("TeacherExercise")


class TestAttempt(Base):
    """Records one student's attempt at a specific test."""
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    total_score = Column(Integer, nullable=True)        
    xp_earned = Column(Integer, default=0)
    ai_feedback = Column(Text, nullable=True)           
    is_completed = Column(Boolean, default=False)

    test = relationship("Test", back_populates="attempts")
    student = relationship("User", foreign_keys=[student_id])
    answers = relationship("TestAnswer", back_populates="attempt", cascade="all, delete-orphan")


class TestAnswer(Base):
    """Individual answer within a TestAttempt (one row per exercise in the test)."""
    __tablename__ = "test_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.id"), nullable=False)
    test_exercise_id = Column(Integer, ForeignKey("test_exercises.id"), nullable=False)
    user_answer = Column(Text)
    grammar_score = Column(Integer, nullable=True)
    fluency_score = Column(Integer, nullable=True)
    ai_explanation = Column(Text, nullable=True)

    attempt = relationship("TestAttempt", back_populates="answers")
    test_exercise = relationship("TestExercise")


class StudentSession(Base):
    """
    Tracks how long a student spends in the app.
    POST /sessions/start  →  creates a row (returns session_id)
    PUT  /sessions/{id}/end  →  sets ended_at and duration
    """
    __tablename__ = "student_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    user = relationship("User")


class ImprovementSuggestion(Base):
    """
    Stores AI-generated improvement tips for a student,
    generated after each exercise result or after a full test.
    """
    __tablename__ = "improvement_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String)          
    source_id = Column(Integer)           
    suggestion_text = Column(Text)       
    focus_areas = Column(Text)            
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_read = Column(Boolean, default=False)

    user = relationship("User")

class Homework(Base):
    """A homework assignment created by a teacher for a classroom."""
    __tablename__ = "homework"
 
    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=True)
    teacher_exercise_id = Column(Integer, ForeignKey("teacher_exercises.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
 
    teacher = relationship("User", foreign_keys=[teacher_id])
    classroom = relationship("Classroom")
    exercise = relationship("Exercise")
    teacher_exercise = relationship("TeacherExercise")

class HomeworkSubmission(Base):
    """
    Links a student's Result to a specific Homework assignment.
    A Result can exist without a HomeworkSubmission (free learning path).
    A HomeworkSubmission always points to a Result (the actual answers).
    """
    __tablename__ = "homework_submissions"
 
    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    result_id = Column(Integer, ForeignKey("results.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
 
    homework = relationship("Homework")
    student = relationship("User", foreign_keys=[student_id])
    result = relationship("Result")