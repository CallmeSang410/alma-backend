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
    diagnostico_principal: Optional[str] = None

# 2. Lo que exigimos cuando crean/editan uno nuevo
class PacienteCreate(PacienteBase):
    pass


# --- NUEVOS MOLDES PARA CITAS ---

# Molde de ENTRADA (Lo que pedimos en internet para crear una cita)
class CitaCreate(BaseModel):
    motivo: str
    fecha_cita: datetime # Pydantic exigirá un formato de fecha válido

# Molde de SALIDA (Lo que devolvemos después de guardar)
class CitaOut(BaseModel):
    id: int
    motivo: str
    fecha_cita: datetime
    paciente_id: int # Devolvemos de quién es la cita para estar seguros

    class Config:
        from_attributes = True
        
# 🌟 EL MOLDE DE SALIDA DEFINITIVO Y CORRECTO:
class PacienteOut(PacienteBase): # <-- IMPORTANTE: Ahora sí hereda de PacienteBase
    id: int
    clinica_id: int              # <-- Conservamos el ID de la clínica para el SaaS
    citas: List[CitaOut] = []    # <-- Conservamos el historial de citas jalado de la BD

    class Config:
        from_attributes = True
# Molde para crear el reporte (lo que recibimos del psicólogo)
class ReporteCreate(BaseModel):
    notas_psicologo: str

# Molde para mostrar el reporte (lo que devolvemos)
class ReporteOut(BaseModel):
    id: int
    notas_psicologo: str
    analisis_ia: Optional[str] = None
    fecha_generacion: datetime
    cita_id: int

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
    email: str
    password: str # El usuario manda texto plano
    rol: str = "psicologo"


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
    
class RespuestaIA(BaseModel):
    resumen_paciente: str
    analisis_evolucion: str
    sugerencias_clinicas: List[str]
    pruebas_sugeridas: List[str]
    
# Molde para cuando el psicólogo CREA un evento nuevo
class EventoVidaCreate(BaseModel):
    titulo: str
    fecha_evento: str
    descripcion: str
    impacto: str

# Molde para cuando le ENVIAMOS los eventos a Dervin (React)
class EventoVidaOut(BaseModel):
    id: int
    titulo: str
    fecha_evento: str
    descripcion: str
    impacto: str
    paciente_id: int

    class Config:
        from_attributes = True