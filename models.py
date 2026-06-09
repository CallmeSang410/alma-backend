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
    anticipacion_alerta = Column(Integer, default=24) # Guardará 24, 48 o 72
    encuestas = relationship("EncuestaExperiencia", back_populates="usuario")

class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    telefono = Column(String, nullable=True)
    email = Column(String, index=True, nullable=True)
    edad = Column(Integer, nullable=True)
    sexo = Column(String, nullable=True) # 🌟 NUEVO: Para guardar el dato del frontend
    estado = Column(String, nullable=True)
    diagnostico_principal = Column(String, nullable=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"))
    
    clinica = relationship("Clinica", back_populates="pacientes")
    
    # 🌟 MODO THANOS: cascade="all, delete-orphan" elimina todas las citas al borrar al paciente
    citas = relationship("Cita", back_populates="paciente", cascade="all, delete-orphan")
    
    # 🌟 MODO THANOS: También elimina sus eventos de la línea de tiempo
    eventos = relationship("EventoVida", back_populates="paciente", cascade="all, delete-orphan")

class Cita(Base):
    __tablename__ = "citas"

    id = Column(Integer, primary_key=True, index=True)
    motivo = Column(String)
    fecha_cita = Column(DateTime)
    
    estado = Column(String, default="Pendiente") 
    modalidad = Column(String, default="Presencial") # 🌟 NUEVO: Virtual, Presencial, etc.
    
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))

    paciente = relationship("Paciente", back_populates="citas")
    # 🌟 MODO THANOS: Si se borra la cita, también se borra el reporte asociado
    reporte = relationship("Reporte", back_populates="cita", uselist=False, cascade="all, delete-orphan")

class Reporte(Base):
    __tablename__ = "reportes"
    id = Column(Integer, primary_key=True, index=True)
    
    # Datos de entrada (Pasos 1 y 2)
    motivo_consulta = Column(Text, nullable=True) 
    notas_psicologo = Column(Text)
    pruebas_aplicadas = Column(String, nullable=True) # Ej: "GAD-7, BDI-II"
    
    # La magia de Gemini (Paso 3)
    analisis_ia = Column(Text, nullable=True)
    
    # Cierre profesional (Paso 4)
    diagnostico_final = Column(String, nullable=True)
    recomendaciones = Column(Text, nullable=True)
    plan_accion = Column(String, nullable=True) # Ej: "Tratamiento Terapéutico"
    
    fecha_generacion = Column(DateTime, default=datetime.now)
    
    cita_id = Column(Integer, ForeignKey("citas.id"), unique=True)
    cita = relationship("Cita", back_populates="reporte")

class EventoVida(Base):
    __tablename__ = "eventos_vida"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    fecha_evento = Column(String, nullable=False) 
    descripcion = Column(Text, nullable=True) # Tu descripción original intacta
    impacto = Column(String) 
    
    # 🌟 NUEVAS COLUMNAS EXCLUSIVAS PARA LA BURBUJA
    nota_titulo = Column(String, nullable=True) 
    nota_contenido = Column(Text, nullable=True)
    
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))
    paciente = relationship("Paciente", back_populates="eventos")

class EncuestaExperiencia(Base):
    __tablename__ = "encuestas_experiencia"

    id = Column(Integer, primary_key=True, index=True)
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    
    # --- LAS 10 PREGUNTAS DEL DASHBOARD ---
    q1_satisfaccion_general = Column(Integer) # 1 a 5 estrellas
    q2_cumplimiento_expectativas = Column(String) # "Superó ampliamente", etc.
    q3_empatia_conexion = Column(String) # "Sí, en todo momento", etc.
    q4_aspectos_valorados = Column(String) # "Escucha activa", "Puntualidad" (puede ser texto separado por comas)
    q5_instalaciones = Column(Integer) # 1 a 5 estrellas
    q6_claridad_pautas = Column(String) # "Totalmente claras", etc.
    q7_impacto_animo = Column(String) # "Mucho mejor", etc.
    q8_confianza_seguridad = Column(String) # "Completamente seguro", etc.
    q9_indice_recomendacion = Column(String) # "Definitivamente", etc.
    q10_comentarios = Column(Text, nullable=True) # "Me sentí muy seguro..."
    clasificacion_ia = Column(String(20), nullable=True) # Aquí guardás "NEGATIVO", "POSITIVO" o "NEUTRO"
    # Análisis de sentimiento (Positivo, Negativo, Sugerencia)
    tipo_comentario = Column(String, default="NEUTRO") 

    # --- RELACIONES ---
    # ¿A qué psicólogo le hicieron esta encuesta?
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario", back_populates="encuestas")
