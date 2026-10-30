# HorizonFlow Backend

API FastAPI para gestión clínica de pacientes, citas, reportes, dashboards y encuestas.

## Requisitos

- Python 3.11 o superior.
- PostgreSQL compatible con SQLAlchemy.
- Variables de entorno configuradas.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Variables de entorno

Copia `.env.example` a `.env` y completa los valores fuera del repositorio. Nunca subas secretos.

- `DATABASE_URL`: conexión PostgreSQL.
- `SECRET_KEY`: clave fuerte para firmar JWT.
- `ALGORITHM`: algoritmo JWT, normalmente `HS256`.
- `GOOGLE_CLIENT_ID`: cliente OAuth autorizado.
- `GEMINI_API_KEY`: clave del proveedor de IA.
- `CORS_ORIGINS`: lista separada por comas de orígenes permitidos.

## URLs

- Health: `GET /health`
- Swagger: `/docs`
- OpenAPI: `/openapi.json`

## Seguridad

Las rutas clínicas requieren Bearer token y filtran los recursos por `clinica_id`. No se deben realizar pruebas con pacientes reales. La recuperación directa de contraseña está deshabilitada hasta integrar un flujo seguro con token de un solo uso enviado por un canal verificado.

El CORS de producción debe usar una allowlist explícita mediante `CORS_ORIGINS`; no se permite `*` con credenciales.

## Validación local

```bash
python -m py_compile *.py
python -m pytest
```

La suite debe cubrir autenticación, aislamiento entre clínicas, validación de entradas, recuperación de contraseña, errores y CORS.

## Smoke test

1. `GET /health` devuelve HTTP 200 y `{"status":"ok"}`.
2. `GET /pacientes` sin token devuelve HTTP 401.
3. Un usuario autenticado solo consulta recursos de su clínica.
4. Un usuario de otra clínica no puede leer ni mutar el recurso.
5. Las respuestas de error no contienen stack traces ni secretos.
6. Los logs contienen timestamp, nivel, ruta, request ID y status sin datos clínicos innecesarios.

## Despliegue

Despliega primero en staging con una base de datos aislada. Ejecuta las pruebas, mide p50/p95/p99 con 50 solicitudes y concurrencia 10, revisa logs y confirma rollback antes de producción.
