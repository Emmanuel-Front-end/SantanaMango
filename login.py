# login.py - Sin bloqueo por intentos (solo captcha tras 2 fallos)
import customtkinter as ctk
from tkinter import messagebox, simpledialog
from PIL import Image
import hashlib
import os
import sys
import subprocess
import json
import smtplib
import random
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet
from config import cargar_config, guardar_config
from auth import cifrar_contrasena, guardar_sesion_segura, generar_token, cargar_sesion
from dotenv import load_dotenv

load_dotenv()  # Cargar variables de entorno desde .env

try:
    from menu_principal import abrir_menu_principal
except ImportError:
    def abrir_menu_principal():
        messagebox.showinfo("Info", "Menú principal aún no implementado")

# Archivos de datos
RECORDAR_FILE = "recordar_usuario.json"
CODIGO_2FA_FILE = "codigo_2fa_temp.json"

# Configuración SMTP desde variables de entorno
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ==================== FUNCIONES AUXILIARES ====================
def generar_clave():
    key_file = "recordar.key"
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    return open(key_file, "rb").read()

def guardar_recordar(usuario, recordar):
    if recordar and usuario:
        with open(RECORDAR_FILE, "w") as f:
            json.dump({"usuario": usuario}, f)
    else:
        if os.path.exists(RECORDAR_FILE):
            os.remove(RECORDAR_FILE)

def cargar_recordar():
    if os.path.exists(RECORDAR_FILE):
        try:
            with open(RECORDAR_FILE, "r") as f:
                data = json.load(f)
                return data.get("usuario", "")
        except:
            pass
    return ""

def enviar_correo(destino, asunto, cuerpo):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = destino
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error enviando correo: {e}")
        return False

def generar_codigo_2fa():
    return str(random.randint(100000, 999999))

def guardar_codigo_2fa(codigo):
    with open(CODIGO_2FA_FILE, "w") as f:
        json.dump({"codigo": codigo, "timestamp": time.time()}, f)

def verificar_codigo_2fa(codigo_ingresado):
    if os.path.exists(CODIGO_2FA_FILE):
        with open(CODIGO_2FA_FILE, "r") as f:
            data = json.load(f)
        if data.get("codigo") == codigo_ingresado and (time.time() - data.get("timestamp", 0)) < 300:
            os.remove(CODIGO_2FA_FILE)
            return True
    return False

# ==================== VALIDACIÓN DE ADMINISTRADOR ====================
def verificar_admin_password():
    password = simpledialog.askstring("Autorización requerida", 
                                      "Ingrese la contraseña del administrador:", 
                                      show='*')
    if not password:
        return False
    hash_pass = hashlib.sha256(password.encode()).hexdigest()
    try:
        from database import ejecutar_consulta
        resultado = ejecutar_consulta(
            "SELECT id FROM usuarios WHERE rol='admin' AND contrasena_hash=%s AND activo=true",
            (hash_pass,), fetchone=True
        )
        return resultado is not None
    except Exception as e:
        print(f"Error verificando admin: {e}")
        return False

# ==================== VENTANA DE REGISTRO (solo para admin) ====================
class RegistroWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Registro de nuevo usuario")
        self.geometry("450x500")
        self.resizable(False, False)
        self.grab_set()
        self.parent = parent
        self.idioma = parent.idioma_actual if hasattr(parent, 'idioma_actual') else "es"
        self.textos = parent.textos if hasattr(parent, 'textos') else None
        self._crear_widgets()

    def _crear_widgets(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text="Nuevo Usuario", font=("Arial", 20, "bold")).pack(pady=(0, 20))
        self.user_entry = ctk.CTkEntry(frame, placeholder_text="Usuario", width=300)
        self.user_entry.pack(pady=5)
        self.email_entry = ctk.CTkEntry(frame, placeholder_text="Email", width=300)
        self.email_entry.pack(pady=5)
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text="Contraseña", show="•", width=300)
        self.pass_entry.pack(pady=5)
        self.confirm_entry = ctk.CTkEntry(frame, placeholder_text="Confirmar contraseña", show="•", width=300)
        self.confirm_entry.pack(pady=5)
        self.btn_registrar = ctk.CTkButton(frame, text="Registrarse", command=self.registrar)
        self.btn_registrar.pack(pady=20)
        self.status = ctk.CTkLabel(frame, text="", text_color="red")
        self.status.pack()

    def registrar(self):
        usuario = self.user_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.pass_entry.get()
        confirm = self.confirm_entry.get()
        if not usuario or not email or not password:
            self.status.configure(text="Complete todos los campos")
            return
        if password != confirm:
            self.status.configure(text="Las contraseñas no coinciden")
            return
        if len(password) < 6:
            self.status.configure(text="La contraseña debe tener al menos 6 caracteres")
            return
        if "@" not in email or "." not in email:
            self.status.configure(text="Email inválido")
            return

        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        contrasena_cifrada = cifrar_contrasena(password)

        try:
            from database import ejecutar_consulta
            existe = ejecutar_consulta("SELECT id FROM usuarios WHERE nombre_usuario=%s", (usuario,), fetchone=True)
            if existe:
                self.status.configure(text="El usuario ya existe")
                return
            try:
                ejecutar_consulta(
                    "INSERT INTO usuarios (nombre_usuario, contrasena_hash, contrasena_cifrada, rol, activo, email) VALUES (%s, %s, %s, %s, %s, %s)",
                    (usuario, hash_pass, contrasena_cifrada, "operador", True, email)
                )
            except Exception:
                ejecutar_consulta(
                    "INSERT INTO usuarios (nombre_usuario, contrasena_hash, contrasena_cifrada, rol, activo) VALUES (%s, %s, %s, %s, %s)",
                    (usuario, hash_pass, contrasena_cifrada, "operador", True)
                )
            messagebox.showinfo("Registro", "Usuario registrado correctamente")
            self.parent.cargar_lista_usuarios()
            self.destroy()
        except Exception as e:
            self.status.configure(text=f"Error: {str(e)}")

# ==================== VENTANA PRINCIPAL LOGIN ====================
class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Santana Mango Manager - Login")
        self.geometry("500x700")
        self.resizable(False, False)
        self.configure(fg_color="#0a0a0a")
        self.after(0, self.center_window)

        self.password_visible = False
        self.idioma_actual = "en"
        self.textos = self._cargar_textos()
        self.captcha_valor = None
        self.codigo_2fa_enviado = False
        self.correo_2fa = None
        self.lista_usuarios = []
        self.intentos_fallidos = 0          # Solo para mostrar captcha tras 2 fallos, sin bloqueo

        self.remember_var = ctk.BooleanVar()
        saved_user = cargar_recordar()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self._crear_widgets()
        self.cargar_lista_usuarios()

        if saved_user:
            self.user_combo.set(saved_user)
            self.remember_var.set(True)

        self.alpha = 0
        self.attributes("-alpha", self.alpha)
        self.fade_in()

        self.verificar_columna_contrasena_cifrada()
        self.verificar_conexion_inicial()

    def verificar_columna_contrasena_cifrada(self):
        try:
            from database import ejecutar_consulta
            ejecutar_consulta("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS contrasena_cifrada TEXT")
            ejecutar_consulta("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email VARCHAR(100)")
        except Exception as e:
            print(f"Nota: No se pudo verificar/crear columna: {e}")

    def verificar_conexion_inicial(self):
        config = cargar_config()
        if config is None:
            self.mostrar_boton_red(True)
            self.after(100, lambda: self.mostrar_configuracion_red(primer_inicio=True))
        else:
            try:
                from database import ejecutar_consulta
                ejecutar_consulta("SELECT 1", fetchone=True)
                self.mostrar_boton_red(False)
            except Exception as e:
                print(f"Error de conexión inicial: {e}")
                self.mostrar_boton_red(True)
                self.status_label.configure(text="⚠️ Error de conexión a la base de datos. Configure la red.")

    def mostrar_boton_red(self, mostrar):
        if mostrar:
            self.config_link.pack(side="right", padx=5)
        else:
            self.config_link.pack_forget()

    def cargar_lista_usuarios(self):
        try:
            from database import ejecutar_consulta
            resultados = ejecutar_consulta(
                "SELECT nombre_usuario FROM usuarios WHERE activo=true ORDER BY nombre_usuario",
                fetchall=True
            )
            if resultados:
                self.lista_usuarios = [row[0] for row in resultados]
            else:
                self.lista_usuarios = []
            self.user_combo.configure(values=self.lista_usuarios)
            if self.lista_usuarios and not self.user_combo.get():
                self.user_combo.set(self.lista_usuarios[0])
        except Exception as e:
            print(f"Error cargando usuarios: {e}")
            self.lista_usuarios = []
            self.user_combo.configure(values=[])
            self.mostrar_boton_red(True)

    def _cargar_textos(self):
        return {
            "es": {
                "Usuario": "Usuario",
                "Contraseña": "Contraseña",
                "INICIAR SESIÓN": "INICIAR SESIÓN",
                "Configuración de red": "⚙️ Configuración de red",
                "¿Olvidaste tu contraseña?": "¿Olvidaste tu contraseña?",
                "Registrarse": "Registrarse",
                "Idioma: Español": "🇪🇸 Español",
                "Idioma: Inglés": "🇬🇧 English",
                "Complete todos los campos": "⚠️ Complete ambos campos",
                "Usuario o contraseña incorrectos": "❌ Usuario o contraseña incorrectos",
                "Código 2FA": "Código de verificación",
                "Verificar": "Verificar",
                "Código enviado a su correo": "Se ha enviado un código de verificación a su correo",
                "Captcha": "Captcha",
                "Resultado": "Resultado",
                "Fortaleza: ": "Fortaleza: ",
                "Muy débil": "Muy débil",
                "Débil": "Débil",
                "Media": "Media",
                "Fuerte": "Fuerte",
                "Muy fuerte": "Muy fuerte"
            },
            "en": {
                "Usuario": "Username",
                "Contraseña": "Password",
                "INICIAR SESIÓN": "LOGIN",
                "Configuración de red": "⚙️ Network settings",
                "¿Olvidaste tu contraseña?": "Forgot password?",
                "Registrarse": "Sign up",
                "Idioma: Español": "🇪🇸 Spanish",
                "Idioma: Inglés": "🇬🇧 English",
                "Complete todos los campos": "⚠️ Please fill all fields",
                "Usuario o contraseña incorrectos": "❌ Invalid username or password",
                "Código 2FA": "Verification code",
                "Verificar": "Verify",
                "Código enviado a su correo": "A verification code has been sent to your email",
                "Captcha": "Captcha",
                "Resultado": "Result",
                "Fortaleza: ": "Strength: ",
                "Muy débil": "Very weak",
                "Débil": "Weak",
                "Media": "Medium",
                "Fuerte": "Strong",
                "Muy fuerte": "Very strong"
            }
        }

    def _t(self, key):
        return self.textos.get(self.idioma_actual, {}).get(key, key)

    # ==================== INTERFAZ ====================
    def _crear_widgets(self):
        self.card = ctk.CTkFrame(
            self, width=380, height=560, corner_radius=20,
            fg_color="#141414", border_width=1, border_color="#2a2a2a"
        )
        self.card.pack(expand=True, pady=20)
        self.card.pack_propagate(False)

        # Logo
        logo_path = "./assets/santana_mango_logo.png"
        if os.path.exists(logo_path):
            try:
                logo_image = Image.open(logo_path)
                logo_image = logo_image.resize((120, 120), Image.Resampling.LANCZOS)
                logo_ctk = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(250, 120))
                logo_label = ctk.CTkLabel(self.card, image=logo_ctk, text="")
                logo_label.pack(pady=(30, 5))
            except Exception as e:
                print(f"No se pudo cargar el logo: {e}")
                ctk.CTkLabel(self.card, text="🥭 SANTANA MANGO", font=("Arial", 24, "bold"), text_color="#2e8b57").pack(pady=(40, 5))
        else:
            ctk.CTkLabel(self.card, text="🥭 SANTANA MANGO", font=("Arial", 24, "bold"), text_color="#2e8b57").pack(pady=(40, 5))

        # Campo usuario
        self.user_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.user_frame.pack(fill="x", padx=40, pady=(10, 15))
        ctk.CTkLabel(self.user_frame, text="👤", font=("Arial", 16), width=30).pack(side="left")
        self.user_combo = ctk.CTkComboBox(
            self.user_frame, values=[], height=45, font=("Arial", 14),
            state="readonly", corner_radius=8, fg_color="#1e1e1e", border_color="#3a3a3a"
        )
        self.user_combo.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.user_combo.bind("<Return>", lambda e: self.password_entry.focus())

        # Campo contraseña
        self.pass_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.pass_frame.pack(fill="x", padx=40, pady=(0, 10))
        ctk.CTkLabel(self.pass_frame, text="🔒", font=("Arial", 16), width=30).pack(side="left")
        self.pass_container = ctk.CTkFrame(self.pass_frame, fg_color="#1e1e1e", corner_radius=8)
        self.pass_container.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.password_entry = ctk.CTkEntry(
            self.pass_container, placeholder_text=self._t("Contraseña"), height=45, font=("Arial", 14),
            show="•", fg_color="transparent", border_width=0
        )
        self.password_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.password_entry.bind("<Return>", lambda e: self.iniciar_login())
        self.toggle_label = ctk.CTkLabel(
            self.pass_container, text="👁️", width=30, font=("Segoe UI", 16),
            cursor="hand2", text_color="#aaaaaa"
        )
        self.toggle_label.pack(side="right", padx=(0, 10))
        self.toggle_label.bind("<Button-1>", lambda e: self.toggle_password_visibility())
        self.toggle_label.bind("<Enter>", lambda e: self.toggle_label.configure(text_color="#2e8b57"))
        self.toggle_label.bind("<Leave>", lambda e: self.toggle_label.configure(text_color="#aaaaaa"))

        # Barra de fortaleza
        self.strength_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.strength_frame.pack(fill="x", padx=40, pady=(0, 5))
        self.strength_label = ctk.CTkLabel(self.strength_frame, text="", font=("Arial", 10))
        self.strength_label.pack(anchor="w")
        self.strength_bar = ctk.CTkProgressBar(self.strength_frame, width=300, height=8, corner_radius=4)
        self.strength_bar.pack(pady=(2, 0))
        self.strength_bar.set(0)
        self.password_entry.bind("<KeyRelease>", self.actualizar_fortaleza)

        self.forgot_btn = ctk.CTkButton(
            self.card, text=self._t("¿Olvidaste tu contraseña?"), command=self.recuperar_password,
            fg_color="transparent", text_color="#888888", hover_color="#2a2a2a", font=("Arial", 11)
        )
        self.forgot_btn.pack(pady=(5, 0))

        self.register_btn = ctk.CTkButton(
            self.card, text=self._t("Registrarse"), command=self.abrir_registro,
            fg_color="transparent", text_color="#888888", hover_color="#2a2a2a", font=("Arial", 11)
        )
        self.register_btn.pack(pady=(5, 0))

        self.captcha_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.captcha_frame.pack(fill="x", padx=40, pady=(10, 5))
        self.captcha_frame.pack_forget()
        self.fa_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.fa_frame.pack(fill="x", padx=40, pady=(10, 5))
        self.fa_frame.pack_forget()

        # Botón login
        self.login_button = ctk.CTkButton(
            self.card, text=self._t("INICIAR SESIÓN"), command=self.iniciar_login,
            height=50, font=("Arial", 14, "bold"), fg_color="#2e8b57",
            hover_color="#236b43", corner_radius=10
        )
        self.login_button.pack(fill="x", padx=40, pady=(15, 10))

        toolbar = ctk.CTkFrame(self.card, fg_color="transparent")
        toolbar.pack(fill="x", padx=40, pady=(5, 10))

        self.lang_btn = ctk.CTkButton(
            toolbar, text=self._t("Idioma: Español"), command=self.toggle_language,
            width=120, height=30, fg_color="transparent", text_color="#888888"
        )
        self.lang_btn.pack(side="left", padx=5)

        self.config_link = ctk.CTkButton(
            toolbar, text=self._t("Configuración de red"), command=self.mostrar_configuracion_red,
            fg_color="transparent", text_color="#888888", hover_color="#2a2a2a",
            font=("Arial", 11), width=140
        )

        self.status_label = ctk.CTkLabel(self.card, text="", font=("Arial", 11), text_color="#ff5555")
        self.status_label.pack(pady=(0, 15))

        self.spinner = ctk.CTkProgressBar(self.card, width=200, height=10, corner_radius=5)
        self.spinner.pack(pady=(0, 10))
        self.spinner.set(0)
        self.spinner.pack_forget()

        self.actualizar_textos()

    def actualizar_textos(self):
        self.password_entry.configure(placeholder_text=self._t("Contraseña"))
        self.login_button.configure(text=self._t("INICIAR SESIÓN"))
        self.forgot_btn.configure(text=self._t("¿Olvidaste tu contraseña?"))
        self.register_btn.configure(text=self._t("Registrarse"))
        self.config_link.configure(text=self._t("Configuración de red"))
        self.lang_btn.configure(text=self._t("Idioma: Español") if self.idioma_actual == "es" else self._t("Idioma: Inglés"))

    # ==================== MÉTODOS ====================
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def fade_in(self):
        if self.alpha < 1:
            self.alpha += 0.05
            self.attributes("-alpha", self.alpha)
            self.after(20, self.fade_in)

    def toggle_password_visibility(self):
        if self.password_visible:
            self.password_entry.configure(show="•")
            self.toggle_label.configure(text="👁️")
            self.password_visible = False
        else:
            self.password_entry.configure(show="")
            self.toggle_label.configure(text="🔒")
            self.password_visible = True

    def actualizar_fortaleza(self, event=None):
        pwd = self.password_entry.get()
        fuerza = 0
        if len(pwd) >= 6: fuerza += 1
        if any(c.isdigit() for c in pwd): fuerza += 1
        if any(c.isupper() for c in pwd): fuerza += 1
        if any(c in "!@#$%^&*" for c in pwd): fuerza += 1
        if len(pwd) >= 10: fuerza += 1
        niveles = ["Muy débil", "Débil", "Media", "Fuerte", "Muy fuerte"]
        colores = ["red", "orange", "gold", "yellowgreen", "green"]
        valor = fuerza / 5
        self.strength_bar.set(valor)
        self.strength_label.configure(text=f"{self._t('Fortaleza: ')}{self._t(niveles[fuerza])}")
        self.strength_bar.configure(progress_color=colores[fuerza] if fuerza < len(colores) else "green")

    def generar_captcha(self):
        a = random.randint(10, 99)
        b = random.randint(10, 99)
        self.captcha_valor = a + b
        self.captcha_label.configure(text=f"{a} + {b} = ?")
        self.captcha_entry.delete(0, 'end')

    def enviar_codigo_2fa(self, email):
        codigo = generar_codigo_2fa()
        guardar_codigo_2fa(codigo)
        enviar_correo(email, "Código de verificación Santana Mango", f"Su código de acceso es: {codigo}")
        self.correo_2fa = email
        self.codigo_2fa_enviado = True
        self.mostrar_notificacion(self._t("Código enviado a su correo"))

    def verificar_codigo_2fa(self):
        codigo = self.fa_entry.get().strip()
        if verificar_codigo_2fa(codigo):
            self.fa_frame.pack_forget()
            self.realizar_login()
        else:
            self.status_label.configure(text="Código incorrecto")

    def recuperar_password(self):
        if verificar_admin_password():
            dialog = ctk.CTkToplevel(self)
            dialog.title(self._t("Recuperación de contraseña"))
            dialog.geometry("350x200")
            dialog.grab_set()
            ctk.CTkLabel(dialog, text=self._t("Ingrese su email")).pack(pady=10)
            email_entry = ctk.CTkEntry(dialog, width=250)
            email_entry.pack(pady=10)
            def enviar():
                email = email_entry.get().strip()
                if email:
                    enviar_correo(email, "Recuperación de contraseña Santana Mango",
                                  "Haga clic en el enlace para restablecer su contraseña: [simulado]")
                    messagebox.showinfo(self._t("Recuperación"),
                                        self._t("Se ha enviado un enlace de recuperación a su correo"))
                    dialog.destroy()
            ctk.CTkButton(dialog, text=self._t("Enviar"), command=enviar).pack(pady=10)
        else:
            messagebox.showerror("Acceso denegado", "Solo el administrador puede recuperar contraseñas.")

    def abrir_registro(self):
        if verificar_admin_password():
            RegistroWindow(self)
        else:
            messagebox.showerror("Acceso denegado", "Solo el administrador puede registrar nuevos usuarios.")

    def mostrar_configuracion_red(self, primer_inicio=False):
        ventana = ctk.CTkToplevel(self)
        ventana.title(self._t("Configuración de conexión"))
        ventana.geometry("450x450")
        ventana.resizable(False, False)
        ventana.transient(self)
        ventana.grab_set()
        ventana.configure(fg_color="#141414")

        ctk.CTkLabel(ventana, text="Configuración del servidor PostgreSQL", font=("Arial", 16, "bold")).pack(pady=(20, 15))

        campos = ["IP del servidor", "Puerto (5432)", "Base de datos", "Usuario", "Contraseña"]
        entradas = {}
        for campo in campos:
            frame = ctk.CTkFrame(ventana, fg_color="transparent")
            frame.pack(pady=8, padx=30, fill="x")
            ctk.CTkLabel(frame, text=campo, width=120, anchor="e").pack(side="left", padx=5)
            entrada = ctk.CTkEntry(frame, width=200, fg_color="#1e1e1e", border_color="#3a3a3a")
            entrada.pack(side="right", expand=True, fill="x", padx=5)
            entradas[campo] = entrada

        config_actual = cargar_config()
        if config_actual:
            entradas["IP del servidor"].insert(0, config_actual.get("db_host", ""))
            entradas["Puerto (5432)"].insert(0, config_actual.get("db_port", "5432"))
            entradas["Base de datos"].insert(0, config_actual.get("db_name", "santana_mango"))
            entradas["Usuario"].insert(0, config_actual.get("db_user", "postgres"))
            entradas["Contraseña"].insert(0, config_actual.get("db_password", ""))
        else:
            entradas["Puerto (5432)"].insert(0, "5432")
            entradas["Base de datos"].insert(0, "santana_mango")
            entradas["Usuario"].insert(0, "postgres")

        def probar_conexion():
            from database import ejecutar_consulta
            try:
                guardar_config(
                    db_host=entradas["IP del servidor"].get(),
                    db_port=entradas["Puerto (5432)"].get(),
                    db_name=entradas["Base de datos"].get(),
                    db_user=entradas["Usuario"].get(),
                    db_password=entradas["Contraseña"].get()
                )
                resultado = ejecutar_consulta("SELECT 1", fetchone=True)
                if resultado:
                    messagebox.showinfo("Conexión", "Conexión exitosa a la base de datos")
                else:
                    messagebox.showerror("Conexión", "No se pudo conectar")
            except Exception as e:
                messagebox.showerror("Conexión", f"Error: {str(e)}")

        btn_frame = ctk.CTkFrame(ventana, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="Probar conexión", command=probar_conexion, width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Guardar y reiniciar", command=lambda: self._guardar_red(entradas, ventana), fg_color="#2e8b57").pack(side="left", padx=5)

    def _guardar_red(self, entradas, ventana):
        guardar_config(
            db_host=entradas["IP del servidor"].get(),
            db_port=entradas["Puerto (5432)"].get(),
            db_name=entradas["Base de datos"].get(),
            db_user=entradas["Usuario"].get(),
            db_password=entradas["Contraseña"].get()
        )
        try:
            from database import ejecutar_consulta
            ejecutar_consulta("SELECT 1", fetchone=True)
            self.mostrar_boton_red(False)
            messagebox.showinfo("Configuración", "Configuración guardada y conexión exitosa. Reinicie la aplicación.")
        except Exception as e:
            self.mostrar_boton_red(True)
            messagebox.showerror("Configuración", f"Configuración guardada pero no se pudo conectar: {e}\nRevise los datos.")
            ventana.destroy()
            return
        ventana.destroy()
        self.destroy()
        subprocess.Popen([sys.executable, __file__])
        sys.exit(0)

    def toggle_language(self):
        self.idioma_actual = "en" if self.idioma_actual == "es" else "es"
        self.actualizar_textos()
        self.lang_btn.configure(text=self._t("Idioma: Español") if self.idioma_actual == "es" else self._t("Idioma: Inglés"))

    def mostrar_notificacion(self, mensaje):
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.geometry(f"300x50+{self.winfo_x()+100}+{self.winfo_y()+self.winfo_height()-100}")
        toast.attributes("-topmost", True)
        ctk.CTkLabel(toast, text=mensaje, fg_color="#2e8b57", text_color="white", corner_radius=10).pack(fill="both", expand=True)
        toast.after(2000, toast.destroy)

    def mostrar_carga(self, mostrar):
        if mostrar:
            self.spinner.pack(pady=(0, 10))
            self.spinner.start()
            self.login_button.configure(state="disabled")
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.login_button.configure(state="normal")

    def iniciar_login(self):
        try:
            from database import ejecutar_consulta
            ejecutar_consulta("SELECT 1", fetchone=True)
        except Exception as e:
            self.status_label.configure(text="⚠️ Error de conexión a la base de datos. Configure la red.")
            self.mostrar_boton_red(True)
            return

        # Mostrar captcha después de 2 fallos (solo visual, sin bloqueo)
        if self.intentos_fallidos >= 2 and not hasattr(self, 'captcha_frame_visible'):
            self._mostrar_captcha()
            return

        usuario = self.user_combo.get().strip()
        password = self.password_entry.get()
        if not usuario or not password:
            self.mostrar_notificacion(self._t("Complete todos los campos"))
            return

        # Validar captcha si está activo
        if hasattr(self, 'captcha_frame_visible') and self.captcha_frame_visible:
            try:
                resultado_usuario = int(self.captcha_entry.get())
                if resultado_usuario != self.captcha_valor:
                    self.status_label.configure(text="Captcha incorrecto")
                    self.generar_captcha()
                    return
            except:
                self.status_label.configure(text="Captcha inválido")
                self.generar_captcha()
                return
            self.captcha_frame.pack_forget()
            delattr(self, 'captcha_frame_visible')

        self.mostrar_carga(True)
        threading.Thread(target=self.validar_login, args=(usuario, password), daemon=True).start()

    def validar_login(self, usuario, password):
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        try:
            from database import ejecutar_consulta
            try:
                resultado = ejecutar_consulta(
                    "SELECT id, rol, email FROM usuarios WHERE nombre_usuario=%s AND contrasena_hash=%s AND activo=true",
                    (usuario, hash_pass), fetchone=True
                )
                tiene_email = True
            except Exception as e:
                if "email" in str(e):
                    resultado = ejecutar_consulta(
                        "SELECT id, rol FROM usuarios WHERE nombre_usuario=%s AND contrasena_hash=%s AND activo=true",
                        (usuario, hash_pass), fetchone=True
                    )
                    tiene_email = False
                else:
                    raise e
            self.after(0, lambda: self.procesar_resultado(usuario, password, resultado, tiene_email))
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.mostrar_error_login(error_msg))

    def procesar_resultado(self, usuario, password, resultado, tiene_email=True):
        self.mostrar_carga(False)
        if resultado:
            usuario_id = resultado[0]
            rol = resultado[1]
            email = resultado[2] if tiene_email and len(resultado) > 2 else None
            if email and not self.codigo_2fa_enviado and SMTP_USER != "":
                self.enviar_codigo_2fa(email)
                self._mostrar_2fa()
                self.status_label.configure(text="Ingrese el código enviado a su correo")
                self._credenciales_temp = (usuario_id, usuario, rol, password)
                return
            elif self.codigo_2fa_enviado:
                return
            self.realizar_login(usuario_id, usuario, rol, password)
        else:
            # Solo incrementar contador de fallos para activar captcha (sin bloqueo)
            self.intentos_fallidos += 1
            self.status_label.configure(text=self._t("Usuario o contraseña incorrectos"))
            self.mostrar_notificacion(self._t("Usuario o contraseña incorrectos"))

    def _mostrar_captcha(self):
        if not hasattr(self, 'captcha_label'):
            self.captcha_label = ctk.CTkLabel(self.captcha_frame, text="")
            self.captcha_label.pack(anchor="w")
            self.captcha_entry = ctk.CTkEntry(self.captcha_frame, placeholder_text=self._t("Resultado"), width=150)
            self.captcha_entry.pack(pady=5)
            self.generar_captcha()
        self.captcha_frame.pack(fill="x", padx=40, pady=(10, 5))
        self.captcha_frame_visible = True

    def _mostrar_2fa(self):
        if not hasattr(self, 'fa_label'):
            self.fa_label = ctk.CTkLabel(self.fa_frame, text=self._t("Código 2FA"))
            self.fa_label.pack(anchor="w")
            self.fa_entry = ctk.CTkEntry(self.fa_frame, placeholder_text=self._t("Código 2FA"), width=150)
            self.fa_entry.pack(pady=5)
            self.fa_verify_btn = ctk.CTkButton(self.fa_frame, text=self._t("Verificar"), command=self.verificar_codigo_2fa)
            self.fa_verify_btn.pack()
        self.fa_frame.pack(fill="x", padx=40, pady=(10, 5))

    def realizar_login(self, usuario_id=None, usuario=None, rol=None, password=None):
        if hasattr(self, '_credenciales_temp') and usuario_id is None:
            usuario_id, usuario, rol, password = self._credenciales_temp
            delattr(self, '_credenciales_temp')
        try:
            token = generar_token()
            guardar_sesion_segura(usuario_id, usuario, rol, token)
        except Exception as e:
            print(f"Error guardando sesión segura: {e}")
        if self.remember_var.get():
            guardar_recordar(usuario, True)
        try:
            from database import ejecutar_consulta
            ejecutar_consulta(
                "INSERT INTO logs_sistema (usuario, accion, modulo, ip) VALUES (%s, %s, %s, %s)",
                (usuario, "Inicio de sesión exitoso", "login", "127.0.0.1")
            )
        except:
            pass
        self.destroy()
        abrir_menu_principal()

    def mostrar_error_login(self, error_msg):
        self.mostrar_carga(False)
        if "No hay configuración de red" in error_msg:
            self.status_label.configure(text="⚠️ No hay configuración de red. Configúrela.")
            self.mostrar_boton_red(True)
            self.mostrar_configuracion_red(primer_inicio=False)
        elif "no existe la relación" in error_msg or "does not exist" in error_msg:
            self.status_label.configure(text="⚠️ Base de datos no inicializada. Ejecute el script SQL.")
            self.mostrar_boton_red(True)
            self.mostrar_configuracion_red(primer_inicio=False)
        elif "could not connect" in error_msg.lower() or "connection refused" in error_msg.lower():
            self.status_label.configure(text="⚠️ Error de conexión a la base de datos. Verifique la red.")
            self.mostrar_boton_red(True)
        else:
            self.status_label.configure(text=f"❌ Error: {error_msg[:80]}...")
            print(f"Error detallado: {error_msg}")

if __name__ == "__main__":
    app = LoginWindow()
    app.mainloop()