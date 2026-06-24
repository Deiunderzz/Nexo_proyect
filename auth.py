import psycopg2
import bcrypt
import re
import random
from datetime import date, datetime, timedelta
import jwt
import uuid
from bcv_provider import obtener_tasas_bcv

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
                pass
        return {"status": "success", "message": "Pre-registro de cédula guardado temporalmente."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def completar_registro_usuario(nombre, apellido, correo, telefono, contrasena, fecha_nacimiento_str, edad):
    if not validar_complejidad_contrasena(contrasena):
        return {"status": "error", "message": "La contraseña debe tener mínimo 8 caracteres, una mayúscula, un número y un símbolo."}
    
    salt = bcrypt.gensalt(12)
    contrasena_hasheada = bcrypt.hashpw(contrasena.encode('utf-8'), salt).decode('utf-8')
    
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, fecha_nacimiento, edad, rol)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'cliente') RETURNING id;
                """, (nombre, apellido, correo, telefono, contrasena_hasheada, fecha_nacimiento_str, edad))
                usuario_id = cursor.fetchone()[0]
                
                codigo_otp = str(random.randint(100000, 999999))
                cursor.execute("INSERT INTO codigos_verificacion (usuario_id, codigo) VALUES (%s, %s);", (usuario_id, codigo_otp))
                conexion.commit()
                
                print(f"📧 [SIMULACIÓN CORREO] Código de verificación enviado a {correo}: {codigo_otp}")
                return {"status": "success", "message": "Usuario registrado. Introduce el código OTP enviado a tu correo.", "usuario_id": usuario_id}
    except psycopg2.IntegrityError:
        return {"status": "error", "message": "El correo o teléfono ya se encuentra registrado."}
    except Exception as e:
        return {"status": "error", "message": f"Error del servidor: {str(e)}"}

def confirmar_codigo_correo(usuario_id, codigo_ingresado):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, codigo FROM codigos_verificacion WHERE usuario_id = %s ORDER BY id DESC LIMIT 1;", (usuario_id,))
                resultado = cursor.fetchone()
                
                if not resultado or resultado[1] != codigo_ingresado:
                    return {"status": "error", "message": "Código OTP inválido o expirado."}
                
                cursor.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s;", (usuario_id,))
                cursor.execute("DELETE FROM codigos_verificacion WHERE usuario_id = %s;", (usuario_id,))
                conexion.commit()
                
                return {"status": "success", "message": "Cuenta activada con éxito. Ya puedes iniciar sesión."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def iniciar_sesion(correo, contrasena):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, contrasena, rol, discoteca_id, verificado FROM usuarios WHERE correo = %s;", (correo,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    return {"status": "error", "message": "Credenciales inválidas."}
                
                usuario_id, hash_contra, rol, discoteca_id, verificado = usuario
                
                if not bcrypt.checkpw(contrasena.encode('utf-8'), hash_contra.encode('utf-8')):
                    return {"status": "error", "message": "Credenciales inválidas."}
                
                # --- FLUJO CONTROLADO DE NEXO EMPRESAS ---
                if rol == 'admin':
                    codigo_otp = str(random.randint(100000, 999999))
                    cursor.execute("INSERT INTO codigos_verificacion (usuario_id, codigo) VALUES (%s, %s);", (usuario_id, codigo_otp))
                    conexion.commit()
                    
                    print(f"📧 [NEXO EMPRESAS OTP] Código enviado al dueño ({correo}): {codigo_otp}")
                    return {
                        "status": "requires_otp",
                        "message": "🔒 Perfil corporativo detectado. Ingrese el código OTP de 6 dígitos enviado.",
                        "usuario_id": usuario_id
                    }
                
                if not verificado:
                    return {"status": "requires_verification", "message": "Tu cuenta no está verificada.", "usuario_id": usuario_id}
                
                # Payload del cliente regular
                payload = {"usuario_id": usuario_id, "rol": rol, "exp": datetime.utcnow() + timedelta(days=1)}
                token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
                return {"status": "success", "rol": rol, "token": token, "message": "¡Sesión iniciada!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def verificar_otp_empresa(usuario_id, codigo_otp):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, codigo FROM codigos_verificacion WHERE usuario_id = %s ORDER BY id DESC LIMIT 1;", (usuario_id,))
                res = cursor.fetchone()
                if not res or res[1] != codigo_otp:
                    return {"status": "error", "message": "Código de verificación erróneo o expirado."}
                
                cursor.execute("SELECT id, rol, discoteca_id FROM usuarios WHERE id = %s;", (usuario_id,))
                usuario = cursor.fetchone()
                
                # Payload reforzado con la discoteca asignada para aislamiento total
                payload = {
                    "usuario_id": usuario[0],
                    "rol": usuario[1],
                    "discoteca_id": usuario[2],
                    "exp": datetime.utcnow() + timedelta(hours=8)
                }
                token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
                cursor.execute("DELETE FROM codigos_verificacion WHERE usuario_id = %s;", (usuario_id,))
                conexion.commit()
                
                return {
                    "status": "success",
                    "rol": usuario[1],
                    "discoteca_id": usuario[2],
                    "token": token,
                    "message": "🔒 Autenticado en Nexo Empresas de manera segura."
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_discotecas():
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, nombre, ubicacion FROM discotecas;")
                discos = cursor.fetchall()
                return {"status": "success", "data": [{"id": d[0], "nombre": d[1], "ubicacion": d[2]} for d in discos]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def liberar_reservas_expiradas(cursor):
    cursor.execute("""
        UPDATE reservas SET estado = 'expirada' 
        WHERE estado = 'pendiente_pago' AND expira_en < CURRENT_TIMESTAMP;
    """)

def obtener_layout_discoteca(disco_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                liberar_reservas_expiradas(cursor)
                conexion.commit()
                
                cursor.execute("""
                    SELECT m.id, m.identificador_mesa, m.posicion_x, m.posicion_y, z.nombre_zona, z.consumo_minimo_usd,
                           (SELECT estado FROM reservas r WHERE r.mesa_id = m.id AND r.estado IN ('pendiente_pago', 'pagado_aprobado') LIMIT 1) as estado_actual
                    FROM mesas m
                    JOIN zonas_discoteca z ON m.zona_id = z.id
                    WHERE m.discoteca_id = %s;
                """, (disco_id,))
                mesas_bd = cursor.fetchall()
                
                layout = []
                for m in mesas_bd:
                    estado_reserva = m[6]
                    disponibilidad = "disponible"
                    if estado_reserva == "pendiente_pago": disponibilidad = "bloqueada_temporalmente"
                    elif estado_reserva == "pagado_aprobado": disponibilidad = "ocupada"
                    
                    layout.append({
                        "mesa_id": m[0],
                        "identificador": m[1],
                        "x": m[2],
                        "y": m[3],
                        "zona_nombre": m[4],
                        "consumo_minimo_usd": float(m[5]),
                        "disponibilidad": disponibilidad
                    })
                return {"status": "success", "discoteca_id": disco_id, "layout": layout}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_menu_botellas(disco_id):
    tasas = obtener_tasas_bcv()
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, nombre_licor, categoria, precio_usd, stock FROM inventario_botellas WHERE discoteca_id = %s AND disponible = TRUE;", (disco_id,))
                botellas = cursor.fetchall()
                
                menu = []
                for b in botellas:
                    p_usd = float(b[3])
                    p_ves = p_usd * tasas["USD"]
                    p_eur = (p_usd * tasas["USD"]) / tasas["EUR"] if disco_id == 1 else None # Recargo/Cambio Kabal
                    
                    menu.append({
                        "botella_id": b[0],
                        "nombre_licor": b[1],
                        "categoria": b[2],
                        "precio_usd": p_usd,
                        "precio_ves_bcv": round(p_ves, 2),
                        "precio_eur": round(p_eur, 2) if p_eur else None,
                        "stock_disponible": b[4]
                    })
                return {"status": "success", "tasa_bcv_usada": tasas["USD"], "menu": menu}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_precio_botella(botella_id, nuevo_precio_usd, admin_disco_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                # Comprobación de aislamiento multitenant
                cursor.execute("SELECT discoteca_id FROM inventario_botellas WHERE id = %s;", (botella_id,))
                res = cursor.fetchone()
                if not res or res[0] != admin_disco_id:
                    return {"status": "error", "message": "Acceso denegado. Este licor no pertenece a tu discoteca."}
                
                cursor.execute("UPDATE inventario_botellas SET precio_usd = %s WHERE id = %s;", (nuevo_precio_usd, botella_id))
                conexion.commit()
                return {"status": "success", "message": "Precio de menú actualizado en vivo."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_consumo_zona(zona_id, nuevo_minimo_usd, admin_disco_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT discoteca_id FROM zonas_discoteca WHERE id = %s;", (zona_id,))
                res = cursor.fetchone()
                if not res or res[0] != admin_disco_id:
                    return {"status": "error", "message": "Acceso denegado. Esta zona no pertenece a tu discoteca."}
                    
                cursor.execute("UPDATE zonas_discoteca SET consumo_minimo_usd = %s WHERE id = %s;", (nuevo_minimo_usd, zona_id))
                conexion.commit()
                return {"status": "success", "message": "Consumo mínimo de la zona reconfigurado."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def validar_y_crear_intencion_reserva(usuario_id, mesa_id, pedido_botellas):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                liberar_reservas_expiradas(cursor)
                
                cursor.execute("""
                    SELECT r.id FROM reservas r 
                    WHERE r.mesa_id = %s AND r.estado IN ('pendiente_pago', 'pagado_aprobado');
                """, (mesa_id,))
                if cursor.fetchone():
                    return {"status": "error", "message": "La mesa ya se encuentra ocupada o retenida por otro usuario."}
                
                cursor.execute("""
                    SELECT m.discoteca_id, z.consumo_minimo_usd 
                    FROM mesas m 
                    JOIN zonas_discoteca z ON m.zona_id = z.id WHERE m.id = %s;
                """, (mesa_id,))
                mesa_datos = cursor.fetchone()
                if not mesa_datos: return {"status": "error", "message": "Mesa no encontrada."}
                disco_id, consumo_minimo = mesa_datos
                
                total_carrito = 0.0
                items_validados = []
                
                for item in pedido_botellas:
                    cursor.execute("SELECT nombre_licor, precio_usd, disponible, stock FROM inventario_botellas WHERE id = %s AND discoteca_id = %s;", (item["botella_id"], disco_id))
                    botella = cursor.fetchone()
                    # 👈 CORREGIDO: de 'bottle' a 'botella'
                    if not botella: return {"status": "error", "message": f"Licor ID {item['botella_id']} no pertenece a este local."}
                    
                    nombre, precio, disp, stock = botella
                    if not disp or stock < item["cantidad"]:
                        return {"status": "error", "message": f"Stock insuficiente o licor agotado: {nombre}."}
                    
                    total_carrito += float(precio) * item["cantidad"]
                    items_validados.append((item["botella_id"], item["cantidad"]))
                
                if total_carrito < float(consumo_minimo):
                    return {"status": "error", "message": f"El pedido actual (${total_carrito}) no cubre el consumo mínimo obligatorio de la mesa (${consumo_minimo})."}
                
                expiracion = datetime.now() + timedelta(minutes=15)
                cursor.execute("""
                    INSERT INTO reservas (usuario_id, mesa_id, total_usd, estado, expira_en) 
                    VALUES (%s, %s, %s, 'pendiente_pago', %s) RETURNING id;
                """, (usuario_id, mesa_id, total_carrito, expiracion))
                reserva_id = cursor.fetchone()[0]
                
                for b_id, cant in items_validados:
                    cursor.execute("INSERT INTO detalles_reserva_botellas (reserva_id, botella_id, cantidad) VALUES (%s, %s, %s);", (reserva_id, b_id, cant))
                
                conexion.commit()
                return {"status": "success", "message": "Mesa retenida exitosamente por 15 minutos.", "reserva_id": reserva_id, "total_a_pagar_usd": total_carrito, "expira_en": expiracion.isoformat()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def registrar_pago_reserva_en_bd(reserva_id, metodo_pago, referencia_bancaria, captura_url):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT estado, expira_en FROM reservas WHERE id = %s;", (reserva_id,))
                res = cursor.fetchone()
                if not res: return {"status": "error", "message": "Reserva inexistente."}
                
                if res[0] == 'expirada' or datetime.now() > res[1]:
                    cursor.execute("UPDATE reservas SET estado = 'expirada' WHERE id = %s;", (reserva_id,))
                    conexion.commit()
                    return {"status": "error", "message": "El tiempo límite de 15 minutos expiró. Mesa liberada."}
                
                cursor.execute("""
                    UPDATE reservas 
                    SET estado = 'esperando_aprobacion', metodo_pago = %s, referencia_bancaria = %s, captura_url = %s
                    WHERE id = %s;
                """, (metodo_pago, referencia_bancaria, captura_url, reserva_id))
                conexion.commit()
                return {"status": "success", "message": "Comprobante recibido. En cola de verificación humana de Nexo."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def admin_aprobar_pago_reserva(reserva_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT estado, mesa_id FROM reservas WHERE id = %s;", (reserva_id,))
                res = cursor.fetchone()
                if not res or res[0] != 'esperando_aprobacion':
                    return {"status": "error", "message": "La reserva no está en espera de aprobación."}
                
                cursor.execute("SELECT botella_id, cantidad FROM detalles_reserva_botellas WHERE reserva_id = %s;", (reserva_id,))
                botellas = cursor.fetchall()
                for b_id, cant in botellas:
                    cursor.execute("UPDATE inventario_botellas SET stock = stock - %s WHERE id = %s;", (cant, b_id))
                
                qr_seguro = f"NEXO-PASS-{uuid.uuid4().hex.upper()}"
                cursor.execute("UPDATE reservas SET estado = 'pagado_aprobado', codigo_qr_token = %s WHERE id = %s;", (qr_seguro, reserva_id))
                conexion.commit()
                return {"status": "success", "message": "Pago conciliado. Inventario disminuido y pase QR generado.", "qr_token": qr_seguro}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_historial_usuario(usuario_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT r.id, r.total_usd, r.estado, r.metodo_pago, r.codigo_qr_token, r.creado_en, m.identificador_mesa, z.id, z.nombre_zona
                    FROM reservas r
                    JOIN mesas m ON r.mesa_id = m.id
                    JOIN zonas_discoteca z ON m.zona_id = z.id
                    WHERE r.usuario_id = %s ORDER BY r.creado_en DESC;
                """, (usuario_id,))
                reservas = cursor.fetchall()
                
                historial_completo = []
                for r in reservas:
                    res_id, total_usd, estado, metodo, qr_token, creado_en, id_mesa, zona_id, nombre_zona = r
                    
                    cursor.execute("""
                        SELECT dr.botella_id, ib.nombre_licor, dr.cantidad, ib.precio_usd 
                        FROM detalles_reserva_botellas dr
                        JOIN inventario_botellas ib ON dr.botella_id = ib.id WHERE dr.reserva_id = %s;
                    """, (res_id,))
                    botellas_bd = cursor.fetchall()
                    desglose = [{"botella_id": b[0], "nombre_licor": b[1], "cantidad": b[2], "precio_unitario_usd": float(b[3])} for b in botellas_bd]
                    
                    historial_completo.append({
                        "reserva_id": res_id,
                        "mesa": id_mesa,
                        "zona": {"id": zona_id, "nombre": nombre_zona},
                        "total_usd": float(total_usd),
                        "estado": estado,
                        "metodo_pago": metodo or "No especificado",
                        "codigo_qr_token": qr_token or "BLOQUEADO - Esperando pago",
                        "fecha_creacion": creado_en.isoformat(),
                        "pedido_botellas": desglose
                    })
        return {"status": "success", "data": historial_completo}
    except Exception as e:
        return {"status": "error", "message": str(e)}