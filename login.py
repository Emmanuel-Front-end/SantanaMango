# login.py - VERSIÓN ACTUALIZADA CON SEGURIDAD MEJORADA
import customtkinter as ctk
from tkinter import messagebox
import hashlib
import os
import sys
import subprocess
from config import cargar_config, guardar_config

# Importación del menú principal
try:
    from menu_principal import abrir_menu_principal
except ImportError:
    def abrir_menu_principal():
        messagebox.showinfo("Info", "Menú principal aún no implementado")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Santana Mango Manager - Login")
        self.geometry("500x600")
        self.resizable(False, False)
        self.configure(fg_color="#0a0a0a")
        self.after(0, self.center_window)

        # Tarjeta principal
        self.card = ctk.CTkFrame(
            self,
            width=380,
            height=480,
            corner_radius=20,
            fg_color="#141414",
            border_width=1,
            border_color="#2a2a2a"
        )
        self.card.pack(expand=True, pady=20)
        self.card.pack_propagate(False)

        # Logo y título
        ctk.CTkLabel(
            self.card,
            text="🥭 SANTANA MANGO",
            font=("Arial", 24, "bold"),
            text_color="#2e8b57"
        ).pack(pady=(40, 5))
        ctk.CTkLabel(
            self.card,
            text="Sistema de Gestión",
            font=("Arial", 12),
            text_color="#888888"
        ).pack(pady=(0, 30))

        # Campo usuario
        self.user_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.user_frame.pack(fill="x", padx=40, pady=(10, 15))
        ctk.CTkLabel(self.user_frame, text="👤", font=("Arial", 16), width=30).pack(side="left")
        self.user_entry = ctk.CTkEntry(
            self.user_frame,
            placeholder_text="Usuario",
            height=45,
            font=("Arial", 14),
            fg_color="#1e1e1e",
            border_color="#3a3a3a"
        )
        self.user_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.user_entry.bind("<Return>", lambda e: self.password_entry.focus())

        # Campo contraseña
        self.pass_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.pass_frame.pack(fill="x", padx=40, pady=(0, 25))
        ctk.CTkLabel(self.pass_frame, text="🔒", font=("Arial", 16), width=30).pack(side="left")
        self.password_entry = ctk.CTkEntry(
            self.pass_frame,
            placeholder_text="Contraseña",
            height=45,
            font=("Arial", 14),
            show="•",
            fg_color="#1e1e1e",
            border_color="#3a3a3a"
        )
        self.password_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.password_entry.bind("<Return>", lambda e: self.validar_login())

        # Botón login
        self.login_button = ctk.CTkButton(
            self.card,
            text="INICIAR SESIÓN",
            command=self.validar_login,
            height=50,
            font=("Arial", 14, "bold"),
            fg_color="#2e8b57",
            hover_color="#236b43",
            corner_radius=10
        )
        self.login_button.pack(fill="x", padx=40, pady=(15, 10))
        self.login_button.bind("<Enter>", lambda e: self.card.configure(border_color="#2e8b57"))
        self.login_button.bind("<Leave>", lambda e: self.card.configure(border_color="#2a2a2a"))

        # Enlace configuración de red
        self.config_link = ctk.CTkButton(
            self.card,
            text="⚙️ Configuración de red",
            command=self.mostrar_configuracion_red,
            fg_color="transparent",
            text_color="#666666",
            hover_color="#2a2a2a",
            font=("Arial", 11),
            width=200
        )
        self.config_link.pack(pady=(10, 20))

        self.status_label = ctk.CTkLabel(self.card, text="", font=("Arial", 11), text_color="#ff5555")
        self.status_label.pack(pady=(0, 15))

        # Si no hay configuración, mostrar ventana de configuración
        if not cargar_config():
            self.mostrar_configuracion_red()

    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def mostrar_configuracion_red(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Configuración de conexión")
        ventana.geometry("450x400")
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

        entradas["Puerto (5432)"].insert(0, "5432")
        entradas["Base de datos"].insert(0, "santana_mango")
        entradas["Usuario"].insert(0, "postgres")

        def guardar():
            guardar_config(
                db_host=entradas["IP del servidor"].get(),
                db_port=entradas["Puerto (5432)"].get(),
                db_name=entradas["Base de datos"].get(),
                db_user=entradas["Usuario"].get(),
                db_password=entradas["Contraseña"].get()
            )
            messagebox.showinfo("Configuración", "Configuración guardada. Reinicie la aplicación.")
            ventana.destroy()
            self.destroy()
            # Reiniciar la aplicación
            subprocess.Popen([sys.executable, __file__])
            sys.exit(0)

        btn = ctk.CTkButton(ventana, text="Guardar y reiniciar", command=guardar, height=40, fg_color="#2e8b57", hover_color="#236b43")
        btn.pack(pady=30)

    def validar_login(self):
        usuario = self.user_entry.get().strip()
        password = self.password_entry.get()
        
        if not usuario or not password:
            self.status_label.configure(text="⚠️ Complete ambos campos")
            return
        
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            from database import ejecutar_consulta
            resultado = ejecutar_consulta(
                "SELECT id, rol FROM usuarios WHERE nombre_usuario=%s AND contrasena_hash=%s AND activo=true",
                (usuario, hash_pass),
                fetchone=True
            )
            
            if resultado:
                usuario_id = resultado[0]
                rol = resultado[1]
                
                # === NUEVO: Guardar sesión segura ===
                try:
                    from auth import guardar_sesion_segura, generar_token
                    token = generar_token()
                    guardar_sesion_segura(usuario_id, usuario, rol, token)
                except Exception as e:
                    print(f"Error guardando sesión segura: {e}")
                
                # Guardar también el archivo simple para compatibilidad
                with open("session_user.txt", "w") as f:
                    f.write(f"{usuario}|{rol}")
                
                # Registrar en log de sistema
                try:
                    ejecutar_consulta(
                        "INSERT INTO logs_sistema (usuario, accion, modulo, ip) VALUES (%s, %s, %s, %s)",
                        (usuario, "Inicio de sesión exitoso", "login", "127.0.0.1")
                    )
                except:
                    pass  # Si no existe la tabla logs, continuar
                
                self.destroy()
                abrir_menu_principal()
            else:
                self.status_label.configure(text="❌ Usuario o contraseña incorrectos")
                
        except Exception as e:
            error_msg = str(e)
            if "No hay configuración de red" in error_msg:
                self.status_label.configure(text="⚠️ No hay configuración de red. Configúrela.")
                self.mostrar_configuracion_red()
            elif "no existe la relación" in error_msg or "does not exist" in error_msg:
                # La tabla usuarios no existe aún
                self.status_label.configure(text="⚠️ Base de datos no inicializada. Configure primero.")
                self.mostrar_configuracion_red()
            else:
                self.status_label.configure(text=f"❌ Error: {error_msg[:50]}...")

if __name__ == "__main__":
    app = LoginWindow()
    app.mainloop()