import os
import shutil
import re
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# 🔑 Todas las importaciones de lógica transaccional unificadas desde auth
from auth import (
    iniciar_sesion, 
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
    admin_aprobar_pago_reserva
)

from ocr_processor import procesar_cedula

app = FastAPI(
    title="Nexo Core API",
    description="Backend transaccional de reservas y seguridad para Nexo",
    version="1.2.0"
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

# ========================================================
# 📦 SCHEMAS / MODELOS PYDANTIC
# ========================================================
class CompletarRegistroRequest(BaseModel):
    usuario_id: int      
    nombre: str          
    apellido: str        
    correo: EmailStr
    telefono: str
    contrasena: str

class LoginRequest(BaseModel):
    identificador: str  
    contrasena: str

class VerificacionRequest(BaseModel):
    usuario_id: int
    codigo: str

class ModificarBotellaRequest(BaseModel):
    botella_id: int
    nuevo_precio: float
    disponible: bool = True

class ModificarZonaRequest(BaseModel):
    zona_id: int
    nuevo_minimo_consumo: float

class ItemBotellaPedido(BaseModel):
    botella_id: int
    cantidad: int

class CrearReservaRequest(BaseModel):
    usuario_id: int
    zona_id: int
    pedido_botellas: list[ItemBotellaPedido]

# ========================================================
# 🗺️ ENDPOINTS DE CONSULTA (INCLUYEN LIMPIEZA PASIVA C)
# ========================================================
@app.get("/api/discotecas")
def api_listar_discotecas():
    resultado = obtener_discotecas()
    if resultado["status"] == "error": raise HTTPException(status_code=500, detail=resultado["message"])
    return resultado["data"]

@app.get("/api/discotecas/{id}/layout")
def api_ver_layout(id: int):
    resultado = obtener_layout_discoteca(id)
    if resultado["status"] == "error": raise HTTPException(status_code=500, detail=resultado["message"])
    return resultado["data"]

@app.get("/api/discotecas/{id}/menu")
def api_ver_menu(id: int):
    resultado = obtener_menu_botellas(id)
    if resultado["status"] == "error": raise HTTPException(status_code=500, detail=resultado["message"])
    return resultado["data"]

# ========================================================
# 🔐 ENDPOINTS DE SEGURIDAD, SECURE AUTH & SCAN-ID
# ========================================================
@app.post("/api/auth/scan-id")
def api_escanear_cedula(foto: UploadFile = File(...)):
    ruta_temporal = os.path.join(CARPETA_TEMPORAL, foto.filename)
    try:
        with open(ruta_temporal, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
        datos_extraidos = procesar_cedula(ruta_temporal)
        if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
        
        if datos_extraidos["status"] == "error": raise HTTPException(status_code=400, detail=datos_extraidos["message"])
        
        datos_ia = datos_extraidos.get("datos", {})
        resultado_db = pre_registrar_cedula(datos_ia.get("nombre"), datos_ia.get("apellido"), datos_ia.get("fecha_nacimiento"), datos_ia.get("edad"))
        return {"status": "success", "usuario_id": resultado_db["usuario_id"], "datos_autorellenar": datos_ia}
    except Exception as e:
        if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/register")
def api_registrar_usuario(datos: CompletarRegistroRequest):
    resultado = completar_registro_usuario(datos.usuario_id, datos.nombre, datos.apellido, datos.correo, datos.telefono, datos.contrasena)
    if resultado["status"] == "error": raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verify-code")
def api_verificar_codigo(datos: VerificacionRequest):
    resultado = confirmar_codigo_correo(datos.usuario_id, datos.codigo)
    if resultado["status"] == "error": raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/login")
def login(datos: LoginRequest):
    resultado = iniciar_sesion(datos.identificador, datos.contrasena)
    if resultado["status"] == "error": raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

# ========================================================
# 🛒 ENDPOINTS OPERATIVOS: RESERVAS Y PAGO MÓVIL (OPCIÓN B & C)
# ========================================================
@app.post("/api/reservas/crear")
def api_crear_intencion_reserva(datos: CrearReservaRequest):
    desglose_botellas = [{"botella_id": item.botella_id, "cantidad": item.cantidad} for item in datos.pedido_botellas]
    resultado = validar_y_crear_intencion_reserva(datos.usuario_id, datos.zona_id, desglose_botellas)
    if resultado["status"] == "error": raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/reservas/pagar")
def api_pagar_reserva(
    reserva_id: int = Form(...),
    metodo_pago: str = Form(...),
    referencia_bancaria: str = Form(...),  # 🔒 Obligatorio debido a la regla de negocio
    foto_captura: UploadFile = File(None)
):
    # 🔍 Validación estricta: Exclusivamente los últimos 4 dígitos numéricos
    if not re.match(r"^[0-9]{4}$", referencia_bancaria):
        raise HTTPException(
            status_code=400, 
            detail="La referencia bancaria es obligatoria y debe contener exactamente los últimos 4 dígitos numéricos."
        )

    ruta_guardada = None
    if foto_captura:
        ruta_guardada = os.path.join(CARPETA_TEMPORAL, f"capture_{reserva_id}_{foto_captura.filename}")
        with open(ruta_guardada, "wb") as buffer:
            shutil.copyfileobj(foto_captura.file, buffer)

    resultado = registrar_pago_reserva_en_bd(
        reserva_id=reserva_id,
        metodo_pago=metodo_pago,
        referencia_bancaria=referencia_bancaria,
        captura_url=ruta_guardada
    )
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

# ========================================================
# 👑 ENDPOINTS PANEL DE CONTROL ADMINISTRATIVO
# ========================================================
@app.put("/api/admin/reservas/{reserva_id}/aprobar")
def api_admin_aprobar_pago(reserva_id: int):
    resultado = admin_aprobar_pago_reserva(reserva_id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado