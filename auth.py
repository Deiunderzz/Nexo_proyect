import psycopg2
import bcrypt
import re
import random
from datetime import date, datetime, timedelta
import jwt
import uuid
from bcv_provider import obtener_tasas_bcv

# Configuración de la conexión a PostgreSQL
DB_CONFIG = {
    "host": "localhost",
    "database": "nexo_db",
    "user": "postgres",
    "password": "hOMERO20*"
}

JWT_SECRET = "NexoSuperSecretKey2026_CambiarEnProduccion"
JWT_ALGORITHM = "HS256"

def validar_complejidad_contrasena(contrasena):
    if len(contrasena) < 8: return False
    if not re.search(r"[A-Z]", contrasena): return False
    if not re.search(r"[0-9]", contrasena): return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", contrasena): return False
    return True

def calcular_edad(fecha_nacimiento_str):
    fecha_nac = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
    hoy = date.today()
    return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))

def pre_registrar_cedula(nombre, apellido, fecha_nacimiento_str, edad):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                sql_check = "SELECT id FROM usuarios WHERE nombre = %s AND apellido = %s AND fecha_nacimiento = %s;"
                cursor.execute(sql_check, (nombre, apellido, fecha_nacimiento_str))
                usuario_existente = cursor.fetchone()
                
                if usuario_existente:
                    return {"status": "success", "usuario_id": usuario_existente[0]}
                
                sql_insert = """
                INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, fecha_nacimiento, edad, verificado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING id;
                """
                correo_temporal = f"temp_{random.randint(10000, 99999)}@nexo.com"
                telefono_temporal = f"+58temp{random.randint(1000000, 9999999)}"
                contrasena_hash = bcrypt.hashpw(b"TempPassword123*", bcrypt.gensalt()).decode('utf-8')
                
                cursor.execute(sql_insert, (nombre, apellido, correo_temporal, telefono_temporal, contrasena_hash, fecha_nacimiento_str, edad))
                nuevo_id = cursor.fetchone()[0]
                conexion.commit()
                
        return {"status": "success", "usuario_id": nuevo_id}
    except Exception as e:
        return {"status": "error", "message": f"Error en base de datos: {str(e)}"}

def completar_registro_usuario(usuario_id, nombre, apellido, correo, telefono, contrasena_plana):
    try:
        if not validar_complejidad_contrasena(contrasena_plana):
            return {"status": "error", "message": "La contraseña debe tener al menos 8 caracteres, una mayúscula, un número y un carácter especial."}
        
        contrasena_encriptada = bcrypt.hashpw(contrasena_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE correo = %s AND id != %s;", (correo, usuario_id))
                if cursor.fetchone():
                    return {"status": "error", "message": "El correo electrónico ya está registrado por otro usuario."}
                
                cursor.execute("SELECT id FROM usuarios WHERE telefono = %s AND id != %s;", (telefono, usuario_id))
                if cursor.fetchone():
                    return {"status": "error", "message": "El número de teléfono ya está registrado por otro usuario."}
                
                sql_update = """
                UPDATE usuarios 
                SET nombre = %s, apellido = %s, correo = %s, telefono = %s, contrasena = %s
                WHERE id = %s;
                """
                cursor.execute(sql_update, (nombre, apellido, correo, telefono, contrasena_encriptada, usuario_id))
                
                codigo_verificacion = str(random.randint(100000, 999996))
                cursor.execute("DELETE FROM codigos_verificacion WHERE usuario_id = %s;", (usuario_id,))
                cursor.execute("INSERT INTO codigos_verificacion (usuario_id, codigo) VALUES (%s, %s);", (usuario_id, codigo_verificacion))
                
                conexion.commit()
                
        print(f"📧 [SIMULACIÓN CORREO] Enviando código {codigo_verificacion} a {correo}")
        return {"status": "success", "message": "Datos de contacto actualizados. Código enviado."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def confirmar_codigo_correo(usuario_id, codigo_ingresado):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT codigo, creado_en FROM codigos_verificacion WHERE usuario_id = %s;", (usuario_id,))
                registro = cursor.fetchone()
                
                if not registro:
                    return {"status": "error", "message": "No se ha generado ningún código para este usuario."}
                
                codigo_correcto, creado_en = registro
                if datetime.now() - creado_en > timedelta(minutes=10):
                    return {"status": "error", "message": "El código ha expirado (Validez: 10 min). Solicita uno nuevo."}
                
                if codigo_ingresado != codigo_correcto:
                    return {"status": "error", "message": "Código incorrecto."}
                
                cursor.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s;", (usuario_id,))
                cursor.execute("DELETE FROM codigos_verificacion WHERE usuario_id = %s;", (usuario_id,))
                conexion.commit()
                
        return {"status": "success", "message": "Cuenta activada con éxito. Ya puedes iniciar sesión."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def iniciar_sesion(identificador, contrasena_plana):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, nombre, apellido, contrasena, verificado, nivel_lealtad FROM usuarios WHERE correo = %s OR telefono = %s;", (identificador, identificador))
                usuario = cursor.fetchone()
                
                if not usuario:
                    return {"status": "error", "message": "Credenciales inválidas (Usuario no encontrado)."}
                
                u_id, nombre, apellido, contrasena_hash, verificado, nivel_lealtad = usuario
                
                if not bcrypt.checkpw(contrasena_plana.encode('utf-8'), contrasena_hash.encode('utf-8')):
                    return {"status": "error", "message": "Credenciales inválidas (Contraseña incorrecta)."}
                
                if not verificado:
                    return {"status": "error", "message": "Tu cuenta no está activada. Verifica tu correo primero."}
                
                payload = {
                    "usuario_id": u_id,
                    "nombre": nombre,
                    "apellido": apellido,
                    "nivel_lealtad": nivel_lealtad,
                    "exp": datetime.utcnow() + timedelta(hours=24)
                }
                token_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
                
        return {
            "status": "success",
            "message": "Autenticación exitosa",
            "token_nexo": token_jwt,
            "perfil": {"nombre": nombre, "apellido": apellido, "rango": nivel_lealtad}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_discotecas():
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, nombre, ubicacion FROM discotecas;")
                columnas = [desc[0] for desc in cursor.description]
                resultado = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"status": "success", "data": resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def liberar_reservas_expiradas():
    """
    ⏱️ LÓGICA CRON (OPCIÓN C)
    Busca reservas 'Pendiente' que lleven más de 15 minutos sin pagarse,
    las cancela y vuelve a poner sus zonas disponibles en el plano.
    """
    try:
        limite_tiempo = datetime.now() - timedelta(minutes=15)
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                # 1. Buscar las zonas que pertenecen a reservas colgadas/expiradas
                cursor.execute("""
                    SELECT id, zona_id FROM reservas 
                    WHERE estado = 'Pendiente' AND creado_en <= %s;
                """, (limite_tiempo,))
                expiradas = cursor.fetchall()
                
                if expiradas:
                    reserva_ids = [r[0] for r in expiradas]
                    zona_ids = list(set([r[1] for r in expiradas])) # Evitar duplicados
                    
                    # 2. Mover el estatus a 'Expirada'
                    cursor.execute("""
                        UPDATE reservas SET estado = 'Expirada' 
                        WHERE id = ANY(%s);
                    """, (reserva_ids,))
                    
                    # 3. Liberar las zonas para que vuelvan a estar disponibles en el mapa
                    cursor.execute("""
                        UPDATE zonas_discoteca SET disponible = TRUE 
                        WHERE id = ANY(%s);
                    """, (zona_ids,))
                    
                    conexion.commit()
                    print(f"⏱️ [NEXO CRON] Se expiraron automáticamente {len(reserva_ids)} reservas colgadas.")
    except Exception as e:
        print(f"⚠️ Error en limpieza automática de reservas: {e}")

def obtener_layout_discoteca(discoteca_id):
    try:
        # ⏱️ LLAMADA EN CALIENTE (OPCIÓN C): Limpia reservas antes de consultar el mapa
        liberar_reservas_expiradas()
        
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT id, nombre_zona, capacidad, precio_minimo_consumo, coordenada_x, coordenada_y, disponible 
                    FROM zonas_discoteca WHERE discoteca_id = %s;
                """, (discoteca_id,))
                columnas = [desc[0] for desc in cursor.description]
                resultado = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"status": "success", "data": resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_menu_botellas(discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT id, nombre_licor, categoria, precio_usd, disponible 
                    FROM inventario_botellas WHERE discoteca_id = %s;
                """, (discoteca_id,))
                columnas = [desc[0] for desc in cursor.description]
                resultado = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"status": "success", "data": resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_precio_botella(botella_id, nuevo_precio, disponible):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "UPDATE inventario_botellas SET precio_usd = %s, disponible = %s WHERE id = %s;",
                    (nuevo_precio, disponible, botella_id)
                )
                conexion.commit()
        return {"status": "success", "message": "Inventario de botella modificado dinámicamente."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_consumo_zona(zona_id, nuevo_minimo):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "UPDATE zonas_discoteca SET precio_minimo_consumo = %s WHERE id = %s;",
                    (nuevo_minimo, zona_id)
                )
                conexion.commit()
        return {"status": "success", "message": "Consumo mínimo de la zona actualizado."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def validar_y_crear_intencion_reserva(usuario_id, zona_id, desglose_pedido):
    try:
        tasas = obtener_tasas_bcv()
        factor_eur_a_usd = tasas["EUR"] / tasas["USD"] 
        factor_usd_a_eur = tasas["USD"] / tasas["EUR"]

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT precio_minimo_consumo, discoteca_id FROM zonas_discoteca WHERE id = %s;", (zona_id,))
                zona = cursor.fetchone()
                if not zona:
                    return {"status": "error", "message": "La zona o mesa seleccionada no existe."}
                
                consumo_minimo_usd = float(zona[0])
                discoteca_id = zona[1]
                total_pedido_usd = 0.0
                desglose_respuesta = []
                
                for item in desglose_pedido:
                    b_id = item.get("botella_id")
                    cant = item.get("cantidad", 0)
                    if cant <= 0: continue
                        
                    cursor.execute("SELECT nombre_licor, precio_usd, disponible FROM inventario_botellas WHERE id = %s;", (b_id,))
                    botella = cursor.fetchone()
                    
                    if not botella:
                        return {"status": "error", "message": f"La botella con ID {b_id} no existe."}
                    if not botella[2]:
                        return {"status": "error", "message": f"El producto '{botella[0]}' está agotado."}
                        
                    precio_bd = float(botella[1])
                    
                    if discoteca_id == 1:
                        precio_unitario_eur = precio_bd
                        precio_unitario_usd = precio_unitario_eur * factor_eur_a_usd
                    else:
                        precio_unitario_usd = precio_bd
                        precio_unitario_eur = precio_unitario_usd * factor_usd_a_eur
                        
                    subtotal_usd = precio_unitario_usd * cant
                    total_pedido_usd += subtotal_usd
                    
                    desglose_respuesta.append({
                        "botella_id": b_id,
                        "nombre_licor": botella[0],
                        "cantidad": cant,
                        "precio_unitario_usd": round(precio_unitario_usd, 2),
                        "precio_unitario_eur": round(precio_unitario_eur, 2),
                        "subtotal_usd": round(subtotal_usd, 2)
                    })
                
                if total_pedido_usd < consumo_minimo_usd:
                    faltante_usd = consumo_minimo_usd - total_pedido_usd
                    if discoteca_id == 1:
                        minimo_eur = consumo_minimo_usd * factor_usd_a_eur
                        actual_eur = total_pedido_usd * factor_usd_a_eur
                        faltante_eur = minimo_eur - actual_eur
                        msg = f"No cumples con el consumo mínimo en Kabal. Te faltan {faltante_eur:.2f} EUR (€) por añadir en botellas."
                    else:
                        msg = f"No cumples con el consumo mínimo de la mesa. Te faltan {faltante_usd:.2f} USD ($) por añadir."

                    return {
                        "status": "error", 
                        "message": msg,
                        "moneda_discoteca": "EUR" if discoteca_id == 1 else "USD"
                    }
                
                # Bloquear mesa asignándola como no disponible temporalmente en el plano
                cursor.execute("UPDATE zonas_discoteca SET disponible = FALSE WHERE id = %s;", (zona_id,))
                
                sql_reserva = "INSERT INTO reservas (usuario_id, zona_id, total_pago_usd, estado) VALUES (%s, %s, %s, 'Pendiente') RETURNING id;"
                cursor.execute(sql_reserva, (usuario_id, zona_id, total_pedido_usd))
                reserva_id = cursor.fetchone()[0]
                
                sql_detalle = "INSERT INTO detalles_reserva_botellas (reserva_id, botella_id, cantidad, precio_unitario_usd) VALUES (%s, %s, %s, %s);"
                for det in desglose_respuesta:
                    cursor.execute(sql_detalle, (reserva_id, det["botella_id"], det["cantidad"], det["precio_unitario_usd"]))
                
                conexion.commit()
                
        # ⏱️ MARCA DE EXPIRACIÓN EN CALIENTE PARA EL CONTADOR DEL FRONTEND
        hora_expiracion = datetime.now() + timedelta(minutes=15)
        total_eur_calculado = total_pedido_usd * factor_usd_a_eur
        
        return {
            "status": "success", 
            "reserva_id": reserva_id,
            "moneda_local": "EUR (€)" if discoteca_id == 1 else "USD ($)",
            "total_usd": round(total_pedido_usd, 2),
            "total_eur": round(total_eur_calculado, 2) if discoteca_id == 1 else "N/A",
            "limite_pago_timestamp": hora_expiracion.isoformat(), # 🕒 Formato ISO para alimentar el Timer de la App
            "tiempo_gracia_minutos": 15,
            "message": "Consumo mínimo aprobado con éxito. Tienes 15 minutos para reportar tu pago."
        }
    except Exception as error:
        return {"status": "error", "message": str(error)}

def registrar_pago_reserva_en_bd(reserva_id, metodo_pago, referencia_bancaria=None, captura_url=None):
    try:
        tasas = obtener_tasas_bcv()
        tasa_dolar = tasas["USD"]
        
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                # 1. Verificar si la reserva existe y está Pendiente
                cursor.execute("SELECT estado, total_pago_usd FROM reservas WHERE id = %s;", (reserva_id,))
                reserva = cursor.fetchone()
                
                if not reserva:
                    return {"status": "error", "message": "La reserva especificada no existe."}
                if reserva[0] in ["Confirmada", "Por Verificar"]:
                    return {"status": "error", "message": f"Esta reserva no se puede pagar. Estatus actual: {reserva[0]}"}
                if reserva[0] == "Expirada":
                    return {"status": "error", "message": "El tiempo de gracia de esta reserva expiró y la mesa fue liberada."}
                
                total_usd = float(reserva[1])
                metodo_pago_lower = metodo_pago.lower()
                
                # Definir comportamiento según el método de pago
                es_pago_nacional = metodo_pago_lower in ["pago movil", "transferencia bs"]
                monto_en_bolivares = total_usd * tasa_dolar if es_pago_nacional else 0.0
                
                if es_pago_nacional:
                    # Requiere verificación: va a estatus 'Por Verificar' y SIN Token QR todavía
                    estado_nuevo = "Por Verificar"
                    token_qr = None
                    msg_exito = "Comprobante recibido con éxito. Tu reserva está en espera de validación bancaria."
                else:
                    # Efectivo o método automático (Zelle/Tarjeta si se integrara): Pasa directo
                    estado_nuevo = "Confirmada"
                    token_qr = f"NEXO-{reserva_id}-{str(uuid.uuid4())[:8].upper()}"
                    msg_exito = "Pago en divisa procesado directamente. Reserva Confirmada."
                
                # 2. ACTUALIZAR BASE DE DATOS
                sql_update = """
                    UPDATE reservas 
                    SET estado = %s, metodo_pago = %s, codigo_qr_token = %s, captura_pago_url = %s
                    WHERE id = %s;
                """
                cursor.execute(sql_update, (estado_nuevo, metodo_pago, token_qr, referencia_bancaria or captura_url, reserva_id))
                conexion.commit()
                
        return {
            "status": "success",
            "message": msg_exito,
            "detalle_transaccion": {
                "reserva_id": reserva_id,
                "estatus_actual": estado_nuevo,
                "monto_en_divisa": round(total_usd, 2),
                "monto_en_bolivares_bcv": round(monto_en_bolivares, 2) if es_pago_nacional else "N/A",
                "codigo_acceso_qr": token_qr or "BLOQUEADO - Esperando aprobación del local",
                "referencia_registrada": referencia_bancaria
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Falla transaccional en Base de Datos: {str(e)}"}


def admin_aprobar_pago_reserva(reserva_id):
    """
    Función exclusiva para el Gerente/Admin. Revisa que el estatus sea 'Por Verificar',
    lo aprueba y le genera el código QR definitivo al cliente.
    """
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT estado FROM reservas WHERE id = %s;", (reserva_id,))
                reserva = cursor.fetchone()
                
                if not reserva:
                    return {"status": "error", "message": "Reserva no encontrada."}
                if reserva[0] != "Por Verificar":
                    return {"status": "error", "message": f"No se puede aprobar esta reserva. Su estatus actual es: {reserva[0]}"}
                
                # Generar el QR definitivo ahora que el dinero está en el banco
                token_qr = f"NEXO-{reserva_id}-{str(uuid.uuid4())[:8].upper()}"
                
                cursor.execute("""
                    UPDATE reservas 
                    SET estado = 'Confirmada', codigo_qr_token = %s 
                    WHERE id = %s;
                """, (token_qr, reserva_id))
                
                conexion.commit()
                
        return {
            "status": "success",
            "message": f"🎉 ¡Reserva {reserva_id} aprobada por el administrador! Mesa liberada y QR generado.",
            "codigo_qr_token": token_qr
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}