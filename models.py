from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Clinica(Base):
    __tablename__ = "clinicas"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    
    # Relaciones
    usuarios = relationship("Usuario", back_populates="clinica")
    pacientes = relationship("Paciente", back_populates="clinica")

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    rol = Column(String) # "admin", "psicologo", "recepcionista"
    
    clinica_id = Column(Integer, ForeignKey("clinicas.id"))
    clinica = relationship("Clinica", back_populates="usuarios")

class Paciente(Base):
    __tablename__ = "pacientes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    telefono = Column(String)
    
    clinica_id = Column(Integer, ForeignKey("clinicas.id"))
    clinica = relationship("Clinica", back_populates="pacientes")
    
    citas = relationship("Cita", back_populates="paciente")

class Cita(Base):
    __tablename__ = "citas"
    id = Column(Integer, primary_key=True, index=True)
    fecha_cita = Column(DateTime, default=datetime.now)
    motivo = Column(String)
    
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))
    paciente = relationship("Paciente", back_populates="citas")
    
    # Relación uno a uno con el reporte
    reporte = relationship("Reporte", back_populates="cita", uselist=False)

class Reporte(Base):
    __tablename__ = "reportes"
    id = Column(Integer, primary_key=True, index=True)
    notas_psicologo = Column(Text)
    analisis_ia = Column(Text, nullable=True)
    fecha_generacion = Column(DateTime, default=datetime.now)
    
    cita_id = Column(Integer, ForeignKey("citas.id"), unique=True)
    cita = relationship("Cita", back_populates="reporte")

class EventoVida(Base):
    __tablename__ = "eventos_vida"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False) # Ej: "Fallecimiento del abuelo"
    fecha_evento = Column(String, nullable=False) # Usamos String para que sea fácil (Ej: "2015" o "2015-05-14")
    descripcion = Column(Text) # Detalles de lo que pasó
    impacto = Column(String) # Ej: "Positivo", "Negativo", "Trauma", "Neutral"
    
    # La llave foránea para saber a qué paciente le pertenece este recuerdo
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))