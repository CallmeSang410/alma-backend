from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
import models, schemas
from database import engine, get_db
import bcrypt
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from test_ia import analizar_notas_con_ia
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware # <-- Asegurate de importar esto
from datetime import datetime, timedelta
from fastapi import Query
import google.generativeai as genai

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
    # 🌟 AHORA SÍ GUARDAMOS LA URGENCIA Y EL ESTADO 🌟
    nueva_cita = models.Cita(
    motivo=cita.motivo,
    fecha_cita=cita.fecha_cita,
    estado=cita.estado,
    modalidad=cita.modalidad, # 🌟 GUARDANDO EL DATO
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
    cita_encontrada.urgencia = cita_actualizada.urgencia
    cita_encontrada.estado = cita_actualizada.estado
    
    # 3. Guardamos los cambios
    db.commit()
    db.refresh(cita_encontrada)
    
    return cita_encontrada


# --- VENTANILLA 3: ELIMINAR UNA CITA (Para cuando le den a la X roja) ---
@app.delete("/citas/{cita_id}")
def eliminar_cita(cita_id: int, db: Session = Depends(get_db)):
    
    cita_encontrada = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    
    db.delete(cita_encontrada)
    db.commit()
    
    return {"mensaje": "La cita fue eliminada exitosamente del calendario"}

@app.get("/citas/alertas-activas")
def obtener_alertas_activas(
    horas: int = Query(24), 
    db: Session = Depends(get_db)
):
    ahora = datetime.now()
    limite_alerta = ahora + timedelta(hours=horas)
    
    # Traemos las citas en peligro
    citas_criticas = db.query(models.Cita).filter(
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
            # 🌟 CORRECCIÓN: Como el motivo vive en reportes, aquí ponemos un texto genérico
            "motivo_consulta": "Consulta Programada", 
            "paciente": {
                "nombre": paciente_db.nombre if paciente_db else "Paciente Desconocido"
            }
        }
        respuesta.append(cita_dict)
        
    return respuesta

# --- VENTANILLA 4: OBTENER EL CALENDARIO MAESTRO ---
@app.get("/citas", response_model=List[schemas.CitaOut])
def obtener_todas_las_citas(db: Session = Depends(get_db)):
    # Tráeme TODAS las citas de la tabla para pintarlas en React
    lista_citas = db.query(models.Cita).all()
    return lista_citas
# --- VENTANILLA: OBTENER TODOS LOS REPORTES (Unidos con Paciente) ---
# --- VENTANILLA: OBTENER TODOS LOS REPORTES (A prueba de balas) ---
@app.get("/reportes", response_model=List[schemas.ReporteOut])
def obtener_todos_los_reportes(db: Session = Depends(get_db)):
    
    # 1. Traemos todos los reportes crudos
    db_reportes = db.query(models.Reporte).all()

    respuesta = []
    
    # 2. Armamos la maleta a mano para que FastAPI no se confunda
    for reporte in db_reportes:
        # Buscamos quién es el dueño de este reporte
        cita = db.query(models.Cita).filter(models.Cita.id == reporte.cita_id).first()
        paciente = None
        if cita:
            paciente = db.query(models.Paciente).filter(models.Paciente.id == cita.paciente_id).first()
        
        # Armamos el diccionario exacto que espera tu React
        rep_dict = {
            "id": reporte.id,
            "motivo_consulta": reporte.motivo_consulta,
            "notas_psicologo": reporte.notas_psicologo,
            "pruebas_aplicadas": reporte.pruebas_aplicadas,
            "analisis_ia": reporte.analisis_ia,
            "diagnostico_final": reporte.diagnostico_final,
            "recomendaciones": reporte.recomendaciones,
            "plan_accion": reporte.plan_accion,
            "fecha_generacion": reporte.fecha_generacion,
            "cita_id": reporte.cita_id,
            "paciente_data": paciente # Aquí va Dervin con su edad y teléfono
        }
        respuesta.append(rep_dict)

    return respuesta


# 🌟 RUTA NUEVA: SE EJECUTA EN EL PASO 3 DE REACT
# 🌟 RUTA NUEVA: SE EJECUTA EN EL PASO 3 DE REACT
@app.post("/reportes/analizar")
def generar_analisis_ia(datos: schemas.AnalisisIARequest):
    prompt_maestro = f"""
    Actúa como un neuropsicólogo clínico senior con 20 años de experiencia. Tu tarea es analizar las notas iniciales de una sesión terapéutica y redactar un análisis técnico-profesional para ayudar al psicólogo humano a formular su diagnóstico.

    CONTEXTO CLÍNICO PROPORCIONADO:
    - Motivo de Consulta: {datos.motivo_consulta}
    - INSTRUMENTOS Y TÉCNICAS APLICADAS: {datos.pruebas_aplicadas or 'Entrevista clínica semiestructurada'}
    - NOTAS CRUDAS DE LA SESIÓN: "{datos.notas_psicologo}"

    REGLAS ESTRICTAS DE ANÁLISIS Y FORMATO:
    1. INTEGRACIÓN DE INSTRUMENTOS (¡OBLIGATORIO!): Analiza críticamente cómo los síntomas se relacionan con los instrumentos aplicados.
    2. DEBES insertar un DOBLE SALTO DE LÍNEA después de cada título (##). NUNCA inicies el párrafo en la misma línea del título.
    3. Usa **negritas** para resaltar síntomas clave, síndromes, escalas o posibles códigos del DSM-5.
    4. Limítate estrictamente a la impresión diagnóstica. NO sugieras planes de acción, recomendaciones ni tratamientos, eso es labor exclusiva del terapeuta.

    ESTRUCTURA DE SALIDA EXACTA (Solo 2 secciones):

    ## 🔍 Análisis Sintomatológico y Observaciones
    
    (Párrafo descriptivo integrando síntomas e instrumentos).

    ## 🧠 Posibles Ejes Diagnósticos (Alineación DSM-5)
    
    (Sugiere posibles diagnósticos y códigos DSM-5 que el terapeuta debería considerar según las notas).
    """

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        respuesta_ia = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_maestro
        )
        return {"analisis": respuesta_ia.text}
    except Exception as e:
        print(f"❌ Error en Gemini: {e}")
        raise HTTPException(status_code=500, detail="Error interno de la IA")


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


# --- VENTANILLA: OBTENER LA LÍNEA DE TIEMPO COMPLETA ---
@app.get("/pacientes/{paciente_id}/eventos", response_model=List[schemas.EventoVidaOut])
def obtener_linea_tiempo(paciente_id: int, db: Session = Depends(get_db)):
    # 1. Buscamos todos los eventos de este paciente específico
    # Y los ordenamos (.order_by) por fecha para que la línea de tiempo tenga sentido cronológico
    eventos = db.query(models.EventoVida)\
                .filter(models.EventoVida.paciente_id == paciente_id)\
                .order_by(models.EventoVida.fecha_evento.asc())\
                .all()
    
    return eventos

# --- VENTANILLA: MODIFICAR UN EVENTO (UPDATE) ---
@app.put("/eventos/{evento_id}", response_model=schemas.EventoVidaOut)
def actualizar_evento(evento_id: int, evento_actualizado: schemas.EventoVidaCreate, db: Session = Depends(get_db)):
    
    # 1. Buscamos el evento exacto en la base de datos
    evento_encontrado = db.query(models.EventoVida).filter(models.EventoVida.id == evento_id).first()
    
    if not evento_encontrado:
        raise HTTPException(status_code=404, detail="El evento no existe")
        
    # 2. Reemplazamos los datos viejos con los nuevos que nos mandó el frontend
    evento_encontrado.titulo = evento_actualizado.titulo
    evento_encontrado.fecha_evento = evento_actualizado.fecha_evento
    evento_encontrado.descripcion = evento_actualizado.descripcion
    evento_encontrado.impacto = evento_actualizado.impacto
    
    # 3. Guardamos los cambios
    db.commit()
    db.refresh(evento_encontrado)
    
    return evento_encontrado

# --- VENTANILLA: BORRAR UN EVENTO (DELETE) ---
@app.delete("/eventos/{evento_id}")
def eliminar_evento(evento_id: int, db: Session = Depends(get_db)):
    
    # 1. Buscamos el evento
    evento_encontrado = db.query(models.EventoVida).filter(models.EventoVida.id == evento_id).first()
    
    if not evento_encontrado:
        raise HTTPException(status_code=404, detail="El evento no existe")
        
    # 2. Le damos la orden a SQLAlchemy de borrarlo
    db.delete(evento_encontrado)
    db.commit()
    
    # 3. Devolvemos un mensaje de éxito para que React sepa que ya no existe
    return {"mensaje": f"El evento '{evento_encontrado.titulo}' ha sido eliminado exitosamente del historial."}

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
    

    # 2. Le damos a la IA su "Personalidad" y el conocimiento de ALMA
instrucciones_alma = """
Eres el asistente virtual oficial de soporte técnico del sistema ALMA (HorizonFlow).
Tu objetivo es ayudar a psicólogos y administradores clínicos a usar la plataforma.

Conoces las siguientes funcionalidades clave del sistema:
1. Directorio de Pacientes: Permite agregar pacientes, ver su expediente, editar su perfil y eliminarlos de forma segura.
2. Expediente Clínico: Contiene la información de contacto, la línea de tiempo gráfica (Historial Evolutivo) y el historial de reportes.
3. Reportes IA: El sistema permite estructurar notas clínicas usando IA para generar análisis y diagnósticos.
4. Ajustes: Permite cambiar entre Tema Claro/Oscuro, ajustar el tamaño de texto, establecer alertas de 24/48/72 horas y reportar bugs.

Reglas:
- Sé amable, conciso y muy profesional. Dirígete al usuario de forma respetuosa.
- Si preguntan sobre cómo funciona algo, explícalo en pasos cortos.
- Eres soporte técnico de software: NO des consejos médicos, diagnósticos o terapia a pacientes.
"""

# IMPORTANTE: Usamos la versión de Gemini más reciente y actualizada disponible
modelo_soporte = genai.GenerativeModel(
    model_name='gemini-2.5-flash', 
    system_instruction=instrucciones_alma
)

# 3. LA VENTANILLA DE CONEXIÓN CON REACT
@app.post("/soporte/chat")
def chat_soporte_alma(request: schemas.ChatRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="El servidor no tiene configurada la API Key de Gemini.")
        
    try:
        # Enviamos el mensaje del usuario al modelo
        respuesta = modelo_soporte.generate_content(request.mensaje)
        
        # Devolvemos el texto generado hacia la interfaz de React
        return {"respuesta": respuesta.text}
        
    except Exception as e:
        print(f"❌ Error en Gemini: {e}")
        raise HTTPException(status_code=500, detail="El asistente está descansando en este momento. Intenta de nuevo más tarde.")

