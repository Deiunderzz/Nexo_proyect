import os
import shutil
import uuid
import asyncio
import jwt
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from auth import (
    iniciar_sesion, 
    verificar_otp_empresa,
    completar_registro_usuario, 
    confirmar_codigo_correo, 
    solicitar_recuperacion_contrasena,
    procesar_cambio_contrasena_otp,
    obtener_datos_pago_discoteca,
    obtener_discotecas, 
    obtener_layout_discoteca, 
    obtener_menu_botellas, 
    actualizar_precio_botella, 
    actualizar_consumo_zona, 
    validar_y_crear_intencion_reserva, 
    registrar_pago_reserva_en_bd,
    admin_aprobar_pago_reserva,
    validar_entrada_qr_portero,
    obtener_historial_usuario,
    actualizar_estado_mesa,
    actualizar_datos_pago_discoteca,
    JWT_SECRET,
    JWT_ALGORITHM,
    DB_CONFIG
)
import psycopg2
from ocr_processor import procesar_cedula
from bcv_provider import obtener_tasas_bcv

app = FastAPI(
    title="Nexo Core API",
    description="Backend transaccional y de control de accesos para Nexo",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "./comprobantes_pago"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("./temp_cedulas", exist_ok=True)

# --- MODELOS PYDANTIC ACTUALIZADOS ---
class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str

class VerifyOtp2faRequest(BaseModel):
    usuario_id: int
    codigo_otp: str

class RegistroCompletoRequest(BaseModel):
    token_cedula: str
    correo: EmailStr
    telefono: str
    contrasena: str
    nombre: str
    apellido: str
    cedula: Optional[str] = None  # Permite corregir el número si la IA lo leyó mal

class ConfirmarCorreoRequest(BaseModel):
    usuario_id: int
    codigo_otp: str

class VerificarOtpPorCorreoRequest(BaseModel):
    correo: EmailStr
    otp: str

class RecuperarClaveRequest(BaseModel):
    correo: EmailStr

class CambiarClaveOTPRequest(BaseModel):
    correo: EmailStr
    codigo_otp: str
    nueva_contrasena: str

class ItemBotella(BaseModel):
    botella_id: int
    cantidad: int

class ReservaRequest(BaseModel):
    usuario_id: int
    mesa_id: int
    botellas: List[ItemBotella]

class EstadoMesaRequest(BaseModel):
    admin_discoteca_id: int
    nuevo_estado: str  # 'libre' | 'bloqueada'

class DatosPagoRequest(BaseModel):
    admin_discoteca_id: int
    pago_movil_banco: Optional[str] = None
    pago_movil_telefono: Optional[str] = None
    pago_movil_cedula_rif: Optional[str] = None
    pago_movil_titular: Optional[str] = None
    zelle_correo: Optional[str] = None
    zelle_titular: Optional[str] = None
    efectivo_nota: Optional[str] = None

# --- ENDPOINTS ---
@app.post("/api/auth/escanear-cedula")
async def api_escanear_cedula(file: UploadFile = File(...)):
    # Asignación de nombre único para evitar colisiones entre peticiones simultáneas
    extension = os.path.splitext(file.filename)[1]
    ruta_temporal = f"./temp_cedulas/{uuid.uuid4()}{extension}"
    
    try:
        with open(ruta_temporal, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 🚀 Ejecución no bloqueante del OCR en un hilo secundario de CPU
        resultado_ocr = await asyncio.to_thread(procesar_cedula, ruta_temporal)
            
        if resultado_ocr["status"] == "error":
            raise HTTPException(status_code=400, detail=resultado_ocr["message"])
            
        datos = resultado_ocr["datos"]

        # Bloqueo duro: si la IA determina que es menor de edad, no se emite token
        # y el flujo de registro no puede continuar.
        if not datos.get("es_mayor_edad"):
            raise HTTPException(status_code=403, detail="Debes ser mayor de 18 años para registrarte en Nexo.")

        token_identidad = jwt.encode(datos, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return {"status": "success", "token_cedula": token_identidad, "datos_extraidos": datos}

    finally:
        # Garantiza que los archivos temporales se eliminen sin importar el resultado
        if os.path.exists(ruta_temporal):
            try:
                os.remove(ruta_temporal)
            except Exception:
                pass

@app.post("/api/auth/registrar")
def api_registro_completo(data: RegistroCompletoRequest):
    resultado = completar_registro_usuario(
        data.token_cedula, 
        data.correo, 
        data.telefono, 
        data.contrasena, 
        data.nombre, 
        data.apellido,
        cedula_manual=data.cedula
    )
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verificar-correo")
def api_verificar_correo(data: ConfirmarCorreoRequest):
    resultado = confirmar_codigo_correo(data.usuario_id, data.codigo_otp)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verificar-otp")
def api_verificar_otp_por_correo(data: VerificarOtpPorCorreoRequest):
    try:
        with psycopg2.connect(**DB_CONFIG) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE correo = %s;", (data.correo.strip().lower(),))
                usuario = cursor.fetchone()
                if not usuario:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado con ese correo electrónico.")
                usuario_id = usuario[0]
                
        resultado = confirmar_codigo_correo(usuario_id, data.otp.strip())
        if resultado["status"] == "error":
            raise HTTPException(status_code=400, detail=resultado["message"])
        return resultado
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/iniciar-sesion")
def api_login(data: LoginRequest):
    resultado = iniciar_sesion(data.correo, data.contrasena)
    if resultado["status"] == "error":
        raise HTTPException(status_code=401, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verificar-2fa-corporativo")
def api_verificar_2fa(data: VerifyOtp2faRequest):
    resultado = verificar_otp_empresa(data.usuario_id, data.codigo_otp)
    if resultado["status"] == "error":
        raise HTTPException(status_code=403, detail=resultado["message"])
    return resultado

@app.post("/api/auth/recuperar-contrasena")
def api_solicitar_recuperacion(data: RecuperarClaveRequest):
    return solicitar_recuperacion_contrasena(data.correo)

@app.post("/api/auth/cambiar-contrasena-otp")
def api_procesar_cambio(data: CambiarClaveOTPRequest):
    resultado = procesar_cambio_contrasena_otp(data.correo, data.codigo_otp, data.nueva_contrasena)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.get("/api/discotecas")
def api_listar_discotecas():
    return obtener_discotecas()

@app.get("/api/tasa-bcv")
def api_tasa_bcv():
    # Solo para mostrar un estimado en pantalla antes de pagar. El monto real
    # en Bs. que se cobra siempre se recalcula en el servidor al reportar el
    # pago (ver registrar_pago_reserva_en_bd), así que esto nunca es la fuente
    # de verdad financiera, solo una referencia visual para el usuario.
    return obtener_tasas_bcv()

@app.get("/api/discotecas/{discoteca_id}/layout")
def api_layout(discoteca_id: int):
    return obtener_layout_discoteca(discoteca_id)

@app.get("/api/discotecas/{discoteca_id}/menu")
def api_menu(discoteca_id: int):
    return obtener_menu_botellas(discoteca_id)

@app.get("/api/discotecas/{discoteca_id}/datos-pago")
def api_datos_pago(discoteca_id: int):
    resultado = obtener_datos_pago_discoteca(discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=404, detail=resultado["message"])
    return resultado

@app.put("/api/admin/discotecas/{discoteca_id}/datos-pago")
def api_actualizar_datos_pago(discoteca_id: int, data: DatosPagoRequest):
    payload = data.dict(exclude={"admin_discoteca_id"})
    resultado = actualizar_datos_pago_discoteca(discoteca_id, payload, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.put("/api/admin/mesas/{mesa_id}/estado")
def api_actualizar_estado_mesa(mesa_id: int, data: EstadoMesaRequest):
    resultado = actualizar_estado_mesa(mesa_id, data.nuevo_estado, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/reservas/intencion")
def api_crear_intencion(data: ReservaRequest):
    lista_dict = [{"botella_id": b.botella_id, "cantidad": b.cantidad} for b in data.botellas]
    resultado = validar_y_crear_intencion_reserva(data.usuario_id, data.mesa_id, lista_dict)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/reservas/pagar")
async def api_registrar_pago(
    reserva_id: int = Form(...),
    metodo_pago: str = Form(...),
    referencia_bancaria: str = Form(...),
    foto_captura: UploadFile = File(None)
):
    ruta_guardada = None
    if foto_captura:
        ruta_guardada = os.path.join(UPLOAD_DIR, f"reserva_{reserva_id}_{foto_captura.filename}")
        with open(ruta_guardada, "wb") as buffer:
            shutil.copyfileobj(foto_captura.file, buffer)
            
    resultado = registrar_pago_reserva_en_bd(reserva_id, metodo_pago, referencia_bancaria, ruta_guardada)
    if resultado["status"] == "error":
        if ruta_guardada and os.path.exists(ruta_guardada):
            os.remove(ruta_guardada)
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado