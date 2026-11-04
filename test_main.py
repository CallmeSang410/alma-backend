"""
Suite de pruebas automatizadas (Laboratorio 15).

Usa SQLite en memoria para no tocar la base de datos de producción.
Los orígenes CORS y el SECRET_KEY de JWT se fijan antes de importar `main`.
"""
import os
from datetime import datetime

# Aislamiento de entorno ANTES de importar database / main.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-lab15-no-produccion"
os.environ["ALGORITHM"] = "HS256"
os.environ["CORS_ORIGINS"] = "https://horizonflowai.vercel.app"
os.environ.pop("GEMINI_API_KEY", None)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=TEST_ENGINE,
)

database.engine = TEST_ENGINE
database.SessionLocal = TestingSessionLocal


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


database.get_db = override_get_db

import models  # noqa: E402

models.Base.metadata.create_all(bind=TEST_ENGINE)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from main import app, SECRET_KEY, ALGORITHM  # noqa: E402
from database import get_db  # noqa: E402

app.dependency_overrides[get_db] = override_get_db

ORIGEN_PERMITIDO = "https://horizonflowai.vercel.app"
ORIGEN_NO_AUTORIZADO = "https://sitio-malicioso.example"


def _reset_db():
    models.Base.metadata.drop_all(bind=TEST_ENGINE)
    models.Base.metadata.create_all(bind=TEST_ENGINE)


def _token_para(usuario_id: int, clinica_id: int, rol: str = "psicologo") -> str:
    return jwt.encode(
        {
            "usuario_id": usuario_id,
            "clinica_id": clinica_id,
            "rol": rol,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _headers_auth(usuario_id: int, clinica_id: int, rol: str = "psicologo") -> dict:
    return {"Authorization": f"Bearer {_token_para(usuario_id, clinica_id, rol)}"}


def _sembrar_dos_clinicas():
    """Crea dos clínicas, un usuario y un paciente en cada una."""
    db = TestingSessionLocal()
    try:
        clinica_a = models.Clinica(nombre="Clinica Alpha", codigo_invitacion="ALMA-AAAAAA")
        clinica_b = models.Clinica(nombre="Clinica Beta", codigo_invitacion="ALMA-BBBBBB")
        db.add_all([clinica_a, clinica_b])
        db.commit()
        db.refresh(clinica_a)
        db.refresh(clinica_b)

        usuario_a = models.Usuario(
            username="alpha@test.com",
            hashed_password="hash-de-prueba",
            rol="psicologo",
            clinica_id=clinica_a.id,
        )
        usuario_b = models.Usuario(
            username="beta@test.com",
            hashed_password="hash-de-prueba",
            rol="psicologo",
            clinica_id=clinica_b.id,
        )
        db.add_all([usuario_a, usuario_b])
        db.commit()
        db.refresh(usuario_a)
        db.refresh(usuario_b)

        paciente_a = models.Paciente(
            nombre="Paciente Alpha",
            clinica_id=clinica_a.id,
            folio_visual=1,
            estado="Activo",
        )
        paciente_b = models.Paciente(
            nombre="Paciente Beta",
            clinica_id=clinica_b.id,
            folio_visual=1,
            estado="Activo",
        )
        db.add_all([paciente_a, paciente_b])
        db.commit()
        db.refresh(paciente_a)
        db.refresh(paciente_b)

        cita_a = models.Cita(
            motivo="Sesion Alpha",
            fecha_cita=datetime(2026, 10, 30, 10, 0, 0),
            estado="Pendiente",
            modalidad="Presencial",
            tarifa=500.0,
            paciente_id=paciente_a.id,
        )
        cita_b = models.Cita(
            motivo="Sesion Beta",
            fecha_cita=datetime(2026, 10, 30, 11, 0, 0),
            estado="Pendiente",
            modalidad="Virtual",
            tarifa=400.0,
            paciente_id=paciente_b.id,
        )
        db.add_all([cita_a, cita_b])
        db.commit()
        db.refresh(cita_a)
        db.refresh(cita_b)

        return {
            "usuario_a_id": usuario_a.id,
            "usuario_a_clinica_id": usuario_a.clinica_id,
            "usuario_a_rol": usuario_a.rol,
            "usuario_b_id": usuario_b.id,
            "usuario_b_clinica_id": usuario_b.clinica_id,
            "usuario_b_rol": usuario_b.rol,
            "paciente_a_id": paciente_a.id,
            "paciente_b_id": paciente_b.id,
            "cita_a_id": cita_a.id,
            "cita_b_id": cita_b.id,
        }
    finally:
        db.close()


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Disponibilidad
# ---------------------------------------------------------------------------
def test_health_devuelve_200():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. CORS / Headers: no se reflejan orígenes arbitrarios
# ---------------------------------------------------------------------------
def test_cors_rechaza_origen_no_autorizado():
    respuesta = client.get("/health", headers={"Origin": ORIGEN_NO_AUTORIZADO})
    assert respuesta.status_code == 200
    assert respuesta.headers.get("access-control-allow-origin") != ORIGEN_NO_AUTORIZADO


def test_cors_preflight_no_autoriza_origen_arbitrario():
    respuesta = client.options(
        "/pacientes",
        headers={
            "Origin": ORIGEN_NO_AUTORIZADO,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert respuesta.headers.get("access-control-allow-origin") != ORIGEN_NO_AUTORIZADO
    assert respuesta.status_code in (400, 403, 405)


def test_cors_permite_origen_configurado():
    respuesta = client.get("/health", headers={"Origin": ORIGEN_PERMITIDO})
    assert respuesta.status_code == 200
    assert respuesta.headers.get("access-control-allow-origin") == ORIGEN_PERMITIDO


# ---------------------------------------------------------------------------
# 3. Autenticación en rutas clínicas
# ---------------------------------------------------------------------------
def test_get_pacientes_sin_token_devuelve_401():
    respuesta = client.get("/pacientes")
    assert respuesta.status_code == 401


def test_get_citas_sin_token_devuelve_401():
    respuesta = client.get("/citas")
    assert respuesta.status_code == 401


def test_token_bearer_invalido_devuelve_401():
    respuesta = client.get(
        "/pacientes",
        headers={"Authorization": "Bearer token-inventado"},
    )
    assert respuesta.status_code == 401


# ---------------------------------------------------------------------------
# 4. Validación de esquemas Pydantic → 422
# ---------------------------------------------------------------------------
def test_login_datos_incompletos_devuelve_422():
    respuesta = client.post("/login", json={"email": "sin-password@test.com"})
    assert respuesta.status_code == 422


def test_crear_paciente_tipos_erroneos_devuelve_422():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    headers = _headers_auth(
        datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
    )

    respuesta = client.post(
        "/pacientes",
        headers=headers,
        json={"nombre": "Ana", "edad": "veintinueve"},
    )
    assert respuesta.status_code == 422


def test_crear_cita_payload_incompleto_devuelve_422():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    headers = _headers_auth(
        datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
    )
    paciente_id = datos["paciente_a_id"]

    respuesta = client.post(
        f"/pacientes/{paciente_id}/citas",
        headers=headers,
        json={"motivo": "Falta fecha y modalidad"},
    )
    assert respuesta.status_code == 422


# ---------------------------------------------------------------------------
# 5. Aislamiento por clínica
# ---------------------------------------------------------------------------
def test_listado_pacientes_filtra_por_clinica_del_usuario():
    _reset_db()
    datos = _sembrar_dos_clinicas()

    respuesta = client.get(
        "/pacientes",
        headers=_headers_auth(
            datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
        ),
    )
    assert respuesta.status_code == 200
    nombres = {p["nombre"] for p in respuesta.json()}
    assert "Paciente Alpha" in nombres
    assert "Paciente Beta" not in nombres


def test_listado_citas_filtra_por_clinica_del_usuario():
    _reset_db()
    datos = _sembrar_dos_clinicas()

    respuesta = client.get(
        "/citas",
        headers=_headers_auth(
            datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
        ),
    )
    assert respuesta.status_code == 200
    motivos = {c["motivo"] for c in respuesta.json()}
    assert "Sesion Alpha" in motivos
    assert "Sesion Beta" not in motivos


def test_no_puede_leer_paciente_de_otra_clinica():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    id_ajeno = datos["paciente_b_id"]

    respuesta = client.get(
        f"/pacientes/{id_ajeno}",
        headers=_headers_auth(
            datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
        ),
    )
    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# 6. Encabezados HTTP de seguridad y trazabilidad (Fase 5.2 y Fase 6)
# ---------------------------------------------------------------------------
def test_respuestas_incluyen_encabezados_de_seguridad_y_request_id():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.headers.get("x-content-type-options") == "nosniff"
    assert respuesta.headers.get("x-frame-options") == "DENY"
    assert respuesta.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in (respuesta.headers.get("permissions-policy") or "")
    assert respuesta.headers.get("x-request-id") is not None


# ---------------------------------------------------------------------------
# 7. Validación de formatos y rangos CP-05 y CP-07 (Fase 3)
# ---------------------------------------------------------------------------
def test_crear_paciente_nombre_en_blanco_o_edad_negativa_devuelve_422():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    headers = _headers_auth(
        datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
    )

    resp_vacio = client.post("/pacientes", headers=headers, json={"nombre": "   "})
    assert resp_vacio.status_code == 422

    resp_edad_neg = client.post(
        "/pacientes", headers=headers, json={"nombre": "Paciente Test", "edad": -5}
    )
    assert resp_edad_neg.status_code == 422

    resp_email_invalido = client.post(
        "/pacientes",
        headers=headers,
        json={"nombre": "Paciente Test", "email": "correo-sin-arroba"},
    )
    assert resp_email_invalido.status_code == 422


def test_crear_cita_tarifa_negativa_devuelve_422():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    headers = _headers_auth(
        datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
    )
    paciente_id = datos["paciente_a_id"]

    respuesta = client.post(
        f"/pacientes/{paciente_id}/citas",
        headers=headers,
        json={
            "motivo": "Consulta",
            "fecha_cita": "2026-11-10T10:00:00",
            "estado": "Pendiente",
            "modalidad": "Presencial",
            "tarifa": -150.0,
        },
    )
    assert respuesta.status_code == 422


def test_encuesta_publica_psicologo_inexistente_devuelve_404():
    _reset_db()
    respuesta = client.post(
        "/encuestas/publica/999999",
        json={
            "q1_satisfaccion_general": 5,
            "q2_cumplimiento_expectativas": "Sí",
            "q3_empatia_conexion": "Excelente",
            "q4_aspectos_valorados": "Puntualidad",
            "q5_instalaciones": 5,
            "q6_claridad_pautas": "Muy claras",
            "q7_impacto_animo": "Positivo",
            "q8_confianza_seguridad": "Alta",
            "q9_indice_recomendacion": "Definitivamente",
            "q10_comentarios": "Excelente atención",
        },
    )
    assert respuesta.status_code == 404
