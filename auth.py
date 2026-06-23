import psycopg2
import bcrypt
import re
import random
from datetime import date, datetime, timedelta
import jwt

# Configuración de la conexión a PostgreSQL
DB_CONFIG = {
    "host": "localhost",
    "database": "nexo_db",
    "user": "postgres",
    "password": "hOMERO20*"
}

# 🔒 Configuración de Seguridad JWT
JWT_SECRET = "NexoSuperSecretKey2026_CambiarEnProduccion"
JWT_ALGORITHM = "HS256"

# ========================================================
# 🚀 FUNCIONES DE VALIDACIÓN
# ========================================================
def validar_complejidad_contrasena(contrasena):
    if len(contrasena) < 8:
        return False
    if not re.search(r"[A-Z]", contrasena):  
        return False
    if not re.search(r"[0-9]", contrasena):  
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", contrasena):  
        return False
    return True

def calcular_edad(fecha_nacimiento_str):
    fecha_nac = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
    hoy = date.today()
    edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    return edad

# ========================================================
# 🔑 REGISTRO, LOGIN Y CÉDULAS
# ========================================================
def pre_registrar_cedula(nombre, apellido, fecha_nacimiento_str, edad):
    try:
        sql = """
        INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, fecha_nacimiento, edad, verificado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING id;
        """
        uuid_provisional = f"temp_{random.randint(100000, 999999)}"
        correo_temp = f"anonimo_{uuid_provisional}@nexo.com"
        telefono_temp = f"temp_{uuid_provisional}"
        pass_falsa = bcrypt.hashpw(uuid_provisional.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql, (nombre, apellido, correo_temp, telefono_temp, pass_falsa, fecha_nacimiento_str, edad))
                usuario_id = cursor.fetchone()[0]
                conexion.commit()
        return {"status": "success", "usuario_id": usuario_id}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def completar_registro_usuario(usuario_id, nombre, apellido, correo, telefono, contrasena_plana):
    try:
        if not validar_complejidad_contrasena(contrasena_plana):
            return {"status": "error", "message": "La contraseña debe tener al menos 8 caracteres, una mayúscula, un número y un carácter especial."}

        hash_contrasena = bcrypt.hashpw(contrasena_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        sql_update = """
        UPDATE usuarios 
        SET nombre = %s, apellido = %s, correo = %s, telefono = %s, contrasena = %s
        WHERE id = %s;
        """
        sql_codigo = """
        INSERT INTO codigos_verificacion (usuario_id, codigo, expira_en)
        VALUES (%s, %s, %s);
        """
        codigo_aleatorio = str(random.randint(100000, 999999))
        tiempo_expiracion = datetime.now() + timedelta(minutes=10)

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql_update, (nombre, apellido, correo, telefono, hash_contrasena, usuario_id))
                cursor.execute(sql_codigo, (usuario_id, codigo_aleatorio, tiempo_expiracion))
                conexion.commit()

        print(f"📧 [EMAIL SIMULADO] Enviando código {codigo_aleatorio} al correo {correo}")
        return {"status": "success", "message": "Datos completados. Código de verificación enviado al correo electrónico."}
    except psycopg2.errors.UniqueViolation:
        return {"status": "error", "message": "El correo o teléfono ya se encuentran registrados en el sistema."}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def iniciar_sesion(identificador, contrasena_plana):
    try:
        sql = "SELECT id, nombre, contrasena, verificado FROM usuarios WHERE correo = %s OR telefono = %s;"
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql, (identificador, identificador))
                usuario = cursor.fetchone()

        if not usuario:
            return {"status": "error", "message": "Credenciales inválidas."}

        usuario_id, nombre, hash_contrasena, verificado = usuario

        if not verificado:
            return {"status": "error", "message": "Tu cuenta aún no está verificada por correo electrónico."}

        if not bcrypt.checkpw(contrasena_plana.encode('utf-8'), hash_contrasena.encode('utf-8')):
            return {"status": "error", "message": "Credenciales inválidas."}

        token = generar_jwt_token(usuario_id, nombre)
        return {"status": "success", "token": token, "usuario": {"id": usuario_id, "nombre": nombre}}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def confirmar_codigo_correo(usuario_id, codigo_ingresado):
    try:
        sql_buscar = """
        SELECT id, codigo, expira_en, utilizado 
        FROM codigos_verificacion 
        WHERE usuario_id = %s 
        ORDER BY id DESC LIMIT 1;
        """
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql_buscar, (usuario_id,))
                registro = cursor.fetchone()
                
                if not registro:
                    return {"status": "error", "message": "Código no solicitado."}
                    
                token_id, codigo_db, expira_en, utilizado = registro
                
                if utilizado or datetime.now() > expira_en or str(codigo_ingresado).strip() != str(codigo_db).strip():
                    return {"status": "error", "message": "Código inválido, expirado o usado."}
                    
                cursor.execute("UPDATE codigos_verificacion SET utilizado = TRUE WHERE id = %s;", (token_id,))
                cursor.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s;", (usuario_id,))
                conexion.commit()
        
        return {"status": "success", "message": "Cuenta verificada con éxito."}
    except Exception as error:
        return {"status": "error", "message": str(error)}
    
def generar_jwt_token(usuario_id, nombre):
    payload = {
        "usuario_id": usuario_id,
        "nombre": nombre,
        "exp": datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# ========================================================
# 🏢 ENDPOINTS GESTIÓN DE DISCOTECAS (ADMINISTRACIÓN/MENÚ)
# ========================================================
def obtener_discotecas():
    try:
        sql = "SELECT id, nombre, ubicacion FROM discotecas ORDER BY id;"
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql)
                columnas = [col[0] for col in cursor.description]
                resultado = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"status": "success", "data": resultado}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def obtener_layout_discoteca(discoteca_id):
    try:
        sql = """
        SELECT id, nombre_zona, identificador_mesa, capacidad, 
               precio_minimo_consumo, foto_url, coordenada_x, coordenada_y, TRUE as disponible
        FROM zonas_discoteca WHERE discoteca_id = %s ORDER BY identificador_mesa;
        """
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql, (discoteca_id,))
                columnas = [col[0] for col in cursor.description]
                resultado = []
                for fila in cursor.fetchall():
                    fila_dict = dict(zip(columnas, fila))
                    fila_dict["precio_minimo_consumo"] = float(fila_dict["precio_minimo_consumo"])
                    resultado.append(fila_dict)
        return {"status": "success", "data": resultado}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def obtener_menu_botellas(discoteca_id):
    try:
        sql = "SELECT id, nombre_licor, categoria, precio_usd, disponible FROM inventario_botellas WHERE discoteca_id = %s ORDER BY categoria, nombre_licor;"
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql, (discoteca_id,))
                columnas = [col[0] for col in cursor.description]
                resultado = []
                for fila in cursor.fetchall():
                    fila_dict = dict(zip(columnas, fila))
                    fila_dict["precio_usd"] = float(fila_dict["precio_usd"])
                    resultado.append(fila_dict)
        return {"status": "success", "data": resultado}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def actualizar_precio_botella(botella_id, nuevo_precio, disponible=None):
    try:
        if disponible is not None:
            sql = "UPDATE inventario_botellas SET precio_usd = %s, disponible = %s WHERE id = %s RETURNING id;"
            parametros = (nuevo_precio, disponible, botella_id)
        else:
            sql = "UPDATE inventario_botellas SET precio_usd = %s WHERE id = %s RETURNING id;"
            parametros = (nuevo_precio, botella_id)

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql, parametros)
                resultado = cursor.fetchone()
                conexion.commit()
        if not resultado:
            return {"status": "error", "message": "La botella especificada no existe."}
        return {"status": "success", "message": "Inventario actualizado correctamente."}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def actualizar_consumo_zona(zona_id, nuevo_minimo):
    try:
        sql = "UPDATE zonas_discoteca SET precio_minimo_consumo = %s WHERE id = %s RETURNING id;"
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(sql, (nuevo_minimo, zona_id))
                resultado = cursor.fetchone()
                conexion.commit()
        if not resultado:
            return {"status": "error", "message": "La mesa especificada no existe."}
        return {"status": "success", "message": "Precio de reservado modificado con éxito."}
    except Exception as error:
        return {"status": "error", "message": str(error)}

# ========================================================
# 🛒 MOTOR DE RESERVAS Y VALIDACIÓN DE CONSUMO MÍNIMO
# ========================================================
def validar_y_crear_intencion_reserva(usuario_id, zona_id, botellas_seleccionadas):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT precio_minimo_consumo FROM zonas_discoteca WHERE id = %s;", (zona_id,))
                zona = cursor.fetchone()
                if not zona:
                    return {"status": "error", "message": "La zona o mesa seleccionada no existe."}
                
                consumo_minimo_requerido = float(zona[0])
                total_pedido_usd = 0.0
                desglose_pedido = []
                
                for item in botellas_seleccionadas:
                    b_id = item.get("botella_id")
                    cant = item.get("cantidad", 0)
                    if cant <= 0:
                        continue
                        
                    cursor.execute("SELECT nombre_licor, precio_usd, disponible FROM inventario_botellas WHERE id = %s;", (b_id,))
                    botella = cursor.fetchone()
                    
                    if not botella:
                        return {"status": "error", "message": f"La botella con ID {b_id} no existe en el catálogo."}
                    if not botella[2]:
                        return {"status": "error", "message": f"Lo sentimos, el producto '{botella[0]}' está agotado."}
                        
                    precio_real = float(botella[1])
                    subtotal = precio_real * cant
                    total_pedido_usd += subtotal
                    
                    desglose_pedido.append({
                        "botella_id": b_id,
                        "cantidad": cant,
                        "precio_unitario": precio_real
                    })
                
                if total_pedido_usd < consumo_minimo_requerido:
                    faltante = consumo_minimo_requerido - total_pedido_usd
                    return {
                        "status": "error", 
                        "message": f"No cumples con el consumo mínimo de la mesa. Te faltan {faltante:.2f} USD por añadir en botellas.",
                        "total_actual": total_pedido_usd,
                        "minimo_requerido": consumo_minimo_requerido
                    }
                
                sql_reserva = "INSERT INTO reservas (usuario_id, zona_id, total_pago_usd, estado) VALUES (%s, %s, %s, 'Pendiente') RETURNING id;"
                cursor.execute(sql_reserva, (usuario_id, zona_id, total_pedido_usd))
                reserva_id = cursor.fetchone()[0]
                
                sql_detalle = "INSERT INTO detalles_reserva_botellas (reserva_id, botella_id, cantidad, precio_unitario_usd) VALUES (%s, %s, %s, %s);"
                for det in desglose_pedido:
                    cursor.execute(sql_detalle, (reserva_id, det["botella_id"], det["cantidad"], det["precio_unitario"]))
                
                conexion.commit()
                
        return {
            "status": "success", 
            "reserva_id": reserva_id, 
            "total_usd": total_pedido_usd,
            "message": "Consumo mínimo aprobado. Procediendo a pasarela de selección de pago."
        }
    except Exception as error:
        return {"status": "error", "message": str(error)}