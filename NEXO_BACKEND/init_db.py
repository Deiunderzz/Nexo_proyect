import os
import psycopg2
import bcrypt
from dotenv import load_dotenv

load_dotenv()

def iniciar_base_de_datos():
    try:
        conexion = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "nexo_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD")
        )
        cursor = conexion.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        
        sql_tablas = """
        DROP TABLE IF EXISTS detalles_reserva_botellas, reservas, tasas_cambio, inventario_botellas, mesas, zonas_discoteca, codigos_verificacion, usuarios, discotecas CASCADE;

        CREATE TABLE discotecas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL UNIQUE,
            ubicacion VARCHAR(150) NOT NULL
        );

        CREATE TABLE usuarios (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL,
            apellido VARCHAR(50) NOT NULL,
            cedula VARCHAR(20),
            correo VARCHAR(100) UNIQUE NOT NULL,
            telefono VARCHAR(20) UNIQUE NOT NULL,
            contrasena VARCHAR(255) NOT NULL,
            fecha_nacimiento DATE,
            edad INT,
            nivel_lealtad VARCHAR(20) DEFAULT 'Bronce',
            verificado BOOLEAN DEFAULT FALSE,
            rol VARCHAR(20) DEFAULT 'cliente',
            discoteca_id INT REFERENCES discotecas(id) ON DELETE SET NULL,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE codigos_verificacion (
            id SERIAL PRIMARY KEY,
            usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
            codigo_otp VARCHAR(10) NOT NULL,
            expiracion TIMESTAMP NOT NULL,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE zonas_discoteca (
            id SERIAL PRIMARY KEY,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            nombre_zona VARCHAR(50) NOT NULL,
            consumo_minimo_usd NUMERIC(10, 2) NOT NULL,
            capacidad_mesas INT NOT NULL
        );

        CREATE TABLE mesas (
            id SERIAL PRIMARY KEY,
            zona_id INT REFERENCES zonas_discoteca(id) ON DELETE CASCADE,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            identificador_mesa VARCHAR(20) NOT NULL,
            posicion_x INT NOT NULL,
            posicion_y INT NOT NULL
        );

        CREATE TABLE inventario_botellas (
            id SERIAL PRIMARY KEY,
            discoteca_id INT REFERENCES discotecas(id) ON DELETE CASCADE,
            nombre_licor VARCHAR(100) NOT NULL,
            categoria VARCHAR(50),
            precio_usd NUMERIC(10, 2) NOT NULL,
            stock INT DEFAULT 0,
            disponible BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE tasas_cambio (
            id SERIAL PRIMARY KEY,
            usd_ves NUMERIC(10, 4) NOT NULL,
            eur_ves NUMERIC(10, 4) NOT NULL,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE reservas (
            id SERIAL PRIMARY KEY,
            usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
            mesa_id INT REFERENCES mesas(id) ON DELETE CASCADE,
            total_usd NUMERIC(10, 2) NOT NULL,
            total_ves NUMERIC(10, 2),
            tasa_bcv_aplicada NUMERIC(10, 4),
            metodo_pago VARCHAR(30),
            referencia_bancaria VARCHAR(50),
            foto_captura_path VARCHAR(255),
            estado VARCHAR(30) DEFAULT 'pendiente',
            codigo_qr_token VARCHAR(255) UNIQUE,
            expiracion_reserva TIMESTAMP NOT NULL,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE detalles_reserva_botellas (
            id SERIAL PRIMARY KEY,
            reserva_id INT REFERENCES reservas(id) ON DELETE CASCADE,
            botella_id INT REFERENCES inventario_botellas(id) ON DELETE CASCADE,
            cantidad INT NOT NULL
        );
        """
        cursor.execute(sql_tablas)
        
        # Inserta catálogo semilla
        cursor.execute("INSERT INTO discotecas (id, nombre, ubicacion) VALUES (1, 'Kabal Club', 'Las Mercedes, Caracas'), (2, 'Zoe Rooftop', 'Altamira, Caracas');")
        
        salt = bcrypt.gensalt()
        clave_hasheada = bcrypt.hashpw("NexoAdmin2026*".encode('utf-8'), salt).decode('utf-8')
        
        sql_seed_gerentes = """
        INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, verificado, rol, discoteca_id) VALUES
        ('Carlos', 'Mendoza', 'gerente@kabal.com', '+584121111111', %s, TRUE, 'admin', 1),
        ('Elena', 'Ríos', 'gerente@zoe.com', '+584122222222', %s, TRUE, 'admin', 2);
        """
        cursor.execute(sql_seed_gerentes, (clave_hasheada, clave_hasheada))
        
        cursor.execute("INSERT INTO zonas_discoteca (id, discoteca_id, nombre_zona, consumo_minimo_usd, capacidad_mesas) VALUES (1, 1, 'VIP Principal Kabal', 500.00, 2), (2, 2, 'VIP Terraza Zoe', 400.00, 2);")
        cursor.execute("INSERT INTO mesas (zona_id, discoteca_id, identificador_mesa, posicion_x, posicion_y) VALUES (1, 1, 'MESA-V1', 120, 150), (2, 2, 'Z-VIP1', 100, 400);")
        cursor.execute("INSERT INTO inventario_botellas (discoteca_id, nombre_licor, categoria, precio_usd, stock, disponible) VALUES (1, 'Ron Santa Teresa 1796', 'Ron', 60.00, 20, TRUE), (2, 'Whisky Old Parr 12 Años', 'Whisky', 45.00, 15, TRUE);")
        
        conexion.commit()
        print("✅ Base de datos relacional Nexo estructurada y sembrada al 100%.")
        cursor.close()
        conexion.close()
    except Exception as e:
        print(f"❌ Error fatal inicializando tablas: {e}")

if __name__ == "__main__":
    iniciar_base_de_datos()