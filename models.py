from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Clinica(Base):
    __tablename__ = "clinicas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)

    # 🌟 Asegúrate de que apunte exactamente a "clinica" en minúsculas y singular
    pacientes = relationship("Paciente", back_populates="clinica")
    usuarios = relationship("Usuario", back_populates="clinica")

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
    telefono = Column(String, nullable=True)
    email = Column(String, index=True, nullable=True)
    edad = Column(Integer, nullable=True)
    estado = Column(String, nullable=True)
    diagnostico_principal = Column(String, nullable=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"))
    
    # La relación que ya arreglamos antes
    clinica = relationship("Clinica", back_populates="pacientes")
    
    # 🌟 AGREGA ESTA LÍNEA QUE ES LA QUE TE FALTA:
    # Le dice a SQLAlchemy: "Un paciente tiene muchas citas, y en la tabla Cita la propiedad se llama 'paciente'"
    citas = relationship("Cita", back_populates="paciente")
    # (Tus otras columnas y relaciones de Paciente...)
    citas = relationship("Cita", back_populates="paciente")
    
    # 🌟 NUEVO: Para la línea de tiempo de HorizonFlow
    eventos = relationship("EventoVida", back_populates="paciente")
class Cita(Base):
    __tablename__ = "citas"

    id = Column(Integer, primary_key=True, index=True)
    motivo = Column(String)
    fecha_cita = Column(DateTime)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))

    paciente = relationship("Paciente", back_populates="citas")
    
    # 🌟 NUEVO: El espejo que el Reporte estaba buscando
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
    titulo = Column(String, nullable=False)
    fecha_evento = Column(String, nullable=False) 
    descripcion = Column(Text) 
    impacto = Column(String) 
    
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))
    
    # 🌟 NUEVO: El espejo para conectar con el Paciente
    paciente = relationship("Paciente", back_populates="eventos")