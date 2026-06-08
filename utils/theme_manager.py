import json
import os

THEME_FILE = "theme_config.json"

def guardar_tema(tema):
    with open(THEME_FILE, "w") as f:
        json.dump({"tema": tema}, f)

def cargar_tema():
    if os.path.exists(THEME_FILE):
        with open(THEME_FILE, "r") as f:
            data = json.load(f)
            return data.get("tema", "dark")
    return "dark"