# HorizonFlow Backend

API RESTful construida con **FastAPI** y **SQLAlchemy (PostgreSQL / Supabase)** para la gestión clínica multi-tenant de pacientes, citas, expedientes clínicos asistidos por IA, analítica de consultorio y encuestas de satisfacción.

## Propósito del Sistema

Proveer el núcleo transaccional, de seguridad y de inteligencia clínica para **HorizonFlow** (`https://horizonflowai.vercel.app/`), garantizando aislamiento estricto de datos por clínica (`clinica_id`), autenticación mediante **JWT + Google OAuth 2.0**, validación de esquemas con Pydantic y observabilidad con logs estructurados en JSON.

## Requisitos

- Python 3.11 o superior.
- PostgreSQL compatible con SQLAlchemy (Supabase en producción).
- Variables de entorno configuradas en `.env`.

## Instalación y Ejecución Local

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
# En Linux/macOS:
source .venv/bin/activate
# En Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar servidor de desarrollo
uvicorn main:app --reload
```

## Variables de Entorno

Copia `.env.example` a `.env` y completa los valores fuera del repositorio. Nunca subas secretos al control de versiones.

| Variable | Requerida | Descripción |
| :--- | :---: | :--- |
| `DATABASE_URL` | Sí | Cadena de conexión PostgreSQL (`postgresql://...`). |
| `SECRET_KEY` | Sí | Clave criptográfica fuerte para firmar tokens JWT. |
| `ALGORITHM` | Sí | Algoritmo de firma JWT (por defecto `HS256`). |
| `GOOGLE_CLIENT_ID` | Sí | Client ID de Google Cloud Console para OAuth 2.0. |
| `GEMINI_API_KEY` | Opcional | API Key de Google Gemini para análisis clínico y soporte IA. |
| `CORS_ORIGINS` | Sí | Lista separada por comas de orígenes permitidos (ej. `https://horizonflowai.vercel.app`). |

## URLs de Producción y Documentación Interactiva

- **Frontend (Vercel):** `https://horizonflowai.vercel.app/`
- **Backend Base URL:** `https://alma-backend-1.onrender.com`
- **Health Check:** `GET https://alma-backend-1.onrender.com/health`
- **Swagger UI:** `https://alma-backend-1.onrender.com/docs`
- **OpenAPI Spec:** `https://alma-backend-1.onrender.com/openapi.json`

## Endpoints Principales y Ejemplos de Uso (Fase 7)

Todas las rutas clínicas requieren el encabezado `Authorization: Bearer <JWT_TOKEN>` y filtran automáticamente la información según el `clinica_id` del profesional autenticado.

### 1. Disponibilidad (`CP-01`)
- **Ruta:** `GET /health`
- **Autenticación:** Pública
- **Respuesta (`200 OK`):**
```json
{
  "status": "ok"
}
```

### 2. Autenticación (`POST /login` y `POST /auth/google`)
- **Ruta:** `POST /login`
- **Cuerpo de solicitud (`application/json`):**
```json
{
  "email": "profesional@clinica.com",
  "password": "PasswordSeguro123"
}
```
- **Respuesta (`200 OK`):**
```json
{
  "mensaje": "¡Bienvenido a HorizonFlow!",
  "tu_gafete_digital": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "email": "profesional@clinica.com",
  "nombre_clinica": "Clínica Horizon",
  "codigo_invitacion": "ALMA-7K9P2X",
  "rol": "psicologo"
}
```
- **Códigos de error:** `401 Unauthorized` (credenciales inválidas), `422 Unprocessable Entity` (campos faltantes).

### 3. Gestión de Pacientes (`CP-02`, `CP-03`, `CP-04`, `CP-05`, `CP-06`, `CP-07`)
- **Listar pacientes de la clínica:** `GET /pacientes` -> `200 OK`
- **Consultar paciente por ID:** `GET /pacientes/{paciente_id}` -> `200 OK` | `404 Not Found`
- **Crear paciente:** `POST /pacientes`
  - **Parámetros (JSON):**
    - `nombre` (`string`, requerido, 1–150 caracteres, no vacío)
    - `edad` (`integer`, opcional, rango `0` a `120`)
    - `email` (`string`, opcional, formato de correo válido `usuario@dominio.tld`)
    - `telefono` (`string`, opcional)
    - `sexo` (`string`, opcional)
    - `estado` (`string`, opcional, por defecto `"Activo"`)
  - **Ejemplo de solicitud:**
```json
{
  "nombre": "Ana Morales",
  "edad": 29,
  "email": "ana.morales@ejemplo.com",
  "telefono": "+505 8888-0000",
  "sexo": "Femenino",
  "estado": "Activo",
  "diagnostico_principal": "Evaluación inicial"
}
```
- **Actualizar paciente:** `PUT /pacientes/{paciente_id}` (mismo esquema validado que `POST /pacientes`).
- **Códigos de error:** `401 Unauthorized` (sin token), `404 Not Found` (ID inexistente o de otra clínica), `422 Unprocessable Entity` (nombre vacío, edad negativa o correo con formato inválido).

### 4. Gestión de Citas (`GET /citas`, `POST /pacientes/{paciente_id}/citas`, `PUT /citas/{cita_id}`)
- **Crear cita para un paciente:** `POST /pacientes/{paciente_id}/citas`
  - **Parámetros (JSON):**
    - `motivo` (`string`, requerido, no vacío)
    - `fecha_cita` (`datetime` ISO-8601, requerido)
    - `estado` (`string`, requerido, ej. `"Pendiente"`, `"Reservada"`, `"completada"`)
    - `modalidad` (`string`, requerido, ej. `"Presencial"`, `"Virtual"`)
    - `tarifa` (`float`, opcional, `>= 0.0`)
  - **Ejemplo de solicitud:**
```json
{
  "motivo": "Sesión de seguimiento cognitivo-conductual",
  "fecha_cita": "2026-11-15T10:00:00",
  "estado": "Pendiente",
  "modalidad": "Presencial",
  "tarifa": 45.0
}
```

### 5. Reportes Clínicos y Dashboard
- **Listar reportes clínicos:** `GET /reportes` -> `200 OK`
- **Crear reporte de sesión:** `POST /citas/{cita_id}/reporte` -> `200 OK` | `400 Bad Request` (si la cita ya tiene reporte) | `404 Not Found`
- **Métricas de Dashboard:**
  - `GET /dashboard/pacientes-activos`
  - `GET /dashboard/agenda-hoy`
  - `GET /dashboard/expedientes-pendientes`
  - `GET /dashboard/metricas-negocio`

## Seguridad y Observabilidad (Fases 4, 5 y 6)

- **Aislamiento Multi-Tenant:** Todas las consultas y mutaciones verifican `clinica_id == current_user.clinica_id`.
- **Encabezados HTTP de Seguridad:** Todas las respuestas del backend incluyen `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()` y `X-Request-ID`.
- **Logs Estructurados en JSON:** Cada solicitud y evento se registra en formato JSON con `timestamp` (UTC ISO-8601), `level` (`INFO`, `WARNING`, `ERROR`), `request_id`, `method`, `path`, `status_code` y `latency_ms`, sin exponer datos sensibles ni trazas internas al cliente.
- **CORS:** Lista blanca explícita configurada mediante `CORS_ORIGINS`.

## Validación Automatizada Local

```bash
python -m py_compile *.py
python -m pytest -v
```

## Smoke Test

1. `GET /health` devuelve HTTP `200` y `{"status":"ok"}` junto con encabezados de seguridad y `X-Request-ID`.
2. `GET /pacientes` sin token devuelve HTTP `401`.
3. `POST /pacientes` con `nombre` vacío, `edad` negativa o `email` inválido devuelve HTTP `422`.
4. Un usuario autenticado solo consulta y modifica recursos de su propia clínica (`clinica_id`).
5. Un usuario de otra clínica recibe HTTP `404` al intentar acceder a un recurso ajeno.
6. Las respuestas de error no contienen stack traces ni secretos.
7. Los logs se emiten en JSON estructurado con `timestamp`, `level`, `path`, `request_id`, `status_code` y `latency_ms`.
