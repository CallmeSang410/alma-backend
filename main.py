from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import engine, get_db
from google import genai  # Solo la importación, sin el configure
import bcrypt
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware



# Creamos las tablas si no existen
models.Base.metadata.create_all(bind=engine)


app = FastAPI()
# Lista de direcciones a las que les damos permiso
origenes_permitidos = [
    "http://localhost:5174", # La dirección de tu React de Vite
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
    
    # 1. Buscamos al paciente en la base de datos (Igual que en el GET)
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    # 2. Si no existe, lanzamos el error 404
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="El paciente no existe")
    
    # 3. Si sí existe, reemplazamos sus datos viejos por los nuevos que llegaron en el JSON
    paciente_encontrado.nombre = paciente_actualizado.nombre
    paciente_encontrado.telefono = paciente_actualizado.telefono
    
    # 4. Guardamos los cambios permanentemente en PostgreSQL
    db.commit()
    
    # 5. Refrescamos para tener la versión más reciente
    db.refresh(paciente_encontrado)
    
    # 6. Devolvemos el paciente ya modificado
    return paciente_encontrado

# --- NUEVA VENTANILLA: ELIMINAR UN PACIENTE ---
# Usamos @app.delete porque la acción es destructiva.
@app.delete("/pacientes/{paciente_id}")
def eliminar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    
    # 1. Buscamos al paciente
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    
    # 2. Si no existe, error 404
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="El paciente no existe")
    
    # 3. La ejecución de SQLAlchemy: "Bórralo de la tabla"
    db.delete(paciente_encontrado)
    
    # 4. Guardamos los cambios para que sea permanente
    db.commit()
    
    # 5. Devolvemos un mensaje de confirmación en lugar de los datos del paciente (porque ya no existen)
    return {"mensaje": f"El paciente con ID {paciente_id} ha sido eliminado de ALMA exitosamente."}

# --- NUEVA VENTANILLA: AGENDAR UNA CITA ---
# Fíjate en la ruta: POST /pacientes/{paciente_id}/citas
# Esto es semántica pura: "Crea una cita DENTRO del paciente X"
@app.post("/pacientes/{paciente_id}/citas", response_model=schemas.CitaOut)
def crear_cita(paciente_id: int, cita: schemas.CitaCreate, db: Session = Depends(get_db)):
    
    # 1. Primero, verificamos que el paciente realmente exista en ALMA
    paciente_encontrado = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if paciente_encontrado is None:
        raise HTTPException(status_code=404, detail="No puedes agendarle una cita a un paciente que no existe")

    # 2. Creamos la cita conectándola con el paciente
    # Tomamos el motivo y la fecha que vinieron de internet, y le inyectamos el ID que vino en la URL
    nueva_cita = models.Cita(
        motivo=cita.motivo, 
        fecha_cita=cita.fecha_cita, 
        paciente_id=paciente_id  # <--- AQUÍ ESTÁ EL PUENTE DE LA LLAVE FORÁNEA
    )
    
    # 3. La guardamos en la bóveda
    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)
    
    # 4. Devolvemos el comprobante de la cita
    return nueva_cita

# --- NUEVA VENTANILLA: OBTENER EL CALENDARIO MAESTRO ---
# Fíjate que la ruta es simplemente /citas, no está amarrada a ningún paciente.
@app.get("/citas", response_model=List[schemas.CitaOut])
def obtener_todas_las_citas(db: Session = Depends(get_db)):
    
    # Le decimos a la base de datos: "Tráeme TODAS las citas de la tabla, sin importar de quién sean"
    lista_citas = db.query(models.Cita).all()
    
    return lista_citas


@app.post("/citas/{cita_id}/reporte", response_model=schemas.ReporteOut)
def crear_reporte_session(cita_id: int, reporte: schemas.ReporteCreate, db: Session = Depends(get_db)):
    
    # 1. Verificamos que la cita exista
    cita_encontrada = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita_encontrada:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    # 2. Evitamos duplicados
    reporte_existente = db.query(models.Reporte).filter(models.Reporte.cita_id == cita_id).first()
    if reporte_existente:
        raise HTTPException(status_code=400, detail="Esta cita ya tiene un reporte generado")

    # --- 3. LA MAGIA DE LA IA (El Cerebro de ALMA) ---
    prompt_maestro = f"""
    Actúa como un psicólogo clínico experto. Transforma estas notas crudas en un análisis para el expediente.
    
    REGLAS ESTRICTAS:
    1. Sé extremadamente directo, breve y conciso.
    2. Usa únicamente viñetas (bullet points).
    3. Cero introducciones (no digas "Estimado colega" ni "Aquí tienes el resumen").
    4. Cero conclusiones largas.
    5. Máximo 2 líneas por punto.

    Estructura tu respuesta estrictamente con estos tres títulos:
    ### 🔍 Observaciones Generales
    ### 🧠 Impresión Diagnóstica Preliminar
    ### 🎯 Recomendaciones

    Notas crudas del psicólogo:
    "{reporte.notas_psicologo}"
    """

    try:
        # Usamos la NUEVA sintaxis de Google y el modelo gemini-2.5-flash
        # ¡IMPORTANTE! Pon tu API Key real aquí:
        client = genai.Client(api_key="AIzaSyDe95wrUINgqN0WSl3xlbNpalSB9m6qGas")
        
        respuesta_ia = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_maestro
        )
        analisis_final = respuesta_ia.text
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la IA: {str(e)}")

    # --- 4. GUARDAR EN LA BÓVEDA ---
    nuevo_reporte = models.Reporte(
        notas_psicologo=reporte.notas_psicologo,
        cita_id=cita_id,
        analisis_ia=analisis_final
    )

    db.add(nuevo_reporte)
    db.commit()
    db.refresh(nuevo_reporte)
    
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
@app.post("/usuarios", response_model=schemas.UsuarioOut)
def crear_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    
    # 1. Encriptamos con bcrypt puro
    # Convertimos la contraseña a bytes, generamos una 'sal' aleatoria, y la licuamos
    password_bytes = usuario.password.encode('utf-8')
    sal = bcrypt.gensalt()
    password_encriptada_bytes = bcrypt.hashpw(password_bytes, sal)
    
    # La convertimos de vuelta a string de texto para guardarla en PostgreSQL
    password_encriptada_str = password_encriptada_bytes.decode('utf-8')
    
    # 2. Creamos el registro con la contraseña segura (El Hash)
    nuevo_usuario = models.Usuario(
        username=usuario.username,
        hashed_password=password_encriptada_str,
        rol=usuario.rol,
        clinica_id=usuario.clinica_id
    )
    
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

# La "contraseña maestra" de tu servidor para firmar los gafetes VIP. 
# En un proyecto real esto se esconde, pero para pruebas está bien aquí.
SECRETO_ALMA = "super_secreto_para_gafetes_123" 
# Instanciamos el escudo de seguridad
security = HTTPBearer()

# Este es el Cadenero Oficial de ALMA
def obtener_usuario_actual(credenciales: HTTPAuthorizationCredentials = Depends(security)):
    token = credenciales.credentials # Aquí saca el gafete del bolsillo invisible
    try:
        # Intenta desencriptar el gafete usando nuestra contraseña maestra
        payload = jwt.decode(token, SECRETO_ALMA, algorithms=["HS256"])
        return payload # Si es válido, devuelve los datos: usuario_id, clinica_id, rol
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El gafete ha expirado. Vuelve a iniciar sesión.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Gafete inválido o falso. ¡Intruso detectado!")

# --- NUESTRO PRIMER ENDPOINT REAL ---
# Usamos @app.post porque vamos a CREAR información nueva
@app.post("/pacientes", response_model=schemas.PacienteOut)
def crear_paciente(
    paciente: schemas.PacienteCreate, 
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual) # <--- 1. Exigimos el gafete
):
    
    # 2. Construimos al paciente fusionando lo que escribió el usuario 
    # con el dato secreto (clinica_id) que venía en su gafete.
    nuevo_paciente = models.Paciente(
        nombre=paciente.nombre,
        telefono=paciente.telefono,
        clinica_id=usuario_actual["clinica_id"] # <--- 3. ¡Inyección automática!
    )
    
    db.add(nuevo_paciente)
    db.commit()
    db.refresh(nuevo_paciente)
    
    return nuevo_paciente

@app.get("/pacientes", response_model=List[schemas.PacienteOut])
def leer_pacientes(
    db: Session = Depends(get_db), 
    usuario_actual: dict = Depends(obtener_usuario_actual) # <--- Aquí pusimos al cadenero en la puerta
):
    # Si el código llega a esta línea, significa que el usuario sí traía un gafete válido.
    
    # En lugar de traer .all(), filtramos usando el dato que venía escondido en el Token:
    pacientes = db.query(models.Paciente).filter(
        models.Paciente.clinica_id == usuario_actual["clinica_id"]
    ).all()
    
    return pacientes
@app.post("/login")
def iniciar_sesion(credenciales: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    
    # 1. Buscar si el usuario existe en el edificio
    usuario_db = db.query(models.Usuario).filter(models.Usuario.username == credenciales.username).first()
    if not usuario_db:
        # Si no existe, lo rebotamos
        raise HTTPException(status_code=404, detail="El usuario no existe")

    # 2. Verificar si la llave (contraseña) encaja
    password_intento_bytes = credenciales.password.encode('utf-8')
    password_real_bytes = usuario_db.hashed_password.encode('utf-8')
    
    # bcrypt.checkpw hace la magia de comparar los dos hashes de forma segura
    if not bcrypt.checkpw(password_intento_bytes, password_real_bytes):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    # 3. Si todo está correcto, le imprimimos su Gafete VIP (Token JWT)
    # Aquí adentro guardamos la información que el sistema necesita recordar de él
    datos_gafete = {
        "usuario_id": usuario_db.id,
        "clinica_id": usuario_db.clinica_id,
        "rol": usuario_db.rol
    }
    
    # Sellamos el gafete con el SECRETO_ALMA para que nadie lo pueda falsificar
    token_vip = jwt.encode(datos_gafete, SECRETO_ALMA, algorithm="HS256")

    # Le entregamos su pase
    return {
        "mensaje": "¡Bienvenido a ALMA!", 
        "tu_gafete_digital": token_vip
    }