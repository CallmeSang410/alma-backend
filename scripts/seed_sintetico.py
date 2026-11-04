"""
Script de Seeding de Datos Sintéticos para HorizonFlow (DATA-01).
Genera exactamente:
- 2 Tenants (Clínicas)
- 4 Usuarios
- 15 Pacientes
- 30 Citas
- 8 Reportes / Notas clínicas sintéticas
Garantiza idempotencia y aislamiento sin datos personales reales.
"""
import os
import sys
from datetime import datetime, timedelta

# Asegurar path para importar modelos y base de datos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def ejecutar_seeder(db_url: str = "sqlite:///seed_sintetico_qa.db", limpiar_primero: bool = True):
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    Session = sessionmaker(bind=engine)
    db = Session()

    if limpiar_primero:
        models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)

    try:
        # 1. Crear 2 Tenants (Clínicas)
        clinicas_existentes = db.query(models.Clinica).count()
        if clinicas_existentes == 0:
            c1 = models.Clinica(nombre="Consultorio San Rafael QA", codigo_invitacion="ALMA-SR001")
            c2 = models.Clinica(nombre="Centro Psicológico Esperanza QA", codigo_invitacion="ALMA-CP002")
            db.add_all([c1, c2])
            db.commit()
            db.refresh(c1)
            db.refresh(c2)
        else:
            c1, c2 = db.query(models.Clinica).limit(2).all()

        # 2. Crear 4 Usuarios (2 por clínica: 1 psicólogo y 1 estudiante/admin)
        usuarios_existentes = db.query(models.Usuario).count()
        if usuarios_existentes == 0:
            hash_pass = pwd_context.hash("Password123!")
            u1 = models.Usuario(username="dr.alvarez@sanrafael-qa.com", hashed_password=hash_pass, rol="psicologo", clinica_id=c1.id)
            u2 = models.Usuario(username="lic.morales@sanrafael-qa.com", hashed_password=hash_pass, rol="estudiante", clinica_id=c1.id)
            u3 = models.Usuario(username="dra.rodriguez@esperanza-qa.com", hashed_password=hash_pass, rol="psicologo", clinica_id=c2.id)
            u4 = models.Usuario(username="admin@esperanza-qa.com", hashed_password=hash_pass, rol="admin", clinica_id=c2.id)
            db.add_all([u1, u2, u3, u4])
            db.commit()

        # 3. Crear 15 Pacientes (8 en c1, 7 en c2)
        pacientes_existentes = db.query(models.Paciente).count()
        if pacientes_existentes == 0:
            pacientes_c1 = []
            for i in range(1, 9):
                pacientes_c1.append(models.Paciente(
                    nombre=f"Paciente Sintético C1-{i:02d}",
                    folio_visual=i,
                    clinica_id=c1.id,
                    estado="Activo",
                    edad=20 + i * 3,
                    sexo="M" if i % 2 == 0 else "F",
                    diagnostico_principal="Ansiedad generalizada" if i % 2 == 0 else "Depresión moderada"
                ))
            pacientes_c2 = []
            for i in range(1, 8):
                pacientes_c2.append(models.Paciente(
                    nombre=f"Paciente Sintético C2-{i:02d}",
                    folio_visual=i,
                    clinica_id=c2.id,
                    estado="Activo",
                    edad=18 + i * 4,
                    sexo="F" if i % 2 == 0 else "M",
                    diagnostico_principal="Estrés postraumático" if i % 2 == 0 else "Duelo prolongado"
                ))
            db.add_all(pacientes_c1 + pacientes_c2)
            db.commit()

        pacientes = db.query(models.Paciente).all()

        # 4. Crear 30 Citas (2 por cada paciente)
        citas_existentes = db.query(models.Cita).count()
        if citas_existentes == 0:
            citas = []
            base_fecha = datetime.now()
            for idx, p in enumerate(pacientes):
                c1_fecha = base_fecha + timedelta(days=idx + 1, hours=9)
                c2_fecha = base_fecha + timedelta(days=idx + 8, hours=11)

                citas.append(models.Cita(
                    motivo=f"Sesión Inicial Diagnóstica #{idx+1}",
                    fecha_cita=c1_fecha,
                    estado="completada" if idx < 8 else "Pendiente",
                    modalidad="Presencial",
                    tarifa=450.0,
                    paciente_id=p.id
                ))
                citas.append(models.Cita(
                    motivo=f"Sesión de Seguimiento #{idx+1}",
                    fecha_cita=c2_fecha,
                    estado="Pendiente",
                    modalidad="Virtual",
                    tarifa=400.0,
                    paciente_id=p.id
                ))
            db.add_all(citas)
            db.commit()

        citas_completadas = db.query(models.Cita).filter(models.Cita.estado == "completada").all()

        # 5. Crear 8 Reportes Clínicos (asociados a las primeras 8 citas completadas)
        reportes_existentes = db.query(models.Reporte).count()
        if reportes_existentes == 0:
            reportes = []
            for idx, c in enumerate(citas_completadas[:8]):
                reportes.append(models.Reporte(
                    motivo_consulta=f"Motivo de consulta sintético #{idx+1}",
                    notas_psicologo=f"Notas clínicas estructuradas para caso sintético #{idx+1}. Buena evolución.",
                    pruebas_aplicadas="BDI-II, GAD-7",
                    analisis_ia=f"Impresión diagnóstica generada para caso #{idx+1}.",
                    diagnostico_final="F41.1 Trastorno de Ansiedad Generalizada",
                    recomendaciones="Continuar psicoterapia cognitivo-conductual semanal.",
                    plan_accion="10 sesiones semanales",
                    cita_id=c.id
                ))
            db.add_all(reportes)
            db.commit()

        # Validación final de conteos
        conteos = {
            "tenants": db.query(models.Clinica).count(),
            "usuarios": db.query(models.Usuario).count(),
            "pacientes": db.query(models.Paciente).count(),
            "citas": db.query(models.Cita).count(),
            "reportes": db.query(models.Reporte).count(),
        }

        print("--- RESULTADO DEL SEEDING SINTÉTICO (DATA-01) ---")
        for k, v in conteos.items():
            print(f"- {k.capitalize()}: {v}")

        assert conteos["tenants"] == 2, f"Esperado 2 tenants, obtenido {conteos['tenants']}"
        assert conteos["usuarios"] == 4, f"Esperado 4 usuarios, obtenido {conteos['usuarios']}"
        assert conteos["pacientes"] == 15, f"Esperado 15 pacientes, obtenido {conteos['pacientes']}"
        assert conteos["citas"] == 30, f"Esperado 30 citas, obtenido {conteos['citas']}"
        assert conteos["reportes"] == 8, f"Esperado 8 reportes, obtenido {conteos['reportes']}"
        print(">> VERIFICACIÓN DATA-01 EXITOSA: Todos los conteos son exactos.")

        return conteos

    finally:
        db.close()


if __name__ == "__main__":
    ejecutar_seeder()

