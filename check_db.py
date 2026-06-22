import psycopg2

def verificar_datos():
    try:
        conexion = psycopg2.connect(
            host="localhost",
            database="nexo_db",
            user="postgres",
            password="hOMERO20*"
        )
        cursor = conexion.cursor()
        
        # Consultar la tabla de discotecas
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