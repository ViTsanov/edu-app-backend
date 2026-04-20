from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import database, models, schemas, crud, security
from typing import List, Optional
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated
import ai_service
import os
import tempfile
from pydantic import BaseModel, field_validator
from passlib.context import CryptContext
import json
import random
import string
from models import (
    TeacherExercise, Test, TestExercise,
    TestAttempt, TestAnswer, StudentSession,
    ImprovementSuggestion, Homework,
)
from datetime import datetime as dt

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4"}
MAX_AUDIO_SIZE_MB = 25
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024

models.Base.metadata.create_all(bind=database.engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(
    title="English Learning API",
    description="Backend for the English Learning App",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to real frontend origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Inline request models ─────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    email: str
    username: str
    password: str
    role_id: int = 1

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Паролата трябва да е поне 8 символа.")
        if not any(c.isupper() for c in v):
            raise ValueError("Паролата трябва да съдържа поне една главна буква.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Паролата трябва да съдържа поне една цифра.")
        return v


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    role_id: int
    total_xp: int
    english_level: str
    profile_picture: Optional[str] = None
    teacher_verification_status: str

    class Config:
        from_attributes = True


class ExerciseUpdateRequest(BaseModel):
    content_prompt: str


class TextSubmissionRequest(BaseModel):
    questions: List[str]
    expected_answers: List[str]
    user_answers: List[str]


class ClassroomCreate(BaseModel):
    name: str
    level_id: int


class JoinClassroomRequest(BaseModel):
    access_code: str


class TeacherExerciseCreate(BaseModel):
    title: str
    content_prompt: str
    module_id: Optional[int] = None
    level_id: Optional[int] = None


class TestCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    classroom_id: int
    time_limit_minutes: int = 0


class AddExerciseToTest(BaseModel):
    exercise_id: Optional[int] = None
    teacher_exercise_id: Optional[int] = None
    order_index: int = 0


class TestSubmission(BaseModel):
    answers: List[dict]


class HomeworkCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    classroom_id: int
    exercise_id: Optional[int] = None
    teacher_exercise_id: Optional[int] = None
    due_date: Optional[str] = None


class TestActivateRequest(BaseModel):
    opens_at: Optional[str] = None


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(security.oauth2_scheme)],
    db: Session = Depends(database.get_db),
):
    email = security.decode_access_token(token)
    if email is None:
        raise HTTPException(status_code=401, detail="Невалиден токен")
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise HTTPException(status_code=401, detail="Потребителят не е намерен")
    return user


def check_is_expert(current_user: Annotated[models.User, Depends(get_current_user)]):
    if current_user.role_id != 3:
        raise HTTPException(
            status_code=403,
            detail="Нямате нужните права. Този ресурс е само за Експерти.",
        )
    return current_user


def check_is_teacher(current_user: models.User = Depends(get_current_user)):
    if current_user.role_id not in (2, 4):
        raise HTTPException(
            status_code=403,
            detail="Само учители имат достъп до тази функция.",
        )
    return current_user


def _random_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── General ───────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Добре дошли в API-то на приложението за английски език!"}


@app.get("/test-db")
def test_db_connection(db: Session = Depends(database.get_db)):
    return {"status": "success", "message": "Успешна връзка с PostgreSQL!"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: UserCreateRequest, db: Session = Depends(database.get_db)):
    existing = db.query(models.User).filter(
        (models.User.email == user.email) | (models.User.username == user.username)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Този имейл или потребителско име вече е зает!")
    new_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=pwd_context.hash(user.password),
        role_id=user.role_id,
        total_xp=0,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Грешен имейл или парола",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: Annotated[models.User, Depends(get_current_user)]):
    return current_user


# ── Expert ────────────────────────────────────────────────────────────────────

@app.get("/expert/dashboard")
def get_expert_dashboard(expert: Annotated[models.User, Depends(check_is_expert)]):
    return {
        "message": f"Здравейте, Експерт {expert.username}!",
        "pending_tasks": "Тук ще се виждат упражненията за одобрение.",
    }


@app.post("/expert/generate-exercise")
async def trigger_ai_exercise(
    module_id: int,
    level_id: int,
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db),
):
    db_level = db.query(models.Level).filter(models.Level.id == level_id).first()
    db_module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not db_level or not db_module:
        raise HTTPException(status_code=400, detail="Невалидно ниво или модул")
    raw_ai_data = await ai_service.generate_exercise_ai(
        module=db_module.name, level=db_level.name
    )
    new_exercise = models.Exercise(
        title=f"AI Generated - Level {db_level.name}",
        content_prompt=raw_ai_data,
        level_id=level_id,
        module_id=module_id,
        status=models.ExerciseStatus.PENDING,
    )
    db.add(new_exercise)
    db.commit()
    db.refresh(new_exercise)
    return {"message": "Упражнението е генерирано и чака преглед!", "id": new_exercise.id}


@app.get("/expert/pending", response_model=List[schemas.ExerciseResponse])
def list_pending(
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db),
):
    return crud.get_pending_exercises(db)


@app.put("/expert/approve/{exercise_id}")
def approve(
    exercise_id: int,
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db),
):
    exercise = crud.approve_exercise(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")
    return {"status": "success", "message": f"Упражнение №{exercise_id} е одобрено!"}


@app.put("/expert/edit/{exercise_id}")
def edit_exercise(
    exercise_id: int,
    request: ExerciseUpdateRequest,
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db),
):
    exercise = crud.update_exercise_content(db, exercise_id, request.content_prompt)
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")
    return {"status": "success", "message": f"Упражнение №{exercise_id} е обновено!"}


@app.delete("/expert/reject/{exercise_id}")
def reject_exercise(
    exercise_id: int,
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db),
):
    exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")
    db.delete(exercise)
    db.commit()
    return {"status": "success", "message": f"Упражнение №{exercise_id} е отхвърлено и изтрито!"}


# ── Exercises ─────────────────────────────────────────────────────────────────

@app.get("/exercises")
def get_exercises(db: Session = Depends(database.get_db)):
    return db.query(models.Exercise).filter(
        models.Exercise.status == models.ExerciseStatus.APPROVED
    ).all()


@app.get("/modules")
def get_all_modules(db: Session = Depends(database.get_db)):
    return [{"id": m.id, "name": m.name} for m in db.query(models.Module).all()]


@app.get("/levels")
def get_all_levels(db: Session = Depends(database.get_db)):
    return [{"id": l.id, "name": l.name} for l in db.query(models.Level).all()]


@app.get("/exercises/my-path")
def get_student_path(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(database.get_db),
):
    approved_exercises = (
        db.query(models.Exercise)
        .join(models.Level, models.Exercise.level_id == models.Level.id)
        .filter(
            models.Exercise.status == models.ExerciseStatus.APPROVED,
            models.Level.name == current_user.english_level,
        )
        .all()
    )
    user_results = db.query(models.Result).filter(
        models.Result.user_id == current_user.id
    ).all()
    exercise_scores: dict = {}
    for res in user_results:
        analysis = db.query(models.AIAnalysis).filter(
            models.AIAnalysis.result_id == res.id
        ).first()
        score = analysis.grammar_score if analysis else 0
        exercise_scores[res.exercise_id] = max(
            exercise_scores.get(res.exercise_id, 0), score
        )
    PASSING_SCORE = 70
    path_response = []
    for ex in approved_exercises:
        best_score = exercise_scores.get(ex.id)
        if best_score is None:
            status = "AVAILABLE"
        elif best_score >= PASSING_SCORE:
            status = "COMPLETED"
        else:
            status = "RETRY"
        path_response.append({
            "id": ex.id,
            "title": ex.title,
            "content_prompt": ex.content_prompt,
            "status": status,
            "best_score": best_score,
        })
    return path_response


@app.post("/exercises/{exercise_id}/submit-audio")
async def submit_audio_exercise(
    exercise_id: int,
    current_user: Annotated[models.User, Depends(get_current_user)],
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
):
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Невалиден формат. Позволени: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}",
        )

    exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")

    instructions = "Read the text aloud or answer the prompt."
    content: list = []
    correct_answers: list = []
    try:
        ex_data = json.loads(exercise.content_prompt)
        instructions = ex_data.get("instructions", instructions)
        content = ex_data.get("content", [])
        correct_answers = ex_data.get("correct_answers", [])
    except (json.JSONDecodeError, AttributeError):
        pass

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Файлът е прекалено голям. Максимален размер: {MAX_AUDIO_SIZE_MB}MB",
        )

    suffix = ext.lower() if ext else ".audio"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(audio_bytes)
        tmp.close()
        ai_evaluation = await ai_service.evaluate_audio_exercise(
            audio_file_path=tmp.name,
            instructions=instructions,
            content=content,
            correct_answers=correct_answers,
        )
        xp_earned = 5 + (ai_evaluation.get("grammar_score", 0) // 10)
        new_result = models.Result(
            user_id=current_user.id,
            exercise_id=exercise_id,
            user_answer=ai_evaluation["transcribed_text"],
            xp_earned=xp_earned,
        )
        db.add(new_result)
        db.flush()
        new_analysis = models.AIAnalysis(
            result_id=new_result.id,
            grammar_score=ai_evaluation.get("grammar_score", 0),
            fluency_score=ai_evaluation.get("fluency_score", 0),
            strengths=ai_evaluation.get("strengths", ""),
            weaknesses=ai_evaluation.get("weaknesses", ""),
            explanation=ai_evaluation.get("explanation", ""),
            pronunciation_tips=ai_evaluation.get("pronunciation_tips", ""),
        )
        db.add(new_analysis)
        current_user.total_xp += xp_earned
        db.commit()
        ai_evaluation["xp_earned"] = xp_earned
        return {
            "status": "success",
            "message": "Аудиото е анализирано успешно!",
            "data": ai_evaluation,
        }
    finally:
        os.unlink(tmp.name)


@app.post("/exercises/{exercise_id}/submit-text")
async def submit_text_exercise(
    exercise_id: int,
    submission: TextSubmissionRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(database.get_db),
):
    ai_evaluation = await ai_service.evaluate_text_exercise(
        submission.questions, submission.expected_answers, submission.user_answers
    )
    xp_earned = 5 + (ai_evaluation["grammar_score"] // 10)
    new_result = models.Result(
        user_id=current_user.id,
        exercise_id=exercise_id,
        user_answer=" | ".join(submission.user_answers),
        xp_earned=xp_earned,
    )
    db.add(new_result)
    db.flush()
    new_analysis = models.AIAnalysis(
        result_id=new_result.id,
        grammar_score=ai_evaluation["grammar_score"],
        fluency_score=0,
        strengths=ai_evaluation.get("strengths", ""),
        weaknesses=ai_evaluation.get("weaknesses", ""),
        explanation=ai_evaluation.get("explanation", ""),
    )
    db.add(new_analysis)
    current_user.total_xp += xp_earned
    db.commit()
    ai_evaluation["xp_earned"] = xp_earned
    return {"status": "success", "data": ai_evaluation}


@app.get("/exercises/{exercise_id}/my-result")
def get_my_exercise_result(
    exercise_id: int,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(database.get_db),
):
    results = db.query(models.Result).filter(
        models.Result.user_id == current_user.id,
        models.Result.exercise_id == exercise_id,
    ).all()
    if not results:
        raise HTTPException(404, "Нямате резултат за това упражнение.")

    best_result = None
    best_score = -1
    best_analysis = None
    for r in results:
        analysis = db.query(models.AIAnalysis).filter(
            models.AIAnalysis.result_id == r.id
        ).first()
        score = analysis.grammar_score if analysis else 0
        if score > best_score:
            best_score = score
            best_result = r
            best_analysis = analysis

    if not best_result:
        raise HTTPException(404, "Резултатът не е намерен.")

    user_answers = best_result.user_answer.split(" | ") if best_result.user_answer else []
    exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    return {
        "exercise_id": exercise_id,
        "exercise_title": exercise.title if exercise else "",
        "exercise_content": exercise.content_prompt if exercise else "",
        "user_answers": user_answers,
        "xp_earned": best_result.xp_earned,
        "completed_at": best_result.created_at.isoformat() if best_result.created_at else None,
        "grammar_score": best_analysis.grammar_score if best_analysis else 0,
        "fluency_score": best_analysis.fluency_score if best_analysis else 0,
        "strengths": best_analysis.strengths if best_analysis else "",
        "weaknesses": best_analysis.weaknesses if best_analysis else "",
        "explanation": best_analysis.explanation if best_analysis else "",
        "pronunciation_tips": best_analysis.pronunciation_tips if best_analysis else None,
    }


# ── Classroom Management ──────────────────────────────────────────────────────

@app.post("/teacher/classrooms")
def create_classroom(
    body: ClassroomCreate,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    code = _random_code()
    while db.query(models.Classroom).filter(models.Classroom.access_code == code).first():
        code = _random_code()
    classroom = models.Classroom(
        name=body.name,
        access_code=code,
        teacher_id=teacher.id,
        level_id=body.level_id,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return {"id": classroom.id, "name": classroom.name, "access_code": code}


@app.get("/teacher/classrooms")
def get_my_classrooms(
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    classrooms = db.query(models.Classroom).filter(
        models.Classroom.teacher_id == teacher.id
    ).all()
    result = []
    for c in classrooms:
        student_count = db.query(models.ClassStudent).filter(
            models.ClassStudent.classroom_id == c.id
        ).count()
        result.append({
            "id": c.id, "name": c.name, "access_code": c.access_code,
            "level_id": c.level_id, "student_count": student_count,
        })
    return result


@app.get("/teacher/classrooms/{classroom_id}/students")
def get_classroom_students(
    classroom_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    classroom = db.query(models.Classroom).filter(
        models.Classroom.id == classroom_id,
        models.Classroom.teacher_id == teacher.id,
    ).first()
    if not classroom:
        raise HTTPException(404, "Класът не е намерен.")
    rows = db.query(models.ClassStudent).filter(
        models.ClassStudent.classroom_id == classroom_id
    ).all()
    students = []
    for row in rows:
        u = db.query(models.User).filter(models.User.id == row.user_id).first()
        if u:
            students.append({
                "id": u.id, "username": u.username, "email": u.email,
                "english_level": u.english_level, "total_xp": u.total_xp,
                "joined_at": row.joined_at.isoformat() if row.joined_at else None,
            })
    return students


@app.delete("/teacher/classrooms/{classroom_id}/students/{student_id}")
def remove_student_from_classroom(
    classroom_id: int,
    student_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    classroom = db.query(models.Classroom).filter(
        models.Classroom.id == classroom_id,
        models.Classroom.teacher_id == teacher.id,
    ).first()
    if not classroom:
        raise HTTPException(404, "Класът не е намерен.")
    row = db.query(models.ClassStudent).filter(
        models.ClassStudent.classroom_id == classroom_id,
        models.ClassStudent.user_id == student_id,
    ).first()
    if not row:
        raise HTTPException(404, "Ученикът не е в класа.")
    db.delete(row)
    db.commit()
    return {"status": "success", "message": "Ученикът е премахнат от класа."}


@app.get("/teacher/classrooms/{classroom_id}/monitoring")
def get_classroom_monitoring(
    classroom_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    classroom = db.query(models.Classroom).filter(
        models.Classroom.id == classroom_id,
        models.Classroom.teacher_id == teacher.id,
    ).first()
    if not classroom:
        raise HTTPException(404, "Класът не е намерен.")
    enrollments = db.query(models.ClassStudent).filter(
        models.ClassStudent.classroom_id == classroom_id
    ).all()
    result = []
    for enrollment in enrollments:
        student = db.query(models.User).filter(models.User.id == enrollment.user_id).first()
        if not student:
            continue
        results = db.query(models.Result).filter(models.Result.user_id == student.id).all()
        exercise_count = len(results)
        avg_score = 0
        if exercise_count > 0:
            scores = []
            for r in results:
                analysis = db.query(models.AIAnalysis).filter(
                    models.AIAnalysis.result_id == r.id
                ).first()
                if analysis:
                    scores.append(analysis.grammar_score)
            avg_score = sum(scores) // len(scores) if scores else 0
        sessions = db.query(models.StudentSession).filter(
            models.StudentSession.user_id == student.id,
            models.StudentSession.duration_seconds.isnot(None),
        ).all()
        total_seconds = sum(s.duration_seconds for s in sessions if s.duration_seconds)
        test_attempts = db.query(models.TestAttempt).filter(
            models.TestAttempt.student_id == student.id,
            models.TestAttempt.is_completed == True,
        ).count()
        result.append({
            "student_id": student.id, "username": student.username,
            "english_level": student.english_level, "total_xp": student.total_xp,
            "exercises_completed": exercise_count, "average_score": avg_score,
            "total_time_seconds": total_seconds, "tests_completed": test_attempts,
        })
    return result


# ── Student ───────────────────────────────────────────────────────────────────

@app.post("/student/join-classroom")
def join_classroom(
    body: JoinClassroomRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    classroom = db.query(models.Classroom).filter(
        models.Classroom.access_code == body.access_code.upper()
    ).first()
    if not classroom:
        raise HTTPException(404, "Невалиден код за достъп.")
    existing = db.query(models.ClassStudent).filter(
        models.ClassStudent.user_id == current_user.id,
        models.ClassStudent.classroom_id == classroom.id,
    ).first()
    if existing:
        raise HTTPException(400, "Вече сте в този клас.")
    enrollment = models.ClassStudent(user_id=current_user.id, classroom_id=classroom.id)
    db.add(enrollment)
    db.commit()
    return {"status": "success", "message": f"Добавен в класа: {classroom.name}"}


@app.get("/student/my-classrooms")
def get_student_classrooms(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    rows = db.query(models.ClassStudent).filter(
        models.ClassStudent.user_id == current_user.id
    ).all()
    result = []
    for row in rows:
        classroom = db.query(models.Classroom).filter(
            models.Classroom.id == row.classroom_id
        ).first()
        if not classroom:
            continue
        teacher = db.query(models.User).filter(models.User.id == classroom.teacher_id).first()
        level = db.query(models.Level).filter(models.Level.id == classroom.level_id).first()
        classmate_count = db.query(models.ClassStudent).filter(
            models.ClassStudent.classroom_id == classroom.id
        ).count()
        homework_count = db.query(models.Homework).filter(
            models.Homework.classroom_id == classroom.id
        ).count()
        result.append({
            "id": classroom.id, "name": classroom.name,
            "access_code": classroom.access_code,
            "teacher_name": teacher.username if teacher else "Unknown",
            "level": level.name if level else "A1",
            "classmate_count": classmate_count,
            "homework_count": homework_count,
            "joined_at": row.joined_at.isoformat() if row.joined_at else None,
        })
    return result


@app.get("/student/homework")
def get_student_homework(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    enrollments = db.query(models.ClassStudent).filter(
        models.ClassStudent.user_id == current_user.id
    ).all()
    classroom_ids = [e.classroom_id for e in enrollments]
    homework_list = db.query(models.Homework).filter(
        models.Homework.classroom_id.in_(classroom_ids)
    ).order_by(models.Homework.due_date.asc()).all()
    now = dt.utcnow()
    result = []
    for hw in homework_list:
        completed = False
        if hw.exercise_id:
            res = db.query(models.Result).filter(
                models.Result.user_id == current_user.id,
                models.Result.exercise_id == hw.exercise_id,
            ).first()
            completed = res is not None
        content_prompt = None
        if hw.exercise_id:
            ex = db.query(models.Exercise).filter(models.Exercise.id == hw.exercise_id).first()
            if ex:
                content_prompt = ex.content_prompt
        elif hw.teacher_exercise_id:
            ex = db.query(TeacherExercise).filter(
                TeacherExercise.id == hw.teacher_exercise_id
            ).first()
            if ex:
                content_prompt = ex.content_prompt
        overdue = hw.due_date is not None and hw.due_date < now
        classroom = db.query(models.Classroom).filter(
            models.Classroom.id == hw.classroom_id
        ).first()
        result.append({
            "id": hw.id, "title": hw.title, "description": hw.description,
            "classroom_name": classroom.name if classroom else "",
            "exercise_id": hw.exercise_id,
            "teacher_exercise_id": hw.teacher_exercise_id,
            "content_prompt": content_prompt,
            "due_date": hw.due_date.isoformat() if hw.due_date else None,
            "completed": completed,
            "overdue": overdue and not completed,
        })
    return result


@app.get("/student/active-tests")
def get_active_tests_for_student(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    enrollments = db.query(models.ClassStudent).filter(
        models.ClassStudent.user_id == current_user.id
    ).all()
    classroom_ids = [e.classroom_id for e in enrollments]
    now = dt.utcnow()
    tests = db.query(models.Test).filter(
        models.Test.classroom_id.in_(classroom_ids),
        models.Test.is_active == True,
    ).all()
    result = []
    for t in tests:
        is_open = t.opens_at is None or t.opens_at <= now
        attempt = db.query(TestAttempt).filter(
            TestAttempt.test_id == t.id,
            TestAttempt.student_id == current_user.id,
            TestAttempt.is_completed == True,
        ).first()
        result.append({
            "id": t.id, "title": t.title, "description": t.description,
            "time_limit_minutes": t.time_limit_minutes,
            "exercise_count": len(t.exercises),
            "is_open": is_open,
            "opens_at": t.opens_at.isoformat() if t.opens_at else None,
            "is_completed": attempt is not None,
            "my_score": attempt.total_score if attempt else None,
        })
    return result


@app.get("/student/tests/{test_id}")
def get_test_for_student(
    test_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    test = db.query(models.Test).filter(
        models.Test.id == test_id,
        models.Test.is_active == True,
    ).first()
    if not test:
        raise HTTPException(404, "Тестът не е намерен или не е активен.")
    enrollment = db.query(models.ClassStudent).filter(
        models.ClassStudent.user_id == current_user.id,
        models.ClassStudent.classroom_id == test.classroom_id,
    ).first()
    if not enrollment:
        raise HTTPException(403, "Нямате достъп до този тест.")
    exercises_out = []
    for te in sorted(test.exercises, key=lambda x: x.order_index):
        if te.exercise_id:
            ex = db.query(models.Exercise).filter(models.Exercise.id == te.exercise_id).first()
            if ex:
                exercises_out.append({
                    "test_exercise_id": te.id, "content_prompt": ex.content_prompt,
                    "title": ex.title, "source": "approved",
                })
        elif te.teacher_exercise_id:
            ex = db.query(TeacherExercise).filter(
                TeacherExercise.id == te.teacher_exercise_id
            ).first()
            if ex:
                exercises_out.append({
                    "test_exercise_id": te.id, "content_prompt": ex.content_prompt,
                    "title": ex.title, "source": "teacher",
                })
    return {
        "id": test.id, "title": test.title,
        "time_limit_minutes": test.time_limit_minutes,
        "exercises": exercises_out,
    }


@app.post("/student/tests/{test_id}/submit")
async def submit_test(
    test_id: int,
    body: TestSubmission,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    if not body.answers:
        raise HTTPException(400, "Трябва да подадете поне един отговор.")
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(404, "Тестът не е намерен.")
    enrollment = db.query(models.ClassStudent).filter(
        models.ClassStudent.user_id == current_user.id,
        models.ClassStudent.classroom_id == test.classroom_id,
    ).first()
    if not enrollment:
        raise HTTPException(403, "Нямате достъп до този тест.")
    attempt = models.TestAttempt(
        test_id=test_id,
        student_id=current_user.id,
        started_at=dt.utcnow(),
    )
    db.add(attempt)
    db.flush()
    total_score = 0
    all_evaluations = []
    for answer_data in body.answers:
        te_id = answer_data.get("test_exercise_id")
        questions = answer_data.get("questions", [])
        expected = answer_data.get("expected_answers", [])
        user_answers = answer_data.get("user_answers", [])
        ai_eval = await ai_service.evaluate_text_exercise(questions, expected, user_answers)
        score = ai_eval.get("grammar_score", 0)
        total_score += score
        ta = TestAnswer(
            attempt_id=attempt.id,
            test_exercise_id=te_id,
            user_answer=json.dumps(user_answers),
            grammar_score=score,
            fluency_score=0,
            ai_explanation=ai_eval.get("explanation", ""),
        )
        db.add(ta)
        all_evaluations.append(ai_eval)
    avg_score = total_score // len(body.answers)
    xp_earned = 10 + (avg_score // 5)
    test_feedback = await ai_service.analyze_test_results(all_evaluations, avg_score)
    attempt.finished_at = dt.utcnow()
    attempt.total_score = avg_score
    attempt.xp_earned = xp_earned
    attempt.ai_feedback = test_feedback
    attempt.is_completed = True
    current_user.total_xp += xp_earned
    suggestion = ImprovementSuggestion(
        user_id=current_user.id,
        source_type="test",
        source_id=attempt.id,
        suggestion_text=test_feedback,
        focus_areas=json.dumps([]),
    )
    db.add(suggestion)
    db.commit()
    return {
        "status": "success",
        "total_score": avg_score,
        "xp_earned": xp_earned,
        "ai_feedback": test_feedback,
        "per_exercise": all_evaluations,
    }


@app.get("/student/improvement-suggestions")
def get_my_suggestions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    suggestions = db.query(ImprovementSuggestion).filter(
        ImprovementSuggestion.user_id == current_user.id
    ).order_by(ImprovementSuggestion.created_at.desc()).limit(5).all()
    return [
        {
            "id": s.id, "source_type": s.source_type,
            "suggestion_text": s.suggestion_text,
            "focus_areas": json.loads(s.focus_areas) if s.focus_areas else [],
            "created_at": s.created_at.isoformat(),
            "is_read": s.is_read,
        }
        for s in suggestions
    ]


@app.put("/student/improvement-suggestions/{suggestion_id}/read")
def mark_suggestion_read(
    suggestion_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    s = db.query(ImprovementSuggestion).filter(
        ImprovementSuggestion.id == suggestion_id,
        ImprovementSuggestion.user_id == current_user.id,
    ).first()
    if s:
        s.is_read = True
        db.commit()
    return {"status": "success"}


# ── Teacher Exercise Library ───────────────────────────────────────────────────

@app.post("/teacher/exercises")
def save_teacher_exercise(
    body: TeacherExerciseCreate,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    ex = TeacherExercise(
        teacher_id=teacher.id,
        title=body.title,
        content_prompt=body.content_prompt,
        module_id=body.module_id,
        level_id=body.level_id,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return {"id": ex.id, "title": ex.title, "message": "Упражнението е запазено в библиотеката."}


@app.get("/teacher/exercises")
def get_teacher_exercises(
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    exercises = db.query(TeacherExercise).filter(
        TeacherExercise.teacher_id == teacher.id
    ).order_by(TeacherExercise.created_at.desc()).all()
    return [
        {
            "id": e.id, "title": e.title, "module_id": e.module_id,
            "level_id": e.level_id, "created_at": e.created_at.isoformat(),
        }
        for e in exercises
    ]


@app.delete("/teacher/exercises/{exercise_id}")
def delete_teacher_exercise(
    exercise_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    ex = db.query(TeacherExercise).filter(
        TeacherExercise.id == exercise_id,
        TeacherExercise.teacher_id == teacher.id,
    ).first()
    if not ex:
        raise HTTPException(404, "Упражнението не е намерено.")
    db.delete(ex)
    db.commit()
    return {"status": "success"}


# ── Test Builder ──────────────────────────────────────────────────────────────

@app.post("/teacher/tests")
def create_test(
    body: TestCreate,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    classroom = db.query(models.Classroom).filter(
        models.Classroom.id == body.classroom_id,
        models.Classroom.teacher_id == teacher.id,
    ).first()
    if not classroom:
        raise HTTPException(404, "Класът не е намерен или не е ваш.")
    test = Test(
        title=body.title,
        description=body.description,
        teacher_id=teacher.id,
        classroom_id=body.classroom_id,
        time_limit_minutes=body.time_limit_minutes,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return {"id": test.id, "title": test.title, "message": "Тестът е създаден."}


@app.post("/teacher/tests/{test_id}/exercises")
def add_exercise_to_test(
    test_id: int,
    body: AddExerciseToTest,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    test = db.query(Test).filter(Test.id == test_id, Test.teacher_id == teacher.id).first()
    if not test:
        raise HTTPException(404, "Тестът не е намерен.")
    if not body.exercise_id and not body.teacher_exercise_id:
        raise HTTPException(400, "Трябва да подадете exercise_id или teacher_exercise_id.")
    te = TestExercise(
        test_id=test_id,
        exercise_id=body.exercise_id,
        teacher_exercise_id=body.teacher_exercise_id,
        order_index=body.order_index,
    )
    db.add(te)
    db.commit()
    return {"status": "success", "message": "Упражнението е добавено в теста."}


@app.put("/teacher/tests/{test_id}/activate")
def activate_test(
    test_id: int,
    body: TestActivateRequest = TestActivateRequest(),
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    test = db.query(Test).filter(Test.id == test_id, Test.teacher_id == teacher.id).first()
    if not test:
        raise HTTPException(404, "Тестът не е намерен.")
    test.is_active = True
    if body.opens_at:
        try:
            test.opens_at = dt.fromisoformat(body.opens_at)
        except ValueError:
            raise HTTPException(400, "Невалиден формат за дата.")
    else:
        test.opens_at = None
    db.commit()
    opens_msg = (
        f"отваря се на {test.opens_at.strftime('%d.%m.%Y %H:%M')}"
        if test.opens_at
        else "достъпен веднага"
    )
    return {
        "status": "success",
        "is_active": True,
        "opens_at": test.opens_at.isoformat() if test.opens_at else None,
        "message": f"Тестът е активиран — {opens_msg}.",
    }


@app.put("/teacher/tests/{test_id}/deactivate")
def deactivate_test(
    test_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    test = db.query(Test).filter(Test.id == test_id, Test.teacher_id == teacher.id).first()
    if not test:
        raise HTTPException(404, "Тестът не е намерен.")
    test.is_active = False
    db.commit()
    return {"status": "success", "is_active": False, "message": "Тестът е деактивиран."}


@app.get("/teacher/tests")
def get_teacher_tests(
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    tests = db.query(Test).filter(
        Test.teacher_id == teacher.id
    ).order_by(Test.created_at.desc()).all()
    result = []
    for t in tests:
        attempt_count = db.query(TestAttempt).filter(TestAttempt.test_id == t.id).count()
        result.append({
            "id": t.id, "title": t.title, "description": t.description,
            "classroom_id": t.classroom_id, "time_limit_minutes": t.time_limit_minutes,
            "is_active": t.is_active, "exercise_count": len(t.exercises),
            "attempt_count": attempt_count, "created_at": t.created_at.isoformat(),
        })
    return result


@app.get("/teacher/tests/{test_id}/results")
def get_test_results(
    test_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    test = db.query(Test).filter(Test.id == test_id, Test.teacher_id == teacher.id).first()
    if not test:
        raise HTTPException(404, "Тестът не е намерен.")
    attempts = db.query(TestAttempt).filter(
        TestAttempt.test_id == test_id,
        TestAttempt.is_completed == True,
    ).all()
    result = []
    for a in attempts:
        student = db.query(models.User).filter(models.User.id == a.student_id).first()
        duration = None
        if a.started_at and a.finished_at:
            duration = int((a.finished_at - a.started_at).total_seconds())
        result.append({
            "student_id": a.student_id,
            "student_name": student.username if student else "Unknown",
            "total_score": a.total_score, "xp_earned": a.xp_earned,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "finished_at": a.finished_at.isoformat() if a.finished_at else None,
            "duration_seconds": duration, "ai_feedback": a.ai_feedback,
        })
    return result


# ── Homework ──────────────────────────────────────────────────────────────────

@app.post("/teacher/homework")
def create_homework(
    body: HomeworkCreate,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    if not body.exercise_id and not body.teacher_exercise_id:
        raise HTTPException(400, "Трябва exercise_id или teacher_exercise_id.")
    classroom = db.query(models.Classroom).filter(
        models.Classroom.id == body.classroom_id,
        models.Classroom.teacher_id == teacher.id,
    ).first()
    if not classroom:
        raise HTTPException(404, "Класът не е намерен.")
    due = None
    if body.due_date:
        try:
            due = dt.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(400, "Невалиден формат за дата.")
    hw = Homework(
        teacher_id=teacher.id,
        classroom_id=body.classroom_id,
        title=body.title,
        description=body.description,
        exercise_id=body.exercise_id,
        teacher_exercise_id=body.teacher_exercise_id,
        due_date=due,
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return {"id": hw.id, "message": "Домашното е зададено успешно!"}


@app.get("/teacher/homework")
def get_teacher_homework(
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    rows = db.query(Homework).filter(
        Homework.teacher_id == teacher.id
    ).order_by(Homework.created_at.desc()).all()
    result = []
    for hw in rows:
        classroom = db.query(models.Classroom).filter(
            models.Classroom.id == hw.classroom_id
        ).first()
        student_ids = [
            row.user_id
            for row in db.query(models.ClassStudent).filter(
                models.ClassStudent.classroom_id == hw.classroom_id
            ).all()
        ]
        completed = 0
        if hw.exercise_id:
            completed = db.query(models.Result).filter(
                models.Result.exercise_id == hw.exercise_id,
                models.Result.user_id.in_(student_ids),
            ).count()
        result.append({
            "id": hw.id, "title": hw.title, "description": hw.description,
            "classroom_name": classroom.name if classroom else "",
            "classroom_id": hw.classroom_id,
            "exercise_id": hw.exercise_id,
            "teacher_exercise_id": hw.teacher_exercise_id,
            "due_date": hw.due_date.isoformat() if hw.due_date else None,
            "created_at": hw.created_at.isoformat(),
            "student_count": len(student_ids), "completed_count": completed,
        })
    return result


@app.delete("/teacher/homework/{homework_id}")
def delete_homework(
    homework_id: int,
    teacher: models.User = Depends(check_is_teacher),
    db: Session = Depends(database.get_db),
):
    hw = db.query(Homework).filter(
        Homework.id == homework_id,
        Homework.teacher_id == teacher.id,
    ).first()
    if not hw:
        raise HTTPException(404, "Домашното не е намерено.")
    db.delete(hw)
    db.commit()
    return {"status": "success"}


# ── Session Tracking ──────────────────────────────────────────────────────────

@app.post("/sessions/start")
def start_session(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    session = StudentSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id}


@app.put("/sessions/{session_id}/end")
def end_session(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    session = db.query(StudentSession).filter(
        StudentSession.id == session_id,
        StudentSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Сесията не е намерена.")
    now = dt.utcnow()
    session.ended_at = now
    if session.started_at:
        session.duration_seconds = int((now - session.started_at).total_seconds())
    db.commit()
    return {"status": "success", "duration_seconds": session.duration_seconds}
