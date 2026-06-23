import psycopg2

def iniciar_base_de_datos():
    try:
        conexion = psycopg2.connect(
            host="localhost",
            database="nexo_db",
            user="postgres",
            password="hOMERO20*"
        )
        cursor = conexion.cursor()
        
        # 1. Habilitar extensión para UUIDs en PostgreSQL
        cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        
        # 2. Creación de tablas de la base de datos
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

        CREATE TABLE IF NOT EXISTS zonas_discoteca (
            id SERIAL PRIMARY KEY,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            nombre_zona VARCHAR(50) NOT NULL,
            identificador_mesa VARCHAR(20) NOT NULL,
            capacidad INT NOT NULL,
            precio_minimo_consumo NUMERIC(10, 2) NOT NULL,
            foto_url VARCHAR(255),
            coordenada_x INT DEFAULT 0,
            coordenada_y INT DEFAULT 0,
            UNIQUE(discoteca_id, identificador_mesa)
        );

        CREATE TABLE IF NOT EXISTS inventario_botellas (
            id SERIAL PRIMARY KEY,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            nombre_licor VARCHAR(100) NOT NULL,
            categoria VARCHAR(50) NOT NULL,
            precio_usd NUMERIC(10, 2) NOT NULL,
            disponible BOOLEAN DEFAULT TRUE,
            UNIQUE(discoteca_id, nombre_licor)
        );

        CREATE TABLE IF NOT EXISTS reservas (
            id SERIAL PRIMARY KEY,
            usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
            zona_id INT REFERENCES zonas_discoteca(id) ON DELETE CASCADE,
            total_pago_usd NUMERIC(10, 2) NOT NULL,
            metodo_pago VARCHAR(50),
            estado VARCHAR(30) DEFAULT 'Pendiente',
            captura_pago_url VARCHAR(255),
            codigo_qr_token TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS detalles_reserva_botellas (
            id SERIAL PRIMARY KEY,
            reserva_id INT REFERENCES reservas(id) ON DELETE CASCADE,
            botella_id INT REFERENCES inventario_botellas(id) ON DELETE CASCADE,
            cantidad INT NOT NULL,
            precio_unitario_usd NUMERIC(10, 2) NOT NULL
        );
        """
        cursor.execute(sql_tablas)
        print("✅ Estructura física completa de tablas creada en PostgreSQL.")
        
        # 3. Insertar las discotecas bases
        cursor.execute("""
            INSERT INTO discotecas (id, nombre, ubicacion) 
            VALUES (1, 'Kabal', 'Zona VIP - Caracas'), (2, 'ZOE', 'Las Mercedes - Caracas')
            ON CONFLICT (nombre) DO NOTHING;
        """)
        
        # 4. DATA SEEDING: Inyectar Zonas/Mesas de prueba
        sql_seed_zonas = """
        INSERT INTO zonas_discoteca (discoteca_id, nombre_zona, identificador_mesa, capacidad, precio_minimo_consumo, foto_url, coordenada_x, coordenada_y) VALUES
        (1, 'Ultra VIP Stage', 'M-01', 10, 500.00, 'https://nexo.com/images/kabal_vip.jpg', 150, 300),
        (1, 'VIP Lateral', 'M-02', 8, 350.00, 'https://nexo.com/images/kabal_lateral.jpg', 250, 450),
        (1, 'General Lounge', 'M-03', 5, 150.00, 'https://nexo.com/images/kabal_gen.jpg', 500, 600),
        (2, 'ZOE Roof VIP', 'Z-01', 12, 600.00, 'https://nexo.com/images/zoe_roof.jpg', 120, 200),
        (2, 'ZOE Dancefloor Side', 'Z-02', 6, 250.00, 'https://nexo.com/images/zoe_side.jpg', 340, 400)
        ON CONFLICT (discoteca_id, identificador_mesa) DO NOTHING;
        """
        cursor.execute(sql_seed_zonas)
        
        # 5. DATA SEEDING: Inyectar licores en el menú
        sql_seed_botellas = """
        INSERT INTO inventario_botellas (discoteca_id, nombre_licor, categoria, precio_usd, disponible) VALUES
        (1, 'Ron Santa Teresa 1796', 'Ron', 120.00, TRUE),
        (1, 'Whisky Old Parr 12 Años', 'Whisky', 90.00, TRUE),
        (1, 'Vodka Grey Goose', 'Vodka', 110.00, TRUE),
        (2, 'Whisky Johnnie Walker Black Label', 'Whisky', 95.00, TRUE),
        (2, 'Tequila Don Julio Blanco', 'Tequila', 150.00, TRUE),
        (2, 'Champaña Moët & Chandon', 'Champaña', 200.00, TRUE)
        ON CONFLICT (discoteca_id, nombre_licor) DO NOTHING;
        """
        cursor.execute(sql_seed_botellas)
        print("🍾 Menú de licores, plano de mesas y sistema de órdenes inyectados correctamente.")

        conexion.commit()
        cursor.close()
        conexion.close()
        print("🚀 Sincronización exitosa con Nexo DB.")

    except Exception as error:
        print(f"❌ Error al sincronizar la base de datos: {error}")

if __name__ == "__main__":
    iniciar_base_de_datos()