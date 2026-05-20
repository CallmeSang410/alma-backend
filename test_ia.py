import os
from dotenv import load_dotenv
import google.generativeai as genai
import json

load_dotenv()
# Pon tu clave real aquí
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

#print("Buscando modelos disponibles para tu cuenta...")
#print("-" * 30)

# Le pedimos a Google la lista de modelos permitidos para tu llave
#for m in genai.list_models():
    #if 'generateContent' in m.supported_generation_methods:
        #print(m.name)

#print("-" * 30)
#print("Copia uno de los nombres de arriba (ej: models/gemini-X.X) y ponlo en tu main.py")


modelo_ia = genai.GenerativeModel(
    model_name="gemini-2.5-flash"
)

def analizar_notas_con_ia(notas_del_psicologo: str):
    # El prompt maestro sigue igual
    prompt = f"""
    Eres un asistente clínico experto para psicólogos. Analiza las siguientes notas de sesión y devuelve un JSON válido.
    
    Notas de la sesión:
    "{notas_del_psicologo}"
    
    El JSON DEBE tener exactamente esta estructura y claves:
    {{
        "resumen_paciente": "Un párrafo conciso resumiendo la sesión",
        "analisis_evolucion": "Breve análisis de cómo va progresando",
        "sugerencias_clinicas": ["sugerencia 1", "sugerencia 2"],
        "pruebas_sugeridas": ["prueba 1", "prueba 2"]
    }}
    """
    
    respuesta = modelo_ia.generate_content(prompt)
    texto_ia = respuesta.text
    
    # Imprimimos para ver qué llegó realmente
    print("RESPUESTA CRUDA DE LA IA:", texto_ia)
    
    # TRUCO NINJA: Limpiamos los acentos invertidos de Markdown por si la IA los mandó
    texto_limpio = texto_ia.replace("```json", "").replace("```", "").strip()
    
    # Ahora sí, convertimos el texto limpio a un diccionario de Python
    datos_json = json.loads(texto_limpio)
    
    return datos_json