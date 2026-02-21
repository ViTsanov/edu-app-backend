from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import database, models, schemas, crud

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

# --- НОВАТА ЧАСТ ЗА РЕГИСТРАЦИЯ ---
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # 1. Проверяваме дали вече има такъв имейл в базата
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        # Ако има, връщаме грешка (за да няма дублирани профили)
        raise HTTPException(status_code=400, detail="Този имейл вече е регистриран")
    
    # 2. Ако всичко е наред, създаваме потребителя
    return crud.create_user(db=db, user=user)