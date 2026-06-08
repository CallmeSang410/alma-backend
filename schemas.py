from pydantic import BaseModel
from datetime import datetime # <-- NUEVO: Importamos el manejador de tiempo
from typing import List, Optional

# 1. El molde base con TODOS los campos
class PacienteBase(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    edad: Optional[int] = None
    estado: Optional[str] = "Activo"
    sexo: Optional[str] = None # 🌟 Tiene que estar aquí para que lo acepte
    diagnostico_principal: Optional[str] = None

# 2. Lo que exigimos cuando crean/editan uno nuevo
class PacienteCreate(PacienteBase):
    pass


# --- NUEVOS MOLDES PARA CITAS ---

# Molde de ENTRADA (Lo que React nos manda al guardar)
class CitaCreate(BaseModel):
    motivo: str
    fecha_cita: datetime 
    estado: str
    modalidad: str # 🌟 ¡NUEVO CAMPO: Presencial, Virtual, A domicilio!

# Molde de SALIDA (Lo que le devolvemos a React para pintar las tarjetas)
class CitaOut(BaseModel):
    id: int
    motivo: str
    fecha_cita: datetime
    estado: str
    modalidad: str # 🌟 ¡NUEVO CAMPO!
    paciente_id: int

    class Config:
        from_attributes = True
        
# 🌟 EL MOLDE DE SALIDA DEFINITIVO Y CORRECTO:
class PacienteOut(PacienteBase): # <-- IMPORTANTE: Ahora sí hereda de PacienteBase
    id: int
    clinica_id: int              # <-- Conservamos el ID de la clínica para el SaaS
    citas: List[CitaOut] = []    # <-- Conservamos el historial de citas jalado de la BD

    class Config:
        from_attributes = True

# Molde de Entrada (Lo que el frontend envía al final del Paso 4)
class ReporteCreate(BaseModel):
    motivo_consulta: str
    notas_psicologo: str
    pruebas_aplicadas: Optional[str] = None
    analisis_ia: str # 🌟 AÑADÍ ESTO: Ahora React nos manda el análisis
    diagnostico_final: str
    recomendaciones: str
    plan_accion: str

class AnalisisIARequest(BaseModel):
    motivo_consulta: str
    notas_psicologo: str
    pruebas_aplicadas: str

# --- Agregá este molde nuevo arriba en schemas.py ---
class PacienteParaReporte(BaseModel):
    nombre: str
    edad: Optional[int] = None
    telefono: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True

# Molde de Salida (Lo que devolvemos)
class ReporteOut(BaseModel):
    id: int
    motivo_consulta: Optional[str] = None
    notas_psicologo: str
    pruebas_aplicadas: Optional[str] = None
    analisis_ia: Optional[str] = None
    diagnostico_final: Optional[str] = None
    recomendaciones: Optional[str] = None
    plan_accion: Optional[str] = None
    fecha_generacion: datetime
    cita_id: int
    
    # 🌟 LA GAVETA MÁGICA: Aquí vendrán los datos del paciente unidos
    paciente_data: Optional[PacienteParaReporte] = None 

    class Config:
        from_attributes = True
        
# --- MOLDES PARA USUARIOS Y CLÍNICAS ---

class ClinicaCreate(BaseModel):
    nombre: str

class ClinicaOut(BaseModel):
    id: int
    nombre: str
    class Config:
        from_attributes = True

class UsuarioCreate(BaseModel):
    nombre_clinica: str  
    email: str
    password: str
    rol: str  # Le quitamos el = "psicologo" para que obligue a React a mandar el rol real


class UsuarioOut(BaseModel):
    id: int
    email: str
    rol: str
    clinica_id: int
    class Config:
        from_attributes = True
        
class UsuarioLogin(BaseModel):
    email: str
    password: str
    
    
# Molde para cuando el psicólogo CREA un evento nuevo
class EventoVidaCreate(BaseModel):
    titulo: str
    fecha_evento: str
    descripcion: Optional[str] = None
    impacto: str
    nota_titulo: Optional[str] = None      # 🌟 NUEVO
    nota_contenido: Optional[str] = None   # 🌟 NUEVO
    

class EventoVidaOut(BaseModel):
    id: int
    titulo: str
    fecha_evento: str
    descripcion: Optional[str] = None
    impacto: str
    nota_titulo: Optional[str] = None      # 🌟 NUEVO
    nota_contenido: Optional[str] = None   # 🌟 NUEVO
    paciente_id: int

    class Config:
        from_attributes = True

from typing import List

class MensajeChat(BaseModel):
    role: str
    texto: str

class ChatbotRequest(BaseModel):
    historial: List[MensajeChat]
    
# Cuando el paciente manda la encuesta
class EncuestaCreate(BaseModel):
    q1_satisfaccion_general: int
    q2_cumplimiento_expectativas: str
    q3_empatia_conexion: str
    q4_aspectos_valorados: str
    q5_instalaciones: int
    q6_claridad_pautas: str
    q7_impacto_animo: str
    q8_confianza_seguridad: str
    q9_indice_recomendacion: str
    q10_comentarios: Optional[str] = None
    cita_id: Optional[int] = None

# Cuando React pide las encuestas (con todos los datos)
class EncuestaOut(EncuestaCreate):
    id: int
    fecha_generacion: datetime
    tipo_comentario: str
    usuario_id: int

    class Config:
        orm_mode = True