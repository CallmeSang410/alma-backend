from pydantic import BaseModel
from datetime import datetime # <-- NUEVO: Importamos el manejador de tiempo
from typing import List, Optional

# --- MOLDES DE PACIENTE (Estos ya los tenías) ---
class PacienteCreate(BaseModel):
    nombre: str
    telefono: str
    # ¡Importante! Aquí NO va el clinica_id. 
    # El usuario no lo envía, nosotros lo pondremos en secreto.

class PacienteOut(BaseModel):
    id: int
    nombre: str
    telefono: str
    clinica_id: int # Aquí sí va, porque se lo mostramos de regreso
    
    class Config:
        from_attributes = True

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
        
# 2. DESPUÉS EL MOLDE DE SALIDA DEL PACIENTE
class PacienteOut(BaseModel):
    id: int
    nombre: str
    telefono: str
    # --- LA MAGIA: Le agregamos el historial de citas ---
    citas: List[CitaOut] = [] 

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
    username: str
    password: str # El usuario manda texto plano
    rol: str = "psicologo"
    clinica_id: int

class UsuarioOut(BaseModel):
    id: int
    username: str
    rol: str
    clinica_id: int
    class Config:
        from_attributes = True
        
class UsuarioLogin(BaseModel):
    username: str
    password: str
    
class RespuestaIA(BaseModel):
    resumen_paciente: str
    analisis_evolucion: str
    sugerencias_clinicas: List[str]
    pruebas_sugeridas: List[str]