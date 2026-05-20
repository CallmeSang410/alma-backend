from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 1. LA URL DE CONEXIÓN (La dirección exacta de tu bóveda)
# Formato: postgresql://usuario:contraseña@servidor:puerto/nombre_bd
# OJO: Cambia "TU_CONTRASEÑA" por la contraseña real que usaste en pgAdmin
URL_BASE_DATOS = "postgresql://postgres:zombiditoz7@localhost:5432/alma_db"

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