import os
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Body, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from dotenv import load_dotenv

import google.generativeai as genai
from pysentimiento import create_analyzer

import models, schemas
from database import engine, get_db
from schemas import PerfilUpdate, RecuperarPassword
from models import Paciente, Cita, EncuestaExperiencia, Usuario

# 1. INICIALIZACIÓN GENERAL
load_dotenv()

app = FastAPI()

# 2. CONFIGURACIÓN DE CORS (Una sola vez y bien hecha)
origenes_permitidos = [
    "http://localhost:5173", # La dirección de tu React
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos, 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
    expose_headers=["*"]
)

# 3. CARGA DE MODELOS DE IA
print("Cargando modelo de IA para sentimientos...")
analyzer = create_analyzer(task="sentiment", lang="es")
print("¡Modelo cargado y listo!")

api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("⚠️ ADVERTENCIA: No se encontró GEMINI_API_KEY en el archivo .env")

# 4. SEGURIDAD Y TOKENS
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

# 5. CREACIÓN DE TABLAS
models.Base.metadata.create_all(bind=engine)

# ==========================================
# 🛡️ EL GUARDIA DE SEGURIDAD ÚNICO (CADENERO)
# ==========================================
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id: int = payload.get("usuario_id")
        
        if usuario_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
        
    usuario_db = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    
    if usuario_db is None:
        raise credentials_exception
        
    return usuario_db


# ==========================================
# 🔑 RUTAS DE AUTENTICACIÓN Y PERFIL
# ==========================================
@app.post("/login")
def iniciar_sesion(credenciales: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    usuario_db = db.query(models.Usuario).filter(models.Usuario.username == credenciales.email).first()
    
    if not usuario_db or not pwd_context.verify(credenciales.password, usuario_db.hashed_password):
        raise HTTPException(status_code=401, detail="El correo o la contraseña son incorrectos")
        
    datos_gafete = {
        "usuario_id": usuario_db.id,
        "clinica_id": usuario_db.clinica_id,
        "rol": usuario_db.rol
    }
    
    token_vip = jwt.encode(datos_gafete, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "mensaje": "¡Bienvenido a HorizonFlow!", 
        "tu_gafete_digital": token_vip
    }

@app.put("/usuarios/actualizar")
def actualizar_perfil(
    datos: PerfilUpdate = Body(...), 
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if usuario.clinica:
        usuario.clinica.nombre = datos.nombre_clinica
    
    if datos.password:
        if not datos.password_actual or not pwd_context.verify(datos.password_actual, usuario.hashed_password):
            raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta.")
        
        if len(datos.password) < 8:
            raise HTTPException(status_code=400, detail="La nueva contraseña debe tener mínimo 8 caracteres.")
            
        usuario.hashed_password = get_password_hash(datos.password)
        
    db.commit()
    return {"mensaje": "Perfil actualizado con éxito"}

@app.post("/usuarios/recuperar")
def recuperar_password(datos: RecuperarPassword, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.username == datos.email).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Este correo no está registrado en HorizonFlow.")
    
    if len(datos.nueva_password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")
        
    usuario.hashed_password = get_password_hash(datos.nueva_password)
    db.commit()
    
    return {"mensaje": "Contraseña recuperada exitosamente"}

@app.post("/clinicas", response_model=schemas.ClinicaOut)
def crear_clinica(clinica: schemas.ClinicaCreate, db: Session = Depends(get_db)):
    nueva_clinica = models.Clinica(nombre=clinica.nombre)
    db.add(nueva_clinica)
    db.commit()
    db.refresh(nueva_clinica)
    return nueva_clinica

@app.post("/usuarios")
def crear_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.Usuario).filter(models.Usuario.username == usuario.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")

    hashed_pwd = pwd_context.hash(usuario.password)

    nueva_clinica = models.Clinica(nombre=usuario.nombre_clinica)
    db.add(nueva_clinica)
    db.commit()
    db.refresh(nueva_clinica)

    nuevo_usuario = models.Usuario(
        username=usuario.email, 
        hashed_password=hashed_pwd,
        rol=usuario.rol, 
        clinica_id=nueva_clinica.id, 
        anticipacion_alerta=24 
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return {"mensaje": "Usuario y Clínica creados con éxito"}


# ==========================================
# 👥 RUTAS DE PACIENTES
# ==========================================
@app.post("/pacientes", response_model=schemas.PacienteOut)
def crear_paciente(
    paciente: schemas.PacienteCreate, 
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user) 
):
    nuevo_paciente = models.Paciente(
        nombre=paciente.nombre,
        telefono=paciente.telefono,
        email=paciente.email,
        edad=paciente.edad,
        estado=paciente.estado,
        diagnostico_principal=paciente.diagnostico_principal,
        clinica_id=current_user.clinica_id 
    )
    
    db.add(nuevo_paciente)
    db.commit()
    db.refresh(nuevo_paciente)
    return nuevo_paciente

@app.get("/pacientes", response_model=List[schemas.PacienteOut])
def leer_pacientes(
    db: Session = Depends(get_db), 
    current_user: models.Usuario = Depends(get_current_user) 
):
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id
    ).all()
    return pacientes

@app.get("/pacientes/{paciente_id}", response_model=schemas.PacienteOut)
def buscar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="El paciente no existe en la clínica ALMA")
    return paciente_encontrado

@app.put("/pacientes/{paciente_id}", response_model=schemas.PacienteOut)
def actualizar_paciente(paciente_id: int, paciente_actualizado: schemas.PacienteCreate, db: Session = Depends(get_db)):
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="El paciente no existe")
    
    paciente_encontrado.nombre = paciente_actualizado.nombre
    paciente_encontrado.telefono = paciente_actualizado.telefono
    paciente_encontrado.email = paciente_actualizado.email
    paciente_encontrado.edad = paciente_actualizado.edad
    paciente_encontrado.estado = paciente_actualizado.estado
    paciente_encontrado.sexo = paciente_actualizado.sexo 
    paciente_encontrado.diagnostico_principal = paciente_actualizado.diagnostico_principal
    
    db.commit()
    db.refresh(paciente_encontrado)
    return paciente_encontrado

@app.delete("/pacientes/{paciente_id}")
def eliminar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    if not paciente_encontrado:
        raise HTTPException(status_code=404, detail="El paciente no existe")
    
    try:
        citas_del_paciente = db.query(models.Cita).filter(models.Cita.paciente_id == paciente_id).all()
        
        for cita in citas_del_paciente:
            db.query(models.Reporte).filter(models.Reporte.cita_id == cita.id).delete(synchronize_session=False)
            
        db.query(models.Cita).filter(models.Cita.paciente_id == paciente_id).delete(synchronize_session=False)
        db.query(models.EventoVida).filter(models.EventoVida.paciente_id == paciente_id).delete(synchronize_session=False)
        db.delete(paciente_encontrado)
        
        db.commit()
        return {"mensaje": f"El paciente {paciente_id} y todo su historial fue erradicado."}
        
    except Exception as e:
        db.rollback() 
        print(f"❌ ERROR NUCLEAR AL BORRAR: {e}")
        raise HTTPException(status_code=500, detail="Error interno al borrar las dependencias del paciente.")


# ==========================================
# 📅 RUTAS DE CITAS
# ==========================================
@app.post("/pacientes/{paciente_id}/citas", response_model=schemas.CitaOut)
def crear_cita(paciente_id: int, cita: schemas.CitaCreate, db: Session = Depends(get_db)):
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="No puedes agendarle una cita a un paciente que no existe")

    nueva_cita = models.Cita(
        motivo=cita.motivo,
        fecha_cita=cita.fecha_cita,
        estado=cita.estado,
        modalidad=cita.modalidad, 
        tarifa=cita.tarifa, 
        paciente_id=paciente_id
    )
    
    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)
    return nueva_cita

@app.put("/citas/{cita_id}", response_model=schemas.CitaOut)
def actualizar_cita(cita_id: int, cita_actualizada: schemas.CitaCreate, db: Session = Depends(get_db)):
    cita_encontrada = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    
    cita_encontrada.motivo = cita_actualizada.motivo
    cita_encontrada.fecha_cita = cita_actualizada.fecha_cita
    cita_encontrada.estado = cita_actualizada.estado
    cita_encontrada.modalidad = cita_actualizada.modalidad 
    cita_encontrada.tarifa = cita_actualizada.tarifa 
    
    db.commit()
    db.refresh(cita_encontrada)
    return cita_encontrada

@app.put("/citas/{cita_id}/completar")
def completar_cita(
    cita_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    cita = db.query(models.Cita).join(models.Paciente).filter(
        models.Cita.id == cita_id,
        models.Paciente.clinica_id == current_user.clinica_id
    ).first()

    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada o no autorizada")

    cita.estado = "completada"
    db.commit()
    db.refresh(cita)

    return {
        "status": "success",
        "message": "Cita marcada como completada con éxito",
        "nuevo_estado": cita.estado
    }

@app.delete("/citas/{cita_id}")
def eliminar_cita(cita_id: int, db: Session = Depends(get_db)):
    cita_encontrada = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    
    db.delete(cita_encontrada)
    db.commit()
    return {"mensaje": "La cita fue eliminada exitosamente del calendario"}

@app.get("/citas")
def obtener_citas(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    citas = (
        db.query(models.Cita)
        .join(models.Paciente)
        .filter(models.Paciente.clinica_id == current_user.clinica_id)
        .all()
    )
    return citas


# ==========================================
# ⏳ RUTAS DE EVENTOS (LÍNEA DE TIEMPO)
# ==========================================
@app.post("/pacientes/{paciente_id}/eventos", response_model=schemas.EventoVidaOut)
def crear_evento_vida(paciente_id: int, evento: schemas.EventoVidaCreate, db: Session = Depends(get_db)):
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if not paciente_encontrado:
        raise HTTPException(status_code=404, detail="El paciente no existe")

    nuevo_evento = models.EventoVida(
        titulo=evento.titulo,
        fecha_evento=evento.fecha_evento,
        descripcion=evento.descripcion,
        impacto=evento.impacto,
        nota_titulo=evento.nota_titulo,
        nota_contenido=evento.nota_contenido,
        paciente_id=paciente_id
    )
    
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)
    return nuevo_evento

@app.get("/pacientes/{paciente_id}/eventos", response_model=List[schemas.EventoVidaOut])
def obtener_eventos_paciente(paciente_id: int, db: Session = Depends(get_db)):
    return db.query(models.EventoVida).filter(models.EventoVida.paciente_id == paciente_id).all()

@app.put("/eventos/{evento_id}", response_model=schemas.EventoVidaOut)
def actualizar_evento(evento_id: int, evento_actualizado: schemas.EventoVidaCreate, db: Session = Depends(get_db)):
    evento_db = db.query(models.EventoVida).filter(models.EventoVida.id == evento_id).first()
    if not evento_db:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    
    evento_db.titulo = evento_actualizado.titulo
    evento_db.fecha_evento = evento_actualizado.fecha_evento
    evento_db.descripcion = evento_actualizado.descripcion
    evento_db.impacto = evento_actualizado.impacto
    evento_db.nota_titulo = evento_actualizado.nota_titulo
    evento_db.nota_contenido = evento_actualizado.nota_contenido
    
    db.commit()
    db.refresh(evento_db)
    return evento_db

@app.delete("/eventos/{evento_id}")
def eliminar_evento(evento_id: int, db: Session = Depends(get_db)):
    evento_db = db.query(models.EventoVida).filter(models.EventoVida.id == evento_id).first()
    if not evento_db:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(evento_db)
    db.commit()
    return {"detail": "Evento eliminado de forma definitiva"}


# ==========================================
# 📄 RUTAS DE REPORTES E IA
# ==========================================
@app.get("/reportes", response_model=List[schemas.ReporteOut])
def obtener_todos_los_reportes(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    db_reportes = (
        db.query(models.Reporte)
        .join(models.Cita)
        .join(models.Paciente)
        .filter(models.Paciente.clinica_id == current_user.clinica_id)
        .all()
    )

    respuesta = []
    for reporte in db_reportes:
        cita = db.query(models.Cita).filter(models.Cita.id == reporte.cita_id).first()
        paciente = None
        if cita:
            paciente = db.query(models.Paciente).filter(models.Paciente.id == cita.paciente_id).first()
        
        rep_dict = {
            "id": reporte.id,
            "motivo_consulta": reporte.motivo_consulta,
            "notas_psicologo": reporte.notas_psicologo,
            "pruebas_aplicadas": reporte.pruebas_aplicadas,
            "resultados_pruebas": getattr(reporte, 'resultados_pruebas', ""), 
            "analisis_ia": reporte.analisis_ia,
            "diagnostico_final": reporte.diagnostico_final,
            "recomendaciones": reporte.recomendaciones,
            "plan_accion": reporte.plan_accion,
            "fecha_generacion": reporte.fecha_generacion,
            "cita_id": reporte.cita_id,
            "paciente_data": paciente 
        }
        respuesta.append(rep_dict)

    return respuesta

@app.post("/reportes/analizar")
def generar_analisis_ia(datos: schemas.AnalisisIARequest):
    prompt_maestro = f"""
    Actúa como un neuropsicólogo clínico senior y supervisor de casos con 20 años de experiencia. Tu tarea es analizar las notas iniciales de una sesión y redactar un análisis técnico-profesional de alto nivel para ayudar al clínico a formular su diagnóstico.

    CONTEXTO CLÍNICO PROPORCIONADO (NO LO REPITAS EN TU RESPUESTA):
    - Edad: {datos.edad_paciente}
    - Sexo biológico: {datos.sexo_paciente}
    - Motivo de Consulta: {datos.motivo_consulta}
    - INSTRUMENTOS Y TÉCNICAS APLICADAS: {datos.pruebas_aplicadas or 'Entrevista clínica semiestructurada'}
    - RESULTADOS CUANTITATIVOS/PUNTAJES: {datos.resultados_pruebas or 'No se proporcionaron puntajes exactos.'}
    - NOTAS CRUDAS DE LA SESIÓN: "{datos.notas_psicologo}"

   REGLAS ESTRICTAS DE REDACCIÓN:
    1. CERO REDUNDANCIA (PROHIBIDO EL EFECTO LORO): NO inicies diciendo la edad del paciente.
    2. DIRECTO A LA INTERPRETACIÓN: Ve directamente a la significancia clínica. 
    3. DIAGNÓSTICO DIFERENCIAL OBLIGATORIO: Debes plantear condiciones médicas a descartar.
    4. NO SUGIERAS TRATAMIENTOS: Limítate a la impresión clínica.
    5. FORMATO: Usa **negritas** para resaltar síntomas clave. DEBES insertar un DOBLE SALTO DE LÍNEA después de cada título (##).
    6. RIGOR DIAGNÓSTICO (DSM-5-TR y CIE-10): Al plantear las hipótesis diagnósticas, DEBES incluir obligatoriamente el código de la APA (DSM) y su equivalente internacional CIE-10 entre paréntesis. Ejemplo: "Trastorno de desregulación destructiva del estado de ánimo, 296.99 (F34.8)".

    ESTRUCTURA DE SALIDA EXACTA (Deben ser exactamente estas 3 secciones):
    ## 🔍 Interpretación Clínica y Sintomatológica
    ## ⚖️ Diagnóstico Diferencial (Descartes necesarios)
    ## 🧠 Hipótesis Diagnósticas (Códigos DSM-5-TR y CIE-10)
    """

    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        respuesta_ia = model.generate_content(prompt_maestro)
        return {"analisis": respuesta_ia.text}
        
    except Exception as e:
        print(f"❌ Error en Gemini (Reportes): {e}")
        raise HTTPException(status_code=500, detail="Error interno al procesar el análisis de IA")

@app.post("/citas/{cita_id}/reporte", response_model=schemas.ReporteOut)
def crear_reporte_session(cita_id: int, reporte: schemas.ReporteCreate, db: Session = Depends(get_db)):
    cita_encontrada = db.query(models.Cita).options(
        joinedload(models.Cita.paciente)
    ).filter(models.Cita.id == cita_id).first()
    
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    reporte_existente = db.query(models.Reporte).filter(models.Reporte.cita_id == cita_id).first()
    if reporte_existente:
        raise HTTPException(status_code=400, detail="Esta cita ya tiene un reporte")

    # 🌟 MODO THANOS: Si el frontend mandó la orden del switch, actualizamos el perfil del paciente
    if reporte.actualizar_diagnostico_paciente:
        if cita_encontrada.paciente:
            cita_encontrada.paciente.diagnostico_principal = reporte.actualizar_diagnostico_paciente

    # Armamos el nuevo reporte para guardarlo en el historial
    nuevo_reporte = models.Reporte(
        motivo_consulta=reporte.motivo_consulta,
        notas_psicologo=reporte.notas_psicologo,
        pruebas_aplicadas=reporte.pruebas_aplicadas,
        analisis_ia=reporte.analisis_ia, 
        diagnostico_final=reporte.diagnostico_final,
        recomendaciones=reporte.recomendaciones,
        plan_accion=reporte.plan_accion,
        cita_id=cita_id
    )

    db.add(nuevo_reporte)
    # Al hacer commit, SQLAlchemy guarda el reporte Y actualiza al paciente al mismo tiempo 😎
    db.commit()
    db.refresh(nuevo_reporte)
    
    nuevo_reporte.paciente_data = cita_encontrada.paciente
    return nuevo_reporte


# ==========================================
# 📊 RUTAS DE DASHBOARD Y MÉTRICAS
# ==========================================
@app.get("/citas/alertas-activas")
def obtener_alertas_activas(
    horas: int = Query(24), 
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user) 
):
    ahora = datetime.now()
    limite_alerta = ahora + timedelta(hours=horas)
    
    citas_criticas = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id, 
        models.Cita.fecha_cita >= ahora,
        models.Cita.fecha_cita <= limite_alerta,
        models.Cita.estado == "Pendiente"
    ).all()
    
    respuesta = []
    for cita in citas_criticas:
        paciente_db = db.query(models.Paciente).filter(models.Paciente.id == cita.paciente_id).first()
        cita_dict = {
            "id": cita.id,
            "fecha_cita": cita.fecha_cita,
            "motivo_consulta": cita.motivo or "Consulta Programada", 
            "modalidad": cita.modalidad or "No especificada",
            "paciente": {
                "nombre": paciente_db.nombre if paciente_db else "Paciente Desconocido"
            }
        }
        respuesta.append(cita_dict)
        
    return respuesta

@app.get("/dashboard/pacientes-activos")
def obtener_pacientes_activos(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id
    ).all()

    hoy = datetime.now()
    mes_actual = hoy.month
    anio_actual = hoy.year

    mes_pasado = 12 if mes_actual == 1 else mes_actual - 1
    anio_pasado = anio_actual - 1 if mes_actual == 1 else anio_actual

    nuevos_este_mes = 0
    nuevos_mes_pasado = 0
    historial_mensual = {}

    for paciente in pacientes:
        primera_cita = db.query(models.Cita).filter(
            models.Cita.paciente_id == paciente.id,
            models.Cita.fecha_cita != None
        ).order_by(models.Cita.fecha_cita.asc()).first()

        if not primera_cita:
            continue
            
        fecha = primera_cita.fecha_cita
        
        if fecha.year == anio_actual and fecha.month == mes_actual:
            nuevos_este_mes += 1
        elif fecha.year == anio_pasado and fecha.month == mes_pasado:
            nuevos_mes_pasado += 1
            
        llave_mes = fecha.strftime("%m-%Y") 
        historial_mensual[llave_mes] = historial_mensual.get(llave_mes, 0) + 1

    if nuevos_mes_pasado == 0:
        porcentaje_str = "+100%" if nuevos_este_mes > 0 else "0%"
    else:
        crecimiento = ((nuevos_este_mes - nuevos_mes_pasado) / nuevos_mes_pasado) * 100
        if crecimiento > 0:
            porcentaje_str = f"+{round(crecimiento)}%"
        elif crecimiento < 0:
            porcentaje_str = f"{round(crecimiento)}%" 
        else:
            porcentaje_str = "0%"

    return {
        "total": len(pacientes), 
        "crecimiento_mes": porcentaje_str,
        "historial": historial_mensual 
    }

@app.get("/dashboard/expedientes-pendientes")
def obtener_expedientes_pendientes(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    ahora = datetime.now()
    limite_24h = ahora - timedelta(hours=24)
    
    citas_vulnerables = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id,
        models.Cita.fecha_cita <= limite_24h,
        models.Cita.estado == "completada" 
    ).filter(
        ~models.Cita.id.in_(db.query(models.Reporte.cita_id))
    ).all()
    
    lista_pendientes = []
    for cita in citas_vulnerables:
        lista_pendientes.append({
            "cita_id": cita.id,
            "paciente_id": cita.paciente_id,
            "paciente_nombre": cita.paciente.nombre if cita.paciente else "Paciente Desconocido",
            "fecha": cita.fecha_cita.strftime("%Y-%m-%d") if cita.fecha_cita else "",
            "motivo": cita.motivo
        })
    
    return {
        "cantidad_pendientes": len(lista_pendientes), 
        "detalles": lista_pendientes                  
    }
    
@app.get("/dashboard/agenda-hoy")
def obtener_agenda_hoy(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    citas_hoy = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id,
        models.Cita.fecha_cita >= hoy_inicio,
        models.Cita.fecha_cita <= hoy_fin,
        models.Cita.estado.notin_(["Cancelada", "cancelada"]) 
    ).order_by(models.Cita.fecha_cita.asc()).all()

    agenda = []
    ahora = datetime.now()

    for cita in citas_hoy:
        estado_visual = cita.estado.lower()
        if estado_visual in ["pendiente", "reservada"] and cita.fecha_cita <= ahora:
            estado_visual = "en_curso"

        agenda.append({
            "id": cita.id,
            "hora": cita.fecha_cita.strftime("%I:%M %p"), 
            "paciente": cita.paciente.nombre if cita.paciente else "Desconocido",
            "tipo": cita.motivo,
            "estado": estado_visual,
            "duracion": "60 min" 
        })

    return agenda

@app.get("/pacientes/{paciente_id}/historial-sesiones")
def obtener_historial_sesiones(paciente_id: int, db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    paciente = db.query(models.Paciente).filter(
        models.Paciente.id == paciente_id,
        models.Paciente.clinica_id == current_user.clinica_id
    ).first()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado o no autorizado")

    citas = db.query(models.Cita).filter(
        models.Cita.paciente_id == paciente_id
    ).order_by(models.Cita.fecha_cita.desc()).all()

    historial = []
    for cita in citas:
        historial.append({
            "cita_id": cita.id,
            "fecha": cita.fecha_cita.strftime("%Y-%m-%d") if cita.fecha_cita else "Sin fecha",
            "hora": cita.fecha_cita.strftime("%I:%M %p") if cita.fecha_cita else "",
            "motivo": cita.motivo,
            "estado": cita.estado.lower(), 
            "modalidad": cita.modalidad,
            "tiene_reporte": cita.reporte is not None,
            "reporte_id": cita.reporte.id if cita.reporte else None
        })

    return historial

@app.get("/estadisticas/motivos-distribucion")
def obtener_distribucion_motivos(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    total_citas = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id, 
        models.Cita.motivo != None
    ).count()

    if total_citas == 0:
        return [] 

    resultados = db.query(
        models.Cita.motivo,
        func.count(models.Cita.id).label('cantidad')
    ).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id, 
        models.Cita.motivo != None
    ).group_by(models.Cita.motivo).order_by(func.count(models.Cita.id).desc()).limit(4).all() 

    distribucion = []
    for motivo, cantidad in resultados:
        porcentaje = round((cantidad / total_citas) * 100)
        distribucion.append({
            "motivo": motivo,
            "porcentaje": porcentaje
        })

    return distribucion

@app.get("/dashboard/alertas-inactividad")
def obtener_alertas_inactividad(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id
    ).all()

    alertas = []
    hoy = datetime.now()

    for paciente in pacientes:
        ultima_cita = db.query(models.Cita).filter(
            models.Cita.paciente_id == paciente.id,
            models.Cita.fecha_cita <= hoy
        ).order_by(models.Cita.fecha_cita.desc()).first()

        cita_futura = db.query(models.Cita).filter(
            models.Cita.paciente_id == paciente.id,
            models.Cita.fecha_cita > hoy
        ).first()

        if ultima_cita and not cita_futura:
            dias_inactivos = (hoy - ultima_cita.fecha_cita).days
            
            if dias_inactivos >= 30:
                if dias_inactivos >= 60:
                    color, bg = "text-rose-600", "bg-rose-50"      
                elif dias_inactivos >= 45:
                    color, bg = "text-amber-600", "bg-amber-50"    
                else:
                    color, bg = "text-slate-500", "bg-slate-100"   

                alertas.append({
                    "id": paciente.id,
                    "name": f"{paciente.nombre}", 
                    "ultimaCita": f"Hace {dias_inactivos} días",
                    "dias": dias_inactivos, 
                    "color": color,
                    "bg": bg
                })

    alertas.sort(key=lambda x: x["dias"], reverse=True)
    return alertas

@app.get("/dashboard/metricas-negocio")
def obtener_metricas_negocio(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    hoy = datetime.now()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    mes_pasado = 12 if mes_actual == 1 else mes_actual - 1
    anio_pasado = anio_actual - 1 if mes_actual == 1 else anio_actual

    citas_validas = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id,
        models.Cita.estado != "Cancelada"
    ).all()

    ingresos_actual = 0.0
    ingresos_pasado = 0.0
    pacientes_con_citas = {}
    citas_completadas = 0

    for cita in citas_validas:
        tarifa_real = cita.tarifa or 0.0

        if cita.fecha_cita.month == mes_actual and cita.fecha_cita.year == anio_actual:
            ingresos_actual += tarifa_real
        elif cita.fecha_cita.month == mes_pasado and cita.fecha_cita.year == anio_pasado:
            ingresos_pasado += tarifa_real

        pacientes_con_citas[cita.paciente_id] = pacientes_con_citas.get(cita.paciente_id, 0) + 1

        if cita.estado.lower() == "completada":
            citas_completadas += 1

    if ingresos_pasado == 0:
        crecimiento_ingresos = "+100%" if ingresos_actual > 0 else "0%"
    else:
        porcentaje = ((ingresos_actual - ingresos_pasado) / ingresos_pasado) * 100
        crecimiento_ingresos = f"+{round(porcentaje)}%" if porcentaje >= 0 else f"{round(porcentaje)}%"

    total_pacientes_vistos = len(pacientes_con_citas)
    pacientes_recurrentes = sum(1 for cantidad in pacientes_con_citas.values() if cantidad > 1)
    
    tasa_retencion = 0
    if total_pacientes_vistos > 0:
        tasa_retencion = round((pacientes_recurrentes / total_pacientes_vistos) * 100)

    minutos_ahorrados = citas_completadas * 15
    horas_ahorradas = round(minutos_ahorrados / 60, 1)

    return {
        "ingresos": {
            "monto": f"${ingresos_actual:,.2f}", 
            "crecimiento": crecimiento_ingresos
        },
        "retencion": f"{tasa_retencion}%",
        "horas_ahorradas": horas_ahorradas
    }


# ==========================================
# 💬 RUTAS DE CHATBOT Y ENCUESTAS
# ==========================================
@app.post("/soporte/chat")
def chat_soporte_alma(request: schemas.ChatbotRequest):
    instrucciones = """
    Eres ALMA, el Asistente Virtual Inteligente de Soporte Técnico de 'HorizonFlow'. 
    HorizonFlow es un avanzado software SaaS de gestión clínica, diseñado estratégicamente para psicólogos profesionales y estudiantes de psicología en prácticas.

    TU OBJETIVO: 
    Ayudar a los usuarios a navegar por la plataforma, resolver sus dudas sobre la interfaz y explicarles a detalle cómo funciona cada herramienta del sistema.

    FUNCIONES Y MÓDULOS DEL SISTEMA QUE DEBES DOMINAR:

    1. GESTIÓN DE PACIENTES Y CALENDARIO:
    - Crear Pacientes: Los usuarios pueden registrar nuevos pacientes llenando su perfil básico (nombre, contacto, edad, sexo).
    - Agendar Citas: Se realiza desde el calendario seleccionando paciente, fecha, hora y motivo.
    - Calendario: Permite agendar, visualizar y gestionar todas las citas clínicas de manera organizada.

    2. DASHBOARD Y ALERTAS:
    - Agenda del Día: El dashboard principal muestra un resumen rápido de las citas programadas para el día actual.
    - Alertas: El sistema notifica sobre citas próximas, pacientes inactivos o tareas pendientes para mantener al profesional organizado.
    - Campana: Es el centro de control de eventos. Notifica en tiempo real sobre citas próximas, recordatorios de tareas, alertas de pacientes con riesgo de abandono (inactividad) y mensajes del sistema.

    3. MÉTRICAS DE SALUD DEL NEGOCIO Y ESTADÍSTICAS:
    - Distribución de Motivos: Un gráfico que muestra cuáles son los problemas más frecuentes por los que asisten los pacientes (ej. Ansiedad, Depresión), ayudando al psicólogo a entender su nicho de mercado.
    - Días de Inactividad: Calcula cuántos días han pasado desde la última sesión de un paciente. Sirve para alertar sobre posible abandono del tratamiento y fomentar la retención.
    - Salud del Negocio: Índice ponderado que se calcula como: (Pacientes Activos / Total de Pacientes) * 100, ajustado por la frecuencia de retención de sesiones. Un porcentaje alto indica una clínica con flujo saludable y pacientes constantes.

    4. REPORTES CLÍNICOS E INTELIGENCIA ARTIFICIAL:
    - Reportes con IA: La plataforma cruza las notas de entrevista y pruebas (BDI-II, GAD-7, etc.) para generar un borrador de análisis clínico fundamentado en el DSM-5.
    - Modo Manual: El usuario puede saltarse la IA ("Guardar Solo Notas") para redactar su propio análisis clínico.
    - Seguimientos y Revaluación: Para pacientes recurrentes, el sistema oculta el diagnóstico final. Si el psicólogo necesita corregir un diagnóstico pasado, usa el "Switch de Ajuste/Revaluación" para actualizar el perfil del paciente sin dañar el historial.
    - Exportación: Se generan reportes en PDF y Word, etiquetados con un Folio único por paciente (Ej. CD-0001).

    5. EXPERIENCIA Y GAMIFICACIÓN:
    - Sistema de Experiencia (XP): Diseñado especialmente para estudiantes y nuevos profesionales. Los usuarios ganan puntos de experiencia al completar reportes, agendar citas y mantener la clínica activa. Sirve para incentivar la constancia y las buenas prácticas de documentación clínica.

    6. CONFIGURACIÓN Y SEGURIDAD:
    - Ajustes: Área para personalizar el perfil del profesional y preferencias del sistema.
    - Cambio de Contraseña: Se realiza desde los ajustes de seguridad, solicitando la contraseña actual y la nueva para proteger la confidencialidad de los datos médicos.

    REGLAS DE TU COMPORTAMIENTO:
    - ERES SOPORTE TÉCNICO DE SOFTWARE, NO PSICÓLOGO. NUNCA des consejos médicos, diagnósticos, ni opiniones sobre pacientes.
    - Si un usuario pregunta cómo tratar un caso, recuérdale que tu función es enseñarle a usar las herramientas de HorizonFlow para documentarlo.
    - Responde de forma profesional, clara, empática y MUY concisa.
    - Usa listas numeradas (1, 2, 3) o viñetas para explicar pasos.
    """

    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=instrucciones
        )
        
        historial_gemini = []
        for msg in request.historial[1:-1]:
            historial_gemini.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.texto]
            })

        ultimo_mensaje = request.historial[-1].texto

        respuesta_ia = model.generate_content(
            contents=historial_gemini + [{"role": "user", "parts": [ultimo_mensaje]}]
        )

        return {"respuesta": respuesta_ia.text}

    except Exception as e:
        print(f"❌ Error en Chatbot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/encuestas/publica/{psicologo_id}")
def crear_encuesta_publica(psicologo_id: int, encuesta: schemas.EncuestaCreate, db: Session = Depends(get_db)):
    tipo_com = "NEUTRO"
    
    if encuesta.q10_comentarios and encuesta.q10_comentarios.strip() != "":
        resultado = analyzer.predict(encuesta.q10_comentarios)
        
        if resultado.output == "POS":
            if encuesta.q1_satisfaccion_general <= 3:
                tipo_com = "NEGATIVO" 
            else:
                tipo_com = "POSITIVO"
        elif resultado.output == "NEG":
            tipo_com = "NEGATIVO"
        else:
            tipo_com = "NEUTRO"

    nueva_encuesta = models.EncuestaExperiencia(
        **encuesta.dict(),
        tipo_comentario=tipo_com,
        usuario_id=psicologo_id
    )
    
    db.add(nueva_encuesta)
    db.commit()
    return {"mensaje": "Feedback anónimo evaluado con IA y guardado con éxito"}

@app.get("/encuestas", response_model=List[schemas.EncuestaOut])
def obtener_encuestas(db: Session = Depends(get_db), current_user: models.Usuario = Depends(get_current_user)):
    encuestas = db.query(models.EncuestaExperiencia).filter(models.EncuestaExperiencia.usuario_id == current_user.id).all()
    return encuestas