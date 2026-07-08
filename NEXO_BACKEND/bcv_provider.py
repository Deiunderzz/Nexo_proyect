import os
import requests
import urllib3
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "nexo_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD")
}

# Memoria volátil de última línea (RAM) para contingencia absoluta
ULTIMA_TASA_CONOCIDA = {
    "USD": 54.50,
    "EUR": 58.80
}

def obtener_tasas_bcv():
    """
    Busca la tasa oficial en vivo. Si internet falla, se alimenta de la última 
    cifra guardada en la Base de Datos. Si la BD falla, usa la última cifra en memoria RAM.
    """
    global ULTIMA_TASA_CONOCIDA
    usd, eur = None, None
    fuente_exitosa = None

    # --- FUENTE 1: API de respaldo/comunidad ---
    try:
        url1 = "https://ve.descargas.net.ve/api/bcv"
        respuesta = requests.get(url1, timeout=4, verify=False)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            usd = float(datos.get("USD", 0))
            eur = float(datos.get("EUR", 0))
            fuente_exitosa = "api_principal"
    except Exception:
        print("⚠️ Fuente 1 caída. Intentando Fuente 2...")

    # --- FUENTE 2 (FALLBACK EN VIVO): API Abierta Alternativa ---
    if not usd or usd < 10.00:  
        try:
            url2 = "https://open.er-api.com/v6/latest/USD"
            respuesta = requests.get(url2, timeout=4)
            if respuesta.status_code == 200:
                datos = respuesta.json()
                tasas = datos.get("rates", {})
                usd = float(tasas.get("VES", 0))
                eur = usd * 1.08
                fuente_exitosa = "api_internacional_fallback"
        except Exception as e:
            print(f"⚠️ Fuente 2 también caída: {e}")

    # --- SI OBTUVIMOS CIFRA FRESCA DE INTERNET ---
    if usd and usd > 10.00:
        ULTIMA_TASA_CONOCIDA["USD"] = usd
        ULTIMA_TASA_CONOCIDA["EUR"] = eur
        
        try:
            with psycopg2.connect(**DB_CONFIG) as conexion:
                with conexion.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO tasas_cambio (usd_ves, eur_ves) VALUES (%s, %s);",
                        (usd, eur)
                    )
                    conexion.commit()
            return {"status": fuente_exitosa, "USD": usd, "EUR": eur}
        except Exception as db_err:
            print(f"⚠️ No se pudo registrar la tasa fresca en BD: {db_err}")
            return {"status": fuente_exitosa, "USD": usd, "EUR": eur}

    # --- CONTINGENCIA 1: RESPALDO HISTÓRICO EN POSTGRESQL ---
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT usd_ves, eur_ves FROM tasas_cambio ORDER BY actualizado_en DESC LIMIT 1;")
                registro = cursor.fetchone()
                if registro:
                    usd_db = float(registro["usd_ves"])
                    eur_db = float(registro["eur_ves"])
                    
                    ULTIMA_TASA_CONOCIDA["USD"] = usd_db
                    ULTIMA_TASA_CONOCIDA["EUR"] = eur_db
                    
                    return {
                        "status": "db_fallback_verificado",
                        "USD": usd_db,
                        "EUR": eur_db
                    }
    except Exception as e:
        print(f"❌ Error crítico leyendo respaldo de BD: {e}")

    # --- CONTINGENCIA 2: ÚLTIMA LÍNEA DE DEFENSA (Memoria RAM viva) ---
    print(f"🚨 [BCV CONTINGENCIA] Usando última cifra retenida en memoria: {ULTIMA_TASA_CONOCIDA['USD']}")
    return {
        "status": "contingencia_memoria_dinamica",
        "USD": ULTIMA_TASA_CONOCIDA["USD"],
        "EUR": ULTIMA_TASA_CONOCIDA["EUR"]
    }