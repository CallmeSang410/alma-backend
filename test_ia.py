import google.generativeai as genai

# Pon tu clave real aquí
genai.configure(api_key="AIzaSyDe95wrUINgqN0WSl3xlbNpalSB9m6qGas")

print("Buscando modelos disponibles para tu cuenta...")
print("-" * 30)

# Le pedimos a Google la lista de modelos permitidos para tu llave
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)

print("-" * 30)
print("Copia uno de los nombres de arriba (ej: models/gemini-X.X) y ponlo en tu main.py")