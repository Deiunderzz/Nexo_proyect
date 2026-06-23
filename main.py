import os
import shutil
import sys
import traceback
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# 🔐 UNIFICADO: Todas las funciones de auth juntas primero
from auth import (
    iniciar_sesion, completar_registro_usuario, confirmar_codigo_correo, pre_registrar_cedula,
    obtener_discotecas, obtener_layout_discoteca, obtener_menu_botellas, actualizar_precio_botella, 
    actualizar_consumo_zona, validar_y_crear_intencion_reserva
)

from ocr_processor import procesar_cedula

app = FastAPI(
    title="Nexo Core API",
    description="Backend de registro, seguridad e IA para Nexo",
    version="1.0.0"
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
    disponible: bool = True  # Permite apagar el producto si se agota

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

# ==========================================
# 🏢 ENDPOINTS DE DISCOTECAS Y DISPONIBILIDAD
# ==========================================

@app.get("/api/discotecas", tags=["Discotecas"])
def api_listar_discotecas():
    """Retorna la lista de discotecas registradas (Kabal / ZOE)"""
    resultado = obtener_discotecas()
    if resultado["status"] == "error":
        raise HTTPException(status_code=500, detail=resultado["message"])
    return resultado["data"]

@app.get("/api/discotecas/{id}/layout", tags=["Discotecas"])
def api_ver_layout(id: int):
    """Retorna el plano de mesas con coordenadas y disponibilidad (Puntos Verdes/Rojos)"""
    resultado = obtener_layout_discoteca(id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=500, detail=resultado["message"])
    return resultado["data"]

@app.get("/api/discotecas/{id}/menu", tags=["Discotecas"])
def api_ver_menu(id: int):
    """Retorna el menú de licores y botellas de la discoteca seleccionada con sus precios en USD"""
    resultado = obtener_menu_botellas(id)
    if resultado["status"] == "error":
        raise HTTPException(status_code=500, detail=resultado["message"])
    return resultado["data"]

# ==========================================
# 🎛️ ENDPOINTS DE PANEL DE CONTROL (APP DEL LOCAL)
# ==========================================

@app.put("/api/admin/inventario/botella", tags=["Administración del Local"])
def api_admin_modificar_botella(datos: ModificarBotellaRequest):
    """
    Permite al administrador de la discoteca cambiar precios o 
    desactivar botellas temporalmente por falta de stock o promociones.
    """
    resultado = actualizar_precio_botella(datos.botella_id, datos.nuevo_precio, datos.disponible)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.put("/api/admin/inventario/zona", tags=["Administración del Local"])
def api_admin_modificar_zona(datos: ModificarZonaRequest):
    """
    Permite al administrador de la discoteca alterar el consumo mínimo de una mesa
    (Útil para subir precios en eventos especiales con DJs internacionales o promociones).
    """
    resultado = actualizar_consumo_zona(datos.zona_id, datos.nuevo_minimo_consumo)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.get("/", tags=["General"])
def inicio():
    return {"status": "online", "proyecto": "Nexo API"}

# ==========================================
# 🧠 ENDPOINTS DE AUTENTICACIÓN E IA
# ==========================================

@app.post("/api/auth/scan-id", tags=["Inteligencia Artificial"])
def api_escanear_cedula(foto: UploadFile = File(...)):
    if not foto.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo subido no es una imagen válida.")
    
    ruta_temporal = os.path.join(CARPETA_TEMPORAL, foto.filename)
    try:
        with open(ruta_temporal, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
        
        datos_extraidos = procesar_cedula(ruta_temporal)
        if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
            
        if datos_extraidos["status"] == "error":
            raise HTTPException(status_code=400, detail=datos_extraidos["message"])
            
        datos_ia = datos_extraidos.get("datos", {})
        fecha_nac = datos_ia.get("fecha_nacimiento")
        
        edad_calculada = datos_ia.get("edad")
        
        if not fecha_nac:
            raise HTTPException(status_code=400, detail="No se pudo leer la fecha de nacimiento.")
            
        resultado_db = pre_registrar_cedula(
            nombre=datos_ia.get("nombre"),
            apellido=datos_ia.get("apellido"),
            fecha_nacimiento_str=fecha_nac,
            edad=edad_calculada
        )
        
        if resultado_db["status"] == "error":
            raise HTTPException(status_code=400, detail=resultado_db["message"])
            
        return {
            "status": "success",
            "usuario_id": resultado_db["usuario_id"],
            "datos_autorellenar": {
                "nombre": datos_ia.get("nombre"),
                "apellido": datos_ia.get("apellido"),
                "fecha_nacimiento_vista": fecha_nac,
                "edad": edad_calculada
            }
        }
    except HTTPException as http_err: raise http_err
    except Exception as e:
        if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/register", tags=["Autenticación"])
def api_registrar_usuario(datos: CompletarRegistroRequest):
    resultado = completar_registro_usuario(
        usuario_id=datos.usuario_id,
        nombre=datos.nombre,
        apellido=datos.apellido,
        correo=datos.correo,
        telefono=datos.telefono,
        contrasena_plana=datos.contrasena
    )
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/verify-code", tags=["Autenticación"])
def api_verificar_codigo(datos: VerificacionRequest):
    resultado = confirmar_codigo_correo(datos.usuario_id, datos.codigo)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

@app.post("/api/auth/login", tags=["Autenticación"])
def login(datos: LoginRequest):
    resultado = iniciar_sesion(datos.identificador, datos.contrasena)
    if resultado["status"] == "error":
        raise HTTPException(status_code=400, detail=resultado["message"])
    return resultado

# ==========================================
# 💸 MOTOR DE RESERVAS
# ==========================================

@app.post("/api/reservas/crear", tags=["Motor de Reservas"])
def api_crear_intencion_reserva(datos: CrearReservaRequest):
    try:
        # Convertimos la lista de objetos Pydantic a una lista pura de diccionarios Python
        desglose_botellas = [
            {"botella_id": item.botella_id, "cantidad": item.cantidad}
            for item in datos.pedido_botellas
        ]
        
        # 🌟 FIJADO DEFINITIVAMENTE: Pasamos parámetros posicionales por orden exacto.
        # Esto previene que explote por discrepancias de nombres entre main.py y auth.py
        resultado = validar_y_crear_intencion_reserva(
            datos.usuario_id,
            datos.zona_id,
            desglose_botellas
        )
        
        if resultado["status"] == "error":
            raise HTTPException(status_code=400, detail=resultado["message"])
            
        return resultado
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en el motor de reservas: {str(e)}")