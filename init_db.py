import psycopg2

def iniciar_base_de_datos():
    try:
        # 1. Conectarse directamente a nexo_db
        conexion = psycopg2.connect(
            host="localhost",
            database="nexo_db",
            user="postgres",
            password="hOMERO20*"
        )
        cursor = conexion.cursor()
        
        # 2. El código SQL de todas las tablas limpias
        sql_tablas = """
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL,
            apellido VARCHAR(50) NOT NULL,
            correo VARCHAR(100) UNIQUE NOT NULL,
            telefono VARCHAR(20) UNIQUE NOT NULL,
            contrasena VARCHAR(255) NOT NULL,
            fecha_nacimiento DATE,
            edad INT,
            nivel_lealtad VARCHAR(20) DEFAULT 'Bronce',
            verificado BOOLEAN DEFAULT FALSE,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS discotecas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL UNIQUE,
            ubicacion VARCHAR(150) NOT NULL
        );

        CREATE TABLE IF NOT EXISTS codigos_verificacion (
            id SERIAL PRIMARY KEY,
            usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
            codigo VARCHAR(6) NOT NULL,
            expira_en TIMESTAMP NOT NULL,
            utilizado BOOLEAN DEFAULT FALSE
        );
        """
        
        # 3. Ejecutar la creación de tablas
        cursor.execute(sql_tablas)
        print("¡Tablas 'usuarios', 'discotecas' y 'codigos_verificacion' listas!")
        
        # 4. Insertar las discotecas por defecto de forma segura
        sql_insertar = """
        INSERT INTO discotecas (nombre, ubicacion) 
        VALUES ('Kabal', 'Zona VIP - Caracas'), ('ZOE', 'Las Mercedes - Caracas')
        ON CONFLICT (nombre) DO NOTHING;
        """
        cursor.execute(sql_insertar)
        print("¡Discotecas iniciales verificadas en la base de datos!")
        
        # Guardar cambios y cerrar
        conexion.commit()
        cursor.close()
        conexion.close()
        print("🚀 Base de datos sincronizada con éxito.")

    except Exception as error:
        print(f"❌ Error al conectar o crear las tablas: {error}")

if __name__ == "__main__":
    iniciar_base_de_datos()