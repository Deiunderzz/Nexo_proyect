import os
import shutil
import jwt
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List

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
    JWT_SECRET,
    JWT_ALGORITHM
)
from ocr_processor import procesar_cedula

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

# --- MODELOS PYDANTIC ---
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

class ConfirmarCorreoRequest(BaseModel):
    usuario_id: int
    codigo_otp: str

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

class CambiarPrecioRequest(BaseModel):
    botella_id: int
    nuevo_precio_usd: float
    admin_discoteca_id: int

class CambiarConsumoRequest(BaseModel):
    zona_id: int
    nuevo_consumo_usd: float
    admin_discoteca_id: int

class ValidarQRRequest(BaseModel):
    token_qr: str
    admin_discoteca_id: int

# --- ENDPOINTS ---
@app.post("/api/auth/escanear-cedula")
async def api_escanear_cedula(file: UploadFile = File(...)):
    ruta_temporal = f"./temp_cedulas/{file.filename}"
    with open(ruta_temporal, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    resultado_ocr = procesar_cedula(ruta_temporal)
    if os.path.exists(ruta_temporal):
        os.remove(ruta_temporal)
        
    if resultado_ocr["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado_ocr["message"])
        
    datos = resultado_ocr["datos"]
    token_identidad = jwt.encode(datos, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"status": "success", "token_cedula": token_identidad, "datos_extraidos": datos}

@app.post("/api/auth/registro-completo")
def api_registro_completo(data: RegistroCompletoRequest):
    resultado = completar_registro_usuario(data.token_cedula, data.correo, data.telefono, data.contrasena)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verificar-correo")
def api_verificar_correo(data: ConfirmarCorreoRequest):
    resultado = confirmar_codigo_correo(data.usuario_id, data.codigo_otp)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

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
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.put("/api/admin/reservas/{reserva_id}/aprobar")
def api_admin_aprobar_pago(reserva_id: int):
    resultado = admin_aprobar_pago_reserva(reserva_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/admin/reservas/validar-qr")
def api_validar_puerta_qr(data: ValidarQRRequest):
    resultado = validar_entrada_qr_portero(data.token_qr, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=403, detail=resultado["message"])
    return resultado

@app.get("/api/usuarios/{usuario_id}/historial")
def api_historial_usuario(usuario_id: int):
    return obtener_historial_usuario(usuario_id)

@app.post("/api/admin/configurar/precios")
def api_admin_cambiar_precio(data: CambiarPrecioRequest):
    resultado = actualizar_precio_botella(data.botella_id, data.nuevo_precio_usd, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=403, detail=resultado["message"])
    return resultado

@app.post("/api/admin/configurar/zonas")
def api_admin_cambiar_consumo(data: CambiarConsumoRequest):
    resultado = actualizar_consumo_zona(data.zona_id, data.nuevo_consumo_usd, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=403, detail=resultado["message"])
    return resultado