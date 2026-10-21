# Guía de Agente: Arquitectura e Integración Backend-Frontend (ALMA / HorizonFlow)

Este documento es la especificación técnica completa y guía de referencia para agentes de IA y desarrolladores. Analiza exhaustivamente la arquitectura del backend (`FastAPI`), su modelo de base de datos (`PostgreSQL` / `SQLAlchemy`) y su sincronización bidireccional con el frontend (`React` + `Vite`).

---

## 1. Visión General del Sistema

**ALMA / HorizonFlow** es una plataforma SaaS de gestión clínica y soporte documental asistido por Inteligencia Artificial, diseñada específicamente para psicólogos clínicos, centros de salud mental y estudiantes de psicología en prácticas.

```mermaid
graph TD
    subgraph Frontend ["Frontend (React + Vite)"]
        UI_Dash["Dashboard.jsx"]
        UI_Pac["Pacientes.jsx"]
        UI_Cit["Citas.jsx"]
        UI_Rep["Reportes.jsx"]
        UI_Exp["Experiencia.jsx"]
        UI_Chat["Soporte ALMA (Interface.jsx)"]
        UI_Form["Formulario Público (Formulario.jsx)"]
    end

    subgraph Backend ["Backend (FastAPI)"]
        Auth["Middleware Auth JWT & CORS"]
        RouterMain["main.py (API Endpoints)"]
        GeminiEngine["Motor Gemini 2.5 Flash"]
    end

    subgraph Storage ["Persistencia"]
        DB[(PostgreSQL / SQLAlchemy)]
    end

    Frontend -- "HTTP / REST (Axios + Bearer Token)" --> Backend
    Backend --> DB
    Backend -- "Análisis DSM-5 / Sentimiento" --> GeminiEngine
```

### Stacks Tecnológicos
* **Backend**:
  * **Framework**: FastAPI (Python 3.10+)
  * **ORM & Base de Datos**: SQLAlchemy 2.0, PostgreSQL (vía `psycopg2-binary`)
  * **Seguridad**: OAuth2 Password Bearer, JWT (`python-jose`), Hashing Bcrypt (`passlib`)
  * **Inteligencia Artificial**: Google Generative AI (`gemini-2.5-flash`, `gemini-flash-latest`)
* **Frontend Relacionado**:
  * **Framework**: React 18 con Vite
  * **Estilos**: TailwindCSS
  * **Cliente HTTP**: Axios con interceptor centralizado (`api.js`)
  * **Internacionalización**: i18next (`es`, `en`, `pt`)

---

## 2. Modelo de Datos y Arquitectura Multi-Tenant

El sistema implementa una arquitectura **Multi-Tenant compartida por base de datos**, aislando la información clínica a través de la clave foránea `clinica_id`.

```mermaid
erDiagram
    Clinica ||--o{ Usuario : "emplea"
    Clinica ||--o{ Paciente : "atiende"
    Usuario ||--o{ EncuestaExperiencia : "evaluado_en"
    Paciente ||--o{ Cita : "agenda"
    Paciente ||--o{ EventoVida : "registra_hitos"
    Cita ||--o| Reporte : "genera_documento"

    Clinica {
        int id PK
        string nombre UK
    }

    Usuario {
        int id PK
        string username UK
        string hashed_password
        string rol "admin | psicologo | recepcionista"
        int clinica_id FK
        int anticipacion_alerta "24 | 48 | 72"
    }

    Paciente {
        int id PK
        string nombre
        string telefono
        string email
        int edad
        string sexo
        string estado "Activo | Inactivo"
        string diagnostico_principal
        int clinica_id FK
    }

    Cita {
        int id PK
        string motivo
        datetime fecha_cita
        string estado "Pendiente | completada | Cancelada"
        string modalidad "Presencial | Virtual"
        float tarifa
        int paciente_id FK
    }

    Reporte {
        int id PK
        text motivo_consulta
        text notas_psicologo
        string pruebas_aplicadas
        text analisis_ia
        string diagnostico_final
        text recomendaciones
        string plan_accion
        datetime fecha_generacion
        int cita_id FK,UK
    }

    EventoVida {
        int id PK
        string titulo
        string fecha_evento
        text descripcion
        string impacto "Alto | Medio | Bajo"
        string nota_titulo
        text nota_contenido
        int paciente_id FK
    }

    EncuestaExperiencia {
        int id PK
        datetime fecha_generacion
        int q1_satisfaccion_general "1 a 5 estrellas"
        string q2_cumplimiento_expectativas
        string q3_empatia_conexion
        string q4_aspectos_valorados
        int q5_instalaciones "1 a 5 estrellas"
        string q6_claridad_pautas
        string q7_impacto_animo
        string q8_confianza_seguridad
        string q9_indice_recomendacion
        text q10_comentarios
        string clasificacion_ia
        string tipo_comentario "POSITIVO | NEGATIVO | NEUTRO"
        int usuario_id FK
    }
```

### Reglas de Cascada Críticas ("Modo Thanos")
Al eliminar un paciente (`DELETE /pacientes/{paciente_id}`):
1. Se buscan todas las citas asociadas al paciente.
2. Se eliminan explícitamente los `Reportes` de cada cita.
3. Se eliminan todas las `Citas`.
4. Se eliminan todos los `EventosVida` de la línea de tiempo.
5. Se borra la entidad `Paciente`.
Todo se ejecuta bajo una transacción ACID protegida con `db.rollback()` en caso de excepción.

---

## 3. Matriz de Integración Backend <-> Frontend

A continuación se detalla cómo cada endpoint del backend se conecta con los componentes del frontend:

| Módulo | Endpoint Backend | Método | Auth | Componente Frontend | Función e Impacto en UI |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Auth** | `/login` | `POST` | No | `Login.jsx` | Valida credenciales, emite JWT (`tu_gafete_digital`). Guarda token en `localStorage`. |
| **Auth** | `/usuarios` | `POST` | No | `Login.jsx` | Registro inicial: crea clínica y usuario psicólogo administrador simultáneamente. |
| **Auth** | `/usuarios/actualizar` | `PUT` | Sí | `Ajustes.jsx` | Permite actualizar nombre de clínica y cambio seguro de contraseña (exige `password_actual`). |
| **Auth** | `/usuarios/recuperar` | `POST` | No | `Login.jsx` | Reseteo directo de contraseña mediante validación de correo registrado. |
| **Pacientes** | `/pacientes` | `GET` | Sí | `Pacientes.jsx` | Lista solo los pacientes pertenecientes a `current_user.clinica_id`. |
| **Pacientes** | `/pacientes` | `POST` | Sí | `Pacientes.jsx` | Crea nuevo expediente clínico asignando automáticamente `clinica_id`. |
| **Pacientes** | `/pacientes/{id}` | `GET` | Sí | `Pacientes.jsx` | Detalle del paciente con citas embebidas (`PacienteOut`). |
| **Pacientes** | `/pacientes/{id}` | `PUT` | Sí | `Pacientes.jsx` | Actualiza datos demográficos, contacto y diagnóstico principal. |
| **Pacientes** | `/pacientes/{id}` | `DELETE` | Sí | `Pacientes.jsx` | Borrado en cascada del paciente y todo su historial. |
| **Línea de Tiempo**| `/pacientes/{id}/eventos` | `GET` | Sí | `Pacientes.jsx` | Consulta hitos biográficos y notas de impacto emocional del paciente. |
| **Línea de Tiempo**| `/pacientes/{id}/eventos` | `POST` | Sí | `Pacientes.jsx` | Inserta evento biográfico con título, fecha, impacto y notas. |
| **Línea de Tiempo**| `/eventos/{id}` | `PUT` | Sí | `Pacientes.jsx` | Modifica hito biográfico existente. |
| **Línea de Tiempo**| `/eventos/{id}` | `DELETE` | Sí | `Pacientes.jsx` | Elimina hito de la línea de tiempo. |
| **Citas** | `/citas` | `GET` | Sí | `Citas.jsx` | Obtiene agenda completa de la clínica para pintar el calendario. |
| **Citas** | `/pacientes/{id}/citas` | `POST` | Sí | `Citas.jsx`, `Pacientes.jsx` | Agenda sesión con motivo, fecha, modalidad (Virtual/Presencial) y tarifa. |
| **Citas** | `/citas/{id}` | `PUT` | Sí | `Citas.jsx` | Reprograma cita, cambia estado o ajusta tarifa. |
| **Citas** | `/citas/{id}/completar` | `PUT` | Sí | `Citas.jsx`, `Dashboard.jsx` | Marca estado como `completada` y habilita redacción de reporte clínico. |
| **Citas** | `/citas/{id}` | `DELETE` | Sí | `Citas.jsx` | Cancela/elimina cita del calendario. |
| **Reportes e IA** | `/reportes/analizar` | `POST` | No/Opc | `Reportes.jsx` | Copiloto IA (Gemini): genera análisis DSM-5-TR / CIE-10 a partir de notas y pruebas. |
| **Reportes e IA** | `/citas/{id}/reporte` | `POST` | Sí | `Reportes.jsx` | Guarda el informe clínico final. Si activa el switch de revaluación, actualiza el diagnóstico del paciente. |
| **Reportes e IA** | `/reportes` | `GET` | Sí | `Reportes.jsx` | Consulta histórico de reportes emitidos con datos del paciente (`paciente_data`). |
| **Dashboard** | `/dashboard/agenda-hoy` | `GET` | Sí | `Dashboard.jsx` | Citas del día actual, calculando dinámicamente estado `en_curso` si ya pasó la hora. |
| **Dashboard** | `/dashboard/pacientes-activos` | `GET` | Sí | `Dashboard.jsx` | Total de pacientes, porcentaje de crecimiento mensual y distribución `MM-YYYY`. |
| **Dashboard** | `/dashboard/expedientes-pendientes` | `GET` | Sí | `Dashboard.jsx` | Detecta citas completadas hace >24h sin reporte redactado. |
| **Dashboard** | `/dashboard/alertas-inactividad` | `GET` | Sí | `Dashboard.jsx` | Pacientes sin cita futura tras 30, 45 o 60+ días de inactividad (riesgo de deserción). |
| **Dashboard** | `/dashboard/metricas-negocio` | `GET` | Sí | `Dashboard.jsx` | Ingresos del mes, % de retención recurrente y horas clínicas ahorradas. |
| **Dashboard** | `/estadisticas/motivos-distribucion` | `GET` | Sí | `Dashboard.jsx` | Top 4 motivos de consulta calculados porcentualmente sobre el total de sesiones. |
| **Alertas** | `/citas/alertas-activas` | `GET` | Sí | `CampanaAlertas.jsx` | Citas pendientes dentro del rango de anticipación configurado (ej. próximas 24h). |
| **Feedback** | `/encuestas/publica/{psicologo_id}` | `POST` | No | `Formulario.jsx` | Envío anónimo de encuesta de 10 preguntas con clasificación automática de sentimiento. |
| **Feedback** | `/encuestas` | `GET` | Sí | `Experiencia.jsx` | Muro de retroalimentación, métricas NPS y gamificación para el psicólogo. |
| **Soporte IA** | `/soporte/chat` | `POST` | No/Opc | `Interface.jsx` (Drawer lateral) | Chatbot "ALMA" asistente del sistema HorizonFlow contextualizado con las reglas clínicas. |

---

## 4. Flujos Clave de Extremo a Extremo

### Flujo 1: Agendamiento, Cierre de Sesión y Generación de Reporte Asistido por IA

```mermaid
sequenceDiagram
    autonumber
    actor Psicologo as Psicólogo (Frontend)
    participant UI as Citas.jsx / Reportes.jsx
    participant API as FastAPI (main.py)
    participant Gemini as Google Gemini 2.5 Flash
    participant DB as PostgreSQL

    Psicologo->>UI: Marca cita como "Completada"
    UI->>API: PUT /citas/{cita_id}/completar
    API->>DB: UPDATE citas SET estado='completada'
    API-->>UI: Confirmación de éxito
    UI->>Psicologo: Redirige al Wizard de Reporte Clínico
    Psicologo->>UI: Ingresa notas de sesión y pruebas (BDI-II, etc.)
    Psicologo->>UI: Clic en "Generar Análisis Clínico con IA"
    UI->>API: POST /reportes/analizar (AnalisisIARequest)
    API->>Gemini: Prompt de Neuropsicólogo Clínico Senior (DSM-5-TR / CIE-10)
    Gemini-->>API: Análisis en Markdown estructurado
    API-->>UI: {"analisis": "## 🔍 INTERPRETACIÓN..."}
    UI->>Psicologo: Muestra borrador editable en pantalla
    Psicologo->>UI: Agrega diagnóstico final y activa switch "Actualizar perfil de paciente"
    UI->>API: POST /citas/{cita_id}/reporte (ReporteCreate)
    API->>DB: INSERT INTO reportes (...)
    API->>DB: UPDATE pacientes SET diagnostico_principal=...
    API-->>UI: ReporteOut con paciente_data
    UI->>Psicologo: Reporte guardado y opción de exportar a PDF/Word
```

### Flujo 2: Encuesta Pública y Análisis de Sentimiento con Detección de Sarcasmo

```mermaid
sequenceDiagram
    autonumber
    actor Paciente as Paciente
    participant Form as Formulario.jsx (Público)
    participant API as FastAPI (/encuestas/publica/{id})
    participant Gemini as Gemini Flash (Sentimiento)
    participant DB as PostgreSQL

    Paciente->>Form: Llena 10 preguntas + comentario abierto
    Form->>API: POST /encuestas/publica/{psicologo_id} (EncuestaCreate)
    alt Comentario no vacío (>3 caracteres)
        API->>Gemini: Clasificar comentario ("POSITIVO", "NEGATIVO", "NEUTRO")
        Gemini-->>API: Etiqueta textual
        alt Etiqueta es "POSITIVO" pero q1_satisfaccion <= 3 estrellas
            Note over API: Detección de Sarcasmo / Contradicción
            API->>API: Forzar clasificación = "NEGATIVO"
        end
    else Comentario vacío o muy corto
        API->>API: Asignar "NEUTRO" directamente
    end
    API->>DB: INSERT INTO encuestas_experiencia (...)
    API-->>Form: {"mensaje": "Feedback guardado con éxito"}
    Form->>Paciente: Pantalla de agradecimiento
```

---

## 5. Especificaciones de Lógica de Negocio Crítica

### A. Alertas de Inactividad y Riesgo de Abandono
Calculadas en `GET /dashboard/alertas-inactividad`:
* Se evalúan pacientes que tienen al menos una cita pasada y **ninguna cita futura agendada**.
* Días de inactividad: `(hoy - fecha_ultima_cita).days`.
* Segmentación con estilos Tailwind:
  * `>= 60 días`: Color crítico (`text-rose-600`, `bg-rose-50`).
  * `45 a 59 días`: Alerta preventiva (`text-amber-600`, `bg-amber-50`).
  * `30 a 44 días`: Seguimiento inicial (`text-slate-500`, `bg-slate-100`).

### B. Detección de Expedientes Clínicos Vulnerables
Calculado en `GET /dashboard/expedientes-pendientes`:
* Identifica citas marcadas como `completada` cuya fecha ocurrió hace más de **24 horas** pero que **no poseen ningún registro en la tabla `reportes`**.
* Alerta al profesional en el Dashboard principal para evitar atrasos médico-legales.

### C. Métricas de Salud del Negocio
Calculadas en `GET /dashboard/metricas-negocio`:
* **Ingresos**: Suma de `cita.tarifa` de citas del mes actual comparadas porcentualmente contra el mes anterior.
* **Tasa de Retención**: Proporción de pacientes que han asistido a más de 1 sesión sobre el total de pacientes con citas registradas:
  $$\text{Tasa de Retención} = \left(\frac{\text{Pacientes Recurrentes}}{\text{Total Pacientes Atendidos}}\right) \times 100$$
* **Horas Ahorradas**: Tiempo clínico recuperado gracias a la automatización documental:
  $$\text{Horas Ahorradas} = \frac{\text{Citas Completadas} \times 15\text{ minutos}}{60}$$

### D. Prompt Engineering del Copiloto Neuropsicológico
En `POST /reportes/analizar`:
* Modelo: `gemini-2.5-flash`.
* Rol asignado: *Neuropsicólogo clínico senior y supervisor de casos con 20 años de experiencia*.
* Parámetros obligatorios: DSM-5-TR con equivalencias internacionales CIE-10 (ej: `296.99 (F34.8)`).
* Salida estructurada estricta:
  1. `## 🔍 Interpretación Clínica y Sintomatológica`
  2. `## ⚖️ Diagnóstico Diferencial (Descartes necesarios)`
  3. `## 🧠 Hipótesis Diagnósticas (Códigos DSM-5-TR y CIE-10)`
* Prohibiciones: Cero redundancia ("efecto loro"), sin repetir edad o datos demográficos; no sugerir tratamientos (enfoque exclusivamente evaluativo y diagnóstico).

---

## 6. Configuración de Entorno y Ejecución

### Variables de Entorno Requeridas (`.env`)
```ini
DATABASE_URL=postgresql://usuario:password@localhost:5432/alma_db
SECRET_KEY=clave_secreta_para_firmar_jwt
ALGORITHM=HS256
GEMINI_API_KEY=AIzaSy...tu_api_key_de_google_gemini
```

### Comandos de Ejecución
```powershell
# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Iniciar servidor de desarrollo FastAPI
uvicorn main:app --reload --port 8000
```

---

## 7. Reglas para Agentes de Código

1. **Aislamiento Multi-Tenant Estricto**:
   * Nunca omitir el filtro `models.Paciente.clinica_id == current_user.clinica_id` en endpoints que retornen o modifiquen información clínica de pacientes, citas o reportes.
2. **Consistencia de Estados de Citas**:
   * Los estados válidos en frontend y backend son `"Pendiente"`, `"completada"` y `"Cancelada"`. Prestar atención a las mayúsculas/minúsculas al filtrar con `.notin_()` o `.lower()`.
3. **Manejo Atómico de Transacciones**:
   * Toda operación que afecte múltiples tablas (como el borrado de pacientes o la creación de reportes con actualización de diagnóstico) debe utilizar bloques `try/except` con `db.rollback()` ante cualquier falla.
4. **Resiliencia de la API de IA**:
   * Si las llamadas a Gemini fallan por límite de cuota o conectividad en encuestas o soporte, el backend debe degradar ordenadamente a respuestas seguras por defecto (`NEUTRO` en encuestas) sin romper el flujo del usuario.
5. **Preguntas logicas**:
    * 5 preguntas y logicas y coherentes que ayuden a mejorar cambios significativos como mejoras en la iterface funcionalidades y otros procesos.

