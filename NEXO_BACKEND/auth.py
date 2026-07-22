import psycopg2
import bcrypt
import re
import random
from datetime import date, datetime, timedelta
import jwt
import uuid
import os
from dotenv import load_dotenv
from bcv_provider import obtener_tasas_bcv
from email_provider import (
    enviar_otp_bienvenida, 
    enviar_otp_corporativo_2fa, 
    enviar_otp_recuperacion_clave, 
    enviar_correo_qr_reserva
)

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "nexo_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD")
}

JWT_SECRET = os.getenv("JWT_SECRET", "NexoSuperSecretKey2026_CambiarEnProduccion")
JWT_ALGORITHM = "HS256"

def validar_complejidad_contrasena(contrasena):
    if len(contrasena) < 8: return False
    if not re.search(r"[A-Z]", contrasena): return False
    if not re.search(r"[0-9]", contrasena): return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", contrasena): return False
    return True

def completar_registro_usuario(token_cedula, correo, telefono, contrasena, nombre, apellido, cedula_manual=None):
    try:
        try:
            payload = jwt.decode(token_cedula, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return {"status": "error", "message": "El token de la cédula ha expirado. Vuelve a escanearla."}
        except jwt.InvalidTokenError:
            return {"status": "error", "message": "Firma inválida o alteración detectada."}

        # El número de cédula lo sugiere la IA, pero el usuario puede corregirlo
        cedula = (cedula_manual or payload.get("cedula") or "").strip() or None
        fecha_nacimiento_str = payload.get("fecha_nacimiento")

        # El OCR entrega la fecha como DD/MM/AAAA (string). Si se manda tal cual,
        # Postgres la interpreta según su DateStyle (normalmente MDY) y "20/05/2006"
        # revienta porque el mes 20 no existe. Se convierte a un date real aquí para
        # que psycopg2 la envíe sin ambigüedad, sin importar el DateStyle del servidor.
        fecha_nacimiento = None
        if fecha_nacimiento_str:
            try:
                fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, "%d/%m/%Y").date()
            except ValueError:
                return {"status": "error", "message": "Fecha de nacimiento inválida en el documento escaneado. Vuelve a escanear."}
        edad = payload.get("edad")

        nombre = (nombre or "").strip()
        apellido = (apellido or "").strip()
        if not nombre or not apellido:
            return {"status": "error", "message": "Nombre y apellido son requeridos."}

        # Segunda comprobación de edad, independiente de la que ya se hizo al escanear:
        # el token no debe poder usarse para registrar a un menor de edad aunque el
        # endpoint de escaneo cambie en el futuro.
        if edad is None or edad < 18:
            return {"status": "error", "message": "Debes ser mayor de 18 años para registrarte en Nexo."}

        if not validar_complejidad_contrasena(contrasena):
            return {"status": "error", "message": "La contraseña no cumple los requisitos mínimos de robustez."}

        salt = bcrypt.gensalt()
        clave_hasheada = bcrypt.hashpw(contrasena.encode('utf-8'), salt).decode('utf-8')

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO usuarios (nombre, apellido, correo, telefono, contrasena, fecha_nacimiento, edad, verificado, rol, cedula)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, 'cliente', %s) RETURNING id;
                    """,
                    (nombre, apellido, correo, telefono, clave_hasheada, fecha_nacimiento, edad, cedula)
                )
                usuario_id = cursor.fetchone()[0]

                codigo_otp = str(random.randint(100000, 999999))
                expiracion = datetime.now() + timedelta(minutes=15)
                cursor.execute(
                    "INSERT INTO codigos_verificacion (usuario_id, codigo_otp, expiracion) VALUES (%s, %s, %s);",
                    (usuario_id, codigo_otp, expiracion)
                )
                conexion.commit()

        enviar_otp_bienvenida(correo, nombre, codigo_otp)
        return {"status": "success", "message": "Introduce el código OTP enviado a tu correo.", "usuario_id": usuario_id}
    except psycopg2.IntegrityError as e:
        if "correo" in str(e): return {"status": "error", "message": "El correo ya está registrado."}
        if "telefono" in str(e): return {"status": "error", "message": "El teléfono ya está registrado."}
        return {"status": "error", "message": "Datos duplicados detectados."}
    except Exception as error:
        return {"status": "error", "message": str(error)}

def confirmar_codigo_correo(usuario_id, codigo_ingresado):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, codigo_otp, expiracion FROM codigos_verificacion WHERE usuario_id = %s ORDER BY creado_en DESC LIMIT 1;", (usuario_id,))
                registro = cursor.fetchone()
                if not registro: return {"status": "error", "message": "No se encontró código."}
                
                codigo_id, otp_bd, expiracion = registro
                if datetime.now() > expiracion: return {"status": "error", "message": "Código expirado."}
                if otp_bd != codigo_ingresado: return {"status": "error", "message": "Código incorrecto."}

                cursor.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s;", (usuario_id,))
                cursor.execute("DELETE FROM codigos_verificacion WHERE id = %s;", (codigo_id,))
                conexion.commit()
        return {"status": "success", "message": "¡Cuenta verificada con éxito!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def iniciar_sesion(correo, contrasena):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, nombre, apellido, contrasena, verificado, rol FROM usuarios WHERE correo = %s;", (correo,))
                usuario = cursor.fetchone()
                if not usuario: return {"status": "error", "message": "Credenciales inválidas."}

                u_id, nombre, apellido, hash_bd, verificado, rol = usuario
                if not bcrypt.checkpw(contrasena.encode('utf-8'), hash_bd.encode('utf-8')):
                    return {"status": "error", "message": "Credenciales inválidas."}

                if not verificado: return {"status": "error", "message": "Cuenta no verificada."}

                if rol == 'admin':
                    # TEMPORAL: código fijo mientras se resuelve la entrega de correo con Resend.
                    # Sustituir por random.randint(100000, 999999) una vez el dominio esté verificado.
                    codigo_otp = "123456"
                    cursor.execute("INSERT INTO codigos_verificacion (usuario_id, codigo_otp, expiracion) VALUES (%s, %s, %s);", (u_id, codigo_otp, datetime.now() + timedelta(minutes=5)))
                    conexion.commit()
                    enviar_otp_corporativo_2fa(correo, codigo_otp)
                    return {"status": "requires_otp", "message": "🔒 Doble factor requerido.", "usuario_id": u_id}

                token = jwt.encode({"usuario_id": u_id, "rol": rol, "exp": datetime.utcnow() + timedelta(days=7)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
                return {"status": "success", "token": token, "usuario": {"id": u_id, "nombre": nombre, "apellido": apellido, "rol": rol}}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def verificar_otp_empresa(usuario_id, codigo_ingresado):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, codigo_otp, expiracion FROM codigos_verificacion WHERE usuario_id = %s ORDER BY creado_en DESC LIMIT 1;", (usuario_id,))
                registro = cursor.fetchone()
                if not registro: return {"status": "error", "message": "No hay token pendiente."}

                codigo_id, otp_bd, expiracion = registro
                if datetime.now() > expiracion: return {"status": "error", "message": "Token expirado."}
                if otp_bd != codigo_ingresado: return {"status": "error", "message": "Token incorrecto."}

                cursor.execute("SELECT id, nombre, apellido, rol, discoteca_id FROM usuarios WHERE id = %s;", (usuario_id,))
                u_id, nombre, apellido, rol, discoteca_id = cursor.fetchone()
                cursor.execute("DELETE FROM codigos_verificacion WHERE id = %s;", (codigo_id,))
                conexion.commit()

                token = jwt.encode({"usuario_id": u_id, "rol": rol, "discoteca_id": discoteca_id, "exp": datetime.utcnow() + timedelta(hours=8)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
                return {"status": "success", "token": token, "usuario": {"id": u_id, "nombre": nombre, "apellido": apellido, "rol": rol, "discoteca_id": discoteca_id}}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def solicitar_recuperacion_contrasena(correo):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE correo = %s;", (correo,))
                usuario = cursor.fetchone()
                if not usuario:
                    return {"status": "success", "message": "Si el correo coincide, recibirás un token OTP."}
                
                usuario_id = usuario[0]
                codigo_otp = str(random.randint(100000, 999999))
                cursor.execute("INSERT INTO codigos_verificacion (usuario_id, codigo_otp, expiracion) VALUES (%s, %s, %s);", (usuario_id, codigo_otp, datetime.now() + timedelta(minutes=15)))
                conexion.commit()
                
        enviar_otp_recuperacion_clave(correo, codigo_otp)
        return {"status": "success", "message": "Código de recuperación enviado con éxito."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def procesar_cambio_contrasena_otp(correo, codigo_otp, nueva_contrasena):
    try:
        if not validar_complejidad_contrasena(nueva_contrasena):
            return {"status": "error", "message": "La contraseña no cumple requisitos mínimos de seguridad."}
            
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT cv.id, cv.usuario_id, cv.expiracion FROM codigos_verificacion cv
                    JOIN usuarios u ON cv.usuario_id = u.id WHERE u.correo = %s AND cv.codigo_otp = %s
                    ORDER BY cv.creado_en DESC LIMIT 1;
                    """, (correo, codigo_otp)
                )
                registro = cursor.fetchone()
                if not registro: return {"status": "error", "message": "Código OTP inválido."}
                    
                id_codigo, usuario_id, expiracion = registro
                if datetime.now() > expiracion: return {"status": "error", "message": "OTP expirado."}
                    
                salt = bcrypt.gensalt()
                clave_hasheada = bcrypt.hashpw(nueva_contrasena.encode('utf-8'), salt).decode('utf-8')
                cursor.execute("UPDATE usuarios SET contrasena = %s WHERE id = %s;", (clave_hasheada, usuario_id))
                cursor.execute("DELETE FROM codigos_verificacion WHERE id = %s;", (id_codigo,))
                conexion.commit()
        return {"status": "success", "message": "Contraseña restablecida correctamente."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_datos_pago_discoteca(discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pago_movil_banco, pago_movil_telefono, pago_movil_cedula_rif, pago_movil_titular,
                           zelle_correo, zelle_titular, efectivo_nota
                    FROM discotecas WHERE id = %s;
                    """, (discoteca_id,)
                )
                fila = cursor.fetchone()
                if not fila: return {"status": "error", "message": "Establecimiento inválido."}

                pm_banco, pm_telefono, pm_cedula_rif, pm_titular, zelle_correo, zelle_titular, efectivo_nota = fila
                data = {
                    "pago_movil": {
                        "banco": pm_banco, "telefono": pm_telefono,
                        "cedula_rif": pm_cedula_rif, "titular": pm_titular
                    },
                    "zelle": {"correo": zelle_correo, "titular": zelle_titular},
                    "efectivo": {"nota": efectivo_nota}
                }
                return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_datos_pago_discoteca(discoteca_id, datos, admin_discoteca_id):
    try:
        # Un admin solo puede editar las cuentas de pago de su propio establecimiento
        if discoteca_id != admin_discoteca_id:
            return {"status": "error", "message": "No tienes permiso para editar este establecimiento."}

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id FROM discotecas WHERE id = %s;", (discoteca_id,))
                if not cursor.fetchone(): return {"status": "error", "message": "Establecimiento inválido."}

                cursor.execute(
                    """
                    UPDATE discotecas SET
                        pago_movil_banco = %s, pago_movil_telefono = %s, pago_movil_cedula_rif = %s, pago_movil_titular = %s,
                        zelle_correo = %s, zelle_titular = %s, efectivo_nota = %s
                    WHERE id = %s;
                    """,
                    (
                        datos.get("pago_movil_banco"), datos.get("pago_movil_telefono"),
                        datos.get("pago_movil_cedula_rif"), datos.get("pago_movil_titular"),
                        datos.get("zelle_correo"), datos.get("zelle_titular"),
                        datos.get("efectivo_nota"), discoteca_id
                    )
                )
                conexion.commit()
        return {"status": "success", "message": "Datos de pago actualizados correctamente."}
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

def obtener_layout_discoteca(discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT m.id, m.identificador_mesa, m.posicion_x, m.posicion_y, z.nombre_zona, z.consumo_minimo_usd, m.estado,
                           EXISTS (SELECT 1 FROM reservas r WHERE r.mesa_id = m.id AND r.estado IN ('pendiente', 'aprobado', 'esperando_aprobacion') AND r.expiracion_reserva > NOW()) as ocupada
                    FROM mesas m JOIN zonas_discoteca z ON m.zona_id = z.id WHERE m.discoteca_id = %s;
                    """, (discoteca_id,)
                )
                mesas = cursor.fetchall()
                return {"status": "success", "data": [{"mesa_id": m[0], "identificador": m[1], "x": m[2], "y": m[3], "zona": m[4], "consumo_minimo_usd": float(m[5]), "estado": m[6], "ocupada": m[7]} for m in mesas]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_menu_botellas(discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id, nombre_licor, categoria, precio_usd, stock FROM inventario_botellas WHERE discoteca_id = %s AND disponible = TRUE;", (discoteca_id,))
                botellas = cursor.fetchall()
                return {"status": "success", "data": [{"id": b[0], "nombre_licor": b[1], "categoria": b[2], "precio_usd": float(b[3]), "stock": b[4]} for b in botellas]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_precio_botella(botella_id, nuevo_precio, admin_discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT discoteca_id FROM inventario_botellas WHERE id = %s;", (botella_id,))
                res = cursor.fetchone()
                if not res or res[0] != admin_discoteca_id: return {"status": "error", "message": "Acceso denegado."}
                cursor.execute("UPDATE inventario_botellas SET precio_usd = %s WHERE id = %s;", (nuevo_precio, botella_id))
                conexion.commit()
        return {"status": "success", "message": "Precio modificado."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_consumo_zona(zona_id, nuevo_consumo, admin_discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT discoteca_id FROM zonas_discoteca WHERE id = %s;", (zona_id,))
                res = cursor.fetchone()
                if not res or res[0] != admin_discoteca_id: return {"status": "error", "message": "Permiso denegado."}
                cursor.execute("UPDATE zonas_discoteca SET consumo_minimo_usd = %s WHERE id = %s;", (nuevo_consumo, zona_id))
                conexion.commit()
        return {"status": "success", "message": "Consumo mínimo ajustado."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def actualizar_estado_mesa(mesa_id, nuevo_estado, admin_discoteca_id):
    try:
        if nuevo_estado not in ("libre", "bloqueada"):
            return {"status": "error", "message": "Estado inválido. Usa 'libre' o 'bloqueada'."}

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT discoteca_id FROM mesas WHERE id = %s;", (mesa_id,))
                res = cursor.fetchone()
                if not res or res[0] != admin_discoteca_id:
                    return {"status": "error", "message": "Acceso denegado."}

                cursor.execute("UPDATE mesas SET estado = %s WHERE id = %s;", (nuevo_estado, mesa_id))
                conexion.commit()
        return {"status": "success", "message": f"Mesa marcada como '{nuevo_estado}'.", "estado": nuevo_estado}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def validar_y_crear_intencion_reserva(usuario_id, mesa_id, lista_botellas):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT m.id, z.id, z.consumo_minimo_usd, m.estado FROM mesas m JOIN zonas_discoteca z ON m.zona_id = z.id WHERE m.id = %s FOR UPDATE;", (mesa_id,))
                mesa_info = cursor.fetchone()
                if not mesa_info: return {"status": "error", "message": "Mesa no encontrada."}
                
                id_mesa, zona_id, consumo_minimo, estado_mesa = mesa_info
                if estado_mesa == 'bloqueada':
                    return {"status": "error", "message": "Esta mesa está bloqueada temporalmente por el establecimiento."}
                cursor.execute("SELECT id FROM reservas WHERE mesa_id = %s AND estado IN ('pendiente', 'aprobado', 'esperando_aprobacion') AND expiracion_reserva > NOW();", (mesa_id,))
                if cursor.fetchone(): return {"status": "error", "message": "Mesa ocupada en este momento."}

                acumulado_usd = 0.0
                detalles_insercion = []

                for item in lista_botellas:
                    b_id = item["botella_id"]
                    cant = item["cantidad"]
                    cursor.execute("SELECT precio_usd, stock, disponible FROM inventario_botellas WHERE id = %s;", (b_id,))
                    botella_info = cursor.fetchone()
                    if not botella_info or not botella_info[2]: return {"status": "error", "message": "Licor no disponible."}
                    
                    precio, stock, _ = botella_info
                    if stock < cant: return {"status": "error", "message": f"Stock insuficiente para ID {b_id}."}
                    acumulado_usd += float(precio) * cant
                    detalles_insercion.append((b_id, cant))

                if acumulado_usd < float(consumo_minimo):
                    return {"status": "error", "message": f"Monto (${acumulado_usd:.2f}) inferior al consumo mínimo requerido (${float(consumo_minimo):.2f})."}

                expiracion_reserva = datetime.now() + timedelta(minutes=15)
                cursor.execute("INSERT INTO reservas (usuario_id, mesa_id, total_usd, estado, expiracion_reserva) VALUES (%s, %s, %s, 'pendiente', %s) RETURNING id;", (usuario_id, mesa_id, acumulado_usd, expiracion_reserva))
                reserva_id = cursor.fetchone()[0]

                for b_id, cant in detalles_insercion:
                    cursor.execute("INSERT INTO detalles_reserva_botellas (reserva_id, botella_id, cantidad) VALUES (%s, %s, %s);", (reserva_id, b_id, cant))
                    cursor.execute("UPDATE inventario_botellas SET stock = stock - %s WHERE id = %s;", (cant, b_id))
                conexion.commit()

        return {"status": "success", "reserva_id": reserva_id, "total_a_pagar_usd": acumulado_usd, "expira_en_minutos": 15}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def registrar_pago_reserva_en_bd(reserva_id, metodo_pago, referencia_bancaria, ruta_captura):
    try:
        if len(referencia_bancaria) < 4: return {"status": "error", "message": "Referencia bancaria muy corta (mínimo 4 dígitos)."}
        tasas = obtener_tasas_bcv()
        tasa_usd = tasas.get("USD", 54.50)

        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT total_usd, estado, expiracion_reserva FROM reservas WHERE id = %s;", (reserva_id,))
                reserva = cursor.fetchone()
                if not reserva: return {"status": "error", "message": "La reserva no existe."}

                total_usd, estado, expiracion = reserva
                if datetime.now() > expiracion: return {"status": "error", "message": "La retención de la mesa ya expiró."}
                if estado != 'pendiente': return {"status": "error", "message": "Estado inválido para reportar pago."}

                total_ves = float(total_usd) * float(tasa_usd)
                cursor.execute(
                    """
                    UPDATE reservas SET metodo_pago = %s, referencia_bancaria = %s, foto_captura_path = %s, tasa_bcv_aplicada = %s, total_ves = %s, estado = 'esperando_aprobacion'
                    WHERE id = %s;
                    """, (metodo_pago, referencia_bancaria, ruta_captura, tasa_usd, total_ves, reserva_id)
                )
                conexion.commit()
        return {"status": "success", "total_calculado_ves": round(total_ves, 2), "tasa_bcv_usada": tasa_usd}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def admin_aprobar_pago_reserva(reserva_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.estado, u.correo, u.nombre, d.nombre, m.identificador_mesa
                    FROM reservas r JOIN usuarios u ON r.usuario_id = u.id
                    JOIN mesas m ON r.mesa_id = m.id JOIN discotecas d ON m.discoteca_id = d.id
                    WHERE r.id = %s;
                    """, (reserva_id,)
                )
                reserva = cursor.fetchone()
                if not reserva: return {"status": "error", "message": "No existe la reserva."}
                
                estado_actual, correo, nom_cli, nom_disco, id_mesa = reserva
                if estado_actual != 'esperando_aprobacion': return {"status": "error", "message": "No está esperando aprobación."}

                token_qr = str(uuid.uuid4())
                cursor.execute("UPDATE reservas SET estado = 'aprobado', codigo_qr_token = %s WHERE id = %s;", (token_qr, reserva_id))
                conexion.commit()

        enviar_correo_qr_reserva(correo, nom_cli, nom_disco, id_mesa, token_qr)
        return {"status": "success", "message": "Aprobado. QR enviado por correo.", "qr_token": token_qr}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def validar_entrada_qr_portero(token_qr, admin_discoteca_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.id, u.nombre, u.apellido, u.cedula, m.identificador_mesa, r.estado, m.discoteca_id
                    FROM reservas r JOIN usuarios u ON r.usuario_id = u.id
                    JOIN mesas m ON r.mesa_id = m.id WHERE r.codigo_qr_token = %s;
                    """, (token_qr,)
                )
                reserva = cursor.fetchone()
                if not reserva: return {"status": "error", "message": "❌ CÓDIGO QR INVÁLIDO."}
                
                r_id, u_nom, u_ape, u_ced, mesa_id, estado, disco_id = reserva
                if disco_id != admin_discoteca_id: return {"status": "error", "message": "❌ PASE DE OTRO ESTABLECIMIENTO."}
                if estado == 'usado': return {"status": "error", "message": "🚨 QR YA UTILIZADO."}
                if estado != 'aprobado': return {"status": "error", "message": "❌ RESERVA NO APROBADA."}
                
                cursor.execute("UPDATE reservas SET estado = 'usado' WHERE id = %s;", (r_id,))
                conexion.commit()
        return {"status": "success", "message": "✅ BIENVENIDO - ACCESO AUTORIZADO", "cliente": f"{u_nom} {u_ape}", "cedula": u_ced, "mesa_asignada": mesa_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def obtener_historial_usuario(usuario_id):
    try:
        historial_completo = []
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.id, r.total_usd, r.estado, r.metodo_pago, r.codigo_qr_token, r.creado_en, m.identificador_mesa, z.id, z.nombre_zona
                    FROM reservas r JOIN mesas m ON r.mesa_id = m.id JOIN zonas_discoteca z ON m.zona_id = z.id
                    WHERE r.usuario_id = %s ORDER BY r.creado_en DESC;
                    """, (usuario_id,)
                )
                reservas_bd = cursor.fetchall()
                
                for r in reservas_bd:
                    res_id, total_usd, estado, metodo, qr_token, creado_en, id_mesa, zona_id, nombre_zona = r
                    cursor.execute("SELECT dr.botella_id, ib.nombre_licor, dr.cantidad, ib.precio_usd FROM detalles_reserva_botellas dr JOIN inventario_botellas ib ON dr.botella_id = ib.id WHERE dr.reserva_id = %s;", (res_id,))
                    botellas_bd = cursor.fetchall()
                    desglose = [{"botella_id": b[0], "nombre_licor": b[1], "cantidad": b[2], "precio_unitario_usd": float(b[3])} for b in botellas_bd]
                    
                    historial_completo.append({
                        "reserva_id": res_id, "mesa": id_mesa, "zona": {"id": zona_id, "nombre": nombre_zona},
                        "total_usd": float(total_usd), "estado": estado, "metodo_pago": metodo or "No especificado",
                        "codigo_qr_token": qr_token or "BLOQUEADO", "fecha_creation": creado_en.isoformat(), "pedido_botellas": desglose
                    })
        return {"status": "success", "data": historial_completo}
    except Exception as e:
        return {"status": "error", "message": str(e)}