from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# ВАЖНО: Смени "your_password" с реалната парола за твоя postgres!
# Форматът е: postgresql://потребител:парола@сървър:порт/име_на_базата
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://postgres:Azsumtarikat123-@localhost:5432/english_learning_db"

# Създаваме "двигателя" за връзка с базата
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Създаваме сесия, през която ще четем и пишем данни
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базов клас, от който ще наследяват всички наши таблици (Users, Exercises и т.н.)
Base = declarative_base()

# Функция, която създава и затваря връзката към базата за всяка заявка
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()