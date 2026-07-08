import os
import re
from datetime import datetime, date
import easyocr

try:
    print("🧠 [NEXO IA] Cargando inicializador de EasyOCR...")
    reader = easyocr.Reader(['es'], gpu=False, verbose=False)
    print("✅ [NEXO IA] Motor EasyOCR listo.")
except Exception as init_err:
    print(f"🚨 [NEXO IA] Fallo cargando EasyOCR: {init_err}")
    reader = None

def calcular_edad(fecha_nacimiento):
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

def procesar_cedula(ruta_imagen):
    try:
        if not os.path.exists(ruta_imagen): return {"status": "error", "message": "Imagen no encontrada."}
        if reader is None: return {"status": "error", "message": "Motor OCR no inicializado."}

        resultado_ocr = reader.readtext(ruta_imagen, detail=0)
        if not resultado_ocr: return {"status": "error", "message": "No se pudo extraer texto de la imagen."}

        texto_unificado = " ".join(resultado_ocr)
        lineas = [str(l).strip() for l in resultado_ocr]

        cedula, nombre, apellido, dob, edad = None, "DESCONOCIDO", "DESCONOCIDO", None, None

        # Expresión regular robusta para Cédulas Venezolanas
        match_cedula = re.search(r'(?:V|E|PASAPORTE|N°|[-.])?\s*(\d{7,8})', texto_unificado.upper())
        if match_cedula:
            cedula = match_cedula.group(1)

        # Buscar Fechas de Nacimiento (Formatos DD/MM/AAAA, DD-MM-AAAA)
        patron_fecha = r'(\d{2})[-/](\d{2})[-/](\d{4})'
        fechas_encontradas = re.findall(patron_fecha, texto_unificado)
        
        fechas_validas = []
        for f in fechas_encontradas:
            try:
                f_obj = datetime.strptime(f"{f[0]}-{f[1]}-{f[2]}", "%d-%m-%Y").date()
                if f_obj.year < date.today().year - 5:
                    fechas_validas.append(f_obj)
            except ValueError:
                continue

        if fechas_validas:
            dob = min(fechas_validas)
            edad = calcular_edad(dob)

        for i, linea in enumerate(lineas):
            linea_upper = linea.upper()
            if "APELL" in linea_upper:
                if i + 1 < len(lineas): apellido = lineas[i + 1].strip().upper()
            if "NOMBR" in linea_upper or "NOMB" in linea_upper:
                if i + 1 < len(lineas): nombre = lineas[i + 1].strip().upper()

        if not dob:
            return {"status": "error", "message": "⚠️ La IA no pudo leer la fecha de nacimiento de manera nítida. Enfoca mejor."}

        if edad and edad < 18:
            return {"status": "error", "message": f"Acceso denegado. Eres menor de edad ({edad} años)."}

        return {"status": "success", "datos": {"cedula": cedula or "N/A", "nombre": nombre, "apellido": apellido, "fecha_nacimiento": str(dob), "edad": edad}}
    except Exception as e:
        return {"status": "error", "message": f"Fallo en procesador OCR: {str(e)}"}