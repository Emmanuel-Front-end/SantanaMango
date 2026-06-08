# auth.py - Sistema de autenticación y permisos corregido
import os
import json
import secrets
from datetime import datetime, timedelta
from database import ejecutar_consulta

SESSION_FILE = "session_secure.dat"
TOKEN_EXPIRATION_HOURS = 8

def generar_token():
    return secrets.token_urlsafe(32)

def guardar_sesion_segura(usuario_id, usuario, rol, token):
    from cryptography.fernet import Fernet
    from config import generar_clave
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
            from cryptography.fernet import Fernet
            from config import generar_clave
            key = generar_clave()
            cipher = Fernet(key)
            with open(SESSION_FILE, "rb") as f:
                encrypted = f.read()
            datos = json.loads(cipher.decrypt(encrypted).decode())
            expira = datetime.fromisoformat(datos["expira"])
            if datetime.now() <= expira:
                permisos = cargar_permisos_usuario(datos["usuario_id"])
                print(f"DEBUG: Permisos cargados para {datos['usuario']}: {list(permisos.keys())}")
                return datos["usuario"], datos["rol"], permisos
    except Exception as e:
        print(f"Error cargando sesión segura: {e}")

    # Fallback: archivo simple
    try:
        if os.path.exists("session_user.txt"):
            with open("session_user.txt", "r") as f:
                contenido = f.read().strip()
                if "|" in contenido:
                    usuario, rol = contenido.split("|")
                else:
                    usuario, rol = contenido, "operador"
            resultado = ejecutar_consulta("SELECT id FROM usuarios WHERE nombre_usuario = %s", (usuario,), fetchone=True)
            if resultado:
                usuario_id = resultado[0]
                permisos = cargar_permisos_usuario(usuario_id)
                return usuario, rol, permisos
    except Exception as e:
        print(f"Error cargando sesión simple: {e}")

    # Usuario por defecto (solo para desarrollo - eliminar en producción)
    print("ADVERTENCIA: Usando usuario admin por defecto sin autenticación real.")
    return "admin", "admin", obtener_permisos_admin()

def obtener_permisos_admin():
    """Permisos completos para administrador"""
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
    """Carga permisos desde la base de datos (si no hay, devuelve permisos mínimos)"""
    try:
        # Verificar si el usuario es administrador (rol 'admin')
        rol = ejecutar_consulta("SELECT rol FROM usuarios WHERE id = %s", (usuario_id,), fetchone=True)
        if rol and rol[0] == 'admin':
            return obtener_permisos_admin()

        # Si no es admin, cargar permisos específicos
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
    """Verifica si el usuario tiene permiso para un módulo y acción específicos"""
    if not permisos:
        return False
    if modulo not in permisos:
        return False
    return permisos[modulo].get(accion, False)

def cerrar_sesion():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    if os.path.exists("session_user.txt"):
        os.remove("session_user.txt")