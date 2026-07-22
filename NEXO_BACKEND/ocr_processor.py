import os
import re
from datetime import datetime, date
import easyocr
from PIL import Image

# 🍏 Soporte nativo para formato de iPhone (HEIC)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("🍏 [NEXO IA] Soporte para imágenes de iPhone (HEIC) activado.")
except ImportError:
    print("⚠️ [NEXO IA] pillow-heif no instalado. Las fotos directas de iPhone (.heic) podrían fallar.")

try:
    print("🧠 [NEXO IA] Cargando inicializador de EasyOCR...")
    # Inicializa el lector en español y deshabilita logs innecesarios
    reader = easyocr.Reader(['es'], gpu=False, verbose=False)
    print("✅ [NEXO IA] Motor EasyOCR listo.")
except Exception as init_err:
    print(f"🚨 [NEXO IA] Fallo cargando EasyOCR: {init_err}")
    reader = None

def calcular_edad(fecha_nacimiento):
    """Calcula la edad exacta del usuario en base a su fecha de nacimiento."""
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

def preprocesar_y_convertir_imagen(ruta_origen, max_dimension=1600):
    """
    1. Detecta si la imagen es un formato HEIC de iPhone y la convierte a JPEG.
    2. SIEMPRE reduce la imagen a un tamaño máximo razonable antes de correr OCR.
       Las fotos de cámara (3000-4000px+) son la causa #1 de timeouts: EasyOCR
       en CPU escala muy mal con el tamaño de imagen. Bajar a ~1600px del lado
       más largo acelera la inferencia drásticamente sin perder legibilidad del texto.
    """
    nombre_archivo, extension = os.path.splitext(ruta_origen)
    ext_limpia = extension.lower()
    es_heic = ext_limpia in ['.heic', '.heif']

    try:
        imagen = Image.open(ruta_origen)
        ancho, alto = imagen.size
        lado_mayor = max(ancho, alto)

        necesita_conversion = es_heic
        necesita_resize = lado_mayor > max_dimension

        if not necesita_conversion and not necesita_resize:
            return ruta_origen, False

        if necesita_resize:
            escala = max_dimension / float(lado_mayor)
            nuevo_tamano = (int(ancho * escala), int(alto * escala))
            print(f"📉 [NEXO IA] Redimensionando imagen de {ancho}x{alto} a {nuevo_tamano[0]}x{nuevo_tamano[1]} para acelerar el OCR...")
            imagen = imagen.resize(nuevo_tamano, Image.LANCZOS)

        if imagen.mode != "RGB":
            imagen = imagen.convert("RGB")

        ruta_temporal_jpg = f"{nombre_archivo}_procesada.jpg"
        imagen.save(ruta_temporal_jpg, "JPEG", quality=90)
        return ruta_temporal_jpg, True  # Indica que es un archivo temporal a eliminar

    except Exception as e:
        print(f"🚨 [NEXO IA] Error al preprocesar la imagen: {e}")
        return ruta_origen, False

def procesar_cedula(ruta_imagen):
    """
    Analiza la imagen de una cédula de identidad mediante OCR con el único
    propósito de verificar mayoría de edad (fecha de nacimiento) y extraer
    el número de cédula como referencia editable por el usuario. No extrae
    nombres/apellidos: esos los ingresa el usuario manualmente en el formulario.
    """
    if reader is None:
        return {
            "status": "error",
            "message": "El motor de lectura OCR no está inicializado en el servidor."
        }

    archivo_a_procesar = ruta_imagen
    es_temporal = False

    try:
        # 1. Asegurar compatibilidad de formato (HEIC de iPhone -> JPG)
        archivo_a_procesar, es_temporal = preprocesar_y_convertir_imagen(ruta_imagen)

        # 2. Ejecutar la extracción de texto plano desde la imagen
        resultados = reader.readtext(archivo_a_procesar, detail=0)
        texto_completo = " ".join(resultados).upper()
        
        # DEBUG: Permite ver en la consola del servidor exactamente qué está leyendo la IA
        print(f"\n🔍 [NEXO IA - DEBUG] Texto extraído de la imagen:\n{texto_completo}\n")
        
        # Inicialización de variables de retorno
        cedula = None
        fecha_nacimiento_valida = None
        fecha_nacimiento_str = ""
        
        # 3. Extracción del Número de Cédula (Patrón venezolano V-XX.XXX.XXX o E-XX.XXX.XXX)
        # Es solo una sugerencia inicial: el usuario la revisa y puede corregirla en la app.
        match_cedula = re.search(r'\b([VE])[-. ]?(\d{1,2})[-. ]?(\d{3})[-. ]?(\d{3})\b', texto_completo)
        if match_cedula:
            nacionalidad = match_cedula.group(1)
            num_limpio = f"{match_cedula.group(2)}.{match_cedula.group(3)}.{match_cedula.group(4)}"
            cedula = f"{nacionalidad}-{num_limpio}"
        else:
            # Fallback simple de solo dígitos secuenciales largos
            match_digitos = re.search(r'\b(\d{7,8})\b', texto_completo)
            if match_digitos:
                num = match_digitos.group(1)
                cedula = f"V-{num[:-6]}.{num[-6:-3]}.{num[-3:]}"
            # Si no se detecta nada, cedula queda en None: el usuario la escribe a mano.

        # 4. Extracción de la Fecha de Nacimiento (Formatos DD/MM/AAAA, DD-MM-AAAA)
        coincidencias_fechas = re.findall(r'\b(\d{2})[-/\.](\d{2})[-/\.](\d{4})\b', texto_completo)
        
        # Filtrar por fechas lógicas de nacimiento (año menor al actual y mayor a 1920)
        anio_actual = datetime.now().year
        for dia, mes, anio in coincidencias_fechas:
            anio_int = int(anio)
            if 1920 < anio_int < anio_actual:
                try:
                    fecha_candidata = datetime.strptime(f"{dia}/{mes}/{anio}", "%d/%m/%Y").date()
                    # Generalmente la fecha de nacimiento es la más antigua en el documento
                    if fecha_nacimiento_valida is None or fecha_candidata < fecha_nacimiento_valida:
                        fecha_nacimiento_valida = fecha_candidata
                        fecha_nacimiento_str = f"{dia}/{mes}/{anio}"
                except ValueError:
                    continue

        # 5. Sin fecha de nacimiento legible no podemos verificar edad: es un error,
        # no un valor por defecto. Un fallback silencioso aquí dejaría pasar a
        # cualquiera con una foto ilegible como si fuera mayor de edad.
        if fecha_nacimiento_valida is None:
            return {
                "status": "error",
                "message": "No pudimos leer la fecha de nacimiento en el documento. Intenta con mejor iluminación o un ángulo más recto."
            }

        edad_calculada = calcular_edad(fecha_nacimiento_valida)
        es_mayor = edad_calculada >= 18

        return {
            "status": "success",
            "datos": {
                "cedula": cedula,
                "fecha_nacimiento": fecha_nacimiento_str,
                "edad": edad_calculada,
                "es_mayor_edad": es_mayor
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Fallo procesando OCR: {str(e)}"
        }
    
    finally:
        # 🗑️ Limpieza: Si creamos un archivo .jpg temporal, lo borramos para no llenar el disco
        if es_temporal and os.path.exists(archivo_a_procesar):
            try:
                os.remove(archivo_a_procesar)
                print("🧹 [NEXO IA] Archivo JPG temporal eliminado con éxito.")
            except Exception as clean_err:
                print(f"⚠️ No se pudo eliminar el archivo temporal: {clean_err}")