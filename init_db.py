import psycopg2
import bcrypt

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
            rol VARCHAR(20) DEFAULT 'cliente', -- 👈 'cliente' o 'admin'
            discoteca_id INT NULL,             -- 👈 Solo si administra un local
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
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS zonas_discoteca (
            id SERIAL PRIMARY KEY,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            nombre_zona VARCHAR(50) NOT NULL,
            consumo_minimo_usd NUMERIC(10, 2) NOT NULL,
            capacidad_mesas INT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mesas (
            id SERIAL PRIMARY KEY,
            zona_id INT REFERENCES zonas_discoteca(id) ON DELETE CASCADE,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            identificador_mesa VARCHAR(10) NOT NULL,
            posicion_x INT NOT NULL,
            posicion_y INT NOT NULL,
            UNIQUE(discoteca_id, identificador_mesa)
        );

        CREATE TABLE IF NOT EXISTS inventario_botellas (
            id SERIAL PRIMARY KEY,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            nombre_licor VARCHAR(100) NOT NULL,
            categoria VARCHAR(50),
            precio_usd NUMERIC(10, 2) NOT NULL,
            stock INT DEFAULT 0,
            disponible BOOLEAN DEFAULT TRUE,
            UNIQUE(discoteca_id, nombre_licor)
        );

        CREATE TABLE IF NOT EXISTS tasas_cambio (
            id SERIAL PRIMARY KEY,
            usd_ves NUMERIC(10, 2) NOT NULL,
            eur_ves NUMERIC(10, 2) NOT NULL,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reservas (
            id SERIAL PRIMARY KEY,
            usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
            mesa_id INT REFERENCES mesas(id) ON DELETE CASCADE,
            total_usd NUMERIC(10, 2) NOT NULL,
            estado VARCHAR(30) DEFAULT 'pendiente_pago',
            metodo_pago VARCHAR(30),
            referencia_bancaria VARCHAR(4),
            captura_url VARCHAR(255),
            codigo_qr_token VARCHAR(255) UNIQUE,
            expira_en TIMESTAMP NOT NULL,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS detalles_reserva_botellas (
            id SERIAL PRIMARY KEY,
            reserva_id INT REFERENCES reservas(id) ON DELETE CASCADE,
            botella_id INT REFERENCES inventario_botellas(id) ON DELETE CASCADE,
            cantidad INT NOT NULL
        );
        """
        cursor.execute(sql_tablas)
        
        # 3. DATA SEEDING: Inyectar discotecas de prueba
        sql_seed_discos = """
        INSERT INTO discotecas (id, nombre, ubicacion) VALUES
        (1, 'Kabal Club', 'Las Mercedes, Caracas'),
        (2, 'Zoe Room', 'Altamira, Caracas')
        ON CONFLICT (id) DO NOTHING;
        """
        cursor.execute(sql_seed_discos)

        # 4. DATA SEEDING: Precarga de Usuarios Administrativos (Nexo Empresas)
        # Contraseña de fábrica para ambos: 'EmpresaNexo2026*'
        salt = bcrypt.gensalt(12)
        clave_hasheada = bcrypt.hashpw('EmpresaNexo2026*'.encode('utf-8'), salt).decode('utf-8')

        sql_seed_gerentes = """
        INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, verificado, rol, discoteca_id) VALUES
        ('Carlos', 'Mendoza', 'gerente@kabal.com', '+584121111111', %s, TRUE, 'admin', 1),
        ('Elena', 'Ríos', 'gerente@zoe.com', '+584122222222', %s, TRUE, 'admin', 2)
        ON CONFLICT (correo) DO NOTHING;
        """
        cursor.execute(sql_seed_gerentes, (clave_hasheada, clave_hasheada))
        
        # Data Seeding de Geometría y Zonas
        sql_seed_zonas = """
        INSERT INTO zonas_discoteca (id, discoteca_id, nombre_zona, consumo_minimo_usd, capacidad_mesas) VALUES
        (1, 1, 'VIP Principal Kabal', 500.00, 2),
        (2, 1, 'General Dancefloor Kabal', 150.00, 2),
        (3, 2, 'VIP Terraza Zoe', 400.00, 2)
        ON CONFLICT (id) DO NOTHING;
        """
        cursor.execute(sql_seed_zonas)

        sql_seed_mesas = """
        INSERT INTO mesas (zona_id, discoteca_id, identificador_mesa, posicion_x, posicion_y) VALUES
        (1, 1, 'MESA-V1', 120, 150),
        (1, 1, 'MESA-V2', 200, 150),
        (2, 1, 'MESA-G1', 450, 300),
        (2, 1, 'MESA-G2', 520, 300),
        (3, 2, 'Z-VIP1', 100, 400),
        (3, 2, 'Z-VIP2', 180, 400)
        ON CONFLICT (discoteca_id, identificador_mesa) DO NOTHING;
        """
        cursor.execute(sql_seed_mesas)
        
        sql_seed_botellas = """
        INSERT INTO inventario_botellas (discoteca_id, nombre_licor, categoria, precio_usd, stock, disponible) VALUES
        (1, 'Ron Santa Teresa 1796', 'Ron', 120.00, 50, TRUE),
        (1, 'Whisky Old Parr 12 Años', 'Whisky', 90.00, 40, TRUE),
        (1, 'Vodka Grey Goose', 'Vodka', 110.00, 30, TRUE),
        (2, 'Whisky Johnnie Walker Black Label', 'Whisky', 95.00, 45, TRUE),
        (2, 'Tequila Don Julio Blanco', 'Tequila', 150.00, 20, TRUE),
        (2, 'Champaña Moët & Chandon', 'Champaña', 200.00, 15, TRUE)
        ON CONFLICT (discoteca_id, nombre_licor) DO NOTHING;
        """
        cursor.execute(sql_seed_botellas)

        cursor.execute("""
            INSERT INTO tasas_cambio (usd_ves, eur_ves) 
            SELECT 45.50, 49.20 WHERE NOT EXISTS (SELECT 1 FROM tasas_cambio);
        """)

        conexion.commit()
        print("✅ Base de datos de Nexo inicializada perfectamente con los roles de Nexo Empresas.")
        cursor.close()
        conexion.close()
    except Exception as e:
        print(f"❌ Error crítico inicializando base de datos: {e}")

if __name__ == "__main__":
    iniciar_base_de_datos()