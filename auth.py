# auth.py - Sistema de autenticación y permisos sin archivo de texto plano
import os
import json
import secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from database import ejecutar_consulta
from config import generar_clave

SESSION_FILE = "session_secure.dat"
TOKEN_EXPIRATION_HOURS = 8

# ==================== CIFRADO DE CONTRASEÑAS (REVERSIBLE) ====================
def cifrar_contrasena(contrasena):
    """Cifra una contraseña de forma reversible usando Fernet."""
    if not contrasena:
        return None
    key = generar_clave()
    cipher = Fernet(key)
    return cipher.encrypt(contrasena.encode()).decode()

def descifrar_contrasena(contrasena_cifrada):
    """Descifra una contraseña previamente cifrada con cifrar_contrasena."""
    if not contrasena_cifrada:
        return ""
    try:
        key = generar_clave()
        cipher = Fernet(key)
        return cipher.decrypt(contrasena_cifrada.encode()).decode()
    except Exception:
        return ""

# ==================== FUNCIONES DE SESIÓN ====================
def generar_token():
    return secrets.token_urlsafe(32)

def guardar_sesion_segura(usuario_id, usuario, rol, token):
    datos = {
        "usuario_id": usuario_id,
        "usuario": usuario,
        "rol": rol,
        "token": token,
        "expira": (datetime.now() + timedelta(hours=TOKEN_EXPIRATION_HOURS)).isoformat()
    }
    key = generar_clave()
    cipher = Fernet(key)
    encrypted = cipher.encrypt(json.dumps(datos).encode())
    with open(SESSION_FILE, "wb") as f:
        f.write(encrypted)

def cargar_sesion():
    # Intento de sesión segura
    try:
        if os.path.exists(SESSION_FILE):
            key = generar_clave()
            cipher = Fernet(key)
            with open(SESSION_FILE, "rb") as f:
                encrypted = f.read()
            datos = json.loads(cipher.decrypt(encrypted).decode())
            expira = datetime.fromisoformat(datos["expira"])
            if datetime.now() <= expira:
                permisos = cargar_permisos_usuario(datos["usuario_id"])
                return datos["usuario"], datos["rol"], permisos
    except Exception as e:
        print(f"Error cargando sesión segura: {e}")

    # Usuario por defecto (solo desarrollo - eliminar en producción)
    print("ADVERTENCIA: Usando usuario admin por defecto sin autenticación real.")
    return "admin", "admin", obtener_permisos_admin()

def obtener_permisos_admin():
    modulos = [
        "catalogos", "recepcion", "gestion_taras", "pesaje_lavado",
        "pesaje_rezaga", "transportes", "hidrotermico", "etiquetas",
        "embarques", "rezaga", "calidad", "reportes", "configuracion"
    ]
    permisos = {}
    for modulo in modulos:
        permisos[modulo] = {"leer": True, "crear": True, "editar": True, "eliminar": True}
    return permisos

def cargar_permisos_usuario(usuario_id):
    try:
        rol = ejecutar_consulta("SELECT rol FROM usuarios WHERE id = %s", (usuario_id,), fetchone=True)
        if rol and rol[0] == 'admin':
            return obtener_permisos_admin()

        query = """
            SELECT m.nombre_modulo,
                   p.puede_leer, p.puede_crear, p.puede_editar, p.puede_eliminar
            FROM permisos_usuario p
            JOIN modulos_sistema m ON p.modulo_id = m.id
            WHERE p.usuario_id = %s
        """
        resultados = ejecutar_consulta(query, (usuario_id,), fetchall=True)
        permisos = {}
        for r in resultados:
            modulo = r[0]
            permisos[modulo] = {
                "leer": r[1],
                "crear": r[2],
                "editar": r[3],
                "eliminar": r[4]
            }
        return permisos
    except Exception as e:
        print(f"Error cargando permisos: {e}")
        return {}

def tiene_permiso(permisos, modulo, accion):
    if not permisos:
        return False
    if modulo not in permisos:
        return False
    return permisos[modulo].get(accion, False)

def cerrar_sesion():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)