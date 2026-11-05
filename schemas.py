import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime # <-- NUEVO: Importamos el manejador de tiempo
from typing import List, Optional, Dict, Any

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TELEFONO_REGEX = re.compile(r"^\+?[0-9\s\-().]{6,25}$")

# 1. El molde base con TODOS los campos
class PacienteBase(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    edad: Optional[int] = None
    estado: Optional[str] = "Activo"
    sexo: Optional[str] = None # 🌟 Tiene que estar aquí para que lo acepte
    diagnostico_principal: Optional[str] = None

# 2. Lo que exigimos cuando crean/editan uno nuevo (Validaciones CP-05, CP-06 y CP-07)
class PacienteCreate(PacienteBase):
    nombre: str = Field(..., min_length=1, max_length=150)
    edad: Optional[int] = Field(default=None, ge=0, le=120)

    @field_validator("nombre")
    @classmethod
    def validar_nombre_no_vacio(cls, v: str) -> str:
        limpio = v.strip()
        if not limpio:
            raise ValueError("El nombre del paciente es obligatorio y no puede estar vacío.")
        return limpio

    @field_validator("telefono")
    @classmethod
    def validar_formato_telefono(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpio = v.strip()
        if not limpio:
            return None
        solo_digitos = re.sub(r"\D", "", limpio)
        if not TELEFONO_REGEX.match(limpio) or len(solo_digitos) < 6 or len(solo_digitos) > 15:
            raise ValueError("El número telefónico debe contener solo números y tener entre 6 y 15 dígitos (ej. +505 8888-8888).")
        return limpio

    @field_validator("email")
    @classmethod
    def validar_formato_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpio = v.strip()
        if not limpio:
            return None
        if not EMAIL_REGEX.match(limpio):
            raise ValueError("El formato del correo electrónico no es válido.")
        return limpio


# --- NUEVOS MOLDES PARA CITAS ---

# Molde de ENTRADA (Lo que React nos manda al guardar)
class CitaCreate(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=250)
    fecha_cita: datetime
    estado: str = Field(..., min_length=1, max_length=50)
    modalidad: str = Field(..., min_length=1, max_length=50)
    tarifa: float = Field(default=0.0, ge=0.0) # 🌟 ¡NUEVO CAMPO FINANCIERO! (Default para que no explote y sin negativos)

    @field_validator("motivo", "estado", "modalidad")
    @classmethod
    def validar_campos_cita_no_vacios(cls, v: str) -> str:
        limpio = v.strip()
        if not limpio:
            raise ValueError("Los campos de motivo, estado y modalidad de la cita son obligatorios.")
        return limpio

# Molde de SALIDA (Lo que le devolvemos a React para pintar las tarjetas)
class CitaOut(BaseModel):
    id: int
    motivo: str
    fecha_cita: datetime
    estado: str
    modalidad: str
    tarifa: float # 🌟 ¡Para que el dashboard pueda sumar los ingresos!
    paciente_id: int

    class Config:
        from_attributes = True

# 🌟 EL MOLDE DE SALIDA DEFINITIVO Y CORRECTO:
class PacienteOut(PacienteBase):
    id: int
    folio_visual: Optional[int] = None  # 🌟 ¡NUEVO! El pase VIP para que React lo vea
    clinica_id: int
    citas: List[CitaOut] = Field(default_factory=list)

    class Config:
        from_attributes = True

# --- Agregá este molde nuevo arriba en schemas.py ---
class PacienteParaReporte(BaseModel):
    nombre: str
    edad: Optional[int] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    folio_visual: Optional[int] = None  # 🌟 ¡NUEVO! Para que el PDF de Word también tenga el folio correcto

    class Config:
        from_attributes = True

# Molde de Entrada (Lo que el frontend envía para guardar el reporte)
class ReporteCreate(BaseModel):
    motivo_consulta: str = Field(..., min_length=1)
    notas_psicologo: str = Field(..., min_length=1)
    pruebas_aplicadas: Optional[str] = None

    # 🌟 AHORA TODO ESTO ES OPCIONAL (Para permitir el guardado rápido)
    analisis_ia: Optional[str] = None
    diagnostico_final: Optional[str] = None
    recomendaciones: Optional[str] = None
    plan_accion: Optional[str] = None

    # 🌟 NUEVO: El campo espía que nos dice si hay que actualizar al paciente
    actualizar_diagnostico_paciente: Optional[str] = None

    @field_validator("motivo_consulta", "notas_psicologo")
    @classmethod
    def validar_reporte_no_vacio(cls, v: str) -> str:
        limpio = v.strip()
        if not limpio:
            raise ValueError("El motivo de consulta y las notas clínicas son obligatorios.")
        return limpio

class AnalisisIARequest(BaseModel):
    motivo_consulta: str = Field(..., min_length=1)
    notas_psicologo: str = Field(..., min_length=1)
    pruebas_aplicadas: str
    resultados_pruebas: str  # 🌟 Asegurate de tener esto
    # 🌟 LAS DOS LÍNEAS QUE EVITAN EL ERROR 422:
    edad_paciente: str
    sexo_paciente: str


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
    nombre: str = Field(..., min_length=1, max_length=150)

class ClinicaOut(BaseModel):
    id: int
    nombre: str
    codigo_invitacion: Optional[str] = None
    class Config:
        from_attributes = True

class UsuarioCreate(BaseModel):
    nombre_clinica: Optional[str] = None
    codigo_invitacion: Optional[str] = None
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    rol: str  # Le quitamos el = "psicologo" para que obligue a React a mandar el rol real


class UsuarioOut(BaseModel):
    id: int
    email: str
    rol: str
    clinica_id: int
    class Config:
        from_attributes = True

class UsuarioLogin(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=10)
    modo: Optional[str] = "login"  # "login" | "signup"
    tipo_clinica: Optional[str] = "nueva"  # "nueva" | "existente"
    nombre_clinica: Optional[str] = None
    codigo_invitacion: Optional[str] = None
    rol: Optional[str] = "psicologo"
    password: Optional[str] = None


class GoogleLinkRequest(BaseModel):
    credential: str = Field(..., min_length=10)


# Molde para cuando el psicólogo CREA un evento nuevo
class EventoVidaCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    fecha_evento: str = Field(..., min_length=1)
    descripcion: Optional[str] = None
    impacto: str = Field(..., min_length=1)
    nota_titulo: Optional[str] = None      # 🌟 NUEVO
    nota_contenido: Optional[str] = None   # 🌟 NUEVO

    @field_validator("titulo", "fecha_evento", "impacto")
    @classmethod
    def validar_evento_no_vacio(cls, v: str) -> str:
        limpio = v.strip()
        if not limpio:
            raise ValueError("El título, la fecha y el impacto del evento son obligatorios.")
        return limpio


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


class MensajeChat(BaseModel):
    role: str = Field(..., min_length=1)
    texto: str = Field(..., min_length=1)

class ChatbotRequest(BaseModel):
    historial: List[MensajeChat] = Field(..., min_length=1)

# Cuando el paciente manda la encuesta
class EncuestaCreate(BaseModel):
    q1_satisfaccion_general: int = Field(..., ge=1, le=5)
    q2_cumplimiento_expectativas: str = Field(..., min_length=1)
    q3_empatia_conexion: str = Field(..., min_length=1)
    q4_aspectos_valorados: str = Field(..., min_length=1)
    q5_instalaciones: int = Field(..., ge=1, le=5)
    q6_claridad_pautas: str = Field(..., min_length=1)
    q7_impacto_animo: str = Field(..., min_length=1)
    q8_confianza_seguridad: str = Field(..., min_length=1)
    q9_indice_recomendacion: str = Field(..., min_length=1)
    q10_comentarios: Optional[str] = None


# Cuando React pide las encuestas (con todos los datos)
class EncuestaOut(EncuestaCreate):
    id: int
    fecha_generacion: datetime
    tipo_comentario: str
    usuario_id: int

    class Config:
        from_attributes = True

class ComentarioFeedback(BaseModel):
    texto: str = Field(..., min_length=1)


class TusStatsDePaciente(BaseModel): # Como sea que se llame tu clase
    total: int
    crecimiento_mes: str
    historial: Dict[str, int] = Field(default_factory=dict) # 🌟 EL PASE VIP PARA QUE LLEGUE A REACT

class PerfilUpdate(BaseModel):
    nombre_clinica: str
    password_actual: Optional[str] = None # 🌟 Recibimos la vieja
    password: Optional[str] = None

class RecuperarPassword(BaseModel):
    email: str = Field(..., min_length=1)
    nueva_password: str = Field(..., min_length=8)
