import psycopg2
import bcrypt
import re
from datetime import date, datetime
import random
from datetime import timedelta

# Configuración de la conexión
DB_CONFIG = {
    "host": "localhost",
    "database": "nexo_db",
    "user": "postgres",
    "password": "hOMERO20*"
}

# ========================================================
# 🚀 NUEVAS FUNCIONES DE VALIDACIÓN
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
# 📝 FUNCIÓN REGISTRAR MODIFICADA (Reemplazar la vieja)
# ========================================================
def registrar_usuario(nombre, apellido, correo, telefono, contrasena_plana, fecha_nacimiento_str):
    try:
        # 1. VALIDAR CONTRASEÑA
        if not validar_complejidad_contrasena(contrasena_plana):
            return {
                "status": "error", 
                "message": "La contraseña no cumple con los requisitos mínimos (8 caracteres, 1 mayúscula, 1 número, 1 símbolo)."
            }

        # 2. CALCULAR Y VALIDAR EDAD
        edad_calculada = calcular_edad(fecha_nacimiento_str)
        if edad_calculada < 18:
            print(f"🚫 Registro denegado: El usuario tiene {edad_calculada} años. Debe ser mayor de edad.")
            return {"status": "error", "message": "Acceso denegado. Debes ser mayor de 18 años."}

        # 3. ENCRIPTAR LA CONTRASEÑA
        bytes_contrasena = contrasena_plana.encode('utf-8')
        salt = bcrypt.gensalt()
        contrasena_encriptada = bcrypt.hashpw(bytes_contrasena, salt).decode('utf-8')

        # 4. CONECTAR A LA BASE DE DATOS
        conexion = psycopg2.connect(**DB_CONFIG)
        cursor = conexion.cursor()

        # 5. SENTENCIA SQL PARA INSERTAR
        sql = """
        INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, fecha_nacimiento, edad)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, creado_en;
        """
        
        cursor.execute(sql, (nombre, apellido, correo, telefono, contrasena_encriptada, fecha_nacimiento_str, edad_calculada))
        
        resultado = cursor.fetchone()
        usuario_id = resultado[0]
        fecha_creacion = resultado[1]

        conexion.commit()
        cursor.close()
        conexion.close()

        print(f"✅ ¡Usuario registrado con éxito! ID asignado: {usuario_id} (Edad: {edad_calculada} años)")
        
        generar_codigo_verificacion(usuario_id)
        
        return {"status": "success", "usuario_id": usuario_id, "creado_en": fecha_creacion}

    except psycopg2.errors.UniqueViolation:
        print("❌ Error: El correo o el teléfono ya están registrados por otro usuario.")
        return {"status": "error", "message": "Correo o teléfono duplicado."}
    except Exception as error:
        print(f"❌ Error inesperado en el registro: {error}")
        return {"status": "error", "message": str(error)}

# ========================================================
# 🔓 LA FUNCIÓN INICIAR_SESION SE QUEDA AQUÍ DEBAJO...
# ========================================================

def iniciar_sesion(identificador, contrasena_plana):
    """
    identificador: Puede ser el correo electrónico o el número de teléfono.
    contrasena_plana: La contraseña que el usuario digita en el login.
    """
    try:
        conexion = psycopg2.connect(**DB_CONFIG)
        cursor = conexion.cursor()

        # Buscamos al usuario si coincide el correo O el teléfono
        sql = """
        SELECT id, nombre, contrasena 
        FROM usuarios 
        WHERE correo = %s OR telefono = %s;
        """
        
        # Pasamos el identificador dos veces (para el correo y para el teléfono)
        cursor.execute(sql, (identificador, identificador))
        usuario = cursor.fetchone()

        cursor.close()
        conexion.close()

        # 1. Si no se encontró ningún usuario con ese correo o teléfono
        if not usuario:
            print("❌ Login fallido: El correo o teléfono no están registrados.")
            return {"status": "error", "message": "Credenciales incorrectas."}

        usuario_id = usuario[0]
        nombre_usuario = usuario[1]
        contrasena_encriptada_db = usuario[2]

        # 2. VERIFICAR LA CONTRASEÑA
        # bcrypt compara los bytes de la clave plana contra el hash guardado
        bytes_plana = contrasena_plana.encode('utf-8')
        bytes_encriptada = contrasena_encriptada_db.encode('utf-8')

        if bcrypt.checkpw(bytes_plana, bytes_encriptada):
            print(f"🔓 ¡Inicio de sesión exitoso! Bienvenido de nuevo, {nombre_usuario}.")
            return {"status": "success", "usuario_id": usuario_id, "nombre": nombre_usuario}
        else:
            print("❌ Login fallido: La contraseña es incorrecta.")
            return {"status": "error", "message": "Credenciales incorrectas."}

    except Exception as error:
        print(f"❌ Error en el inicio de sesión: {error}")
        return {"status": "error", "message": str(error)}
    
def generar_codigo_verificacion(usuario_id):
    """
    Genera un código de 6 dígitos, lo guarda en la DB con validez de 15 min
    y simula el envío al correo.
    """
    codigo = f"{random.randint(100000, 999999)}"
    fecha_expiracion = datetime.now() + timedelta(minutes=15)
    
    try:
        conexion = psycopg2.connect(**DB_CONFIG)
        cursor = conexion.cursor()
        
        sql = """
        INSERT INTO codigos_verificacion (usuario_id, codigo, expira_en)
        VALUES (%s, %s, %s);
        """
        cursor.execute(sql, (usuario_id, codigo, fecha_expiracion))
        conexion.commit()
        
        cursor.close()
        conexion.close()
        
        # Simulación de envío de correo en consola
        print(f"\n📧 [CORREO ENVIADO] Código de verificación para usuario ID {usuario_id}: {codigo}")
        print(f"⏳ Válido hasta: {fecha_expiracion.strftime('%H:%M:%S')}\n")
        return codigo
        
    except Exception as error:
        print(f"❌ Error al generar código de verificación: {error}")
        return None

def confirmar_codigo_correo(usuario_id, codigo_ingresado):
    """
    Verifica si el código ingresado por el usuario es correcto,
    no ha expirado y no ha sido usado antes.
    """
    try:
        conexion = psycopg2.connect(**DB_CONFIG)
        cursor = conexion.cursor()
        
        # Buscamos el último código generado para ese usuario
        sql = """
        SELECT id, codigo, expira_en, utilizado 
        FROM codigos_verificacion 
        WHERE usuario_id = %s 
        ORDER BY id DESC LIMIT 1;
        """
        cursor.execute(sql, (usuario_id,))
        registro = cursor.fetchone()
        
        if not registro:
            print("❌ No se encontró ningún código para este usuario.")
            return {"status": "error", "message": "Código no solicitado."}
            
        token_id, codigo_db, expira_en, utilizado = registro
        
        if utilizado:
            print("❌ El código ya fue utilizado anteriormente.")
            return {"status": "error", "message": "Código ya usado."}
            
        if datetime.now() > expira_en:
            print("❌ El código ya expiró.")
            return {"status": "error", "message": "Código expirado."}
            
        if codigo_ingresado != codigo_db:
            print("❌ El código ingresado es incorrecto.")
            return {"status": "error", "message": "Código incorrecto."}
            
        # Si pasa los filtros: actualizamos el token y activamos al usuario
        cursor.execute("UPDATE codigos_verificacion SET utilizado = TRUE WHERE id = %s;", (token_id,))
        cursor.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s;", (usuario_id,))
        
        conexion.commit()
        cursor.close()
        conexion.close()
        
        print(f"🎉 ¡Usuario ID {usuario_id} verificado con éxito! Cuenta activada.")
        return {"status": "success", "message": "Cuenta verificada con éxito."}
        
    except Exception as error:
        print(f"❌ Error en la verificación: {error}")
        return {"status": "error", "message": str(error)}
    

# --- PRUEBA LOCAL ---
if __name__ == "__main__":
    print("\n--- 🧪 PROBANDO FLUJO DE CORREO INTERACTIVO ---")
    
    # IMPORTANTE: Cambia el correo o teléfono si ya usaste estos en pruebas anteriores 
    # para evitar el error de "Duplicado"
    registro = registrar_usuario(
        nombre="Carlos", 
        apellido="Mendoza", 
        correo="carlos.mendoza@email.com", 
        telefono="+584149998811", 
        contrasena_plana="NexoClave*2026", 
        fecha_nacimiento_str="1998-03-12"
    )
    
    if registro["status"] == "success":
        uid = registro["usuario_id"]
        
        # El programa se va a pausar aquí esperando que escribas en tu terminal
        codigo_usuario = input("Introduce el código de 6 dígitos que imprimió la consola arriba: ")
        confirmar_codigo_correo(uid, codigo_usuario)