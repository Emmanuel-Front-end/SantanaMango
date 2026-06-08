import os
import json
from cryptography.fernet import Fernet

CONFIG_FILE = "network_config.json"
KEY_FILE = "secret.key"

def generar_clave():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    return open(KEY_FILE, "rb").read()

def guardar_config(db_host, db_port, db_name, db_user, db_password):
    data = {
        "db_host": db_host,
        "db_port": db_port,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password
    }
    key = generar_clave()
    cipher = Fernet(key)
    encrypted = cipher.encrypt(json.dumps(data).encode())
    with open(CONFIG_FILE, "wb") as f:
        f.write(encrypted)

def cargar_config():
    if not os.path.exists(CONFIG_FILE) or not os.path.exists(KEY_FILE):
        return None
    key = open(KEY_FILE, "rb").read()
    cipher = Fernet(key)
    with open(CONFIG_FILE, "rb") as f:
        encrypted = f.read()
    decrypted = cipher.decrypt(encrypted)
    return json.loads(decrypted.decode())

def eliminar_config():
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    if os.path.exists(KEY_FILE):
        os.remove(KEY_FILE)