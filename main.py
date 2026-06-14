from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import List
import models, schemas
from database import engine, get_db
import bcrypt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from test_ia import analizar_notas_con_ia
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware # <-- Asegurate de importar esto
from datetime import datetime, timedelta
from fastapi import Query
import google.generativeai as genai
from pysentimiento import create_analyzer

app = FastAPI()

# 🌟 ESTA ES LA PUERTA ABIERTA PARA REACT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir peticiones desde cualquier lugar (en desarrollo)
    allow_credentials=True,
    allow_methods=["*"], # Permitir GET, POST, PUT, DELETE, etc.
    allow_headers=["*"], # Permitir todos los headers (incluyendo tu Token)
    expose_headers=["*"]

)


load_dotenv() # Esto lee tu archivo .env
print("Cargando modelo de IA para sentimientos...")
analyzer = create_analyzer(task="sentiment", lang="es")
print("¡Modelo cargado y listo!")



api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    print("⚠️ ADVERTENCIA: No se encontró GEMINI_API_KEY en el archivo .env")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")


# Esto le dice a FastAPI que busque el token en el Header de "Authorization"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Encendemos el motor de encriptación para las contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Creamos las tablas si no existen
# 💥 LA BOMBA ATÓMICA: Borra todo y lo vuelve a crear con los planos nuevos
models.Base.metadata.create_all(bind=engine)


app = FastAPI()
# Lista de direcciones a las que les damos permiso
origenes_permitidos = [
    "http://localhost:5173", # La dirección de tu React de Vite
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos los headers (incluyendo nuestro Token)
)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Abrimos el gafete digital que mandó React usando tu llave secreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 2. Extraemos la variable EXACTA que pusiste en tu login
        usuario_id: int = payload.get("usuario_id")
        
        if usuario_id is None:
            raise credentials_exception
            
    except JWTError:
        # Si el token es falso o expiró, lo pateamos
        raise credentials_exception
        
    # 3. Buscamos al usuario en la BD usando su ID
    usuario_db = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    
    if usuario_db is None:
        raise credentials_exception
        
    # 4. Devolvemos el perfil completo del psicólogo que está usando el sistema
    return usuario_db




# --- NUEVA VENTANILLA: OBTENER UN PACIENTE ESPECÍFICO ---
# Fíjate en el {paciente_id}. Las llaves le dicen a FastAPI: "Esto no es texto fijo, es una variable que el usuario va a escribir".
@app.get("/pacientes/{paciente_id}", response_model=schemas.PacienteOut)
def buscar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    
    # Le decimos a SQLAlchemy: "Busca en la tabla Paciente, filtra donde el ID coincida con el número que nos pasaron, y dame el primero que encuentres (.first())"
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    # Si la base de datos no encontró nada, paciente_encontrado estará vacío (None).
    # En ese caso, levantamos el muro y le mandamos un error 404 al frontend.
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="El paciente no existe en la clínica ALMA")
    
    # Si sí lo encontró, se lo devolvemos.
    return paciente_encontrado

# --- NUEVA VENTANILLA: ACTUALIZAR UN PACIENTE ---
# Usamos @app.put porque vamos a modificar algo que ya existe.
# Pedimos el {paciente_id} en la URL para saber a quién modificar.
@app.put("/pacientes/{paciente_id}", response_model=schemas.PacienteOut)
def actualizar_paciente(paciente_id: int, paciente_actualizado: schemas.PacienteCreate, db: Session = Depends(get_db)):
    
    # 1. Buscamos al paciente
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="El paciente no existe")
    
    # 2. 🌟 ACTUALIZAMOS ABSOLUTAMENTE TODOS LOS CAMPOS 🌟
    paciente_encontrado.nombre = paciente_actualizado.nombre
    paciente_encontrado.telefono = paciente_actualizado.telefono
    paciente_encontrado.email = paciente_actualizado.email
    paciente_encontrado.edad = paciente_actualizado.edad
    paciente_encontrado.estado = paciente_actualizado.estado
    paciente_encontrado.sexo = paciente_actualizado.sexo # 🌟 AGREGÁ ESTA LÍNEA AQUÍ
    paciente_encontrado.diagnostico_principal = paciente_actualizado.diagnostico_principal
    
    # 3. Guardamos los cambios
    db.commit()
    db.refresh(paciente_encontrado)
    
    return paciente_encontrado

# --- NUEVA VENTANILLA: ELIMINAR UN PACIENTE ---
# Usamos @app.delete porque la acción es destructiva.
@app.delete("/pacientes/{paciente_id}")
def eliminar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    # 1. Buscamos al paciente
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    if not paciente_encontrado:
        raise HTTPException(status_code=404, detail="El paciente no existe")
    
    try:
        # 2. Buscamos todas las citas de este paciente
        citas_del_paciente = db.query(models.Cita).filter(models.Cita.paciente_id == paciente_id).all()
        
        # 3. Borramos los REPORTES de esas citas primero (Las hojas del árbol)
        for cita in citas_del_paciente:
            db.query(models.Reporte).filter(models.Reporte.cita_id == cita.id).delete(synchronize_session=False)
            
        # 4. Ahora sí, borramos las CITAS (Las ramas)
        db.query(models.Cita).filter(models.Cita.paciente_id == paciente_id).delete(synchronize_session=False)
        
        # 5. Borramos los EVENTOS de la línea de tiempo
        db.query(models.EventoVida).filter(models.EventoVida.paciente_id == paciente_id).delete(synchronize_session=False)
        
        # 6. Finalmente, libre de amarras, borramos al PACIENTE (El tronco)
        db.delete(paciente_encontrado)
        
        # Guardamos todos los cambios de un solo
        db.commit()
        return {"mensaje": f"El paciente {paciente_id} y todo su historial fue erradicado."}
        
    except Exception as e:
        db.rollback() # Si algo falla, cancelamos todo para no dañar la BD
        print(f"❌ ERROR NUCLEAR AL BORRAR: {e}")
        raise HTTPException(status_code=500, detail="Error interno al borrar las dependencias del paciente.")

# --- VENTANILLA 1: AGENDAR UNA CITA ---
@app.post("/pacientes/{paciente_id}/citas", response_model=schemas.CitaOut)
def crear_cita(paciente_id: int, cita: schemas.CitaCreate, db: Session = Depends(get_db)):
    
    # 1. Verificamos que el paciente exista
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="No puedes agendarle una cita a un paciente que no existe")

    # 2. Creamos la cita conectándola con el paciente
    nueva_cita = models.Cita(
        motivo=cita.motivo,
        fecha_cita=cita.fecha_cita,
        estado=cita.estado,
        modalidad=cita.modalidad, 
        tarifa=cita.tarifa, # 🌟 AQUÍ ATRAPAMOS EL BILLETE
        paciente_id=paciente_id
    )
    
    # 3. La guardamos en la bóveda
    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)
    
    return nueva_cita


# --- VENTANILLA 2: ACTUALIZAR UNA CITA (Para cuando le den al botón Editar) ---
@app.put("/citas/{cita_id}", response_model=schemas.CitaOut)
def actualizar_cita(cita_id: int, cita_actualizada: schemas.CitaCreate, db: Session = Depends(get_db)):
    
    # 1. Buscamos la cita exacta
    cita_encontrada = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    
    # 2. Reemplazamos todos los datos con lo que mandó React
    cita_encontrada.motivo = cita_actualizada.motivo
    cita_encontrada.fecha_cita = cita_actualizada.fecha_cita
    cita_encontrada.estado = cita_actualizada.estado
    cita_encontrada.modalidad = cita_actualizada.modalidad 
    cita_encontrada.tarifa = cita_actualizada.tarifa # 🌟 ACTUALIZAMOS LA TARIFA SI HUBO CAMBIOS
    
    # 3. Guardamos los cambios
    db.commit()
    db.refresh(cita_encontrada)
    
    return cita_encontrada

@app.put("/citas/{cita_id}/completar")
def completar_cita(
    cita_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # 🔍 Buscamos la cita asegurando el candado de seguridad de tu clínica
    cita = db.query(models.Cita).join(models.Paciente).filter(
        models.Cita.id == cita_id,
        models.Paciente.clinica_id == current_user.clinica_id
    ).first()

    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada o no autorizada")

    # 🔄 Hacemos el update del estado
    cita.estado = "completada"
    db.commit()
    db.refresh(cita)

    return {
        "status": "success",
        "message": "Cita marcada como completada con éxito",
        "nuevo_estado": cita.estado
    }

# --- VENTANILLA 3: ELIMINAR UNA CITA (Para cuando le den a la X roja) ---
@app.delete("/citas/{cita_id}")
def eliminar_cita(cita_id: int, db: Session = Depends(get_db)):
    
    cita_encontrada = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    
    db.delete(cita_encontrada)
    db.commit()
    
    return {"mensaje": "La cita fue eliminada exitosamente del calendario"}

# Importá get_current_user si no lo tenés en este bloque
# from dependencias import get_current_user

@app.get("/citas/alertas-activas")
def obtener_alertas_activas(
    horas: int = Query(24), 
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user) # 🛡️ Candado activo
):
    ahora = datetime.now()
    limite_alerta = ahora + timedelta(hours=horas)
    
    # 🌟 CORRECCIÓN: Unimos la tabla Cita con Paciente usando .join()
    # Así podemos filtrar usando el usuario_id que vive dentro de Paciente
    citas_criticas = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id, # 🛡️ Candado Multi-tenant seguro
        models.Cita.fecha_cita >= ahora,
        models.Cita.fecha_cita <= limite_alerta,
        models.Cita.estado == "Pendiente"
    ).all()
    
    respuesta = []
    
    for cita in citas_criticas:
        # Aquí ya tenés la lógica de mapeo igualita a la de antes
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

@app.get("/citas")
def obtener_citas(
    db: Session = Depends(get_db), 
    current_user: models.Usuario = Depends(get_current_user) # 🌟 Exigimos el usuario logueado
):
    # Filtramos: Solo dame las citas donde el dueño del paciente sea el psicólogo actual
    citas = (
        db.query(models.Cita)
        .join(models.Paciente)
        .filter(models.Paciente.clinica_id == current_user.clinica_id)
        .all()
    )
    return citas
@app.get("/reportes", response_model=List[schemas.ReporteOut])
def obtener_todos_los_reportes(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user) # 🛡️ Candado
):
    # 1. Filtramos los reportes desde la BD usando los joins
    db_reportes = (
        db.query(models.Reporte)
        .join(models.Cita)
        .join(models.Paciente)
        .filter(models.Paciente.clinica_id == current_user.clinica_id)
        .all()
    )

    respuesta = []
    
    # 2. Armamos la maleta a mano con TU código original para ir a lo seguro
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
            # 🌟 AQUÍ ATRAPAMOS EL NUEVO CAMPO PARA EL DASHBOARD
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


# 🌟 RUTA NUEVA: SE EJECUTA EN EL PASO 3 DE REACT

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

    REGLAS ESTRICTAS DE REDACCIÓN (SI LAS ROMPES, EL REPORTE SERÁ RECHAZADO):
    1. CERO REDUNDANCIA (PROHIBIDO EL EFECTO LORO): NO inicies diciendo la edad del paciente, ni resumas el motivo de consulta, ni repitas los puntajes numéricos de las pruebas de forma descriptiva. Asume que el terapeuta ya conoce estos datos.
    2. DIRECTO A LA INTERPRETACIÓN: Ve directamente a la significancia clínica. ¿Qué significa la combinación de esos síntomas y resultados en el funcionamiento neurobiológico y psicológico del paciente?
    3. DIAGNÓSTICO DIFERENCIAL OBLIGATORIO: Debes plantear qué condiciones médicas, orgánicas (endocrinas, neurológicas, deficiencias vitamínicas) o trastornos comórbidos se deben descartar antes de dar un diagnóstico definitivo.
    4. NO SUGIERAS TRATAMIENTOS: Limítate a la impresión clínica. La intervención es tarea del usuario.
    5. FORMATO: Usa **negritas** para resaltar síntomas clave o síndromes. DEBES insertar un DOBLE SALTO DE LÍNEA después de cada título (##).
    6. RIGOR DIAGNÓSTICO (ESTRICTO DSM-5-TR): Utiliza la nomenclatura actualizada del DSM-5-TR, no de manuales anteriores. Si no tienes absoluta certeza del código alfanumérico exacto de un trastorno, proporciona ÚNICAMENTE el nombre clínico y omite el código. Jamás inventes códigos.

    ESTRUCTURA DE SALIDA EXACTA (Deben ser exactamente estas 3 secciones):

    ## 🔍 Interpretación Clínica y Sintomatológica
    
    (Análisis clínico profundo y directo del estado mental y emocional, cruzando observaciones con la significancia de los instrumentos).

    ## ⚖️ Diagnóstico Diferencial (Descartes necesarios)
    
    (Lista de condiciones médicas, orgánicas o trastornos paralelos que el terapeuta debe descartar obligatoriamente basándose en el cuadro clínico y la edad).

    ## 🧠 Hipótesis Diagnósticas (DSM-5-TR)
    
    (Sugiere las hipótesis diagnósticas principales con su código DSM-5, justificando clínicamente por qué aplican al caso).
    """

    try:
        # 1. Configuración a la vieja escuela
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        
        # 2. Inicializamos el modelo de IA
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 3. Mandamos el prompt a la cocina
        respuesta_ia = model.generate_content(prompt_maestro)
        
        # 4. Devolvemos el texto a React
        return {"analisis": respuesta_ia.text}
        
    except Exception as e:
        print(f"❌ Error en Gemini (Reportes): {e}")
        raise HTTPException(status_code=500, detail="Error interno al procesar el análisis de IA")


# 🌟 RUTA ACTUALIZADA: SE EJECUTA EN EL PASO 4 (Solo guarda los datos)
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

    # Ya no llamamos a Gemini aquí. Usamos el texto que generamos en el paso 3 y que React nos envió.
    nuevo_reporte = models.Reporte(
        motivo_consulta=reporte.motivo_consulta,
        notas_psicologo=reporte.notas_psicologo,
        pruebas_aplicadas=reporte.pruebas_aplicadas,
        analisis_ia=reporte.analisis_ia, # 🌟 Guardamos directamente lo que vino de React
        diagnostico_final=reporte.diagnostico_final,
        recomendaciones=reporte.recomendaciones,
        plan_accion=reporte.plan_accion,
        cita_id=cita_id
    )

    db.add(nuevo_reporte)
    db.commit()
    db.refresh(nuevo_reporte)
    
    nuevo_reporte.paciente_data = cita_encontrada.paciente
    return nuevo_reporte

# Ventanilla para crear la Clínica
@app.post("/clinicas", response_model=schemas.ClinicaOut)
def crear_clinica(clinica: schemas.ClinicaCreate, db: Session = Depends(get_db)):
    nueva_clinica = models.Clinica(nombre=clinica.nombre)
    db.add(nueva_clinica)
    db.commit()
    db.refresh(nueva_clinica)
    return nueva_clinica

# Ventanilla para crear el Usuario (Psicólogo)
# No olvides importar la librería de hash si no la tienes: 
# from passlib.context import CryptContext
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.post("/usuarios")
def crear_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    
    # 1. Verificamos si el correo ya existe
    db_user = db.query(models.Usuario).filter(models.Usuario.username == usuario.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")

    # 2. Encriptamos la contraseña (¡NUNCA la guardes en texto plano!)
    hashed_pwd = pwd_context.hash(usuario.password)

    # 3. 🌟 PRIMERO: Creamos la clínica con el nombre que mandó el usuario en el form
    nueva_clinica = models.Clinica(nombre=usuario.nombre_clinica)
    db.add(nueva_clinica)
    db.commit()
    db.refresh(nueva_clinica) # Esto hace que la BD le asigne su ID oficial (ej. 1, 2, 3...)

    # 4. DESPUÉS: Armamos al usuario amarrándolo a la clínica recién creada
    nuevo_usuario = models.Usuario(
        username=usuario.email, 
        hashed_password=hashed_pwd,
        rol=usuario.rol, # Usamos el rol que seleccionó en la pantalla
        clinica_id=nueva_clinica.id, # 🌟 AQUÍ ESTÁ EL TRUCO: Usamos el ID real de arriba
        anticipacion_alerta=24 # Asegurate de que tu modelo Usuario tenga este campo
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return {"mensaje": "Usuario y Clínica creados con éxito"}

# Este es el Cadenero Oficial de ALMA
def obtener_usuario_actual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    print("\n========================================")
    print("       🕵️‍♂️ REVISANDO GAFETE DE SEGURIDAD")
    print("========================================")
    
    try:
        # Abrimos con la llave oficial del .env
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Extraemos el ID del usuario, no el "sub"
        user_id = payload.get("usuario_id") 
        
        if user_id is None:
            raise credentials_exception
            
    except Exception as e:
        print(f"❌ ERROR AL ABRIR EL TOKEN: {e}")
        raise credentials_exception
        
    # Buscamos en PostgreSQL por ID
    usuario = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    
    if usuario is None:
        raise credentials_exception
        
    print("✅ Gafete Válido. Acceso Permitido.")
    print("========================================\n")
    return usuario

@app.post("/pacientes", response_model=schemas.PacienteOut)
def crear_paciente(
    paciente: schemas.PacienteCreate, 
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(obtener_usuario_actual) # <-- ¡Regresa el guardia de seguridad!
):
    
    nuevo_paciente = models.Paciente(
        nombre=paciente.nombre,
        telefono=paciente.telefono,
        email=paciente.email,
        edad=paciente.edad,
        estado=paciente.estado,
        diagnostico_principal=paciente.diagnostico_principal,
        # ¡MAGIA SAAS! El paciente se asigna automáticamente a la clínica del doctor logueado
        clinica_id=usuario_actual.clinica_id 
    )
    
    db.add(nuevo_paciente)
    db.commit()
    db.refresh(nuevo_paciente)
    
    return nuevo_paciente

@app.get("/pacientes", response_model=List[schemas.PacienteOut])
def leer_pacientes(
    db: Session = Depends(get_db), 
    usuario_actual: models.Usuario = Depends(obtener_usuario_actual) 
):
    # Usamos .clinica_id (con punto) porque es un objeto de BD, no un diccionario
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == usuario_actual.clinica_id
    ).all()
    
    return pacientes

# --- VENTANILLA: AGREGAR UN EVENTO A LA LÍNEA DE TIEMPO ---
@app.post("/pacientes/{paciente_id}/eventos", response_model=schemas.EventoVidaOut)
def crear_evento_vida(paciente_id: int, evento: schemas.EventoVidaCreate, db: Session = Depends(get_db)):
    # 1. Verificamos que el paciente exista
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if not paciente_encontrado:
        raise HTTPException(status_code=404, detail="El paciente no existe")

    # 2. Creamos el evento conectándolo con el paciente
    nuevo_evento = models.EventoVida(
        titulo=evento.titulo,
        fecha_evento=evento.fecha_evento,
        descripcion=evento.descripcion,
        impacto=evento.impacto,
        paciente_id=paciente_id
    )
    
    # 3. Lo guardamos
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)
    
    return nuevo_evento


# 🌟 OBTENER TODOS LOS EVENTOS DE UN PACIENTE
@app.get("/pacientes/{paciente_id}/eventos", response_model=List[schemas.EventoVidaOut])
def obtener_eventos_paciente(paciente_id: int, db: Session = Depends(get_db)):
    return db.query(models.EventoVida).filter(models.EventoVida.paciente_id == paciente_id).all()

# 🌟 CREAR UN NUEVO EVENTO
@app.post("/pacientes/{paciente_id}/eventos", response_model=schemas.EventoVidaOut)
def crear_evento_paciente(paciente_id: int, evento: schemas.EventoVidaCreate, db: Session = Depends(get_db)):
    nuevo_evento = models.EventoVida(**evento.dict(), paciente_id=paciente_id)
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)
    return nuevo_evento

@app.put("/eventos/{evento_id}", response_model=schemas.EventoVidaOut)
def actualizar_evento(evento_id: int, evento_actualizado: schemas.EventoVidaCreate, db: Session = Depends(get_db)):
    evento_db = db.query(models.EventoVida).filter(models.EventoVida.id == evento_id).first()
    if not evento_db:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    
    evento_db.titulo = evento_actualizado.titulo
    evento_db.fecha_evento = evento_actualizado.fecha_evento
    evento_db.descripcion = evento_actualizado.descripcion
    evento_db.impacto = evento_actualizado.impacto
    
    # 🌟 GUARDAMOS LAS NOTAS
    evento_db.nota_titulo = evento_actualizado.nota_titulo
    evento_db.nota_contenido = evento_actualizado.nota_contenido
    
    db.commit()
    db.refresh(evento_db)
    return evento_db

# 🌟 ELIMINAR UN EVENTO
@app.delete("/eventos/{evento_id}")
def eliminar_evento(evento_id: int, db: Session = Depends(get_db)):
    evento_db = db.query(models.EventoVida).filter(models.EventoVida.id == evento_id).first()
    if not evento_db:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(evento_db)
    db.commit()
    return {"detail": "Evento eliminado de forma definitiva"}

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
    
    # EL ARREGLO: Usamos la SECRET_KEY global, no el SECRETO_ALMA viejo
    token_vip = jwt.encode(datos_gafete, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "mensaje": "¡Bienvenido a HorizonFlow!", 
        "tu_gafete_digital": token_vip
    }
    

# 🌟 LA VENTANILLA ÚNICA DEL CHATBOT DE SOPORTE HORIZONFLOW
@app.post("/soporte/chat")
def chat_soporte_alma(request: schemas.ChatbotRequest):
    instrucciones = """
    Eres el Asistente Virtual de 'HorizonFlow', un sistema SaaS de gestión clínica. Tu objetivo es dar soporte técnico sobre el uso del software.

    REGLAS ESTRICTAS DE COMPORTAMIENTO:
    1. Ve DIRECTO al grano. Responde ÚNICAMENTE la pregunta específica que hace el usuario.
    2. PROHIBIDO mencionar módulos, funciones o pantallas por las que el usuario no ha preguntado explícitamente.
    3. Usa explicaciones técnicas pero fáciles de entender. Usa listas si es necesario.

    CÁLCULO DE MÉTRICAS (SALUD DEL CONSULTORIO):
    Si el usuario pregunta cómo funcionan o cómo se calculan las métricas del negocio, explícale la lógica interna:
    - Ingresos Estimados (Mes): Se calcula sumando automáticamente la 'Tarifa ($)' que el psicólogo ingresa al crear cada cita, filtrando solo las del mes actual.
    - Tasa de Retención: Mide la fidelidad. Se calcula obteniendo el porcentaje de pacientes del directorio que han llegado a agendar una segunda sesión (o más) frente a los que abandonaron tras la primera.
    - Horas Ahorradas con IA: El sistema estima que redactar un análisis clínico manual toma 15 minutos. El cálculo multiplica la cantidad de expedientes generados con Gemini por 15 minutos, y convierte ese total en horas de trabajo administrativo ahorrado.

    BASE DE DATOS DE OTROS MÓDULOS (Solo úsala si te preguntan específicamente por ellos):
    - Alertas de Inactividad: El sistema detecta y alerta si un paciente activo lleva más de 30 días sin agendar cita.
    - Distribución de Motivos: Gráficos de barra que muestran el porcentaje de los motivos de consulta más frecuentes del mes.
    - Análisis de Experiencia: Módulo para enviar encuestas a pacientes y medir la 'Satisfacción Global' (sobre 5 estrellas) y el 'Índice Promotores' (NPS).

    BASE DE CONOCIMIENTO DE HORIZONFLOW:

    1. GESTIÓN DE PACIENTES Y ALERTAS:
    - Directorio y Búsqueda: Buscador Inteligente que filtra en tiempo real por nombre o teléfono.
    - Alertas de Inactividad: El sistema detecta y notifica automáticamente en el Dashboard si un paciente tiene más de 30 días sin agendar una cita.

    2. AGENDA, NOTIFICACIONES Y FINANZAS:
    - Campana de Alertas: Arriba a la derecha hay una campana que muestra las 'Próximas Citas' con una cuenta regresiva exacta (ej. 'Faltan 23h 15m').
    - Finanzas: Cada cita exige ingresar una tarifa ($), lo que alimenta el módulo de 'Salud del Consultorio' en el Dashboard.

    3. WIZARD DE EVALUACIÓN CLÍNICA (CON IA):
    - Es un proceso de 4 pasos. El Paso 1 vincula la cita y el motivo. El Paso 2 recopila notas e instrumentos.
    - Memoria Inteligente (Chips): Si el psicólogo usa un instrumento o acción recurrente (ej. 'Inventario de Beck'), el sistema lo guarda como un botón de autocompletado rápido para futuras sesiones.
    - El Paso 3 usa Inteligencia Artificial para redactar el Análisis Clínico y sugerir ejes diagnósticos (CIE-11/DSM-5).
    - Exportar a PDF: El reporte final se puede exportar en alta calidad, con membrete oficial y espacio para firmas.

    4. DASHBOARD Y SALUD DEL CONSULTORIO:
    - Es el panel de control principal. Muestra: 'Pacientes Activos', 'Expedientes por Actualizar' y la 'Agenda del Día' (línea de tiempo).
    - Salud del Consultorio: Mide KPIs vitales de negocio: 'Ingresos Estimados' del mes, 'Tasa de Retención' de pacientes y 'Horas Ahorradas con IA'.
    - Distribución de Motivos: Gráficos que muestran cuáles son los diagnósticos o motivos de consulta más frecuentes en la clínica.

    5. MÓDULO DE ANÁLISIS DE EXPERIENCIA (NUEVO):
    - Permite al psicólogo medir la calidad de su servicio mediante encuestas enviadas a los pacientes (Botón 'Compartir Encuesta').
    - Muestra KPIs como 'Satisfacción Global' (sobre 5 estrellas) y el 'Índice Promotores' (NPS).
    - Desglosa métricas pregunta por pregunta: Cumplimiento de expectativas, empatía, instalaciones, etc.
    """

    try:
        # 1. Configuramos la llave (Estilo clásico)
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        
        # 2. Inicializamos el modelo con la personalidad de soporte
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=instrucciones
        )
        
        # 3. Formateamos la memoria del chat (ignoramos el saludo inicial)
        historial_gemini = []
        for msg in request.historial[1:-1]:
            historial_gemini.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.texto]
            })

        # 4. Agarramos la pregunta nuevecita del usuario
        ultimo_mensaje = request.historial[-1].texto

        # 5. Generamos la respuesta con todo el contexto
        respuesta_ia = model.generate_content(
            contents=historial_gemini + [{"role": "user", "parts": [ultimo_mensaje]}]
        )

        # 6. Se lo devolvemos a React
        return {"respuesta": respuesta_ia.text}

    except Exception as e:
        print(f"❌ Error en Chatbot: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# 1. RUTA PARA GUARDAR UNA ENCUESTA NUEVA
# 🌟 RUTA PÚBLICA (Sin el candado de current_user)
@app.post("/encuestas/publica/{psicologo_id}")
def crear_encuesta_publica(
    psicologo_id: int, 
    encuesta: schemas.EncuestaCreate, 
    db: Session = Depends(get_db)
):
    tipo_com = "NEUTRO"
    
    # 2. Evaluamos el texto real con pysentimiento (Si el paciente escribió algo)
    # 2. Evaluamos el texto real con pysentimiento (Si el paciente escribió algo)
    if encuesta.q10_comentarios and encuesta.q10_comentarios.strip() != "":
        
        # Le pasamos el texto al modelo
        resultado = analyzer.predict(encuesta.q10_comentarios)
        
        # Si la IA se confunde y dice POSITIVO, pero la calificación de estrellas (Q1) fue de 3 o menos...
        if resultado.output == "POS" and encuesta.q1_satisfaccion_general <= 3:
            tipo_com = "NEGATIVO" # Tu lógica de ingeniero corrige a la IA
            
        # pysentimiento devuelve 'POS', 'NEG' o 'NEU'. 
        if resultado.output == "POS":
            # 🛡️ VALIDACIÓN CRUZADA: Si la IA dice POSITIVO pero la calificación fue mala/regular (3 o menos), lo forzamos a NEGATIVO o NEUTRO.
            if encuesta.q1_satisfaccion_general <= 3:
                tipo_com = "NEGATIVO" # O "NEUTRO", dependiendo de qué tan estricto querrás ser
            else:
                tipo_com = "POSITIVO"
        
              
        elif resultado.output == "NEG":
            tipo_com = "NEGATIVO"
        else:
            tipo_com = "NEUTRO"

    # 4. Guardamos la encuesta en la BD
    nueva_encuesta = models.EncuestaExperiencia(
        **encuesta.dict(),
        tipo_comentario=tipo_com,
        usuario_id=psicologo_id
    )
    
    db.add(nueva_encuesta)
    db.commit()
    return {"mensaje": "Feedback anónimo evaluado con IA y guardado con éxito"}

# 2. RUTA PARA OBTENER TODAS LAS ENCUESTAS DEL PSICÓLOGO
@app.get("/encuestas", response_model=List[schemas.EncuestaOut])
def obtener_encuestas(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user) # 🛡️ Candado Multi-tenant
):
    # Solo traemos las encuestas de este psicólogo
    encuestas = db.query(models.EncuestaExperiencia).filter(models.EncuestaExperiencia.usuario_id == current_user.id).all()
    return encuestas

@app.get("/dashboard/pacientes-activos")
def obtener_pacientes_activos(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # 1. Obtenemos TODOS los pacientes de esta clínica
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id
    ).all()

    hoy = datetime.now()
    mes_actual = hoy.month
    anio_actual = hoy.year

    if mes_actual == 1:
        mes_pasado = 12
        anio_pasado = anio_actual - 1
    else:
        mes_pasado = mes_actual - 1
        anio_pasado = anio_actual

    nuevos_este_mes = 0
    nuevos_mes_pasado = 0
    historial_mensual = {}

    # 2. El Truco Ninja: Usar la PRIMERA cita como fecha de ingreso
    for paciente in pacientes:
        # Buscamos la cita más antigua de este paciente (.asc())
        primera_cita = db.query(models.Cita).filter(
            models.Cita.paciente_id == paciente.id,
            models.Cita.fecha_cita != None
        ).order_by(models.Cita.fecha_cita.asc()).first()

        # Si el paciente está registrado pero no tiene citas aún, lo ignoramos para la estadística
        if not primera_cita:
            continue
            
        fecha = primera_cita.fecha_cita
        
        # Contabilizamos para el cálculo del porcentaje
        if fecha.year == anio_actual and fecha.month == mes_actual:
            nuevos_este_mes += 1
        elif fecha.year == anio_pasado and fecha.month == mes_pasado:
            nuevos_mes_pasado += 1
            
        # Guardamos en el registro histórico
        llave_mes = fecha.strftime("%m-%Y") 
        historial_mensual[llave_mes] = historial_mensual.get(llave_mes, 0) + 1

    # 3. La fórmula matemática del Crecimiento
    if nuevos_mes_pasado == 0:
        if nuevos_este_mes > 0:
            porcentaje_str = "+100%" 
        else:
            porcentaje_str = "0%"
    else:
        crecimiento = ((nuevos_este_mes - nuevos_mes_pasado) / nuevos_mes_pasado) * 100
        
        if crecimiento > 0:
            porcentaje_str = f"+{round(crecimiento)}%"
        elif crecimiento < 0:
            porcentaje_str = f"{round(crecimiento)}%" 
        else:
            porcentaje_str = "0%"

    return {
        "total": len(pacientes), # El total de pacientes registrados (tengan citas o no)
        "crecimiento_mes": porcentaje_str,
        "historial": historial_mensual 
    }

@app.get("/dashboard/expedientes-pendientes")
def obtener_expedientes_pendientes(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    ahora = datetime.now()
    limite_24h = ahora - timedelta(hours=24)
    
    # 🔍 Traemos todas las citas que cumplen las condiciones
    citas_vulnerables = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id,
        models.Cita.fecha_cita <= limite_24h,
        models.Cita.estado == "completada" 
    ).filter(
        ~models.Cita.id.in_(db.query(models.Reporte.cita_id))
    ).all() # 🌟 Usamos .all() para traer los objetos reales
    
    # 📝 Construimos la lista con los detalles de los pacientes
    lista_pendientes = []
    for cita in citas_vulnerables:
        lista_pendientes.append({
            "cita_id": cita.id,
            "paciente_id": cita.paciente_id,
            "paciente_nombre": cita.paciente.nombre if cita.paciente else "Paciente Desconocido",
            "fecha": cita.fecha_cita.strftime("%Y-%m-%d") if cita.fecha_cita else "",
            "motivo": cita.motivo
        })
    
    # 🚀 RETORNO CRÍTICO: Asegurate de mandar AMBAS llaves
    return {
        "cantidad_pendientes": len(lista_pendientes), # El número para la tarjeta
        "detalles": lista_pendientes                  # La lista para tu Modal
    }
    
@app.get("/dashboard/agenda-hoy")
def obtener_agenda_hoy(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # 1. Sacamos las fronteras del día de hoy (desde las 00:00 hasta las 23:59)
    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    # 2. Buscamos las citas del usuario para hoy, ordenadas por hora
    citas_hoy = db.query(models.Cita).join(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id,
        models.Cita.fecha_cita >= hoy_inicio,
        models.Cita.fecha_cita <= hoy_fin,
        models.Cita.estado.notin_(["Cancelada", "cancelada"]) # Ocultamos las canceladas
    ).order_by(models.Cita.fecha_cita.asc()).all()

    agenda = []
    ahora = datetime.now()

    for cita in citas_hoy:
        estado_visual = cita.estado.lower()
        
        # 🌟 LÓGICA INTELIGENTE: Si la cita es para ahorita o ya pasó la hora, 
        # y no la han marcado completada, la ponemos "en_curso"
        if estado_visual in ["pendiente", "reservada"]:
            if cita.fecha_cita <= ahora:
                estado_visual = "en_curso"

        agenda.append({
            "id": cita.id,
            "hora": cita.fecha_cita.strftime("%I:%M %p"), # Convierte a formato "08:00 AM"
            "paciente": cita.paciente.nombre if cita.paciente else "Desconocido",
            "tipo": cita.motivo,
            "estado": estado_visual,
            "duracion": "60 min" # Lo dejamos fijo por ahora, o si tenés el campo, lo cambiás
        })

    return agenda

@app.get("/pacientes/{paciente_id}/historial-sesiones")
def obtener_historial_sesiones(
    paciente_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # 1. Seguridad del SaaS: Validamos que el paciente pertenezca a la clínica del usuario
    paciente = db.query(models.Paciente).filter(
        models.Paciente.id == paciente_id,
        models.Paciente.clinica_id == current_user.clinica_id
    ).first()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado o no autorizado")

    # 2. Traemos TODAS las citas de este paciente, la más reciente primero
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
            "estado": cita.estado.lower(), # Lo mandamos en minúscula para manejarlo fácil en React
            "modalidad": cita.modalidad,
            # 🌟 AQUÍ ESTÁ LA MAGIA: Gracias al relationship, SQLAlchemy sabe si hay reporte
            "tiene_reporte": cita.reporte is not None,
            "reporte_id": cita.reporte.id if cita.reporte else None
        })

    return historial

@app.get("/estadisticas/motivos-distribucion")
def obtener_distribucion_motivos(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # 1. Contamos el TOTAL de citas de los pacientes de esta CLÍNICA
    total_citas = db.query(models.Cita).join(
        models.Paciente # 🔗 Conectamos Cita con Paciente
    ).filter(
        models.Paciente.clinica_id == current_user.clinica_id, # 🛡️ El candado de seguridad
        models.Cita.motivo != None
    ).count()

    if total_citas == 0:
        return [] 

    # 2. Agrupamos por motivo usando el JOIN
    resultados = db.query(
        models.Cita.motivo,
        func.count(models.Cita.id).label('cantidad')
    ).join(
        models.Paciente # 🔗 Volvemos a conectar las tablas
    ).filter(
        models.Paciente.clinica_id == current_user.clinica_id, # 🛡️ Mismo candado
        models.Cita.motivo != None
    ).group_by(
        models.Cita.motivo
    ).order_by(
        func.count(models.Cita.id).desc()
    ).limit(4).all() 

    # 3. Formateamos la respuesta con los porcentajes exactos
    distribucion = []
    for motivo, cantidad in resultados:
        porcentaje = round((cantidad / total_citas) * 100)
        distribucion.append({
            "motivo": motivo,
            "porcentaje": porcentaje
        })

    return distribucion

@app.get("/dashboard/alertas-inactividad")
def obtener_alertas_inactividad(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # 1. Buscamos a los pacientes de esta clínica (Multi-tenant)
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == current_user.clinica_id
    ).all()

    alertas = []
    hoy = datetime.now()

    for paciente in pacientes:
        # 2. Buscamos su última cita pasada
        ultima_cita = db.query(models.Cita).filter(
            models.Cita.paciente_id == paciente.id,
            models.Cita.fecha_cita <= hoy
        ).order_by(models.Cita.fecha_cita.desc()).first()

        # 3. Verificamos que NO tenga citas en el futuro
        cita_futura = db.query(models.Cita).filter(
            models.Cita.paciente_id == paciente.id,
            models.Cita.fecha_cita > hoy
        ).first()

        # 4. Si tiene una cita pasada y no tiene citas futuras, calculamos los días
        if ultima_cita and not cita_futura:
            dias_inactivos = (hoy - ultima_cita.fecha_cita).days
            
            if dias_inactivos >= 30:
                # Le asignamos los colores dinámicos de tu diseño según la gravedad
                if dias_inactivos >= 60:
                    color, bg = "text-rose-600", "bg-rose-50"      # Crítico (Rojo)
                elif dias_inactivos >= 45:
                    color, bg = "text-amber-600", "bg-amber-50"    # Advertencia (Naranja)
                else:
                    color, bg = "text-slate-500", "bg-slate-100"   # Normal (Gris)

                alertas.append({
                    "id": paciente.id,
                    # Asumiendo que tenés nombres y apellidos en tu modelo:
                    "name": f"{paciente.nombre}", 
                    "ultimaCita": f"Hace {dias_inactivos} días",
                    "dias": dias_inactivos, # Lo guardamos oculto para ordenar
                    "color": color,
                    "bg": bg
                })

    # 5. Ordenamos para que los más críticos (más días) salgan primero
    alertas.sort(key=lambda x: x["dias"], reverse=True)
    
    return alertas
@app.get("/dashboard/metricas-negocio")
def obtener_metricas_negocio(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    hoy = datetime.now()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # Manejo del cambio de año para el mes pasado
    mes_pasado = 12 if mes_actual == 1 else mes_actual - 1
    anio_pasado = anio_actual - 1 if mes_actual == 1 else anio_actual

    # Obtenemos todas las citas válidas de esta clínica
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

        # 1. Cálculos de Ingresos
        if cita.fecha_cita.month == mes_actual and cita.fecha_cita.year == anio_actual:
            ingresos_actual += tarifa_real
        elif cita.fecha_cita.month == mes_pasado and cita.fecha_cita.year == anio_pasado:
            ingresos_pasado += tarifa_real

        # 2. Conteo para Retención
        pacientes_con_citas[cita.paciente_id] = pacientes_con_citas.get(cita.paciente_id, 0) + 1

        # 3. Conteo para Horas Ahorradas (Solo citas finalizadas generan reporte)
        if cita.estado.lower() == "completada":
            citas_completadas += 1

    # --- MATEMÁTICA FINAL ---
    
    # Crecimiento de Ingresos (Fórmula MoM)
    if ingresos_pasado == 0:
        crecimiento_ingresos = "+100%" if ingresos_actual > 0 else "0%"
    else:
        porcentaje = ((ingresos_actual - ingresos_pasado) / ingresos_pasado) * 100
        crecimiento_ingresos = f"+{round(porcentaje)}%" if porcentaje >= 0 else f"{round(porcentaje)}%"

    # Tasa de Retención
    total_pacientes_vistos = len(pacientes_con_citas)
    pacientes_recurrentes = sum(1 for cantidad in pacientes_con_citas.values() if cantidad > 1)
    
    tasa_retencion = 0
    if total_pacientes_vistos > 0:
        tasa_retencion = round((pacientes_recurrentes / total_pacientes_vistos) * 100)

    minutos_ahorrados = citas_completadas * 15
    horas_ahorradas = round(minutos_ahorrados / 60, 1) # Lo redondeamos a 1 decimal (ej: 2.5 hrs)

    return {
        "ingresos": {
            "monto": f"${ingresos_actual:,.2f}", 
            "crecimiento": crecimiento_ingresos
        },
        "retencion": f"{tasa_retencion}%",
        "horas_ahorradas": horas_ahorradas
    }