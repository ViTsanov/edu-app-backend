from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import database
import models  # ВАЖНО: Импортираме новия файл с моделите

# Тази команда автоматично създава таблиците в базата данни, ако не съществуват
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