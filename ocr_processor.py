import os
import re
from datetime import datetime, date
import easyocr

def calcular_edad(fecha_nacimiento):
    """Calcula la edad exacta."""
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad

def escanear_cedula(ruta_imagen):
    """
    Usa EasyOCR para extraer el texto de la cédula y validar la edad.
    """
    try:
        if not os.path.exists(ruta_imagen):
            print(f"❌ Error: No se encontró la imagen en: {ruta_imagen}")
            return {"status": "error", "message": "Archivo no encontrado."}

        print("🧠 Inicializando el motor de IA (EasyOCR)...")
        # Inicializamos el lector en español ('es')
        lector = easyocr.Reader(['es'], gpu=False) 
        
        print("📸 Analizando la imagen...")
        # Extrae solo las cadenas de texto legibles
        resultado = lector.readtext(ruta_imagen, detail=0)
        
        # Unimos todo el texto encontrado en un solo bloque separado por líneas
        texto_completo = "\n".join(resultado)
        
        print("\n--- 📝 TEXTO DETECTADO POR LA IA ---")
        print(texto_completo)
        print("------------------------------------\n")
        
        # Buscamos fechas de nacimiento (Formatos: DD/MM/AAAA o DD-MM-AAAA)
        patron_fecha = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", texto_completo)
        
        dob = None
        edad = None
        
        if patron_fecha:
            fecha_str = f"{patron_fecha.group(3)}-{patron_fecha.group(2)}-{patron_fecha.group(1)}"
            dob = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            edad = calcular_edad(dob)
            
        if edad and edad < 18:
            return {
                "status": "error",
                "message": f"Acceso denegado. Eres menor de edad ({edad} años)."
            }
            
        return {
            "status": "success",
            "datos": {
                "nombre": "Extraído_OCR",
                "apellido": "Extraído_OCR",
                "dob": str(dob) if dob else None,
                "edad": edad
            }
        }
        
    except Exception as error:
        print(f"❌ Error en el proceso de OCR: {error}")
        return {"status": "error", "message": str(error)}

if __name__ == "__main__":
    print("--- 🧪 PROBANDO ESCÁNER INTELIGENTE ---")
    resultado_escaneo = escanear_cedula("test_cedula.jpeg")
    print("Resultado final:", resultado_escaneo)