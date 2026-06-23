# ocr_processor.py
import os
import re
import sys
import traceback
from datetime import datetime, date
import easyocr

# ========================================================
# 🧠 INICIALIZACIÓN SEGURO DEL MOTOR DE IA (EasyOCR)
# ========================================================
try:
    print("🧠 [NEXO IA] Cargando inicializador de EasyOCR...")
    # 'verbose=True' mostrará las barras de descarga en tu consola si falta el modelo.
    # 'gpu=False' fuerza el uso de CPU (cambiar a True si configuras CUDA en el futuro).
    reader = easyocr.Reader(['es'], gpu=False, verbose=True)
    print("✅ [NEXO IA] Motor EasyOCR listo y cargado en memoria.")
except Exception as init_err:
    print(f"🚨 [NEXO IA] ADVERTENCIA: No se pudo inicializar EasyOCR automáticamente.")
    print(f"   Detalle del error: {init_err}")
    print("   El sistema continuará operando, pero el endpoint de escaneo retornará un error controlado.")
    reader = None


def calcular_edad(fecha_nacimiento):
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad


def procesar_cedula(ruta_imagen):
    try:
        # 1. Validaciones previas de seguridad
        if not os.path.exists(ruta_imagen):
            return {"status": "error", "message": f"Archivo no encontrado en la ruta: {ruta_imagen}"}
        
        if reader is None:
            return {
                "status": "error", 
                "message": "El motor de IA (EasyOCR) no pudo inicializarse en este servidor debido a fallas de red o dependencias faltantes."
            }
        
        print(f"📸 [NEXO IA] Analizando la imagen con Visión Artificial: {ruta_imagen}")
        
        # 2. Extracción de bloques de texto plano de la imagen
        lineas = reader.readtext(ruta_imagen, detail=0)
        texto_completo = " ".join(lineas).upper()
        
        print(f"📝 [NEXO IA] Texto crudo detectado:\n{lineas}")

        # Variables para almacenar los datos limpios extraídos
        cedula = None
        nombre = "NO DETECTADO"
        apellido = "NO DETECTADO"
        dob = None
        edad = None

        # 3. EXTRACCIÓN CON REGEX DE FECHA DE NACIMIENTO
        # Busca formatos comunes en identificaciones: DD/MM/AAAA o DD-MM-AAAA
        patron_fecha = re.search(r"(\d{2})[/\-.](\d{2})[/\-.](\d{4})", texto_completo)
        if patron_fecha:
            dia, mes, anio = patron_fecha.groups()
            try:
                dob = datetime.strptime(f"{anio}-{mes}-{dia}", "%Y-%m-%d").date()
                edad = calcular_edad(dob)
            except ValueError:
                pass  # Fecha inválida en la lectura

        # 4. EXTRACCIÓN CON REGEX DEL NÚMERO DE CÉDULA
        # Captura formatos como: 26.123.456, 26123456 o V-26.123.456
        patron_cedula = re.search(r"(\d{1,2})[.,\s]?(\d{3})[.,\s]?(\d{3})", texto_completo)
        if patron_cedula:
            cedula = f"{patron_cedula.group(1)}.{patron_cedula.group(2)}.{patron_cedula.group(3)}"

        # 5. EXTRACCIÓN POR ANÁLISIS DE POSICIÓN (Nombres y Apellidos)
        for i, linea in enumerate(lineas):
            linea_upper = linea.upper()
            if "APELLI" in linea_upper or "APELIO" in linea_upper:
                if i + 1 < len(lineas):
                    apellido = lineas[i + 1].strip().upper()
            
            if "NOMBR" in linea_upper or "NOMB" in linea_upper:
                if i + 1 < len(lineas):
                    nombre = lineas[i + 1].strip().upper()

        # 6. FILTRO REGLA DE NEGOCIO: Mayoría de edad obligatoria para Discotecas
        if edad and edad < 18:
            return {
                "status": "error",
                "message": f"Acceso denegado. Eres menor de edad ({edad} años). Ingreso exclusivo para mayores de 18 años."
            }
            
        return {
            "status": "success",
            "datos": {
                "cedula": cedula if cedula else "N/A",
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": str(dob) if dob else None,
                "edad": edad
            }
        }

    except Exception as e:
        print("🚨 [NEXO IA] Error crítico procesando la imagen:")
        traceback.print_exc(file=sys.stdout)
        return {"status": "error", "message": f"Falla en el reconocimiento del documento: {str(e)}"}