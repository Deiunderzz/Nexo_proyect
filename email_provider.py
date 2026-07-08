import os
import resend
from dotenv import load_dotenv

load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY", "re_JeJHeN65_BC6XSZw9bm2f3oWyJnfB599w")

def enviar_otp_bienvenida(correo_destino, nombre_usuario, codigo_otp):
    try:
        html_contenido = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
            <h2 style="color: #6C5CE7; text-align: center;">¡Bienvenido a Nexo, {nombre_usuario}! 🚀</h2>
            <p style="font-size: 16px; color: #333;">Para completar tu registro y activar tu cuenta, introduce el siguiente código de verificación de un solo uso (OTP):</p>
            <div style="background-color: #f9f9f9; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #2D3436;">{codigo_otp}</span>
            </div>
            <p style="font-size: 12px; color: #777;">Este código expira en 15 minutos.</p>
        </div>
        """
        resend.Emails.send({
            "from": "Nexo <onboarding@resend.dev>",
            "to": correo_destino,
            "subject": f"Código de Activación Nexo: {codigo_otp}",
            "html": html_contenido
        })
        return True
    except Exception as e:
        print(f"🚨 Error enviando correo: {str(e)}")
        return False

def enviar_otp_corporativo_2fa(correo_destino, codigo_otp):
    try:
        html_contenido = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #dcdde1; border-radius: 10px; background-color: #1e1e24; color: #ffffff;">
            <h2 style="color: #00cec9; text-align: center;">🔒 Alerta de Acceso Corporativo</h2>
            <p style="font-size: 15px; color: #f5f6fa;">Para autorizar el ingreso al panel administrativo de Nexo Empresas, introduce este token:</p>
            <div style="background-color: #2f3640; padding: 15px; text-align: center; border-radius: 8px; margin: 25px 0; border: 1px solid #00cec9;">
                <span style="font-size: 34px; font-weight: bold; letter-spacing: 6px; color: #00cec9;">{codigo_otp}</span>
            </div>
        </div>
        """
        resend.Emails.send({
            "from": "Nexo Seguridad <onboarding@resend.dev>",
            "to": correo_destino,
            "subject": f"🔒 Código 2FA Gerencial: {codigo_otp}",
            "html": html_contenido
        })
        return True
    except Exception as e:
        print(f"🚨 Error enviando correo 2FA: {str(e)}")
        return False

def enviar_otp_recuperacion_clave(correo_destino, codigo_otp):
    try:
        html_contenido = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #fab1a0; border-radius: 10px;">
            <h2 style="color: #e17055; text-align: center;">🔑 Restablecer tu Contraseña</h2>
            <p style="font-size: 16px; color: #333;">Recibimos una solicitud para cambiar tu contraseña. Introduce este código temporal para proceder:</p>
            <div style="background-color: #fff9f8; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0; border: 1px dashed #e17055;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #d63031;">{codigo_otp}</span>
            </div>
            <p style="font-size: 12px; color: #636e72;">Este token vencerá en 15 minutos.</p>
        </div>
        """
        resend.Emails.send({
            "from": "Nexo Soporte <onboarding@resend.dev>",
            "to": correo_destino,
            "subject": f"🔒 Código de Recuperación Nexo: {codigo_otp}",
            "html": html_contenido
        })
        return True
    except Exception as e:
        print(f"🚨 Error enviando correo de recuperación: {str(e)}")
        return False

def enviar_correo_qr_reserva(correo_destino, nombre_usuario, nombre_discoteca, identificador_mesa, token_qr):
    try:
        url_qr_api = f"https://chart.googleapis.com/chart?cht=qr&chs=300x300&chl={token_qr}"
        html_contenido = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #00b894; border-radius: 10px; text-align: center;">
            <h2 style="color: #00b894;">✨ ¡Tu Reserva está Confirmada! ✨</h2>
            <p style="font-size: 16px; color: #2d3436; text-align: left;">Hola <strong>{nombre_usuario}</strong>, tu pago ha sido verificado con éxito por el equipo de <strong>{nombre_discoteca}</strong>.</p>
            <div style="background-color: #f5f6fa; padding: 15px; border-radius: 8px; text-align: left; margin: 15px 0;">
                <p style="margin: 5px 0;">🏢 <strong>Establecimiento:</strong> {nombre_discoteca}</p>
                <p style="margin: 5px 0;">🛋️ <strong>Mesa Asignada:</strong> {identificador_mesa}</p>
            </div>
            <p style="font-size: 15px; color: #2d3436;">Presenta este código QR digital en la entrada para validar tu acceso:</p>
            <div style="margin: 25px 0;">
                <img src="{url_qr_api}" alt="Código QR de Acceso Nexo" style="border: 4px solid #00b894; border-radius: 10px; width: 220px; height: 220px;" />
            </div>
            <p style="font-size: 11px; color: #b2bec3;">ID de Pase: {token_qr}</p>
        </div>
        """
        resend.Emails.send({
            "from": "Nexo Accesos <onboarding@resend.dev>",
            "to": correo_destino,
            "subject": f"🎉 ¡Pase de Acceso Confirmado para {nombre_discoteca}! 🎟️",
            "html": html_contenido
        })
        return True
    except Exception as e:
        print(f"🚨 Error enviando pase QR: {str(e)}")
        return False