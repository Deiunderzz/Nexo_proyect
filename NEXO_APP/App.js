import React, { useState } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, Alert, StatusBar } from 'react-native';

export default function App() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = () => {
    Alert.alert("Iniciar Sesión", `Conectando al backend con:\n${email}`);
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" />
      
      {/* Bloque Central */}
      <View style={styles.mainContent}>
        
        {/* Encabezado estilizado con fuentes premium */}
        <View style={styles.headerContainer}>
          <Text style={styles.title}>NEXO</Text>
          <Text style={styles.subtitle}>After Hours Society</Text>
        </View>

        {/* Formulario */}
        <View style={styles.formContainer}>
          <Text style={styles.label}>Correo electrónico</Text>
          <TextInput 
            style={styles.input}
            placeholder="ejemplo@nexo.com"
            placeholderTextColor="#444"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
          />

          <Text style={styles.label}>Contraseña</Text>
          <TextInput 
            style={styles.input}
            placeholder="••••••••••••"
            placeholderTextColor="#444"
            value={password}
            onChangeText={setPassword}
            secureTextEntry={true}
          />

          <TouchableOpacity style={styles.forgotPassword}>
            <Text style={styles.forgotPasswordText}>¿Olvidaste tu contraseña?</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.button} onPress={handleLogin}>
            <Text style={styles.buttonText}>Ingresar</Text>
          </TouchableOpacity>
        </View>

      </View>

      {/* Footer fijo abajo */}
      <TouchableOpacity style={styles.footer}>
        <Text style={styles.footerText}>¿No tienes cuenta? <Text style={styles.registerText}>Crear una cuenta</Text></Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0813', 
    justifyContent: 'space-between',
    paddingHorizontal: 28,
    paddingTop: 40,
    paddingBottom: 40,
  },
  mainContent: {
    flex: 1,
    justifyContent: 'center', 
    width: '100%',
  },
  headerContainer: {
    alignItems: 'center',
    marginBottom: 45, 
  },
  title: {
    fontSize: 60,              // Tamaño elegante
    fontWeight: '300',         // Más fina y sofisticada
    color: '#9D4EDD', 
    fontFamily: 'Impact', // Fuente premium
    letterSpacing: 5,          // Espaciado VIP entre letras
    textAlign: 'center',
    textTransform: 'uppercase',
  },
  subtitle: {
    fontSize: 12,              // Micro-texto premium
    fontWeight: '750', 
    color: '#625E70',          // Tono misterioso
    fontFamily: 'Academy Engraved LET',
    marginTop: 12,
    textAlign: 'center',
    letterSpacing: 8,          // Espaciado dramático
    textTransform: 'uppercase', // Fuerza las mayúsculas estéticas
  },
  formContainer: {
    width: '100%',
  },
  label: {
    color: '#9D4EDD',
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  input: {
    width: '100%',
    height: 56,
    backgroundColor: '#151026',
    borderRadius: 12,
    paddingHorizontal: 16,
    color: '#FFF',
    fontSize: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#241B40',
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    marginBottom: 28,
  },
  forgotPasswordText: {
    color: '#7B7788',
    fontSize: 14,
  },
  button: {
    width: '100%',
    height: 56,
    backgroundColor: '#7B2CBF',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#7B2CBF',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 5,
  },
  buttonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '700',
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
  },
  footerText: {
    color: '#7B7788',
    fontSize: 14,
  },
  registerText: {
    color: '#9D4EDD',
    fontWeight: '700',
  },
});