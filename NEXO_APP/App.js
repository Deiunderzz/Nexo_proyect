import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TextInput, 
  TouchableOpacity, 
  Alert, 
  StatusBar, 
  ActivityIndicator, 
  ScrollView,
  FlatList,
  Modal,
  Image,
  KeyboardAvoidingView,
  Platform
} from 'react-native';

// Configura la IP de tu servidor FastAPI
const API_URL = "http://192.168.0.101:8080";
const TASA_BCV = 732.48; 

export default function App() {
  // --- ESTADOS DE NAVEGACIÓN Y SESIÓN ---
  const [currentScreen, setCurrentScreen] = useState('LOGIN'); 
  const [loading, setLoading] = useState(false);
  const [userSession, setUserSession] = useState(null); 

  // --- ESTADOS DE FORMULARIOS ---
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false); 
  const [pendingAdminId, setPendingAdminId] = useState(null); // usuario_id de admin/gerente en espera del OTP 2FA
  const [adminOtp, setAdminOtp] = useState('');

  const [regNombre, setRegNombre] = useState('');
  const [regApellido, setRegApellido] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regCedula, setRegCedula] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false); 
  const [isIdVerified, setIsIdVerified] = useState(false); 
  const [tokenCedula, setTokenCedula] = useState(''); // Token JWT del OCR requerido por el Backend
  const [pendingUserId, setPendingUserId] = useState(null); // usuario_id devuelto al registrar, pendiente de verificar OTP
  const [regOtp, setRegOtp] = useState('');
  // --- ESTADOS DE RECUPERACIÓN DE CONTRASEÑA ---
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotOtpSent, setForgotOtpSent] = useState(false);
  const [forgotOtp, setForgotOtp] = useState('');
  const [forgotNewPassword, setForgotNewPassword] = useState('');
  const [showForgotPassword, setShowForgotPassword] = useState(false);

  // --- ESTADOS DEL DASHBOARD, MESAS Y MENÚ ---
  const [discotecas, setDiscotecas] = useState([]);
  const [selectedClub, setSelectedClub] = useState(null);
  const [selectedMesa, setSelectedMesa] = useState(null); 
  const [viewingMenu, setViewingMenu] = useState(false);
  const [clubMesas, setClubMesas] = useState([]);
  const [clubMenu, setClubMenu] = useState([]);

  // --- BASE DE DATOS LOCAL REACTIVA (MESA Y MENÚ) ---
  const [mesasData, setMesasData] = useState({
    1: [
      { id: "1", nro: "MESA-V1", capacidad: 8, precio: 500, estado: "libre" },
      { id: "2", nro: "MESA-V2", capacidad: 6, precio: 300, estado: "libre" }
    ],
    2: [
      { id: "3", nro: "Z-VIP1", capacidad: 6, precio: 400, estado: "libre" }
    ]
  });

  const [menuData, setMenuData] = useState({
    1: [
      { id: "1", nombre: "Ron Santa Teresa 1796", precio: 60, tipo: "Ron", stock: 15 },
      { id: "2", nombre: "Whisky Old Parr 12 Años", precio: 45, tipo: "Whisky", stock: 20 },
      { id: "3", nombre: "Gin Hendrick's", precio: 70, tipo: "Ginebra", stock: 8 }
    ],
    2: [
      { id: "4", nombre: "Champagne Moët & Chandon", precio: 150, tipo: "Champagne", stock: 5 },
      { id: "5", nombre: "Vodka Grey Goose", precio: 80, tipo: "Vodka", stock: 12 }
    ]
  });

  // --- GESTIÓN DE CONFIGURACIÓN DEL ADMINISTRADOR ---
  const [adminSelectedClub, setAdminSelectedClub] = useState(1); 
  const [adminTab, setAdminTab] = useState('MAIN'); 
  
  const [newMesaNro, setNewMesaNro] = useState('');
  const [newMesaCapacidad, setNewMesaCapacidad] = useState('');
  const [newMesaPrecio, setNewMesaPrecio] = useState('');

  const [newBotellaNombre, setNewBotellaNombre] = useState('');
  const [newBotellaPrecio, setNewBotellaPrecio] = useState('');
  const [newBotellaTipo, setNewBotellaTipo] = useState('');
  const [newBotellaStock, setNewBotellaStock] = useState('');

  // --- SISTEMA DE PEDIDOS / CARRITO ---
  const [cart, setCart] = useState([]); 
  const [isCartVisible, setIsCartVisible] = useState(false);
  
  // --- MODALES Y ENTRADA DE CANTIDAD ---
  const [qtyModalVisible, setQtyModalVisible] = useState(false);
  const [selectedLicorForQty, setSelectedLicorForQty] = useState(null);
  const [typedQuantity, setTypedQuantity] = useState('1');

  // --- ESTADOS PAGO MÓVIL Y CONFIRMACIÓN ---
  const [pagoTelefono, setPagoTelefono] = useState('');
  const [pagoBanco, setPagoBanco] = useState('');
  const [pagoReferencia, setPagoReferencia] = useState('');
  const [pedidoIdCreado, setPedidoIdCreado] = useState(null);
  const [ultimoPedidoConfirmado, setUltimoPedidoConfirmado] = useState(null);

  // --- ESTADOS DE CONTROL DE ACCESO (ADMIN) ---
  const [qrScanResult, setQrScanResult] = useState(null);

  // ==========================================
  // GESTIÓN DEL CARRITO Y VALIDACIONES
  // ==========================================
  const handleOpenQtyModal = (licor) => {
    if (!selectedMesa) {
      Alert.alert("Selección Requerida", "Por favor, selecciona una mesa primero para asignar tu pedido.");
      return;
    }
    setSelectedLicorForQty(licor);
    setTypedQuantity('1');
    setQtyModalVisible(true);
  };

  const handleConfirmAddDirectQty = () => {
    const qty = parseInt(typedQuantity, 10);
    if (isNaN(qty) || qty <= 0) {
      Alert.alert("Error", "Por favor ingresa una cantidad válida.");
      return;
    }

    if (qty > selectedLicorForQty.stock) {
      Alert.alert("Falta de Stock", `Lo sentimos, sólo quedan ${selectedLicorForQty.stock} unidades de este producto.`);
      return;
    }

    setCart((prevCart) => {
      const existingItem = prevCart.find(item => item.id === selectedLicorForQty.id);
      if (existingItem) {
        return prevCart.map(item => 
          item.id === selectedLicorForQty.id ? { ...item, cantidad: qty } : item
        );
      } else {
        return [...prevCart, { ...selectedLicorForQty, cantidad: qty }];
      }
    });

    setQtyModalVisible(false);
    setSelectedLicorForQty(null);
  };

  const getCartTotal = () => {
    return cart.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
  };

  const handleIncrementCartItem = (itemId) => {
    setCart((prevCart) => prevCart.map(item => {
      if (item.id !== itemId) return item;
      if (item.cantidad + 1 > item.stock) {
        Alert.alert("Falta de Stock", `Sólo quedan ${item.stock} unidades de este producto.`);
        return item;
      }
      return { ...item, cantidad: item.cantidad + 1 };
    }));
  };

  const handleDecrementCartItem = (itemId) => {
    setCart((prevCart) => prevCart
      .map(item => item.id === itemId ? { ...item, cantidad: item.cantidad - 1 } : item)
      .filter(item => item.cantidad > 0)
    );
  };

  const handleRemoveCartItem = (itemId) => {
    setCart((prevCart) => prevCart.filter(item => item.id !== itemId));
  };

  // ==========================================
  // PROCESAMIENTO DEL PEDIDO Y TRANSICIÓN
  // ==========================================
  const handleSendOrder = async () => {
    if (cart.length === 0) {
      Alert.alert("Pedido vacío", "No has agregado nada al carrito.");
      return;
    }

    const total = getCartTotal();
    const consumoMinimo = selectedMesa ? selectedMesa.precio : 0;

    if (total < consumoMinimo) {
      Alert.alert(
        "Consumo Mínimo Pendiente",
        `Tu pedido actual es de $${total}. Te faltan $${consumoMinimo - total} para cubrir el mínimo de la mesa.`,
        [
          { text: "Agregar más", style: "cancel" },
          { text: "Enviar así", onPress: () => processOrderSubmit() }
        ]
      );
    } else {
      processOrderSubmit();
    }
  };

  const processOrderSubmit = async () => {
    setLoading(true);
    const orderPayload = {
      usuario_id: userSession?.id || 1,
      mesa_id: parseInt(selectedMesa?.id),
      botellas: cart.map(item => ({
        botella_id: parseInt(item.id),
        cantidad: item.cantidad
      }))
    };

    try {
      const response = await fetch(`${API_URL}/api/reservas/intencion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderPayload)
      });
      const data = await response.json();

      if (response.ok) {
        setPedidoIdCreado(data.reserva_id);
        setIsCartVisible(false);
        setCurrentScreen('PAGO_MOVIL'); 
      } else {
        Alert.alert("No se pudo crear el pedido", data.detail || "Intenta de nuevo.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor para crear el pedido.");
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // REGISTRO Y ENVÍO DEL PAGO MÓVIL
  // ==========================================
  const handleRegisterPagoMovil = async () => {
    if (!pagoTelefono.trim() || !pagoBanco.trim() || !pagoReferencia.trim()) {
      Alert.alert("Campos Obligatorios", "Por favor, completa los datos del pago móvil.");
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('reserva_id', String(pedidoIdCreado));
      formData.append('metodo_pago', `Pago Móvil (${pagoBanco})`);
      formData.append('referencia_bancaria', pagoReferencia);

      const response = await fetch(`${API_URL}/api/reservas/pagar`, {
        method: 'POST',
        body: formData,
        headers: { 'Accept': 'application/json' },
      });
      const data = await response.json();

      if (response.ok) {
        showReceiptFlow();
      } else {
        Alert.alert("Error al Reportar Pago", data.detail || "No se pudo registrar el pago. Intenta de nuevo.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor para reportar el pago.");
    } finally {
      setLoading(false);
    }
  };

  const showReceiptFlow = () => {
    setUltimoPedidoConfirmado({
      id: pedidoIdCreado,
      mesa: selectedMesa?.nro,
      banco: pagoBanco,
      referencia: pagoReferencia,
      montoUsd: getCartTotal(),
      montoVes: (getCartTotal() * TASA_BCV).toFixed(2),
      items: [...cart]
    });

    setCurrentScreen('RECIBO');
  };

  const finalizeOrderFlow = () => {
    setCart([]);
    setSelectedMesa(null);
    setViewingMenu(false);
    setPagoTelefono('');
    setPagoBanco('');
    setPagoReferencia('');
    setPedidoIdCreado(null);
    setUltimoPedidoConfirmado(null);
    setCurrentScreen('DASHBOARD');
  };

  // ==========================================
  // GESTIÓN ADMINISTRATIVA (MESAS Y MENÚ)
  // ==========================================
  const handleAddMesa = () => {
    if (!newMesaNro.trim() || !newMesaCapacidad || !newMesaPrecio) {
      Alert.alert("Campos obligatorios", "Por favor completa todos los campos.");
      return;
    }

    const nuevaMesaObj = {
      id: String(Date.now()),
      nro: newMesaNro.toUpperCase(),
      capacidad: parseInt(newMesaCapacidad, 10),
      precio: parseFloat(newMesaPrecio),
      estado: "libre"
    };

    setMesasData(prev => ({
      ...prev,
      [adminSelectedClub]: [...(prev[adminSelectedClub] || []), nuevaMesaObj]
    }));

    setNewMesaNro('');
    setNewMesaCapacidad('');
    setNewMesaPrecio('');
    Alert.alert("Éxito", "Mesa registrada correctamente.");
  };

  const handleDeleteMesa = (mesaId) => {
    Alert.alert(
      "Eliminar Mesa",
      "¿Estás seguro de que deseas eliminar esta mesa?",
      [
        { text: "Cancelar", style: "cancel" },
        { 
          text: "Eliminar", 
          style: "destructive", 
          onPress: () => {
            setMesasData(prev => ({
              ...prev,
              [adminSelectedClub]: prev[adminSelectedClub].filter(m => m.id !== mesaId)
            }));
          } 
        }
      ]
    );
  };

  const handleAddBotella = () => {
    if (!newBotellaNombre.trim() || !newBotellaPrecio || !newBotellaTipo.trim() || !newBotellaStock) {
      Alert.alert("Campos obligatorios", "Por favor completa todos los datos de la botella.");
      return;
    }

    const nuevaBotellaObj = {
      id: String(Date.now()),
      nombre: newBotellaNombre,
      precio: parseFloat(newBotellaPrecio),
      tipo: newBotellaTipo,
      stock: parseInt(newBotellaStock, 10)
    };

    setMenuData(prev => ({
      ...prev,
      [adminSelectedClub]: [...(prev[adminSelectedClub] || []), nuevaBotellaObj]
    }));

    setNewBotellaNombre('');
    setNewBotellaPrecio('');
    setNewBotellaTipo('');
    setNewBotellaStock('');
    Alert.alert("Éxito", "Botella añadida al menú correctamente.");
  };

  const handleUpdatePriceStock = (botellaId, field, newValue) => {
    const numericValue = parseFloat(newValue) || 0;
    setMenuData(prev => {
      const updatedList = prev[adminSelectedClub].map(botella => {
        if (botella.id === botellaId) {
          return { ...botella, [field]: numericValue };
        }
        return botella;
      });
      return { ...prev, [adminSelectedClub]: updatedList };
    });
  };

  const handleDeleteBotella = (botellaId) => {
    Alert.alert(
      "Eliminar del Menú",
      "¿Deseas remover este licor del inventario?",
      [
        { text: "Cancelar", style: "cancel" },
        { 
          text: "Eliminar", 
          style: "destructive", 
          onPress: () => {
            setMenuData(prev => ({
              ...prev,
              [adminSelectedClub]: prev[adminSelectedClub].filter(b => b.id !== botellaId)
            }));
          } 
        }
      ]
    );
  };

  // ==========================================
  // REGISTRO E INICIO DE SESIÓN
  // ==========================================
  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert("Campos requeridos", "Por favor ingresa tus datos de acceso.");
      return;
    }

    const lowerEmail = email.trim().toLowerCase();

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/iniciar-sesion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ correo: lowerEmail, contrasena: password })
      });
      const data = await response.json();

      if (response.ok) {
        if (data.status === 'requires_otp') {
          // Cuentas admin/gerente requieren 2FA por correo antes de emitir sesión
          setPendingAdminId(data.usuario_id);
          setAdminOtp('');
          setCurrentScreen('ADMIN_2FA');
        } else if (data.usuario) {
          setUserSession(data.usuario);
          if (data.usuario.rol === 'admin' || data.usuario.rol === 'portero') {
            setCurrentScreen('ADMIN');
          } else {
            fetchDiscotecas();
            setCurrentScreen('DASHBOARD');
          }
        }
      } else {
        Alert.alert("Error", data.detail || "Verifica las credenciales.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor. Verifica que el backend esté activo.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAdminOtp = async () => {
    if (!adminOtp.trim() || adminOtp.trim().length !== 6) {
      Alert.alert("Código Requerido", "Ingresa el código de 6 dígitos que enviamos a tu correo.");
      return;
    }
    if (!pendingAdminId) {
      Alert.alert("Flujo inválido", "Por favor inicia sesión nuevamente.");
      setCurrentScreen('LOGIN');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/verificar-2fa-corporativo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          usuario_id: pendingAdminId,
          codigo_otp: adminOtp.trim()
        })
      });
      const data = await response.json();

      if (response.ok && data.usuario) {
        setUserSession(data.usuario);
        setPendingAdminId(null);
        setAdminOtp('');
        setCurrentScreen('ADMIN');
      } else {
        Alert.alert("Código Incorrecto", data.detail || "Verifica el código e intenta de nuevo.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!regEmail.trim() || !regPassword.trim() || !regPhone.trim() || !regNombre.trim() || !regApellido.trim()) {
      Alert.alert("Campos Requeridos", "Por favor completa nombre, apellido, correo, teléfono y contraseña.");
      return;
    }

    if (!tokenCedula) {
      Alert.alert("Flujo inválido", "Por favor escanea tu cédula primero.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/registrar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_cedula: tokenCedula,
          correo: regEmail.toLowerCase().trim(),
          telefono: regPhone.trim(),
          contrasena: regPassword,
          nombre: regNombre.trim(),
          apellido: regApellido.trim(),
          cedula: regCedula.trim() || null
        })
      });
      const data = await response.json();

      if (response.ok) {
        setPendingUserId(data.usuario_id);
        setCurrentScreen('VERIFY_OTP');
      } else {
        Alert.alert("Error de registro", data.detail || "Verifica los datos.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyRegistrationOtp = async () => {
    if (!regOtp.trim() || regOtp.trim().length !== 6) {
      Alert.alert("Código Requerido", "Ingresa el código de 6 dígitos que enviamos a tu correo.");
      return;
    }
    if (!pendingUserId) {
      Alert.alert("Flujo inválido", "Por favor regístrate nuevamente.");
      setCurrentScreen('REGISTER');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/verificar-correo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          usuario_id: pendingUserId,
          codigo_otp: regOtp.trim()
        })
      });
      const data = await response.json();

      if (response.ok) {
        Alert.alert("Cuenta Verificada ✅", "Tu cuenta de socio Nexo ha sido activada. Ya puedes iniciar sesión.");
        // Limpiar todo el estado del flujo de registro
        setIsIdVerified(false);
        setTokenCedula('');
        setPendingUserId(null);
        setRegOtp('');
        setRegNombre('');
        setRegApellido('');
        setRegCedula('');
        setRegPassword('');
        setCurrentScreen('LOGIN');
      } else {
        Alert.alert("Código Incorrecto", data.detail || "Verifica el código e intenta de nuevo.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  const handleSolicitarRecuperacion = async () => {
    if (!forgotEmail.trim()) {
      Alert.alert("Correo Requerido", "Ingresa el correo con el que te registraste.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/recuperar-contrasena`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ correo: forgotEmail.toLowerCase().trim() })
      });
      const data = await response.json();

      if (response.ok) {
        // El backend siempre responde "success" exista o no el correo, para no filtrar
        // qué correos están registrados. Igual avanzamos al paso 2.
        setForgotOtpSent(true);
        Alert.alert("Revisa tu Correo", data.message || "Si el correo está registrado, recibirás un código.");
      } else {
        Alert.alert("Error", data.detail || "No se pudo procesar la solicitud.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  const handleCambiarContrasenaOtp = async () => {
    if (!forgotOtp.trim() || forgotOtp.trim().length !== 6) {
      Alert.alert("Código Requerido", "Ingresa el código de 6 dígitos que enviamos a tu correo.");
      return;
    }
    if (!forgotNewPassword.trim()) {
      Alert.alert("Contraseña Requerida", "Ingresa tu nueva contraseña.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/cambiar-contrasena-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          correo: forgotEmail.toLowerCase().trim(),
          codigo_otp: forgotOtp.trim(),
          nueva_contrasena: forgotNewPassword
        })
      });
      const data = await response.json();

      if (response.ok) {
        Alert.alert("Contraseña Restablecida ✅", "Ya puedes iniciar sesión con tu nueva contraseña.");
        setForgotEmail('');
        setForgotOtp('');
        setForgotNewPassword('');
        setForgotOtpSent(false);
        setCurrentScreen('LOGIN');
      } else {
        Alert.alert("Error", data.detail || "No se pudo restablecer la contraseña.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  // =========================================================================
  // ESCANEO SEGURO DE CÉDULA (OCR CONFIGURADO CON EL ENDPOINT DEL BACKEND)
  // =========================================================================
  const handleScanCedulaRegister = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert("Permiso requerido", "Se necesita acceso a la cámara para escanear tu documento.");
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      setLoading(true);
      
      try {
        const localUri = result.assets[0].uri;

        // Redimensionar ANTES de subir: las fotos de cámara (3000-4000px+) tardan
        // mucho en subir y en procesarse con OCR. Bajar a 1600px de ancho acelera
        // ambas cosas sin perder legibilidad del texto de la cédula.
        const manipulado = await ImageManipulator.manipulateAsync(
          localUri,
          [{ resize: { width: 1600 } }],
          { compress: 0.8, format: ImageManipulator.SaveFormat.JPEG }
        );

        const cleanUri = Platform.OS === 'ios' ? manipulado.uri.replace('file://', '') : manipulado.uri;

        const formData = new FormData();
        formData.append('file', {
          uri: cleanUri,
          name: 'cedula.jpg',
          type: 'image/jpeg',
        });

        // El OCR puede tardar; le damos más margen que el timeout por defecto de fetch
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000); // 90s

        // Consumir el endpoint transaccional correcto de FastAPI
        const response = await fetch(`${API_URL}/api/auth/escanear-cedula`, {
          method: 'POST',
          body: formData,
          headers: {
            'Accept': 'application/json',
          },
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        const data = await response.json();

        if (response.ok) {
          // El backend solo verifica edad y sugiere la cédula; nombre/apellido los escribe el usuario
          setRegCedula(data.datos_extraidos.cedula || '');
          
          // Almacenar el token requerido para el paso 2 de registro completo
          setTokenCedula(data.token_cedula); 
          
          setIsIdVerified(true); 
          Alert.alert("Verificación de Edad Exitosa ✅", "Documento válido. Completa tus datos para continuar.");
        } else {
          Alert.alert("Error de Lectura", data.detail || "No se pudo procesar la imagen de tu cédula.");
        }
      } catch (error) {
        console.error("Error en escaneo de cédula:", error);
        if (error.name === 'AbortError') {
          Alert.alert("Tiempo Agotado", "El servidor tardó demasiado en procesar la imagen. Intenta con mejor iluminación o revisa el servidor.");
        } else {
          Alert.alert("Error de Servidor", "No se pudo establecer conexión para procesar el OCR.");
        }
      } finally {
        setLoading(false);
      }
    }
  };

  const handleScanQRDoor = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert("Permiso requerido", "Se necesita acceso a la cámara para leer el QR.");
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      setLoading(true);
      setTimeout(() => {
        setLoading(false);
        setQrScanResult({
          socio: "Carlos Pérez",
          cedula: "V-27.123.456",
          membresia: "Black VIP Club",
          mesaAsignada: "MESA-V1",
          status: "AUTORIZADO ✅"
        });
      }, 800);
    }
  };

  const fetchDiscotecas = async () => {
    try {
      const response = await fetch(`${API_URL}/api/discotecas`);
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setDiscotecas(data.data || []);
      } else {
        Alert.alert("Error", "No se pudieron cargar los establecimientos.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor.");
    }
  };

  const handleSelectClub = async (club) => {
    setSelectedClub(club);
    setClubMesas([]);
    setClubMenu([]);

    try {
      const [layoutRes, menuRes] = await Promise.all([
        fetch(`${API_URL}/api/discotecas/${club.id}/layout`),
        fetch(`${API_URL}/api/discotecas/${club.id}/menu`)
      ]);
      const layoutData = await layoutRes.json();
      const menuDataRes = await menuRes.json();

      if (layoutRes.ok && layoutData.status === 'success') {
        // Normaliza los campos de la BD (mesa_id, identificador, consumo_minimo_usd, ocupada)
        // a lo que las tarjetas de la UI esperan (id, nro, precio, estado).
        setClubMesas((layoutData.data || []).map(m => ({
          id: m.mesa_id,
          nro: m.identificador,
          zona: m.zona,
          precio: m.consumo_minimo_usd,
          estado: m.ocupada ? 'ocupada' : 'libre'
        })));
      } else {
        Alert.alert("Error", "No se pudo cargar el layout de mesas.");
      }

      if (menuRes.ok && menuDataRes.status === 'success') {
        // Normaliza (id, nombre_licor, categoria, precio_usd, stock) a (id, nombre, tipo, precio, stock)
        setClubMenu((menuDataRes.data || []).map(b => ({
          id: b.id,
          nombre: b.nombre_licor,
          tipo: b.categoria,
          precio: b.precio_usd,
          stock: b.stock
        })));
      } else {
        Alert.alert("Error", "No se pudo cargar el menú de licores.");
      }
    } catch (error) {
      Alert.alert("Error de Conexión", "No se pudo comunicar con el servidor para cargar el establecimiento.");
    }
  };

  const handleLogout = () => {
    setUserSession(null);
    setEmail('');
    setPassword('');
    setSelectedClub(null);
    setSelectedMesa(null);
    setViewingMenu(false);
    setCart([]);
    setQrScanResult(null);
    setCurrentScreen('LOGIN');
  };

  // ==========================================
  // RENDERIZADO DE LAS VISTAS
  // ==========================================
  const renderLoginScreen = () => (
    <View style={styles.centerContainer}>
      <View style={styles.headerContainer}>
        <Text style={styles.title}>NEXO</Text>
        <Text style={styles.subtitle}>After Hours Society</Text>
      </View>
      <View style={styles.formContainer}>
        <Text style={styles.label}>Correo electrónico</Text>
        <TextInput style={styles.input} placeholder="admin@nexo.com" placeholderTextColor="#444" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
        
        <Text style={styles.label}>Contraseña</Text>
        <View style={styles.passwordContainer}>
          <TextInput 
            style={styles.passwordInput} 
            placeholder="••••••••" 
            placeholderTextColor="#444" 
            secureTextEntry={!showLoginPassword} 
            value={password} 
            onChangeText={setPassword} 
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity style={styles.eyeBtn} onPress={() => setShowLoginPassword(!showLoginPassword)}>
            <Text style={styles.eyeEmoji}>{showLoginPassword ? '🙈' : '👁️'}</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.button} onPress={handleLogin}>
          <Text style={styles.buttonText}>Ingresar</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.switchAuthBtn} onPress={() => { setForgotEmail(''); setForgotOtpSent(false); setForgotOtp(''); setForgotNewPassword(''); setCurrentScreen('FORGOT_PASSWORD'); }}>
          <Text style={styles.switchAuthText}>¿Olvidaste tu <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>contraseña?</Text></Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.switchAuthBtn} onPress={() => setCurrentScreen('REGISTER')}>
          <Text style={styles.switchAuthText}>¿No tienes cuenta? <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>Regístrate aquí</Text></Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderForgotPasswordScreen = () => (
    <View style={styles.centerContainer}>
      <View style={styles.headerContainer}>
        <Text style={styles.title}>NEXO</Text>
        <Text style={styles.subtitle}>Recuperar Contraseña</Text>
      </View>
      <View style={styles.formContainer}>
        {!forgotOtpSent ? (
          <>
            <Text style={styles.stepDescription}>
              Ingresa el correo con el que te registraste. Te enviaremos un código para restablecer tu contraseña.
            </Text>
            <Text style={styles.label}>Correo electrónico</Text>
            <TextInput style={styles.input} placeholder="socio@correo.com" placeholderTextColor="#444" value={forgotEmail} onChangeText={setForgotEmail} keyboardType="email-address" autoCapitalize="none" />

            <TouchableOpacity style={styles.button} onPress={handleSolicitarRecuperacion}>
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Enviar Código</Text>}
            </TouchableOpacity>
          </>
        ) : (
          <>
            <Text style={styles.stepDescription}>
              Ingresa el código de 6 dígitos enviado a {forgotEmail}, y tu nueva contraseña.
            </Text>
            <Text style={styles.label}>Código OTP</Text>
            <TextInput
              style={[styles.input, { textAlign: 'center', letterSpacing: 8, fontSize: 20 }]}
              placeholder="000000"
              placeholderTextColor="#444"
              value={forgotOtp}
              onChangeText={(texto) => setForgotOtp(texto.replace(/[^0-9]/g, '').slice(0, 6))}
              keyboardType="number-pad"
              maxLength={6}
            />

            <Text style={styles.label}>Nueva Contraseña</Text>
            <View style={styles.passwordContainer}>
              <TextInput
                style={styles.passwordInput}
                placeholder="••••••••"
                placeholderTextColor="#444"
                secureTextEntry={!showForgotPassword}
                value={forgotNewPassword}
                onChangeText={setForgotNewPassword}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TouchableOpacity style={styles.eyeBtn} onPress={() => setShowForgotPassword(!showForgotPassword)}>
                <Text style={styles.eyeEmoji}>{showForgotPassword ? '🙈' : '👁️'}</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.button} onPress={handleCambiarContrasenaOtp}>
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Restablecer Contraseña</Text>}
            </TouchableOpacity>

            <TouchableOpacity style={[styles.switchAuthBtn, { marginTop: 15 }]} onPress={() => setForgotOtpSent(false)}>
              <Text style={styles.switchAuthText}>¿Correo incorrecto? <Text style={{ color: '#FF5E5E', fontWeight: 'bold' }}>Volver a intentar</Text></Text>
            </TouchableOpacity>
          </>
        )}

        <TouchableOpacity style={[styles.switchAuthBtn, { marginTop: 15 }]} onPress={() => setCurrentScreen('LOGIN')}>
          <Text style={styles.switchAuthText}>Volver al <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>Inicio de Sesión</Text></Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderRegisterScreen = () => (
    <View style={styles.centerContainer}>
      <View style={styles.headerContainer}>
        <Text style={styles.title}>NEXO</Text>
        <Text style={styles.subtitle}>Registro de Socio VIP</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} style={{ width: '100%' }} contentContainerStyle={{ paddingBottom: 20 }}>
        
        {!isIdVerified ? (
          <View style={styles.verificationStepContainer}>
            <Text style={styles.stepTitle}>Paso 1: Verificación de Identidad</Text>
            <Text style={styles.stepDescription}>
              Para ingresar a la sociedad, primero debemos validar tu mayoría de edad analizando tu documento de identidad con nuestra IA.
            </Text>
            
            <TouchableOpacity style={styles.scanLargeBtn} onPress={handleScanCedulaRegister}>
              <Text style={styles.scanLargeEmoji}>📸</Text>
              <Text style={styles.scanLargeBtnText}>Escanear Cédula de Identidad</Text>
              <Text style={styles.scanLargeSubtitle}>Reconocimiento facial y biométrico automático</Text>
            </TouchableOpacity>

            {loading && <ActivityIndicator size="large" color="#9D4EDD" style={{ marginTop: 20 }} />}
            
            <TouchableOpacity style={styles.switchAuthBtn} onPress={() => { setIsIdVerified(false); setCurrentScreen('LOGIN'); }}>
              <Text style={styles.switchAuthText}>Volver al <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>Inicio de Sesión</Text></Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.formContainer}>
            <View style={styles.verifiedAlertBadge}>
              <Text style={styles.verifiedAlertText}>✓ Identidad Escaneada y Verificada por IA</Text>
            </View>

            <Text style={styles.stepTitle}>Paso 2: Datos de Membresía</Text>

            <Text style={styles.label}>Nombre</Text>
            <TextInput style={styles.input} placeholder="Nombre" placeholderTextColor="#444" value={regNombre} onChangeText={setRegNombre} autoCapitalize="words" />
            
            <Text style={styles.label}>Apellido</Text>
            <TextInput style={styles.input} placeholder="Apellido" placeholderTextColor="#444" value={regApellido} onChangeText={setRegApellido} autoCapitalize="words" />

            <Text style={styles.label}>Cédula (verifica que sea correcta)</Text>
            <TextInput style={styles.input} placeholder="V-12.345.678" placeholderTextColor="#444" value={regCedula} onChangeText={setRegCedula} autoCapitalize="characters" />
            
            <Text style={styles.label}>Correo Electrónico</Text>
            <TextInput style={styles.input} placeholder="socio@correo.com" placeholderTextColor="#444" value={regEmail} onChangeText={setRegEmail} keyboardType="email-address" autoCapitalize="none" />
            
            <Text style={styles.label}>Teléfono Móvil</Text>
            <TextInput style={styles.input} placeholder="0412-1234567" placeholderTextColor="#444" value={regPhone} onChangeText={setRegPhone} keyboardType="phone-pad" />
            
            <Text style={styles.label}>Contraseña</Text>
            <View style={styles.passwordContainer}>
              <TextInput 
                style={styles.passwordInput} 
                placeholder="••••••••" 
                placeholderTextColor="#444" 
                secureTextEntry={!showRegPassword} 
                value={regPassword} 
                onChangeText={setRegPassword} 
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TouchableOpacity style={styles.eyeBtn} onPress={() => setShowRegPassword(!showRegPassword)}>
                <Text style={styles.eyeEmoji}>{showRegPassword ? '🙈' : '👁️'}</Text>
              </TouchableOpacity>
            </View>
            
            <TouchableOpacity style={styles.button} onPress={handleRegister}>
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Crear Cuenta y Solicitar Acceso</Text>}
            </TouchableOpacity>

            <TouchableOpacity style={[styles.switchAuthBtn, { marginTop: 15 }]} onPress={() => { setIsIdVerified(false); setTokenCedula(''); }}>
              <Text style={styles.switchAuthText}>¿Escanear otro documento? <Text style={{ color: '#FF5E5E', fontWeight: 'bold' }}>Re-escanear</Text></Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </View>
  );

  const renderVerifyOtpScreen = () => (
    <View style={styles.centerContainer}>
      <View style={styles.headerContainer}>
        <Text style={styles.title}>NEXO</Text>
        <Text style={styles.subtitle}>Verifica tu Correo</Text>
      </View>

      <View style={styles.formContainer}>
        <Text style={styles.stepDescription}>
          Enviamos un código de 6 dígitos a {regEmail || 'tu correo'}. Ingrésalo para activar tu cuenta.
        </Text>

        <Text style={styles.label}>Código OTP</Text>
        <TextInput
          style={[styles.input, { textAlign: 'center', letterSpacing: 8, fontSize: 20 }]}
          placeholder="000000"
          placeholderTextColor="#444"
          value={regOtp}
          onChangeText={(texto) => setRegOtp(texto.replace(/[^0-9]/g, '').slice(0, 6))}
          keyboardType="number-pad"
          maxLength={6}
        />

        <TouchableOpacity style={styles.button} onPress={handleVerifyRegistrationOtp}>
          {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Verificar Cuenta</Text>}
        </TouchableOpacity>

        <TouchableOpacity style={[styles.switchAuthBtn, { marginTop: 15 }]} onPress={() => { setCurrentScreen('LOGIN'); }}>
          <Text style={styles.switchAuthText}>Verificar más tarde, ir a <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>Inicio de Sesión</Text></Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderAdminOtpScreen = () => (
    <View style={styles.centerContainer}>
      <View style={styles.headerContainer}>
        <Text style={styles.title}>NEXO</Text>
        <Text style={styles.subtitle}>Verificación en Dos Pasos</Text>
      </View>

      <View style={styles.formContainer}>
        <Text style={styles.stepDescription}>
          Por seguridad, enviamos un código de 6 dígitos al correo corporativo asociado a esta cuenta. Ingrésalo para continuar.
        </Text>

        <Text style={styles.label}>Código de Seguridad</Text>
        <TextInput
          style={[styles.input, { textAlign: 'center', letterSpacing: 8, fontSize: 20 }]}
          placeholder="000000"
          placeholderTextColor="#444"
          value={adminOtp}
          onChangeText={(texto) => setAdminOtp(texto.replace(/[^0-9]/g, '').slice(0, 6))}
          keyboardType="number-pad"
          maxLength={6}
        />

        <TouchableOpacity style={styles.button} onPress={handleVerifyAdminOtp}>
          {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Verificar y Entrar</Text>}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.switchAuthBtn, { marginTop: 15 }]}
          onPress={() => { setPendingAdminId(null); setAdminOtp(''); setCurrentScreen('LOGIN'); }}
        >
          <Text style={styles.switchAuthText}>Cancelar, volver a <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>Inicio de Sesión</Text></Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderDashboardScreen = () => {
    const totalActual = getCartTotal();

    if (selectedClub) {
      return (
        <View style={styles.mainContent}>
          <View style={styles.dashboardHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.dashboardUserRole}>SELECCIONADO</Text>
              <Text style={styles.dashboardWelcome}>{selectedClub.nombre}</Text>
            </View>
            <TouchableOpacity style={styles.logoutBtn} onPress={() => setSelectedClub(null)}>
              <Text style={{ color: '#9D4EDD', fontWeight: 'bold' }}>Volver</Text>
            </TouchableOpacity>
          </View>

          {selectedMesa && (
            <View style={styles.mesaSelectedBadge}>
              <Text style={styles.mesaSelectedText}>🛋️ Mesa activa: {selectedMesa.nro}</Text>
            </View>
          )}

          <View style={styles.selectorTabContainer}>
            <TouchableOpacity style={[styles.selectorTab, !viewingMenu && styles.selectorTabActive]} onPress={() => setViewingMenu(false)}>
              <Text style={styles.selectorTabText}>Ver Mesas</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.selectorTab, viewingMenu && styles.selectorTabActive]} onPress={() => {
              if(!selectedMesa) { Alert.alert("Mesa Requerida", "Selecciona una mesa primero."); return; }
              setViewingMenu(true);
            }}>
              <Text style={styles.selectorTabText}>Carta / Menú</Text>
            </TouchableOpacity>
          </View>

          {!viewingMenu ? (
            <FlatList
              data={clubMesas}
              keyExtractor={(item) => item.id}
              numColumns={2}
              columnWrapperStyle={{ justifyContent: 'space-between' }}
              renderItem={({ item }) => {
                const ocupada = item.estado === 'ocupada';
                return (
                  <TouchableOpacity 
                    style={[styles.clubCard, { width: '48%', borderColor: selectedMesa?.id === item.id ? '#9D4EDD' : '#241B40', borderWidth: 1, opacity: ocupada ? 0.4 : 1 }]}
                    onPress={() => {
                      if (ocupada) {
                        Alert.alert("Mesa Ocupada", "Esta mesa ya tiene una reserva activa. Elige otra.");
                        return;
                      }
                      setSelectedMesa(item);
                      setViewingMenu(true);
                    }}
                  >
                    <Text style={{ color: '#FFF', fontWeight: 'bold' }}>{item.nro}</Text>
                    <Text style={{ color: '#9D4EDD', fontSize: 12, marginTop: 4 }}>Min: ${item.precio}</Text>
                    {ocupada && <Text style={{ color: '#FF5E5E', fontSize: 11, marginTop: 2 }}>Ocupada</Text>}
                  </TouchableOpacity>
                );
              }}
            />
          ) : (
            <View style={{ flex: 1 }}>
              <FlatList
                data={clubMenu}
                keyExtractor={(item) => item.id}
                renderItem={({ item }) => (
                  <TouchableOpacity 
                    style={[styles.clubCard, { opacity: item.stock === 0 ? 0.4 : 1 }]} 
                    onPress={() => item.stock > 0 ? handleOpenQtyModal(item) : Alert.alert("Agotado", "No queda stock de este producto.")}
                  >
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                      <Text style={{ color: '#FFF', fontWeight: 'bold' }}>{item.nombre}</Text>
                      <Text style={{ color: item.stock > 3 ? '#9D4EDD' : '#FF5E5E', fontSize: 11 }}>Stock: {item.stock}</Text>
                    </View>
                    <Text style={{ color: '#9D4EDD', marginTop: 4 }}>${item.precio}</Text>
                  </TouchableOpacity>
                )}
              />
              {cart.length > 0 && (
                <TouchableOpacity style={styles.floatingCartBtn} onPress={() => setIsCartVisible(true)}>
                  <Text style={styles.floatingCartText}>🛒 Mi Cuenta Real (${totalActual})</Text>
                </TouchableOpacity>
              )}
            </View>
          )}

          {/* Modal de Cantidad */}
          <Modal visible={qtyModalVisible} transparent={true} animationType="fade">
            <View style={styles.modalOverlayCentered}>
              <View style={styles.qtyBoxModal}>
                <Text style={styles.qtyModalTitle}>Cantidad de Botellas</Text>
                <Text style={{ color: '#625E70', fontSize: 11, marginBottom: 10 }}>Fijar Cantidad Máxima: {selectedLicorForQty?.stock}</Text>
                <TextInput
                  style={styles.qtyInputText}
                  keyboardType="numeric"
                  value={typedQuantity}
                  onChangeText={setTypedQuantity}
                  autoFocus={true}
                />
                <View style={styles.qtyModalButtonsContainer}>
                  <TouchableOpacity style={[styles.qtyModalBtn, { backgroundColor: '#241B40' }]} onPress={() => setQtyModalVisible(false)}>
                    <Text style={{ color: '#FFF' }}>Cancelar</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.qtyModalBtn, { backgroundColor: '#7B2CBF' }]} onPress={handleConfirmAddDirectQty}>
                    <Text style={{ color: '#FFF' }}>Agregar</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          </Modal>

          {/* Modal del Carrito */}
          <Modal visible={isCartVisible} animationType="slide" transparent={true}>
            <View style={styles.modalOverlay}>
              <View style={styles.modalContent}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>Tu Pedido</Text>
                  <TouchableOpacity onPress={() => setIsCartVisible(false)}>
                    <Text style={styles.closeModalText}>Cerrar</Text>
                  </TouchableOpacity>
                </View>

                {selectedMesa && (() => {
                  const consumoMinimo = selectedMesa.precio || 0;
                  const progreso = consumoMinimo > 0 ? Math.min(1, totalActual / consumoMinimo) : 1;
                  const cubierto = totalActual >= consumoMinimo;
                  return (
                    <View style={{ marginBottom: 14 }}>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 }}>
                        <Text style={{ color: '#B8B0C8', fontSize: 12 }}>Consumo mínimo: ${consumoMinimo}</Text>
                        <Text style={{ color: cubierto ? '#4ADE80' : '#9D4EDD', fontSize: 12, fontWeight: 'bold' }}>
                          ${totalActual} / ${consumoMinimo}
                        </Text>
                      </View>
                      <View style={styles.progressBarTrack}>
                        <View style={[styles.progressBarFill, { width: `${progreso * 100}%`, backgroundColor: cubierto ? '#4ADE80' : '#9D4EDD' }]} />
                      </View>
                    </View>
                  );
                })()}

                <FlatList
                  data={cart}
                  keyExtractor={(item) => item.id}
                  renderItem={({ item }) => (
                    <View style={styles.cartItem}>
                      <View style={{ flex: 1 }}>
                        <Text style={{ color: '#FFF' }}>{item.nombre}</Text>
                        <Text style={{ color: '#625E70', fontSize: 11, marginTop: 2 }}>${item.precio} c/u</Text>
                      </View>
                      <View style={styles.cartStepperRow}>
                        <TouchableOpacity style={styles.cartStepperBtn} onPress={() => handleDecrementCartItem(item.id)}>
                          <Text style={styles.cartStepperBtnText}>−</Text>
                        </TouchableOpacity>
                        <Text style={styles.cartStepperQty}>{item.cantidad}</Text>
                        <TouchableOpacity style={styles.cartStepperBtn} onPress={() => handleIncrementCartItem(item.id)}>
                          <Text style={styles.cartStepperBtnText}>+</Text>
                        </TouchableOpacity>
                      </View>
                      <Text style={{ color: '#9D4EDD', width: 60, textAlign: 'right' }}>${item.precio * item.cantidad}</Text>
                      <TouchableOpacity style={styles.cartDeleteBtn} onPress={() => handleRemoveCartItem(item.id)}>
                        <Text style={styles.cartDeleteBtnText}>✕</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                  ListEmptyComponent={<Text style={{ color: '#625E70', textAlign: 'center', marginTop: 20 }}>Tu carrito está vacío.</Text>}
                />

                <View style={styles.cartTotalRow}>
                  <Text style={styles.cartTotalLabel}>Total</Text>
                  <Text style={styles.cartTotalValue}>${totalActual}</Text>
                </View>

                <TouchableOpacity style={styles.checkoutBtn} onPress={handleSendOrder}>
                  <Text style={styles.checkoutBtnText}>Enviar e ir a Pagar</Text>
                </TouchableOpacity>
              </View>
            </View>
          </Modal>
        </View>
      );
    }

    return (
      <View style={styles.mainContent}>
        <View style={styles.dashboardHeader}>
          <Text style={styles.dashboardWelcome}>Socio VIP Nexo</Text>
          <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
            <Text style={styles.logoutBtnText}>Salir</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.sectionTitle}>Discotecas Disponibles</Text>
        <FlatList
          data={discotecas}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.clubCard} onPress={() => handleSelectClub(item)}>
              <Text style={styles.clubTitle}>{item.nombre}</Text>
              <Text style={styles.clubAddress}>{item.ubicacion}</Text>
            </TouchableOpacity>
          )}
        />
      </View>
    );
  };

  const renderPagoMovilScreen = () => {
    const totalUsd = getCartTotal();
    const totalVes = (totalUsd * TASA_BCV).toFixed(2);
    const pmString = `pagomovil:0172|04125551234|J-501234567|${totalVes}|PedidoNexo`;
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&color=9d4edd&bgcolor=151026&data=${encodeURIComponent(pmString)}`;

    return (
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.mainContent}>
        <ScrollView showsVerticalScrollIndicator={false}>
          <View style={styles.dashboardHeader}>
            <View>
              <Text style={styles.dashboardUserRole}>TRANSACCIÓN</Text>
              <Text style={styles.dashboardWelcome}>Pago Móvil Auto-QR</Text>
            </View>
          </View>

          <View style={styles.qrContainer}>
            <Text style={styles.qrInstructions}>Escanea desde tu App Bancaria</Text>
            <Image source={{ uri: qrUrl }} style={styles.qrCodeImage} placeholder={<ActivityIndicator color="#9D4EDD" />} />
            <Text style={styles.qrFooterText}>La información del monto y destino ya viene pre-cargada.</Text>
          </View>

          <View style={styles.paymentReceiptBadge}>
            <Text style={styles.receiptLabel}>MONTO TOTAL A REPORTAR</Text>
            <Text style={styles.receiptAmountVes}>Bs. {totalVes}</Text>
            <Text style={styles.receiptAmountUsd}>Ref: ${totalUsd} USD • Tasa BCV: {TASA_BCV}</Text>
          </View>

          <Text style={styles.sectionTitle}>Datos manuales de Pago Móvil</Text>
          <View style={styles.pmDetailsCard}>
            <View style={styles.pmDetailsRow}><Text style={styles.pmLabel}>Banco:</Text><Text style={styles.pmValue}>Bancamiga (0172)</Text></View>
            <View style={styles.pmDetailsRow}><Text style={styles.pmLabel}>RIF:</Text><Text style={styles.pmValue}>J-501234567</Text></View>
            <View style={styles.pmDetailsRow}><Text style={styles.pmLabel}>Teléfono:</Text><Text style={styles.pmValue}>0412-5551234</Text></View>
          </View>

          <Text style={styles.sectionTitle}>Reportar Transacción</Text>
          
          <Text style={styles.label}>Banco Emisor</Text>
          <TextInput style={styles.input} placeholder="Banesco, Mercantil, Provincial..." placeholderTextColor="#444" value={pagoBanco} onChangeText={setPagoBanco} />

          <Text style={styles.label}>Teléfono Origen</Text>
          <TextInput style={styles.input} placeholder="0412-1234567" placeholderTextColor="#444" keyboardType="phone-pad" value={pagoTelefono} onChangeText={setPagoTelefono} />

          <Text style={styles.label}>Últimos 4 dígitos de Referencia</Text>
          <TextInput style={styles.input} placeholder="1234" placeholderTextColor="#444" keyboardType="numeric" maxLength={4} value={pagoReferencia} onChangeText={setPagoReferencia} />

          <TouchableOpacity style={styles.button} onPress={handleRegisterPagoMovil} disabled={loading}>
            {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Confirmar Pago</Text>}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  };

  const renderReceiptScreen = () => {
    if (!ultimoPedidoConfirmado) return null;

    return (
      <View style={styles.mainContent}>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingVertical: 20 }}>
          <View style={styles.receiptHeader}>
            <Text style={styles.receiptCheckIcon}>🎉</Text>
            <Text style={styles.receiptMainTitle}>¡Pedido Registrado!</Text>
            <Text style={styles.receiptSubTitle}>Tu pago móvil está siendo procesado por administración.</Text>
          </View>

          <View style={styles.ticketBox}>
            <View style={styles.ticketHeader}>
              <Text style={styles.ticketHeading}>RESUMEN DE ORDEN</Text>
              <Text style={styles.ticketId}>ID: {ultimoPedidoConfirmado.id}</Text>
            </View>

            <View style={styles.divider} />

            <View style={styles.ticketRow}>
              <Text style={styles.ticketLabel}>Mesa:</Text>
              <Text style={styles.ticketValue}>{ultimoPedidoConfirmado.mesa}</Text>
            </View>
            <View style={styles.ticketRow}>
              <Text style={styles.ticketLabel}>Banco Emisor:</Text>
              <Text style={styles.ticketValue}>{ultimoPedidoConfirmado.banco}</Text>
            </View>
            <View style={styles.ticketRow}>
              <Text style={styles.ticketLabel}>Ref. Reportada:</Text>
              <Text style={styles.ticketValue}>#{ultimoPedidoConfirmado.referencia}</Text>
            </View>

            <View style={styles.divider} />

            <Text style={styles.ticketHeading}>ITEMS:</Text>
            {ultimoPedidoConfirmado.items.map((item, index) => (
              <View key={index} style={styles.ticketItemRow}>
                <Text style={styles.ticketItemText}>{item.nombre} x{item.cantidad}</Text>
                <Text style={styles.ticketItemPrice}>${item.precio * item.cantidad}</Text>
              </View>
            ))}

            <View style={styles.divider} />

            <View style={styles.ticketRowTotal}>
              <Text style={styles.totalLabel}>Monto total:</Text>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.totalUsdText}>${ultimoPedidoConfirmado.montoUsd} USD</Text>
                <Text style={styles.totalVesText}>Bs. {ultimoPedidoConfirmado.montoVes}</Text>
              </View>
            </View>
          </View>

          <TouchableOpacity style={styles.button} onPress={finalizeOrderFlow}>
            <Text style={styles.buttonText}>Volver al Menu Principal</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  };

  const renderAdminScreen = () => (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.mainContent}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.dashboardHeader}>
          <View>
            <Text style={[styles.dashboardUserRole, { color: '#FF7000' }]}>CONTROL CORPORATIVO</Text>
            <Text style={styles.dashboardWelcome}>ADMINISTRACIÓN NEXO</Text>
          </View>
          <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
            <Text style={styles.logoutBtnText}>Cerrar</Text>
          </TouchableOpacity>
        </View>

        {adminTab === 'MAIN' && (
          <View>
            <Text style={styles.sectionTitle}>Operaciones de Entrada</Text>

            <TouchableOpacity style={styles.adminActionCard} onPress={handleScanQRDoor}>
              <Text style={styles.adminCardIcon}>📸</Text>
              <View>
                <Text style={styles.adminCardTitle}>Validar QR de Puerta</Text>
                <Text style={styles.adminCardSubtitle}>Escanear pase digital de socio</Text>
              </View>
            </TouchableOpacity>

            {loading && <ActivityIndicator color="#9D4EDD" size="large" style={{ marginTop: 20 }} />}

            {qrScanResult && !loading && (
              <View style={styles.qrResultContainer}>
                <Text style={styles.qrResultStatus}>{qrScanResult.status}</Text>
                <View style={styles.qrResultDetails}>
                  <Text style={styles.qrResultLabel}>Socio: <Text style={styles.qrResultValue}>{qrScanResult.socio}</Text></Text>
                  <Text style={styles.qrResultLabel}>ID: <Text style={styles.qrResultValue}>{qrScanResult.cedula}</Text></Text>
                  <Text style={styles.qrResultLabel}>Mesa Reservada: <Text style={styles.qrResultValue}>{qrScanResult.mesaAsignada}</Text></Text>
                  <Text style={styles.qrResultLabel}>Membresía: <Text style={{ color: '#FFD700', fontWeight: 'bold' }}>{qrScanResult.membresia}</Text></Text>
                </View>
                <TouchableOpacity style={styles.clearScanBtn} onPress={() => setQrScanResult(null)}>
                  <Text style={styles.clearScanBtnText}>Limpiar Registro</Text>
                </TouchableOpacity>
              </View>
            )}

            <Text style={styles.sectionTitle}>Gestión de Locales</Text>

            <View style={styles.selectorTabContainer}>
              <TouchableOpacity style={[styles.selectorTab, adminSelectedClub === 1 && styles.selectorTabActive]} onPress={() => setAdminSelectedClub(1)}>
                <Text style={styles.selectorTabText}>Kabal Club</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.selectorTab, adminSelectedClub === 2 && styles.selectorTabActive]} onPress={() => setAdminSelectedClub(2)}>
                <Text style={styles.selectorTabText}>Zoe Rooftop</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.adminActionCard} onPress={() => setAdminTab('MESAS')}>
              <Text style={styles.adminCardIcon}>🛋️</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.adminCardTitle}>Administrar Mesas</Text>
                <Text style={styles.adminCardSubtitle}>Añadir, remover y fijar consumos mínimos ({mesasData[adminSelectedClub]?.length || 0} registradas)</Text>
              </View>
            </TouchableOpacity>

            <TouchableOpacity style={styles.adminActionCard} onPress={() => setAdminTab('INVENTARIO')}>
              <Text style={styles.adminCardIcon}>🍾</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.adminCardTitle}>Administrar Inventario</Text>
                <Text style={styles.adminCardSubtitle}>Editar licores, cambiar stock y precios ({menuData[adminSelectedClub]?.length || 0} botellas)</Text>
              </View>
            </TouchableOpacity>
          </View>
        )}

        {adminTab === 'MESAS' && (
          <View>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
              <Text style={styles.sectionTitle}>🛋️ Configurar Mesas ({adminSelectedClub === 1 ? 'Kabal' : 'Zoe'})</Text>
              <TouchableOpacity style={styles.adminBackBtn} onPress={() => setAdminTab('MAIN')}>
                <Text style={styles.adminBackBtnText}>Volver</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.adminFormContainer}>
              <Text style={styles.adminFormTitle}>Agregar Nueva Mesa</Text>
              <TextInput style={styles.adminInput} placeholder="Código (Ej: MESA-V3)" placeholderTextColor="#625E70" value={newMesaNro} onChangeText={setNewMesaNro} />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <TextInput style={[styles.adminInput, { width: '48%' }]} placeholder="Capacidad (Ej: 6)" placeholderTextColor="#625E70" keyboardType="numeric" value={newMesaCapacidad} onChangeText={setNewMesaCapacidad} />
                <TextInput style={[styles.adminInput, { width: '48%' }]} placeholder="Consumo Mín. $" placeholderTextColor="#625E70" keyboardType="numeric" value={newMesaPrecio} onChangeText={setNewMesaPrecio} />
              </View>
              <TouchableOpacity style={[styles.button, { marginTop: 5 }]} onPress={handleAddMesa}>
                <Text style={styles.buttonText}>Registrar Mesa</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.sectionTitle}>Mesas Registradas</Text>
            {(mesasData[adminSelectedClub] || []).map((mesa) => (
              <View key={mesa.id} style={styles.adminListItem}>
                <View>
                  <Text style={styles.adminItemBold}>{mesa.nro}</Text>
                  <Text style={styles.adminItemSub}>Capacidad: {mesa.capacidad} pers. • Min: ${mesa.precio}</Text>
                </View>
                <TouchableOpacity style={styles.adminDeleteBtn} onPress={() => handleDeleteMesa(mesa.id)}>
                  <Text style={styles.adminDeleteBtnText}>Eliminar</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {adminTab === 'INVENTARIO' && (
          <View>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
              <Text style={styles.sectionTitle}>🍾 Configurar Botellas ({adminSelectedClub === 1 ? 'Kabal' : 'Zoe'})</Text>
              <TouchableOpacity style={styles.adminBackBtn} onPress={() => setAdminTab('MAIN')}>
                <Text style={styles.adminBackBtnText}>Volver</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.adminFormContainer}>
              <Text style={styles.adminFormTitle}>Agregar Nueva Botella</Text>
              <TextInput style={styles.adminInput} placeholder="Nombre (Ej: Black Label)" placeholderTextColor="#625E70" value={newBotellaNombre} onChangeText={setNewBotellaNombre} />
              <TextInput style={styles.adminInput} placeholder="Tipo (Ej: Whisky)" placeholderTextColor="#625E70" value={newBotellaTipo} onChangeText={setNewBotellaTipo} />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <TextInput style={[styles.adminInput, { width: '48%' }]} placeholder="Precio ($)" placeholderTextColor="#625E70" keyboardType="numeric" value={newBotellaPrecio} onChangeText={setNewBotellaPrecio} />
                <TextInput style={[styles.adminInput, { width: '48%' }]} placeholder="Stock Inicial" placeholderTextColor="#625E70" keyboardType="numeric" value={newBotellaStock} onChangeText={setNewBotellaStock} />
              </View>
              <TouchableOpacity style={[styles.button, { marginTop: 5 }]} onPress={handleAddBotella}>
                <Text style={styles.buttonText}>Añadir Botella</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.sectionTitle}>Botellas en Carta</Text>
            {(menuData[adminSelectedClub] || []).map((botella) => (
              <View key={botella.id} style={styles.adminMenuEditCard}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.adminItemBold}>{botella.nombre}</Text>
                  <Text style={styles.adminItemSub}>{botella.tipo}</Text>
                  
                  <View style={styles.inlineEditContainer}>
                    <View style={styles.inlineEditBlock}>
                      <Text style={styles.inlineEditLabel}>Precio $</Text>
                      <TextInput style={styles.inlineEditInput} keyboardType="numeric" value={String(botella.precio)} onChangeText={(val) => handleUpdatePriceStock(botella.id, 'precio', val)} />
                    </View>
                    <View style={styles.inlineEditBlock}>
                      <Text style={styles.inlineEditLabel}>Stock</Text>
                      <TextInput style={styles.inlineEditInput} keyboardType="numeric" value={String(botella.stock)} onChangeText={(val) => handleUpdatePriceStock(botella.id, 'stock', val)} />
                    </View>
                  </View>
                </View>
                
                <TouchableOpacity style={[styles.adminDeleteBtn, { alignSelf: 'center' }]} onPress={() => handleDeleteBotella(botella.id)}>
                  <Text style={styles.adminDeleteBtnText}>Remover</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" />
      {currentScreen === 'LOGIN' && renderLoginScreen()}
      {currentScreen === 'REGISTER' && renderRegisterScreen()}
      {currentScreen === 'VERIFY_OTP' && renderVerifyOtpScreen()}
      {currentScreen === 'ADMIN_2FA' && renderAdminOtpScreen()}
      {currentScreen === 'FORGOT_PASSWORD' && renderForgotPasswordScreen()}
      {currentScreen === 'DASHBOARD' && renderDashboardScreen()}
      {currentScreen === 'PAGO_MOVIL' && renderPagoMovilScreen()}
      {currentScreen === 'RECIBO' && renderReceiptScreen()}
      {currentScreen === 'ADMIN' && renderAdminScreen()}
    </View>
  );
}

// --- ESTILOS COMPLEMENTARIOS ---
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0B0813', paddingHorizontal: 20, paddingTop: 50 },
  mainContent: { flex: 1, width: '100%' },
  centerContainer: { flex: 1, width: '100%', justifyContent: 'center', alignItems: 'center' },
  headerContainer: { alignItems: 'center', marginBottom: 30 },
  title: { fontSize: 45, fontWeight: 'bold', color: '#9D4EDD', letterSpacing: 3, textAlign: 'center' },
  subtitle: { fontSize: 12, color: '#625E70', letterSpacing: 5, marginTop: 8, textAlign: 'center' },
  formContainer: { width: '100%' },
  label: { color: '#9D4EDD', fontSize: 11, marginBottom: 8, alignSelf: 'flex-start' },
  input: { height: 50, width: '100%', backgroundColor: '#151026', borderRadius: 12, paddingHorizontal: 16, color: '#FFF', marginBottom: 15 },
  passwordContainer: { flexDirection: 'row', alignItems: 'center', width: '100%', backgroundColor: '#151026', borderRadius: 12, marginBottom: 15, paddingRight: 12 },
  passwordInput: { flex: 1, height: 50, paddingHorizontal: 16, color: '#FFF' },
  eyeBtn: { padding: 4 },
  eyeEmoji: { fontSize: 18 },
  button: { height: 50, width: '100%', backgroundColor: '#7B2CBF', borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginTop: 10 },
  buttonText: { color: '#FFF', fontWeight: 'bold' },
  switchAuthBtn: { marginTop: 20, alignSelf: 'center' },
  switchAuthText: { color: '#625E70', fontSize: 13 },
  dashboardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, paddingBottom: 15, borderBottomWidth: 1, borderBottomColor: '#241B40' },
  dashboardUserRole: { color: '#9D4EDD', fontSize: 11 },
  dashboardWelcome: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
  logoutBtn: { backgroundColor: '#241B40', padding: 8, borderRadius: 8 },
  logoutBtnText: { color: '#FF5E5E', fontWeight: 'bold' },
  sectionTitle: { color: '#9D4EDD', fontSize: 13, fontWeight: 'bold', marginBottom: 15, marginTop: 10 },
  clubCard: { backgroundColor: '#151026', padding: 16, borderRadius: 12, marginBottom: 15 },
  clubTitle: { color: '#FFF', fontSize: 16, fontWeight: 'bold' },
  clubAddress: { color: '#625E70', fontSize: 12 },
  adminActionCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#151026', padding: 18, borderRadius: 14, marginBottom: 15 },
  adminCardIcon: { fontSize: 24, marginRight: 15 },
  adminCardTitle: { color: '#FFF', fontWeight: 'bold' },
  adminCardSubtitle: { color: '#625E70', fontSize: 11, marginTop: 2 },
  selectorTabContainer: { flexDirection: 'row', backgroundColor: '#151026', borderRadius: 10, padding: 4, marginBottom: 15 },
  selectorTab: { flex: 1, paddingVertical: 8, alignItems: 'center', borderRadius: 8 },
  selectorTabActive: { backgroundColor: '#7B2CBF' },
  selectorTabText: { color: '#FFF', fontWeight: 'bold' },
  floatingCartBtn: { position: 'absolute', bottom: 20, left: 10, right: 10, backgroundColor: '#7B2CBF', padding: 16, borderRadius: 12, alignItems: 'center' },
  floatingCartText: { color: '#FFF', fontWeight: 'bold' },
  modalOverlayCentered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.8)' },
  qtyBoxModal: { backgroundColor: '#151026', padding: 24, borderRadius: 16, width: '80%', alignItems: 'center', borderWidth: 1, borderColor: '#7B2CBF' },
  qtyModalTitle: { color: '#FFF', fontSize: 16, fontWeight: 'bold', marginBottom: 5 },
  qtyInputText: { backgroundColor: '#0B0813', color: '#FFF', width: '50%', height: 45, textAlign: 'center', borderRadius: 10, fontSize: 18 },
  qtyModalButtonsContainer: { flexDirection: 'row', justifyContent: 'space-between', width: '100%', marginTop: 20 },
  qtyModalBtn: { flex: 0.45, height: 40, justifyContent: 'center', alignItems: 'center', borderRadius: 8 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.8)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#151026', padding: 20, borderTopLeftRadius: 20, borderTopRightRadius: 20, height: '70%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 15 },
  modalTitle: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
  closeModalText: { color: '#9D4EDD' },
  cartItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#241B40' },
  cartStepperRow: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 10 },
  cartStepperBtn: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#241B40', justifyContent: 'center', alignItems: 'center' },
  cartStepperBtnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16, lineHeight: 18 },
  cartStepperQty: { color: '#FFF', fontWeight: 'bold', marginHorizontal: 10, minWidth: 16, textAlign: 'center' },
  cartDeleteBtn: { marginLeft: 10, width: 26, height: 26, borderRadius: 13, backgroundColor: '#FF5E5E22', justifyContent: 'center', alignItems: 'center' },
  cartDeleteBtnText: { color: '#FF5E5E', fontWeight: 'bold', fontSize: 12 },
  cartTotalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: 14, marginTop: 6, borderTopWidth: 1, borderTopColor: '#241B40' },
  cartTotalLabel: { color: '#B8B0C8', fontSize: 14, fontWeight: 'bold' },
  cartTotalValue: { color: '#FFF', fontSize: 20, fontWeight: 'bold' },
  progressBarTrack: { height: 8, borderRadius: 4, backgroundColor: '#241B40', overflow: 'hidden' },
  progressBarFill: { height: '100%', borderRadius: 4 },
  checkoutBtn: { backgroundColor: '#7B2CBF', height: 50, borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginTop: 15 },
  checkoutBtnText: { color: '#FFF', fontWeight: 'bold' },
  mesaSelectedBadge: { backgroundColor: '#1C1333', padding: 10, borderRadius: 8, marginBottom: 10 },
  mesaSelectedText: { color: '#9D4EDD', fontWeight: 'bold' },
  qrContainer: { alignItems: 'center', backgroundColor: '#151026', borderRadius: 16, padding: 20, marginBottom: 20, borderWidth: 1, borderColor: '#241B40' },
  qrInstructions: { color: '#9D4EDD', fontWeight: 'bold', fontSize: 13, marginBottom: 15 },
  qrCodeImage: { width: 180, height: 180, borderRadius: 8 },
  qrFooterText: { color: '#625E70', fontSize: 10, marginTop: 12, textAlign: 'center' },
  paymentReceiptBadge: { backgroundColor: '#1C1333', padding: 15, borderRadius: 12, alignItems: 'center', marginBottom: 15 },
  receiptLabel: { color: '#9D4EDD', fontSize: 10, fontWeight: 'bold' },
  receiptAmountVes: { color: '#FFF', fontSize: 26, fontWeight: 'bold', marginVertical: 4 },
  receiptAmountUsd: { color: '#625E70', fontSize: 11 },
  pmDetailsCard: { backgroundColor: '#151026', padding: 12, borderRadius: 10, marginBottom: 15 },
  pmDetailsRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  pmLabel: { color: '#625E70' },
  pmValue: { color: '#FFF' },
  qrResultContainer: { backgroundColor: '#1C1333', borderLeftWidth: 4, borderLeftColor: '#00E676', padding: 16, borderRadius: 12, marginBottom: 20 },
  qrResultStatus: { color: '#00E676', fontWeight: 'bold', fontSize: 16, marginBottom: 10 },
  qrResultDetails: { marginBottom: 12 },
  qrResultLabel: { color: '#7B7788', fontSize: 12, marginBottom: 4 },
  qrResultValue: { color: '#FFF', fontWeight: '600' },
  clearScanBtn: { alignSelf: 'flex-end', backgroundColor: '#241B40', paddingVertical: 6, paddingHorizontal: 12, borderRadius: 6 },
  clearScanBtnText: { color: '#9D4EDD', fontSize: 12, fontWeight: 'bold' },
  receiptHeader: { alignItems: 'center', marginVertical: 20 },
  receiptCheckIcon: { fontSize: 48, marginBottom: 10 },
  receiptMainTitle: { color: '#FFF', fontSize: 22, fontWeight: 'bold' },
  receiptSubTitle: { color: '#625E70', fontSize: 12, textAlign: 'center', marginTop: 6, paddingHorizontal: 20 },
  ticketBox: { backgroundColor: '#151026', borderRadius: 16, padding: 20, marginBottom: 25, borderStyle: 'solid', borderWidth: 1, borderColor: '#241B40' },
  ticketHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  ticketHeading: { color: '#9D4EDD', fontSize: 11, fontWeight: 'bold', letterSpacing: 1, marginBottom: 8 },
  ticketId: { color: '#625E70', fontSize: 11 },
  divider: { height: 1, backgroundColor: '#241B40', marginVertical: 12 },
  ticketRow: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 4 },
  ticketLabel: { color: '#625E70', fontSize: 13 },
  ticketValue: { color: '#FFF', fontSize: 13, fontWeight: '600' },
  ticketItemRow: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 3 },
  ticketItemText: { color: '#FFF', fontSize: 13 },
  ticketItemPrice: { color: '#9D4EDD', fontSize: 13 },
  ticketRowTotal: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  totalLabel: { color: '#9D4EDD', fontSize: 15, fontWeight: 'bold' },
  totalUsdText: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
  totalVesText: { color: '#625E70', fontSize: 12 },
  adminBackBtn: { backgroundColor: '#241B40', paddingVertical: 6, paddingHorizontal: 12, borderRadius: 8 },
  adminBackBtnText: { color: '#9D4EDD', fontWeight: 'bold', fontSize: 12 },
  adminFormContainer: { backgroundColor: '#151026', padding: 15, borderRadius: 14, marginBottom: 20, borderWidth: 1, borderColor: '#241B40' },
  adminFormTitle: { color: '#FFF', fontSize: 14, fontWeight: 'bold', marginBottom: 12 },
  adminInput: { height: 42, backgroundColor: '#0B0813', borderRadius: 8, paddingHorizontal: 12, color: '#FFF', marginBottom: 10, fontSize: 13 },
  adminListItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#151026', padding: 15, borderRadius: 10, marginBottom: 10 },
  adminItemBold: { color: '#FFF', fontWeight: 'bold', fontSize: 14 },
  adminItemSub: { color: '#625E70', fontSize: 11, marginTop: 2 },
  adminDeleteBtn: { backgroundColor: '#FF5E5E22', paddingVertical: 6, paddingHorizontal: 12, borderRadius: 6 },
  adminDeleteBtnText: { color: '#FF5E5E', fontSize: 11, fontWeight: 'bold' },
  adminMenuEditCard: { backgroundColor: '#151026', padding: 15, borderRadius: 12, marginBottom: 12, flexDirection: 'row', justifyContent: 'space-between' },
  inlineEditContainer: { flexDirection: 'row', marginTop: 10 },
  inlineEditBlock: { marginRight: 15 },
  inlineEditLabel: { color: '#625E70', fontSize: 9, marginBottom: 4 },
  inlineEditInput: { backgroundColor: '#0B0813', color: '#9D4EDD', width: 60, height: 30, borderRadius: 6, textAlign: 'center', fontSize: 12, fontWeight: 'bold' },
  
  verificationStepContainer: { width: '100%', alignItems: 'center', paddingVertical: 10 },
  stepTitle: { color: '#FFF', fontSize: 18, fontWeight: 'bold', marginBottom: 8, textAlign: 'center' },
  stepDescription: { color: '#625E70', fontSize: 13, textAlign: 'center', marginBottom: 30, lineHeight: 18, paddingHorizontal: 10 },
  scanLargeBtn: { width: '100%', backgroundColor: '#151026', borderColor: '#9D4EDD', borderWidth: 2, borderStyle: 'dashed', borderRadius: 18, paddingVertical: 35, alignItems: 'center', justifyContent: 'center' },
  scanLargeEmoji: { fontSize: 40, marginBottom: 12 },
  scanLargeBtnText: { color: '#FFF', fontSize: 15, fontWeight: 'bold' },
  scanLargeSubtitle: { color: '#9D4EDD', fontSize: 11, marginTop: 6 },
  verifiedAlertBadge: { backgroundColor: '#00E67615', borderColor: '#00E676', borderWidth: 1, paddingVertical: 10, paddingHorizontal: 15, borderRadius: 10, marginBottom: 25, width: '100%', alignItems: 'center' },
  verifiedAlertText: { color: '#00E676', fontWeight: 'bold', fontSize: 13 }
});