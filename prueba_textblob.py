from textblob import TextBlob
from deep_translator import GoogleTranslator

def probar_comentario(texto_paciente):
    print(f"\n--- Analizando: '{texto_paciente}' ---")
    
    # 1. Traducimos gratis al inglés
    texto_en = GoogleTranslator(source='es', target='en').translate(texto_paciente)
    print(f"Traducción: '{texto_en}'")
    
    # 2. TextBlob calcula el sentimiento
    analisis = TextBlob(texto_en)
    polaridad = analisis.sentiment.polarity
    print(f"Puntaje de polaridad: {polaridad}")
    
    # 3. Clasificamos
    if polaridad > 0.1:
        resultado = "POSITIVO"
    elif polaridad < -0.1:
        resultado = "NEGATIVO"
    else:
        resultado = "NEUTRO"
        
    print(f"✅ ETIQUETA FINAL: {resultado}")

# ----- ZONA DE PRUEBAS -----
# Aquí podés poner los comentarios reales que te han dejado
probar_comentario("nada xele")
probar_comentario("Dirk no me puede decir nada útil, fue una pérdida de tiempo")
probar_comentario("Me sentí muy bien escuchado, excelente doctor")
probar_comentario("El consultorio estaba limpio")