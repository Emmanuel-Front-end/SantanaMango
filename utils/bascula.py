# utils/bascula.py
import customtkinter as ctk
import serial
import serial.tools.list_ports
import json
import os
import threading
import time
from datetime import datetime

class Bascula:
    def __init__(self):
        self.puerto = self.cargar_config()
        self.conexion = None
        self.lectura_continua = False
        self.hilo_lectura = None
        self.callback_peso = None
        self.peso_actual = 0.0
        
    def cargar_config(self):
        """Carga configuración del puerto serie"""
        config_file = "bascula_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                    return config.get("puerto")
            except:
                pass
        return None
    
    def guardar_config(self, puerto):
        """Guarda configuración del puerto"""
        with open("bascula_config.json", "w") as f:
            json.dump({"puerto": puerto, "ultima_actualizacion": datetime.now().isoformat()}, f)
        self.puerto = puerto
    
    def listar_puertos(self):
        """Lista puertos COM disponibles"""
        puertos = []
        for port in serial.tools.list_ports.comports():
            puertos.append(port.device)
        return puertos
    
    def conectar(self, puerto=None):
        """Conecta a la báscula"""
        if puerto:
            self.puerto = puerto
            self.guardar_config(puerto)
        
        if not self.puerto:
            return False, "No hay puerto configurado"
        
        try:
            self.conexion = serial.Serial(
                port=self.puerto,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            return True, f"Conectado a {self.puerto}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def desconectar(self):
        """Desconecta la báscula"""
        self.lectura_continua = False
        if self.hilo_lectura and self.hilo_lectura.is_alive():
            self.hilo_lectura.join(timeout=2)
        if self.conexion and self.conexion.is_open:
            self.conexion.close()
        return True, "Desconectado"
    
    def leer_peso(self):
        """Lee un solo peso de la báscula"""
        if not self.conexion or not self.conexion.is_open:
            return None, "No conectado"
        
        try:
            self.conexion.reset_input_buffer()
            linea = self.conexion.readline().decode('ascii', errors='ignore').strip()
            peso = self._parsear_peso(linea)
            return peso, linea
        except Exception as e:
            return None, str(e)
    
    def _parsear_peso(self, texto):
        """Parsea el peso desde diferentes formatos de báscula"""
        import re
        numeros = re.findall(r'(\d+[.,]\d+|\d+)', texto)
        if numeros:
            peso_str = numeros[-1].replace(',', '.')
            try:
                return float(peso_str)
            except:
                return 0.0
        return 0.0
    
    def iniciar_lectura_continua(self, callback):
        """Inicia lectura continua en segundo plano"""
        self.callback_peso = callback
        self.lectura_continua = True
        self.hilo_lectura = threading.Thread(target=self._loop_lectura, daemon=True)
        self.hilo_lectura.start()
    
    def _loop_lectura(self):
        """Loop de lectura continua"""
        while self.lectura_continua:
            peso, _ = self.leer_peso()
            if peso is not None:
                self.peso_actual = peso
                if self.callback_peso:
                    self.callback_peso(peso)
            time.sleep(0.2)
    
    def detener_lectura(self):
        """Detiene la lectura continua"""
        self.lectura_continua = False
    
    def obtener_peso_estable(self, intentos=5, delay=0.3):
        """Obtiene peso cuando está estable"""
        lecturas = []
        for _ in range(intentos):
            peso, _ = self.leer_peso()
            if peso is not None:
                lecturas.append(peso)
            time.sleep(delay)
        
        if len(lecturas) >= 3 and all(abs(l - lecturas[0]) < 0.5 for l in lecturas):
            return lecturas[0]
        return None


# Widget de báscula para UI
class WidgetBascula(ctk.CTkFrame):
    def __init__(self, parent, on_peso_recibido=None):
        super().__init__(parent, fg_color=("#f0f0f0", "#2a2a2a"), corner_radius=10)
        self.bascula = Bascula()
        self.on_peso_recibido = on_peso_recibido
        self.leyendo = False
        
        self._crear_widgets()
        self._actualizar_puertos()
        
    def _crear_widgets(self):
        # Título
        ctk.CTkLabel(self, text="⚖️ Báscula", font=("Arial", 16, "bold")).pack(pady=(10,5))
        
        # Puerto
        puerto_frame = ctk.CTkFrame(self, fg_color="transparent")
        puerto_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(puerto_frame, text="Puerto:").pack(side="left", padx=5)
        self.combo_puerto = ctk.CTkComboBox(puerto_frame, values=["Seleccionar..."], width=120)
        self.combo_puerto.pack(side="left", padx=5)
        
        # Botón conectar
        self.btn_conectar = ctk.CTkButton(puerto_frame, text="🔌 Conectar", command=self.toggle_conexion, width=80)
        self.btn_conectar.pack(side="left", padx=5)
        
        # Display de peso
        self.peso_frame = ctk.CTkFrame(self, fg_color=("#1e1e1e", "#0a0a0a"), corner_radius=15)
        self.peso_frame.pack(fill="x", padx=20, pady=10)
        
        self.label_peso = ctk.CTkLabel(
            self.peso_frame, 
            text="0.00", 
            font=("Arial", 48, "bold"),
            text_color="#2e8b57"
        )
        self.label_peso.pack(pady=20)
        
        ctk.CTkLabel(self.peso_frame, text="kilogramos", font=("Arial", 12)).pack()
        
        # Botones de acción
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        self.btn_leer = ctk.CTkButton(btn_frame, text="📥 Leer peso", command=self.leer_peso_manual, width=100)
        self.btn_leer.pack(side="left", padx=5)
        
        self.btn_auto = ctk.CTkButton(btn_frame, text="🔄 Lectura continua", command=self.toggle_lectura_continua, width=120)
        self.btn_auto.pack(side="left", padx=5)
        
        self.btn_enviar = ctk.CTkButton(btn_frame, text="✅ Enviar a formulario", command=self.enviar_peso, width=150, fg_color="#2e8b57")
        self.btn_enviar.pack(side="right", padx=5)
        
        # Estado
        self.label_estado = ctk.CTkLabel(self, text="⚫ Desconectado", font=("Arial", 10))
        self.label_estado.pack(pady=(0,10))
    
    def _actualizar_puertos(self):
        puertos = self.bascula.listar_puertos()
        if puertos:
            self.combo_puerto.configure(values=puertos)
            if self.bascula.puerto and self.bascula.puerto in puertos:
                self.combo_puerto.set(self.bascula.puerto)
        else:
            self.combo_puerto.configure(values=["No hay puertos disponibles"])
    
    def toggle_conexion(self):
        if self.bascula.conexion and self.bascula.conexion.is_open:
            self.bascula.desconectar()
            self.btn_conectar.configure(text="🔌 Conectar", fg_color=None)
            self.label_estado.configure(text="⚫ Desconectado", text_color="red")
            self.label_peso.configure(text="0.00")
        else:
            puerto = self.combo_puerto.get()
            exito, mensaje = self.bascula.conectar(puerto)
            if exito:
                self.btn_conectar.configure(text="🔴 Desconectar", fg_color="#8b0000")
                self.label_estado.configure(text="🟢 Conectado", text_color="green")
            else:
                self.label_estado.configure(text=f"❌ {mensaje}", text_color="red")
    
    def leer_peso_manual(self):
        if not self.bascula.conexion or not self.bascula.conexion.is_open:
            self.label_estado.configure(text="❌ Conecte la báscula primero", text_color="red")
            return
        
        peso, _ = self.bascula.leer_peso()
        if peso:
            self.label_peso.configure(text=f"{peso:.2f}")
            self.label_estado.configure(text="✅ Peso leído", text_color="green")
        else:
            self.label_estado.configure(text="⚠️ No se detectó peso", text_color="orange")
    
    def toggle_lectura_continua(self):
        if self.leyendo:
            self.bascula.detener_lectura()
            self.leyendo = False
            self.btn_auto.configure(text="🔄 Lectura continua", fg_color=None)
            self.label_estado.configure(text="Lectura detenida", text_color="orange")
        else:
            if not self.bascula.conexion or not self.bascula.conexion.is_open:
                self.label_estado.configure(text="❌ Conecte la báscula primero", text_color="red")
                return
            self.bascula.iniciar_lectura_continua(self.actualizar_peso_ui)
            self.leyendo = True
            self.btn_auto.configure(text="⏹️ Detener", fg_color="#8b0000")
            self.label_estado.configure(text="🟢 Leyendo continuamente...", text_color="green")
    
    def actualizar_peso_ui(self, peso):
        if peso:
            self.label_peso.configure(text=f"{peso:.2f}")
    
    def enviar_peso(self):
        if self.on_peso_recibido:
            try:
                peso = float(self.label_peso.cget("text"))
                self.on_peso_recibido(peso)
            except:
                pass
    
    def get_peso(self):
        try:
            return float(self.label_peso.cget("text"))
        except:
            return 0.0