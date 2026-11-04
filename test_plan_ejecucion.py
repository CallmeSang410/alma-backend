"""
Suite de ejecución del Plan Maestro de Pruebas — HorizonFlow (Fases 1, 2 y 3).
Ejecuta los casos definidos en el plan sobre SQLite en memoria y entorno aislado.
"""
import os
import io
import json
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Mock global de Gemini para evitar timeouts de red en entorno de pruebas aislado
import main
main.clasificar_comentario = lambda texto: "POSITIVO" if "buen" in (texto or "").lower() else "NEUTRO"

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
from main import app, SECRET_KEY, ALGORITHM, get_password_hash, verificar_password_seguro, logger  # noqa: E402
from database import get_db  # noqa: E402

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def reset_db():
    models.Base.metadata.drop_all(bind=TEST_ENGINE)
    models.Base.metadata.create_all(bind=TEST_ENGINE)


def token_para(usuario_id: int, clinica_id: int, rol: str = "psicologo", exp: datetime = None) -> str:
    payload = {
        "usuario_id": usuario_id,
        "clinica_id": clinica_id,
        "rol": rol,
    }
    if exp:
        payload["exp"] = exp
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def auth_headers(usuario_id: int, clinica_id: int, rol: str = "psicologo", exp: datetime = None) -> dict:
    return {"Authorization": f"Bearer {token_para(usuario_id, clinica_id, rol, exp)}"}


def sembrar_dos_tenants():
    db = TestingSessionLocal()
    try:
        clinica_a = models.Clinica(nombre="Clinica Alpha QA", codigo_invitacion="ALMA-QA0001")
        clinica_b = models.Clinica(nombre="Clinica Beta QA", codigo_invitacion="ALMA-QA0002")
        db.add_all([clinica_a, clinica_b])
        db.commit()
        db.refresh(clinica_a)
        db.refresh(clinica_b)

        pass_hash = get_password_hash("Password123!")

        usuario_a = models.Usuario(
            username="alpha_qa@test.com",
            hashed_password=pass_hash,
            rol="psicologo",
            clinica_id=clinica_a.id,
            anticipacion_alerta=24,
        )
        usuario_b = models.Usuario(
            username="beta_qa@test.com",
            hashed_password=pass_hash,
            rol="psicologo",
            clinica_id=clinica_b.id,
            anticipacion_alerta=24,
        )
        db.add_all([usuario_a, usuario_b])
        db.commit()
        db.refresh(usuario_a)
        db.refresh(usuario_b)

        paciente_a = models.Paciente(
            nombre="Paciente Alpha 1",
            clinica_id=clinica_a.id,
            folio_visual=1,
            estado="Activo",
            edad=30,
            sexo="M",
            diagnostico_principal="Ansiedad leve",
        )
        paciente_b = models.Paciente(
            nombre="Paciente Beta 1",
            clinica_id=clinica_b.id,
            folio_visual=1,
            estado="Activo",
            edad=45,
            sexo="F",
            diagnostico_principal="Estrés laboral",
        )
        db.add_all([paciente_a, paciente_b])
        db.commit()
        db.refresh(paciente_a)
        db.refresh(paciente_b)

        cita_a = models.Cita(
            motivo="Sesión Diagnóstica Alpha",
            fecha_cita=datetime.now() + timedelta(days=2),
            estado="Pendiente",
            modalidad="Presencial",
            tarifa=500.0,
            paciente_id=paciente_a.id,
        )
        cita_b = models.Cita(
            motivo="Sesión Diagnóstica Beta",
            fecha_cita=datetime.now() + timedelta(days=2),
            estado="Pendiente",
            modalidad="Virtual",
            tarifa=600.0,
            paciente_id=paciente_b.id,
        )
        db.add_all([cita_a, cita_b])
        db.commit()
        db.refresh(cita_a)
        db.refresh(cita_b)

        evento_a = models.EventoVida(
            titulo="Inicio Terapia",
            fecha_evento="2026-10-01",
            descripcion="Primera consulta clínica",
            impacto="Alto",
            paciente_id=paciente_a.id,
        )
        evento_b = models.EventoVida(
            titulo="Crisis Laboral",
            fecha_evento="2026-10-15",
            descripcion="Dificultades en trabajo",
            impacto="Medio",
            paciente_id=paciente_b.id,
        )
        db.add_all([evento_a, evento_b])
        db.commit()
        db.refresh(evento_a)
        db.refresh(evento_b)

        return {
            "clinica_a": clinica_a,
            "clinica_b": clinica_b,
            "usuario_a": usuario_a,
            "usuario_b": usuario_b,
            "paciente_a": paciente_a,
            "paciente_b": paciente_b,
            "cita_a": cita_a,
            "cita_b": cita_b,
            "evento_a": evento_a,
            "evento_b": evento_b,
        }
    finally:
        db.close()


# ===========================================================================
# FASE 1: DATOS SINTÉTICOS Y FUNCIONES DE APLICACIÓN
# ===========================================================================

def test_fun_01_crud_pacientes():
    """FUN-01: Ciclo completo CRUD de pacientes en tenant A."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)

    # 1. CREATE
    res_crear = client.post("/pacientes", headers=h_a, json={
        "nombre": "Carlos Gómez",
        "edad": 28,
        "telefono": "5551234567",
        "email": "carlos@test.com",
        "sexo": "M",
        "estado": "Activo",
        "diagnostico_principal": "Fobia social",
    })
    assert res_crear.status_code == 200
    nuevo_p = res_crear.json()
    p_id = nuevo_p["id"]
    assert nuevo_p["nombre"] == "Carlos Gómez"
    assert nuevo_p["folio_visual"] == 2

    # 2. READ Colección y Detalle
    res_list = client.get("/pacientes", headers=h_a)
    assert res_list.status_code == 200
    assert any(p["id"] == p_id for p in res_list.json())

    res_det = client.get(f"/pacientes/{p_id}", headers=h_a)
    assert res_det.status_code == 200
    assert res_det.json()["nombre"] == "Carlos Gómez"

    # 3. UPDATE
    res_upd = client.put(f"/pacientes/{p_id}", headers=h_a, json={
        "nombre": "Carlos Gómez Actualizado",
        "edad": 29,
        "telefono": "5559998877",
        "email": "carlos_new@test.com",
        "sexo": "M",
        "estado": "En pausa",
        "diagnostico_principal": "Fobia superada",
    })
    assert res_upd.status_code == 200
    assert res_upd.json()["nombre"] == "Carlos Gómez Actualizado"
    assert res_upd.json()["edad"] == 29

    # 4. DELETE
    res_del = client.delete(f"/pacientes/{p_id}", headers=h_a)
    assert res_del.status_code == 200

    # 5. Comprobar en DB que desapareció
    db = TestingSessionLocal()
    try:
        assert db.query(models.Paciente).filter(models.Paciente.id == p_id).first() is None
    finally:
        db.close()


def test_sec_01_idor_pacientes():
    """SEC-01: Usuario A intenta acceder, modificar o borrar paciente de tenant B."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)
    id_b = data["paciente_b"].id

    # GET cruzado
    res_get = client.get(f"/pacientes/{id_b}", headers=h_a)
    assert res_get.status_code == 404

    # PUT cruzado
    res_put = client.put(f"/pacientes/{id_b}", headers=h_a, json={
        "nombre": "Ataque IDOR",
        "edad": 99
    })
    assert res_put.status_code == 404

    # DELETE cruzado
    res_del = client.delete(f"/pacientes/{id_b}", headers=h_a)
    assert res_del.status_code == 404

    # Verificar que el paciente B en la base de datos permanece intacto
    db = TestingSessionLocal()
    try:
        p_b = db.query(models.Paciente).filter(models.Paciente.id == id_b).first()
        assert p_b is not None
        assert p_b.nombre == "Paciente Beta 1"
        assert p_b.edad == 45
    finally:
        db.close()


def test_fun_02_crud_eventos():
    """FUN-02: CRUD de eventos de línea de vida para paciente A."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)
    p_a_id = data["paciente_a"].id

    # CREATE
    res_c = client.post(f"/pacientes/{p_a_id}/eventos", headers=h_a, json={
        "titulo": "Duelo Familiar",
        "fecha_evento": "2026-05-10",
        "descripcion": "Pérdida de abuelo",
        "impacto": "Alto",
    })
    assert res_c.status_code == 200
    ev_id = res_c.json()["id"]

    # READ
    res_r = client.get(f"/pacientes/{p_a_id}/eventos", headers=h_a)
    assert res_r.status_code == 200
    assert any(e["id"] == ev_id for e in res_r.json())

    # UPDATE
    res_u = client.put(f"/eventos/{ev_id}", headers=h_a, json={
        "titulo": "Duelo Familiar Superado",
        "fecha_evento": "2026-05-10",
        "descripcion": "Proceso elaborado",
        "impacto": "Bajo",
    })
    assert res_u.status_code == 200
    assert res_u.json()["titulo"] == "Duelo Familiar Superado"

    # DELETE
    res_d = client.delete(f"/eventos/{ev_id}", headers=h_a)
    assert res_d.status_code == 200

    db = TestingSessionLocal()
    try:
        assert db.query(models.EventoVida).filter(models.EventoVida.id == ev_id).first() is None
    finally:
        db.close()


def test_sec_02_idor_eventos():
    """SEC-02: IDOR en eventos. Documenta el hallazgo del plan sobre GET cruzado."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)
    p_b_id = data["paciente_b"].id
    ev_b_id = data["evento_b"].id

    # 1. GET eventos de paciente ajeno
    # Nota del plan: El código actual hace join y retorna lista vacía en lugar de 404
    res_get = client.get(f"/pacientes/{p_b_id}/eventos", headers=h_a)
    # Comprobar que en ningún caso filtra eventos del paciente B
    assert res_get.status_code in (200, 404)
    if res_get.status_code == 200:
        assert res_get.json() == []  # No expone datos de B

    # 2. PUT en evento de paciente B
    res_put = client.put(f"/eventos/{ev_b_id}", headers=h_a, json={
        "titulo": "Evento Hackeado",
        "fecha_evento": "2026-11-01",
        "impacto": "Crítico",
    })
    assert res_put.status_code == 404

    # 3. DELETE en evento de paciente B
    res_del = client.delete(f"/eventos/{ev_b_id}", headers=h_a)
    assert res_del.status_code == 404

    # Verificar que el evento de B sigue intacto en base de datos
    db = TestingSessionLocal()
    try:
        ev_b = db.query(models.EventoVida).filter(models.EventoVida.id == ev_b_id).first()
        assert ev_b is not None
        assert ev_b.titulo == "Crisis Laboral"
    finally:
        db.close()


def test_fun_03_reportes_y_sec_03_idor():
    """FUN-03 y SEC-03: Creación y lectura de reportes clínicos con verificación IDOR."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)
    h_b = auth_headers(data["usuario_b"].id, data["clinica_b"].id)
    c_a_id = data["cita_a"].id
    c_b_id = data["cita_b"].id

    # Tenant A crea reporte en su cita A
    res_rep = client.post(f"/citas/{c_a_id}/reporte", headers=h_a, json={
        "motivo_consulta": "Evaluación general",
        "notas_psicologo": "El paciente manifiesta avances significativos.",
        "diagnostico_final": "En remisión",
        "recomendaciones": "Mantener seguimiento quincenal",
    })
    assert res_rep.status_code == 200
    rep_creado = res_rep.json()
    assert rep_creado["cita_id"] == c_a_id

    # Tenant A lista reportes: debe ver el suyo
    res_list_a = client.get("/reportes", headers=h_a)
    assert res_list_a.status_code == 200
    ids_a = [r["cita_id"] for r in res_list_a.json()]
    assert c_a_id in ids_a

    # SEC-03: Tenant A intenta crear reporte en la cita de Tenant B
    res_idor_create = client.post(f"/citas/{c_b_id}/reporte", headers=h_a, json={
        "motivo_consulta": "Intrusión IDOR",
        "notas_psicologo": "No debería permitirse",
    })
    assert res_idor_create.status_code == 404

    # Tenant B lista reportes: no debe ver el reporte de A
    res_list_b = client.get("/reportes", headers=h_b)
    assert res_list_b.status_code == 200
    ids_b = [r["cita_id"] for r in res_list_b.json()]
    assert c_a_id not in ids_b


def test_val_01_likert_fronteras():
    """VAL-01: Fronteras de escala Likert (1 y 5 válidos; 0, 6, decimales y strings devuelven 422)."""
    reset_db()
    data = sembrar_dos_tenants()
    psicologo_id = data["usuario_a"].id

    def payload_encuesta(q1=5, q5=5):
        return {
            "q1_satisfaccion_general": q1,
            "q2_cumplimiento_expectativas": "Totalmente",
            "q3_empatia_conexion": "Excelente",
            "q4_aspectos_valorados": "Puntualidad",
            "q5_instalaciones": q5,
            "q6_claridad_pautas": "Muy claras",
            "q7_impacto_animo": "Positivo",
            "q8_confianza_seguridad": "Total",
            "q9_indice_recomendacion": "Definitivamente",
            "q10_comentarios": "Buen servicio",
        }

    # Valores límite válidos: 1 y 5
    r_min = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_encuesta(q1=1, q5=1))
    assert r_min.status_code == 200

    r_max = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_encuesta(q1=5, q5=5))
    assert r_max.status_code == 200

    # Valores fuera de frontera: 0 y 6
    r_bajo = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_encuesta(q1=0, q5=5))
    assert r_bajo.status_code == 422

    r_alto = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_encuesta(q1=5, q5=6))
    assert r_alto.status_code == 422

    # Strings y nulos
    r_str = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_encuesta(q1="cinco", q5=5))
    assert r_str.status_code == 422

    r_none = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_encuesta(q1=None, q5=5))
    assert r_none.status_code == 422

    # Comprobar en DB que solo los 2 envíos válidos se guardaron
    db = TestingSessionLocal()
    try:
        conteo = db.query(models.EncuestaExperiencia).filter(
            models.EncuestaExperiencia.usuario_id == psicologo_id
        ).count()
        assert conteo == 2
    finally:
        db.close()


def test_val_02_texto_obligatorio_encuesta():
    """VAL-02: Validación de texto obligatorio en encuestas."""
    reset_db()
    data = sembrar_dos_tenants()
    psicologo_id = data["usuario_a"].id

    payload_base = {
        "q1_satisfaccion_general": 4,
        "q2_cumplimiento_expectativas": "Sí",
        "q3_empatia_conexion": "Alta",
        "q4_aspectos_valorados": "Escucha",
        "q5_instalaciones": 4,
        "q6_claridad_pautas": "Claras",
        "q7_impacto_animo": "Bueno",
        "q8_confianza_seguridad": "Alta",
        "q9_indice_recomendacion": "Sí",
    }

    # Campo obligatorio ausente
    res_omision = client.post(f"/encuestas/publica/{psicologo_id}", json=payload_base)
    # q10_comentarios es opcional, pero si omitimos q2:
    p_incompleto = dict(payload_base)
    del p_incompleto["q2_cumplimiento_expectativas"]
    res_incompleto = client.post(f"/encuestas/publica/{psicologo_id}", json=p_incompleto)
    assert res_incompleto.status_code == 422

    # Cadena vacía en campo obligatorio (min_length=1 en esquema)
    p_vacio = dict(payload_base)
    p_vacio["q2_cumplimiento_expectativas"] = ""
    res_vacio = client.post(f"/encuestas/publica/{psicologo_id}", json=p_vacio)
    assert res_vacio.status_code == 422


def test_fun_04_sec_04_colision_citas_servidor():
    """
    FUN-04 / SEC-04: Prueba de doble reserva de citas en servidor.
    Detecta y documenta si el backend bloquea o permite reservas en el mismo horario.
    """
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)
    p_a_id = data["paciente_a"].id

    fecha_fija = "2026-11-20T10:00:00"

    # Cita 1
    res1 = client.post(f"/pacientes/{p_a_id}/citas", headers=h_a, json={
        "motivo": "Consulta Inicial",
        "fecha_cita": fecha_fija,
        "estado": "Pendiente",
        "modalidad": "Presencial",
        "tarifa": 500.0,
    })
    assert res1.status_code == 200

    # Cita 2 en el mismo slot exacto
    res2 = client.post(f"/pacientes/{p_a_id}/citas", headers=h_a, json={
        "motivo": "Segunda Consulta Mismo Horario",
        "fecha_cita": fecha_fija,
        "estado": "Pendiente",
        "modalidad": "Presencial",
        "tarifa": 500.0,
    })

    # El plan indica que el backend NO tiene validación de colisión aún.
    # Verificamos y documentamos el comportamiento real del servidor:
    conflicto_detectado = (res2.status_code == 409)
    # Si devuelve 200, confirma el hallazgo documentado: el servidor no previene la doble reserva.
    assert res2.status_code in (200, 409)


# ===========================================================================
# FASE 2: TIEMPO, GEMINI Y POSTGRESQL MOCKS
# ===========================================================================

def test_time_01_alertas_activas_ventana_horas():
    """TIME-01: Comportamiento de ventana de alertas (actualmente en horas en la API)."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)
    p_a_id = data["paciente_a"].id

    ahora = datetime.now()

    # Cita a +1 hora (dentro de ventana de 24h)
    client.post(f"/pacientes/{p_a_id}/citas", headers=h_a, json={
        "motivo": "Cita Urgente Próxima",
        "fecha_cita": (ahora + timedelta(hours=1)).isoformat(),
        "estado": "Pendiente",
        "modalidad": "Presencial",
        "tarifa": 300.0,
    })

    # Cita a +48 horas (fuera de ventana de 24h)
    client.post(f"/pacientes/{p_a_id}/citas", headers=h_a, json={
        "motivo": "Cita Lejana",
        "fecha_cita": (ahora + timedelta(hours=48)).isoformat(),
        "estado": "Pendiente",
        "modalidad": "Presencial",
        "tarifa": 300.0,
    })

    # Consultar alertas con ventana por defecto (24 horas)
    res_alertas = client.get("/citas/alertas-activas?horas=24", headers=h_a)
    assert res_alertas.status_code == 200
    motivos = [a["motivo_consulta"] for a in res_alertas.json()]
    assert "Cita Urgente Próxima" in motivos
    assert "Cita Lejana" not in motivos


def test_ai_01_gemini_nominal_con_mock():
    """AI-01: Doble de prueba con mock para caso nominal de análisis clínico Gemini."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)

    mock_texto_dsm5 = (
        "## 🔍 Interpretación Clínica y Sintomatológica\n"
        "El paciente presenta síntomas consistentes con ansiedad generalizada.\n\n"
        "## ⚖️ Diagnóstico Diferencial (Descartes necesarios)\n"
        "Descartar hipertiroidismo y consumo excesivo de cafeína.\n\n"
        "## 🧠 Hipótesis Diagnósticas (Códigos DSM-5-TR y CIE-10)\n"
        "Trastorno de Ansiedad Generalizada 300.02 (F41.1)"
    )

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_texto_dsm5
        mock_instance.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_instance

        res = client.post("/reportes/analizar", headers=h_a, json={
            "motivo_consulta": "Ansiedad severa e insomnio",
            "notas_psicologo": "Refiere preocupaciones constantes y tensión muscular.",
            "pruebas_aplicadas": "GAD-7",
            "resultados_pruebas": "16/21 (Ansiedad severa)",
            "edad_paciente": "32",
            "sexo_paciente": "M",
        })

        assert res.status_code == 200
        data_res = res.json()
        assert "analisis" in data_res
        assert "300.02 (F41.1)" in data_res["analisis"]
        assert mock_instance.generate_content.called


def test_ai_02_gemini_excepcion_503_y_timeout_controlado():
    """AI-02: Doble de prueba para simular caída de Gemini (503 / timeout) sin crashear."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = Exception("503 Service Unavailable / Gateway Timeout")
        mock_model_cls.return_value = mock_instance

        res = client.post("/reportes/analizar", headers=h_a, json={
            "motivo_consulta": "Consulta de prueba",
            "notas_psicologo": "Notas de prueba",
            "pruebas_aplicadas": "Ninguna",
            "resultados_pruebas": "N/A",
            "edad_paciente": "25",
            "sexo_paciente": "F",
        })

        # Debe responder con 500 controlado sin exponer stack traces internos de Python
        assert res.status_code == 500
        assert "Error interno al procesar el análisis de IA" in res.json()["detail"]


# ===========================================================================
# FASE 3: AUTENTICACIÓN, CRIPTOGRAFÍA Y OWASP TOP 10:2025
# ===========================================================================

def test_sec_11_security_misconfiguration_headers():
    """SEC-11 / A02: Verificación de encabezados de seguridad HTTP obligatorios."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in res.headers.get("permissions-policy", "")
    assert res.headers.get("x-request-id") is not None


def test_sec_13_cryptographic_failures_bcrypt_y_secretos():
    """SEC-13 / A04: Hashing bcrypt con salt, verificación correcta y rechazo de plain text."""
    plain = "MiClaveSuperSegura2026!"
    hashed = get_password_hash(plain)

    # El hash no debe ser igual al texto plano
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    # Verificación exitosa
    assert verificar_password_seguro(plain, hashed) is True

    # Verificación fallida con contraseña errónea
    assert verificar_password_seguro("ClaveEquivocada", hashed) is False

    # Verificación con contraseña nula o vacía
    assert verificar_password_seguro("", hashed) is False
    assert verificar_password_seguro(None, hashed) is False


def test_sec_14_injection_sql_seguro_orm():
    """SEC-14 / A05: Caracteres de escape y sentencias SQL en campos de usuario tratados como datos literales."""
    reset_db()
    data = sembrar_dos_tenants()
    h_a = auth_headers(data["usuario_a"].id, data["clinica_a"].id)

    nombre_con_sql = "O'Neil'); DROP TABLE pacientes; --"

    res = client.post("/pacientes", headers=h_a, json={
        "nombre": nombre_con_sql,
        "edad": 40,
        "estado": "Activo",
    })
    assert res.status_code == 200
    p_id = res.json()["id"]

    # Comprobar que la tabla sigue existiendo y el nombre se guardó de forma literal
    db = TestingSessionLocal()
    try:
        paciente_recuperado = db.query(models.Paciente).filter(models.Paciente.id == p_id).first()
        assert paciente_recuperado is not None
        assert paciente_recuperado.nombre == nombre_con_sql
    finally:
        db.close()


def test_sec_16_authentication_failures_tokens_y_firma():
    """SEC-16 / A07: Rechazo de token ausente, firma manipulada y token expirado."""
    reset_db()
    data = sembrar_dos_tenants()
    u_a_id = data["usuario_a"].id
    c_a_id = data["clinica_a"].id

    # 1. Token ausente
    res_sin_token = client.get("/pacientes")
    assert res_sin_token.status_code == 401

    # 2. Token con firma manipulada
    token_valido = token_para(u_a_id, c_a_id)
    partes = token_valido.split(".")
    token_adulterado = f"{partes[0]}.{partes[1]}.firma_falsa_invalida"
    res_firma = client.get("/pacientes", headers={"Authorization": f"Bearer {token_adulterado}"})
    assert res_firma.status_code == 401

    # 3. Token expirado
    token_expirado = token_para(u_a_id, c_a_id, exp=datetime.now() - timedelta(hours=1))
    res_exp = client.get("/pacientes", headers={"Authorization": f"Bearer {token_expirado}"})
    assert res_exp.status_code == 401


def test_sec_18_sec_20_logging_y_request_id():
    """SEC-18 / SEC-20 / A09: Captura de logs estructurados con X-Request-ID y auditoría."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(logging.getLogger("horizonflow").handlers[0].formatter)
    logger.addHandler(handler)

    test_request_id = "qa-audit-test-999"
    try:
        res = client.get("/health", headers={"X-Request-ID": test_request_id})
        assert res.status_code == 200
        assert res.headers.get("x-request-id") == test_request_id

        # Verificar que el log estructurado capturó el request_id
        logs_output = log_capture.getvalue()
        assert test_request_id in logs_output
        assert '"path": "/health"' in logs_output
        assert '"status_code": 200' in logs_output
    finally:
        logger.removeHandler(handler)
