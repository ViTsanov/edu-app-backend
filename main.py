from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import database, models, schemas, crud, security
from typing import List
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated
import ai_service # Не забравяй да го импортнеш най-горе!
import shutil
import os

# Създаваме таблиците, ако не съществуват
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="English Learning API",
    description="Backend for the English Learning App",
    version="1.0.0"
)

async def get_current_user(token: Annotated[str, Depends(security.oauth2_scheme)], db: Session = Depends(database.get_db)):
    # 1. Опитваме се да разкодираме имейла от токена
    email = security.decode_access_token(token)
    if email is None:
        raise HTTPException(status_code=401, detail="Невалиден пропуск (токен)")
    
    # 2. Търсим потребителя в базата данни
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise HTTPException(status_code=401, detail="Потребителят не е намерен")
    
    return user

# Функция, която проверява дали потребителят е Експерт
def check_is_expert(current_user: Annotated[models.User, Depends(get_current_user)]):
    if current_user.role_id != 3:
        raise HTTPException(
            status_code=403, 
            detail="Нямате нужните права. Този ресурс е само за Експерти."
        )
    return current_user

@app.get("/")
def read_root():
    return {"message": "Добре дошли в API-то на приложението за английски език!"}

@app.get("/test-db")
def test_db_connection(db: Session = Depends(database.get_db)):
    return {"status": "success", "message": "Успешна връзка с PostgreSQL!"}

# --- РЕГИСТРАЦИЯ ---
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Този имейл вече е регистриран")
    return crud.create_user(db=db, user=user)

# --- ВХОД (LOGIN) ---
@app.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    # 1. Търсим потребителя по имейл (OAuth2 стандартът нарича това поле 'username')
    user = crud.get_user_by_email(db, email=form_data.username)
    
    # 2. Ако няма такъв потребител ИЛИ паролата е грешна
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401, 
            detail="Грешен имейл или парола",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Ако всичко е точно, създаваме билета (токена)
    access_token = security.create_access_token(data={"sub": user.email})
    
    # Връщаме го на мобилното приложение (или в нашия случай - на браузъра)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: Annotated[models.User, Depends(get_current_user)]):
    # Тази функция ще се изпълни САМО ако токенът е валиден. 
    # FastAPI автоматично ще провери токена чрез get_current_user.
    return current_user

@app.get("/expert/dashboard")
def get_expert_dashboard(expert: Annotated[models.User, Depends(check_is_expert)]):
    return {
        "message": f"Здравейте, Експерт {expert.full_name}!",
        "pending_tasks": "Тук ще се виждат упражненията за одобрение."
    }

@app.post("/expert/generate-exercise")
# ПРОМЯНА: Добавяме 'async'
async def trigger_ai_exercise(
    module_id: int, # Променено да приема ID на модула заради новата база
    level_id: int,  # Променено да приема ID на нивото
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db)
):
    
    db_level = db.query(models.Level).filter(models.Level.id == level_id).first()
    db_module = db.query(models.Module).filter(models.Module.id == module_id).first()
    
    if not db_level or not db_module:
        raise HTTPException(status_code=400, detail="Невалидно ниво или модул")
    # Тъй като AI все още иска текст ("A1", "Grammar"), ще ги подаваме ръчно за теста:
    # В реалния случай тук ще ги извличаме от базата спрямо ID-тата
    level_name = db_level.name 
    module_name = db_level.module

    # 1. Викаме AI да измисли упражнение (Чакаме асинхронно с 'await')
    raw_ai_data = await ai_service.generate_exercise_ai(module=module_name, level=level_name)
    
    # 2. Записваме го в базата като "за одобрение" (PENDING) според новия модел
    new_exercise = models.Exercise(
        title=f"AI Generated - Level {level_name}",
        content_prompt=raw_ai_data,
        level_id=level_id,
        module_id=module_id,
        status=models.ExerciseStatus.PENDING # Използваме новия статус!
    )
    db.add(new_exercise)
    db.commit()
    db.refresh(new_exercise)
    
    return {"message": "Упражнението е генерирано асинхронно и чака преглед!", "id": new_exercise.id}

@app.get("/expert/pending", response_model=List[schemas.ExerciseResponse]) # Ще създадем схемата след малко
def list_pending(expert: Annotated[models.User, Depends(check_is_expert)], db: Session = Depends(database.get_db)):
    return crud.get_pending_exercises(db)

@app.put("/expert/approve/{exercise_id}")
def approve(exercise_id: int, expert: Annotated[models.User, Depends(check_is_expert)], db: Session = Depends(database.get_db)):
    exercise = crud.approve_exercise(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")
    return {"status": "success", "message": f"Упражнение №{exercise_id} е одобрено!"}

@app.get("/exercises")
def get_exercises(db: Session = Depends(database.get_db)):
    # Връщаме всички упражнения от таблицата exercises
    exercises = db.query(models.Exercise).all()
    return exercises

@app.post("/exercises/{exercise_id}/submit-audio")
async def submit_audio_exercise(
    exercise_id: int,
    current_user: Annotated[models.User, Depends(get_current_user)],
    file: UploadFile = File(...), # Това казва на FastAPI да очаква multipart/form-data файл
    db: Session = Depends(database.get_db)
):
    # 1. Проверяваме дали упражнението съществува
    exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")

    # 2. Запазваме файла временно на сървъра, за да го пратим на Whisper
    temp_file_path = f"temp_{current_user.id}_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 3. Викаме нашия AI Service да оцени аудиото
        ai_evaluation = await ai_service.evaluate_audio_exercise(temp_file_path, exercise.title)
        
        # 4. Записваме в базата (Таблица Results)
        new_result = models.Result(
            user_id=current_user.id,
            exercise_id=exercise_id,
            user_answer=ai_evaluation["transcribed_text"],
            xp_earned=10 + ai_evaluation["grammar_score"] # Примерна логика за точки
        )
        db.add(new_result)
        db.flush() # Използваме flush, за да вземем ID-то на резултата веднага
        
        # 5. Записваме в базата (Таблица AI_Analysis - 1:1 връзка!)
        new_analysis = models.AIAnalysis(
            result_id=new_result.id,
            grammar_score=ai_evaluation["grammar_score"],
            fluency_score=ai_evaluation["fluency_score"],
            strengths=ai_evaluation["strengths"],
            weaknesses=ai_evaluation["weaknesses"],
            explanation=ai_evaluation["explanation"]
        )
        db.add(new_analysis)
        db.commit()
        
        return {
            "status": "success", 
            "message": "Аудиото е анализирано успешно!", 
            "data": ai_evaluation
        }
    finally:
        # 6. ВАЖНО: Изтриваме временния аудио файл от сървъра, за да не пълним харддиска (GDPR best practice)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)