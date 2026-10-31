from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, Dict, Any

# 1. El molde base con TODOS los campos
class PacienteBase(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    edad: Optional[int] = None
    estado: Optional[str] = "Activo"
    sexo: Optional[str] = None
    diagnostico_principal: Optional[str] = None

# 2. Lo que exigimos cuando crean/editan uno nuevo
class PacienteCreate(PacienteBase):
    pass


# --- MOLDES PARA CITAS ---

class CitaCreate(BaseModel):
    motivo: str
    fecha_cita: datetime
    estado: str
    modalidad: str
    tarifa: float = 0.0

class CitaOut(BaseModel):
    id: int
    motivo: str
    fecha_cita: datetime
    estado: str
    modalidad: str
    tarifa: float
    paciente_id: int

    model_config = ConfigDict(from_attributes=True)


class PacienteOut(PacienteBase):
    id: int
    folio_visual: Optional[int] = None
    clinica_id: int
    citas: List[CitaOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PacienteParaReporte(BaseModel):
    nombre: str
    edad: Optional[int] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    folio_visual: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ReporteCreate(BaseModel):
    motivo_consulta: str
    notas_psicologo: str
    pruebas_aplicadas: Optional[str] = None
    analisis_ia: Optional[str] = None
    diagnostico_final: Optional[str] = None
    recomendaciones: Optional[str] = None
    plan_accion: Optional[str] = None
    actualizar_diagnostico_paciente: Optional[str] = None


class AnalisisIARequest(BaseModel):
    motivo_consulta: str
    notas_psicologo: str
    pruebas_aplicadas: str
    resultados_pruebas: str
    edad_paciente: str
    sexo_paciente: str


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
    paciente_data: Optional[PacienteParaReporte] = None

    model_config = ConfigDict(from_attributes=True)


# --- MOLDES PARA USUARIOS Y CLÍNICAS ---

class ClinicaCreate(BaseModel):
    nombre: str


class ClinicaOut(BaseModel):
    id: int
    nombre: str
    codigo_invitacion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UsuarioCreate(BaseModel):
    nombre_clinica: Optional[str] = None
    codigo_invitacion: Optional[str] = None
    email: str
    password: str
    rol: str


class UsuarioOut(BaseModel):
    id: int
    email: str
    rol: str
    clinica_id: int

    model_config = ConfigDict(from_attributes=True)


class UsuarioLogin(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str
    modo: Optional[str] = "login"
    nombre_clinica: Optional[str] = None
    tipo_clinica: Optional[str] = "nueva"
    codigo_invitacion: Optional[str] = None
    rol: Optional[str] = "psicologo"


class GoogleLinkRequest(BaseModel):
    credential: str


# --- EVENTOS DE VIDA ---

class EventoVidaCreate(BaseModel):
    titulo: str
    fecha_evento: datetime
    descripcion: str
    impacto: str
    nota_titulo: Optional[str] = None
    nota_contenido: Optional[str] = None


class EventoVidaOut(BaseModel):
    id: int
    titulo: str
    fecha_evento: datetime
    descripcion: str
    impacto: str
    nota_titulo: Optional[str] = None
    nota_contenido: Optional[str] = None
    paciente_id: int

    model_config = ConfigDict(from_attributes=True)


# --- CHATBOT ---

class MensajeChat(BaseModel):
    role: str
    texto: str


class ChatbotRequest(BaseModel):
    historial: List[MensajeChat] = Field(..., min_length=1)


# --- ENCUESTAS ---

class EncuestaCreate(BaseModel):
    q1_satisfaccion_general: int = Field(..., ge=1, le=5)
    q2_cumplimiento_expectativas: str = Field(..., max_length=255)
    q3_empatia_conexion: str = Field(..., max_length=255)
    q4_aspectos_valorados: str = Field(..., max_length=255)
    q5_instalaciones: int = Field(..., ge=1, le=5)
    q6_claridad_pautas: str = Field(..., max_length=255)
    q7_impacto_animo: str = Field(..., max_length=255)
    q8_confianza_seguridad: str = Field(..., max_length=255)
    q9_indice_recomendacion: str = Field(..., max_length=255)
    q10_comentarios: Optional[str] = Field(None, max_length=1000)


class EncuestaOut(EncuestaCreate):
    id: int
    fecha_generacion: datetime
    tipo_comentario: str
    usuario_id: int

    model_config = ConfigDict(from_attributes=True)


class ComentarioFeedback(BaseModel):
    texto: str


class TusStatsDePaciente(BaseModel):
    total: int
    crecimiento_mes: str
    historial: Dict[str, int] = Field(default_factory=dict)


class PerfilUpdate(BaseModel):
    nombre_clinica: str
    password_actual: Optional[str] = None
    password: Optional[str] = None


# --- RECUPERACIÓN DE CONTRASEÑA SEGURA (HF-001) ---

class SolicitarRecuperacionRequest(BaseModel):
    email: str = Field(..., max_length=255)


class ConfirmarRecuperacionRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=128)
    nueva_password: str = Field(..., min_length=8, max_length=72)


class RecuperarPassword(BaseModel):
    email: str
    nueva_password: str
    token: Optional[str] = None
