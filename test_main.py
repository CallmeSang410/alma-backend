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
# 6. Cabeceras OWASP y Request ID (HF-003)
# ---------------------------------------------------------------------------
def test_cabeceras_seguridad_owasp_y_request_id_presentes():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert "x-request-id" in respuesta.headers
    assert respuesta.headers.get("x-content-type-options") == "nosniff"
    assert respuesta.headers.get("x-frame-options") == "DENY"
    assert respuesta.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in respuesta.headers.get("permissions-policy", "")


# ---------------------------------------------------------------------------
# 7. Expiración de Tokens JWT (Fase 2)
# ---------------------------------------------------------------------------
def test_token_expirado_devuelve_401_controlado():
    from datetime import timedelta
    token_vencido = jwt.encode(
        {
            "usuario_id": 1,
            "clinica_id": 1,
            "rol": "psicologo",
            "exp": datetime.utcnow() - timedelta(minutes=5)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    respuesta = client.get(
        "/pacientes",
        headers={"Authorization": f"Bearer {token_vencido}"}
    )
    assert respuesta.status_code == 401
    assert "expirado" in respuesta.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# 8. Recuperación Segura de Contraseña (HF-001)
# ---------------------------------------------------------------------------
def test_solicitar_recuperacion_password_genera_token_temporal():
    _reset_db()
    datos = _sembrar_dos_clinicas()

    respuesta = client.post(
        "/usuarios/recuperar/solicitar",
        json={"email": "alpha@test.com"}
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert "token" in cuerpo
    assert cuerpo["token"] is not None
    assert cuerpo["validez_minutos"] == 15

    # Para correo no registrado, responde con éxito genérico y token None (anti-enumeración)
    resp_inexistente = client.post(
        "/usuarios/recuperar/solicitar",
        json={"email": "no-existe@test.com"}
    )
    assert resp_inexistente.status_code == 200
    assert resp_inexistente.json()["token"] is None


def test_restablecer_password_con_token_valido_y_un_solo_uso():
    _reset_db()
    datos = _sembrar_dos_clinicas()

    solicitud = client.post(
        "/usuarios/recuperar/solicitar",
        json={"email": "alpha@test.com"}
    )
    token = solicitud.json()["token"]

    # 1. Restablecer con éxito
    confirmacion = client.post(
        "/usuarios/recuperar/confirmar",
        json={"token": token, "nueva_password": "nueva-clave-segura-123"}
    )
    assert confirmacion.status_code == 200
    assert "éxito" in confirmacion.json()["mensaje"].lower() or "exito" in confirmacion.json()["mensaje"].lower()

    # 2. Reutilización inmediata rechazada (Un solo uso)
    reintento = client.post(
        "/usuarios/recuperar/confirmar",
        json={"token": token, "nueva_password": "otra-clave-diferente-123"}
    )
    assert reintento.status_code == 400
    assert "inválido" in reintento.json()["detail"].lower() or "invalido" in reintento.json()["detail"].lower()


def test_restablecer_password_token_expirado_falla():
    import hashlib
    from datetime import timedelta
    _reset_db()
    datos = _sembrar_dos_clinicas()

    db = TestingSessionLocal()
    token_caducado_raw = "token-prueba-caducado-12345678"
    token_hash = hashlib.sha256(token_caducado_raw.encode("utf-8")).hexdigest()
    nuevo_token = models.PasswordResetToken(
        usuario_id=datos["usuario_a_id"],
        token_hash=token_hash,
        expiracion=datetime.utcnow() - timedelta(minutes=1),
        usado=False
    )
    db.add(nuevo_token)
    db.commit()
    db.close()

    respuesta = client.post(
        "/usuarios/recuperar/confirmar",
        json={"token": token_caducado_raw, "nueva_password": "password-nueva-123"}
    )
    assert respuesta.status_code == 400
    assert "expirado" in respuesta.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 9. Protección de Mutaciones Multi-Tenant (IDOR en escritura)
# ---------------------------------------------------------------------------
def test_no_puede_modificar_cita_de_otra_clinica():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    cita_b_id = datos["cita_b_id"]

    respuesta = client.put(
        f"/citas/{cita_b_id}",
        headers=_headers_auth(
            datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
        ),
        json={
            "motivo": "Intento de modificación no autorizada",
            "fecha_cita": "2026-10-30T15:00:00",
            "estado": "Cancelada",
            "modalidad": "Virtual",
            "tarifa": 100.0
        }
    )
    assert respuesta.status_code == 404


def test_no_puede_crear_cita_en_paciente_de_otra_clinica():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    paciente_b_id = datos["paciente_b_id"]

    respuesta = client.post(
        f"/pacientes/{paciente_b_id}/citas",
        headers=_headers_auth(
            datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
        ),
        json={
            "motivo": "Cita en clínica ajena",
            "fecha_cita": "2026-10-30T16:00:00",
            "estado": "Pendiente",
            "modalidad": "Presencial",
            "tarifa": 500.0
        }
    )
    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# 10. Robustez en Endpoints Públicos y Chatbot
# ---------------------------------------------------------------------------
def test_encuesta_publica_psicologo_inexistente_devuelve_404():
    _reset_db()
    respuesta = client.post(
        "/encuestas/publica/99999",
        json={
            "q1_satisfaccion_general": 5,
            "q2_cumplimiento_expectativas": "Excelente",
            "q3_empatia_conexion": "Excelente",
            "q4_aspectos_valorados": "Puntualidad",
            "q5_instalaciones": 5,
            "q6_claridad_pautas": "Claridad total",
            "q7_impacto_animo": "Muy positivo",
            "q8_confianza_seguridad": "Total",
            "q9_indice_recomendacion": "Si",
            "q10_comentarios": "Excelente atención"
        }
    )
    assert respuesta.status_code == 404


def test_soporte_chat_historial_vacio_rechazado():
    _reset_db()
    datos = _sembrar_dos_clinicas()
    respuesta = client.post(
        "/soporte/chat",
        headers=_headers_auth(
            datos["usuario_a_id"], datos["usuario_a_clinica_id"], datos["usuario_a_rol"]
        ),
        json={"historial": []}
    )
    assert respuesta.status_code in (400, 422)

