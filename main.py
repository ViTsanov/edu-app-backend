from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import database, models, schemas, crud, security
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated
import ai_service # Не забравяй да го импортнеш най-горе!

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
    if current_user.role != models.UserRole.EXPERT:
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
def trigger_ai_exercise(
    module: str, 
    level: str, 
    expert: Annotated[models.User, Depends(check_is_expert)],
    db: Session = Depends(database.get_db)
):
    # 1. Викаме AI да измисли упражнение
    raw_ai_data = ai_service.generate_exercise_ai(module, level)
    
    # 2. Записваме го в базата като "за одобрение"
    new_exercise = models.Exercise(
        title=f"{module} - {level}",
        content=raw_ai_data,
        cefr_level=level,
        is_approved=False # Важно!
    )
    db.add(new_exercise)
    db.commit()
    db.refresh(new_exercise)
    
    return {"message": "Упражнението е генерирано и чака преглед!", "id": new_exercise.id}

@app.get("/expert/pending", response_model=list[schemas.ExerciseResponse]) # Ще създадем схемата след малко
def list_pending(expert: Annotated[models.User, Depends(check_is_expert)], db: Session = Depends(database.get_db)):
    return crud.get_pending_exercises(db)

@app.put("/expert/approve/{exercise_id}")
def approve(exercise_id: int, expert: Annotated[models.User, Depends(check_is_expert)], db: Session = Depends(database.get_db)):
    exercise = crud.approve_exercise(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнението не е намерено")
    return {"status": "success", "message": f"Упражнение №{exercise_id} е одобрено!"}