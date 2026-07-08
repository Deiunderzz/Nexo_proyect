import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def verificar_datos():
    try:
        conexion = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "nexo_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD")
        )
        cursor = conexion.conexion() if hasattr(conexion, 'conexion') else conexion.cursor()
        
        cursor.execute("SELECT id, nombre, ubicacion FROM discotecas;")
        discotecas = cursor.fetchall()
        
        print("\n--- 🏢 DISCOTECAS EN LA BASE DE DATOS ---")
        for disco in discotecas:
            print(f"ID: {disco[0]} | Nombre: {disco[1]} | Ubicación: {disco[2]}")
        print("-----------------------------------------\n")
        
        cursor.close()
        conexion.close()
    except Exception as error:
        print(f"❌ Error al consultar: {error}")

if __name__ == "__main__":
    verificar_datos()