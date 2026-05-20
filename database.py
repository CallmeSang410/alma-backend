from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv


load_dotenv()
# 1. LA URL DE CONEXIÓN (La dirección exacta de tu bóveda)
URL_BASE_DATOS = os.getenv("DATABASE_URL")

# 2. EL MOTOR (Engine)
# Es el encargado físico de mantener la conexión abierta con PostgreSQL
engine = create_engine(URL_BASE_DATOS)

# 3. LA FÁBRICA DE SESIONES (SessionLocal)
# Cada vez que alguien entra a la clínica y pide datos, creamos una "sesión" temporal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. LA BASE PARA LOS MODELOS (Base)
# De esta clase van a heredar todas las tablas que creemos (Pacientes, Citas, etc.)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()