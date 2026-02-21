from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import database, models, schemas, crud, security

# Създаваме таблиците, ако не съществуват
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="English Learning API",
    description="Backend for the English Learning App",
    version="1.0.0"
)

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