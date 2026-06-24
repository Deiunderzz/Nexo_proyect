import os
import shutil
import re
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from auth import (
    iniciar_sesion, 
    verificar_otp_empresa, # 👈 NUEVO MÓDULO EXCLUSIVO
    completar_registro_usuario, 
    confirmar_codigo_correo, 
    pre_registrar_cedula,
    obtener_discotecas, 
    obtener_layout_discoteca, 
    obtener_menu_botellas, 
    actualizar_precio_botella, 
    actualizar_consumo_zona, 
    validar_y_crear_intencion_reserva, 
    registrar_pago_reserva_en_bd,
    admin_aprobar_pago_reserva,
    obtener_historial_usuario
)

from ocr_processor import procesar_cedula

app = FastAPI(
    title="Nexo Core API",
    description="Backend transaccional de reservas y seguridad para Nexo y Nexo Empresas",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CARPETA_TEMPORAL = "temp_uploads"
os.makedirs(CARPETA_TEMPORAL, exist_ok=True)

# MODELOS PYDANTIC
class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str

class VerificarOtpEmpresaRequest(BaseModel):
    usuario_id: int
    codigo_otp: str

class ConfirmarCorreoRequest(BaseModel):
    usuario_id: int
    codigo_otp: str

class CompletarRegistroRequest(BaseModel):
    nombre: str
    apellido: str
    correo: EmailStr
    telefono: str
    contrasena: str
    fecha_nacimiento: str
    edad: int

class PreRegistroCedulaRequest(BaseModel):
    nombre: str
    apellido: str
    fecha_nacimiento: str
    edad: int

class BotellaPedido(BaseModel):
    botella_id: int
    cantidad: int

class IntencionReservaRequest(BaseModel):
    usuario_id: int
    mesa_id: int
    pedido_botellas: list[BotellaPedido]

class CambiarPrecioRequest(BaseModel):
    botella_id: int
    nuevo_precio_usd: float
    admin_discoteca_id: int

class CambiarConsumoRequest(BaseModel):
    zona_id: int
    nuevo_minimo_usd: float
    admin_discoteca_id: int

# ========================================================
# 🔐 ENDPOINTS DE AUTENTICACIÓN (NEXO / NEXO EMPRESAS)
# ========================================================
@app.post("/api/auth/iniciar-sesion")
def api_iniciar_sesion(data: LoginRequest):
    """
    Maneja el inicio de sesión global.
    Si retorna status 'requires_otp', iOS debe desplegar la vista de Nexo Empresas.
    """
    resultado = iniciar_sesion(data.correo, data.contrasena)
    if resultado["status"] == "error":
        raise HTTPException(status_code=401, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verificar-otp-empresa")
def api_verificar_otp_empresa(data: VerificarOtpEmpresaRequest):
    """
    Valida el código de 6 dígitos enviado al correo del dueño de negocio.
    """
    resultado = verificar_otp_empresa(data.usuario_id, data.codigo_otp)
    if resultado["status"] == "error":
        raise HTTPException(status_code=401, detail=resultado["message"])
    return resultado

@app.post("/api/auth/scan-cedula")
async def api_scan_cedula(foto_cedula: UploadFile = File(...)):
    ruta_guardada = os.path.join(CARPETA_TEMPORAL, f"ocr_{foto_cedula.filename}")
    with open(ruta_guardada, "wb") as buffer:
        shutil.copyfileobj(foto_cedula.file, buffer)
    
    resultado = procesar_cedula(ruta_imagen=ruta_guardada)
    if os.path.exists(ruta_guardada):
        os.remove(ruta_guardada)
        
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/pre-registro")
def api_pre_registro(data: PreRegistroCedulaRequest):
    resultado = pre_registrar_cedula(data.nombre, data.apellido, data.fecha_nacimiento, data.edad)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/completar-registro")
def api_completar_registro(data: CompletarRegistroRequest):
    resultado = completar_registro_usuario(data.nombre, data.apellido, data.correo, data.telefono, data.contrasena, data.fecha_nacimiento, data.edad)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/confirmar-correo")
def api_confirmar_correo(data: ConfirmarCorreoRequest):
    resultado = confirmar_codigo_correo(data.usuario_id, data.codigo_otp)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

# ========================================================
# 🗺️ ENDPOINTS DE EXPLORACIÓN Y FLUJO CLIENTE
# ========================================================
@app.get("/api/discotecas")
def api_obtener_discotecas():
    return obtener_discotecas()

@app.get("/api/discotecas/{discoteca_id}/layout")
def api_obtener_layout(discoteca_id: int):
    return obtener_layout_discoteca(discoteca_id)

@app.get("/api/discotecas/{discoteca_id}/menu")
def api_obtener_menu(discoteca_id: int):
    return obtener_menu_botellas(discoteca_id)

@app.post("/api/reservas/intencion")
def api_crear_intencion_reserva(data: IntencionReservaRequest):
    pedido_lista = [{"botella_id": item.botella_id, "cantidad": item.cantidad} for item in data.pedido_botellas]
    resultado = validar_y_crear_intencion_reserva(data.usuario_id, data.mesa_id, pedido_lista)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/reservas/pagar")
def api_registrar_pago(
    reserva_id: int = Form(...),
    metodo_pago: str = Form(...),
    referencia_bancaria: str = Form(...),
    foto_captura: UploadFile = File(None)
):
    if not re.match(r"^\d{4}$", referencia_bancaria):
        raise HTTPException(status_code=400, detail="La referencia bancaria debe contener exactamente 4 dígitos.")

    ruta_guardada = None
    if foto_captura:
        ruta_guardada = os.path.join(CARPETA_TEMPORAL, f"capture_{reserva_id}_{foto_captura.filename}")
        with open(ruta_guardada, "wb") as buffer:
            shutil.copyfileobj(foto_captura.file, buffer)

    resultado = registrar_pago_reserva_en_bd(reserva_id, metodo_pago, referencia_bancaria, ruta_guardada)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.get("/api/usuarios/{usuario_id}/historial")
def api_historial_usuario(usuario_id: int):
    return obtener_historial_usuario(usuario_id)

# ========================================================
# 👑 PANEL NEXO EMPRESAS (Mantenimiento, Stock y Precios)
# ========================================================
@app.put("/api/admin/reservas/{reserva_id}/aprobar")
def api_admin_aprobar_pago(reserva_id: int):
    resultado = admin_aprobar_pago_reserva(reserva_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/admin/configurar/precios")
def api_admin_cambiar_precio(data: CambiarPrecioRequest):
    """Permite al dueño cambiar los precios del menú de licores de su local en tiempo real."""
    resultado = actualizar_precio_botella(data.botella_id, data.nuevo_precio_usd, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=403, detail=resultado["message"])
    return resultado

@app.post("/api/admin/configurar/zonas")
def api_admin_cambiar_consumo(data: CambiarConsumoRequest):
    """Permite cambiar los consumos mínimos de las zonas VIP o General."""
    resultado = actualizar_consumo_zona(data.zona_id, data.nuevo_minimo_usd, data.admin_discoteca_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=403, detail=resultado["message"])
    return resultado