# menu_principal.py - VERSIÓN CORREGIDA CON REGRESO FUNCIONAL, TOOLTIPS Y F11
import customtkinter as ctk
from datetime import datetime
from auth import cargar_sesion, tiene_permiso
from utils.theme_manager import cargar_tema, guardar_tema
from utils.tooltip import crear_tooltip
from database import ejecutar_consulta
import importlib

tema_guardado = cargar_tema()
ctk.set_appearance_mode(tema_guardado)
ctk.set_default_color_theme("green")

class MenuPrincipal(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Santana Mango Manager")
        self.geometry("1300x750")
        self.minsize(1100, 650)
        self.after(0, self.center_window)

        # Vincular tecla F11 para pantalla completa
        self.bind("<F11>", self.toggle_fullscreen)

        self.usuario, self.rol, self.permisos = cargar_sesion()
        self.current_module_frame = None

        # Layout principal
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=1)   # contenido
        self.grid_columnconfigure(0, weight=1)

        # HEADER
        self.header = ctk.CTkFrame(self, height=70, corner_radius=10, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=20, pady=(10, 5))
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=0)
        self.header.grid_columnconfigure(2, weight=0)
        self.header.grid_columnconfigure(3, weight=0)

        lbl_titulo = ctk.CTkLabel(self.header, text="🥭 SANTANA MANGO", font=("Arial", 24, "bold"), text_color="#2e8b57")
        lbl_titulo.grid(row=0, column=0, sticky="w")
        crear_tooltip(lbl_titulo, "Sistema de Gestión Santana Mango")

        self.clock_label = ctk.CTkLabel(self.header, text="", font=("Arial", 14))
        self.clock_label.grid(row=0, column=1, padx=20)
        crear_tooltip(self.clock_label, "Fecha y hora actual")
        self.actualizar_reloj()

        self.user_button = ctk.CTkButton(self.header, text=f"👤 {self.usuario}  |  {self.rol}", 
                                         command=self.mostrar_menu_usuario,
                                         fg_color="transparent", hover_color=("#3a3a3a", "#e0e0e0"),
                                         width=150, height=40)
        self.user_button.grid(row=0, column=2, padx=10, sticky="e")
        crear_tooltip(self.user_button, "Opciones de usuario (cerrar sesión)")

        self.tema_actual = ctk.get_appearance_mode().lower()
        self.btn_tema = ctk.CTkButton(
            self.header,
            text="🌙" if self.tema_actual == "dark" else "☀️",
            width=40, height=40, corner_radius=20, font=("Segoe UI", 18),
            command=self.toggle_tema,
            fg_color=("gray85", "gray25"), hover_color=("#c0c0c0", "#4a4a4a")
        )
        self.btn_tema.grid(row=0, column=3, padx=(0, 20))
        crear_tooltip(self.btn_tema, "Cambiar tema (claro/oscuro)")

        # CONTENEDOR PRINCIPAL (donde se cargan los módulos)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Mostrar el dashboard inicial
        self.mostrar_dashboard()

    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def actualizar_reloj(self):
        ahora = datetime.now()
        fecha = ahora.strftime("%d/%m/%Y")
        hora = ahora.strftime("%I:%M:%S %p")
        self.clock_label.configure(text=f"{fecha}  |  {hora}")
        self.after(1000, self.actualizar_reloj)

    def limpiar_contenido(self):
        """Destruye el módulo actual y limpia el content_frame"""
        if self.current_module_frame:
            self.current_module_frame.destroy()
            self.current_module_frame = None
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def cargar_modulo(self, modulo_nombre, clase_nombre):
        """Carga un módulo y le pasa el callback de regreso"""
        self.limpiar_contenido()
        try:
            modulo = importlib.import_module(f"modulos.{modulo_nombre}")
            clase = getattr(modulo, clase_nombre)
            self.current_module_frame = clase(self.content_frame, self.permisos, on_regresar=self.mostrar_dashboard)
            self.current_module_frame.pack(fill="both", expand=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_frame = ctk.CTkFrame(self.content_frame)
            error_frame.pack(fill="both", expand=True)
            lbl_error = ctk.CTkLabel(error_frame, text=f"Error al cargar módulo: {e}", 
                                     font=("Arial", 16), text_color="red")
            lbl_error.pack(expand=True)
            crear_tooltip(lbl_error, str(e))
            btn_regresar = ctk.CTkButton(error_frame, text="◀ Regresar", command=self.mostrar_dashboard, fg_color="#8b0000")
            btn_regresar.pack(pady=20)
            crear_tooltip(btn_regresar, "Volver al menú principal")

    def mostrar_dashboard(self):
        """Muestra el dashboard con las tarjetas de módulos"""
        self.limpiar_contenido()

        dashboard_scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        dashboard_scroll.pack(fill="both", expand=True)

        lbl_dashboard = ctk.CTkLabel(dashboard_scroll, text="Dashboard", font=("Arial", 28, "bold"))
        lbl_dashboard.pack(anchor="w", pady=(10, 20))
        crear_tooltip(lbl_dashboard, "Panel principal del sistema")

        grid_frame = ctk.CTkFrame(dashboard_scroll, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)

        modulos = [
            ("📋", "Catálogos", "catalogos", "VentanaCatalogos", "catalogos"),
            ("🚚", "Recepción", "recepcion", "VentanaRecepcion", "recepcion"),
            # ("⚖️", "Taras Jabas", "gestion_taras", "VentanaGestionTaras", "catalogos"),
             ("🧼", "Pesaje Lavado", "pesaje_lavado", "VentanaPesajeLavado", "pesaje_lavado"),
             ("📉", "Pesaje Rezaga", "pesaje_rezaga", "VentanaPesajeRezaga", "pesaje_rezaga"),
            # ("🚛", "Transportes", "transportes", "VentanaTransportes", "transportes"),
            # ("💧", "Hidrotérmico", "hidrotermico", "VentanaHidrotermico", "hidrotermico"),
            # ("🏷️", "Etiquetas", "etiquetas", "VentanaEtiquetas", "etiquetas"),
            # ("📦", "Embarques", "embarques", "VentanaEmbarques", "embarques"),
            # ("⚠️", "Rezaga", "rezaga", "VentanaRezaga", "rezaga"),
            # ("🐞", "Calidad", "calidad", "VentanaCalidad", "calidad"),
            ("📊", "Reportes", "reportes", "VentanaReportes", "reportes"),
            ("⚙️", "Configuración", "configuracion", "VentanaConfiguracion", "configuracion"),
            ("🚪", "Salir", None, self.salir, None)
        ]

        fila, col = 0, 0
        columnas = 4
        for icono, texto, modulo, clase, permiso in modulos:
            if permiso is None or tiene_permiso(self.permisos, permiso, "leer"):
                frame = ctk.CTkFrame(grid_frame, corner_radius=15, border_width=1,
                                     border_color="#2e8b57", fg_color=("#f0f0f0", "#2a2a2a"),
                                     width=200, height=150)
                frame.grid(row=fila, column=col, padx=15, pady=15, sticky="nsew")
                frame.grid_propagate(False)

                icono_label = ctk.CTkLabel(frame, text=icono, font=("Segoe UI", 48))
                icono_label.pack(pady=(20, 5))
                texto_label = ctk.CTkLabel(frame, text=texto, font=("Arial", 16, "bold"))
                texto_label.pack()

                if modulo is None and clase == self.salir:
                    comando = self.salir
                elif modulo is not None:
                    comando = lambda m=modulo, c=clase: self.cargar_modulo(m, c)
                else:
                    comando = None

                if comando:
                    frame.bind("<Button-1>", lambda e, cmd=comando: cmd())
                    icono_label.bind("<Button-1>", lambda e, cmd=comando: cmd())
                    texto_label.bind("<Button-1>", lambda e, cmd=comando: cmd())
                    crear_tooltip(frame, f"Abrir {texto}")

                col += 1
                if col >= columnas:
                    col = 0
                    fila += 1

        for i in range(columnas):
            grid_frame.grid_columnconfigure(i, weight=1)

        # Estadísticas
        stats_frame = ctk.CTkFrame(dashboard_scroll, fg_color="transparent")
        stats_frame.pack(pady=30, fill="x")
        try:
            total_rec = ejecutar_consulta("SELECT COUNT(*) FROM recepcion_carga", fetchone=True)[0]
            total_emb = ejecutar_consulta("SELECT COUNT(*) FROM embarques", fetchone=True)[0]
            total_pes = (ejecutar_consulta("SELECT COUNT(*) FROM pesaje_lavado", fetchone=True)[0] +
                         ejecutar_consulta("SELECT COUNT(*) FROM pesaje_rezaga", fetchone=True)[0])
        except:
            total_rec = total_emb = total_pes = 0

        stats = [("📦 Recepciones", total_rec), ("🚢 Embarques", total_emb), ("⚖️ Pesajes", total_pes)]
        for i, (tit, val) in enumerate(stats):
            frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
            frame.grid(row=0, column=i, padx=20, pady=10, sticky="nsew")
            stats_frame.grid_columnconfigure(i, weight=1)
            lbl_tit = ctk.CTkLabel(frame, text=tit, font=("Arial", 14, "bold"))
            lbl_tit.pack()
            crear_tooltip(lbl_tit, f"Total de {tit.lower()} registrados")
            lbl_val = ctk.CTkLabel(frame, text=str(val), font=("Arial", 24, "bold"), text_color="#2e8b57")
            lbl_val.pack()
            crear_tooltip(lbl_val, f"Cantidad actual: {val}")

        hora = datetime.now().hour
        saludo = "Buenos días" if hora < 12 else "Buenas tardes" if hora < 19 else "Buenas noches"
        lbl_saludo = ctk.CTkLabel(dashboard_scroll, text=f"{saludo}, {self.usuario}.", font=("Arial", 16))
        lbl_saludo.pack(pady=20)
        crear_tooltip(lbl_saludo, f"Sesión iniciada como {self.usuario} ({self.rol})")

    def mostrar_menu_usuario(self):
        menu = ctk.CTkToplevel(self)
        menu.title("Opciones de usuario")
        menu.geometry("200x120")
        menu.resizable(False, False)
        menu.grab_set()

        btn_cerrar = ctk.CTkButton(menu, text="Cerrar sesión", command=self.cerrar_sesion, width=150)
        btn_cerrar.pack(pady=10)
        crear_tooltip(btn_cerrar, "Cerrar sesión actual y volver al login")

        btn_cancelar = ctk.CTkButton(menu, text="Cancelar", command=menu.destroy, width=150)
        btn_cancelar.pack(pady=5)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar este menú")

    def cerrar_sesion(self):
        from auth import cerrar_sesion
        cerrar_sesion()
        self.destroy()
        from login import LoginWindow
        login = LoginWindow()
        login.mainloop()

    def salir(self):
        self.quit()

    def toggle_tema(self):
        if self.tema_actual == "dark":
            ctk.set_appearance_mode("light")
            self.tema_actual = "light"
            self.btn_tema.configure(text="☀️")
            guardar_tema("light")
            crear_tooltip(self.btn_tema, "Cambiar a tema oscuro")
        else:
            ctk.set_appearance_mode("dark")
            self.tema_actual = "dark"
            self.btn_tema.configure(text="🌙")
            guardar_tema("dark")
            crear_tooltip(self.btn_tema, "Cambiar a tema claro")

    # ========== PANTALLA COMPLETA CON F11 ==========
    def toggle_fullscreen(self, event=None):
        """Alterna entre pantalla completa y modo ventana."""
        current_state = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not current_state)

def abrir_menu_principal():
    app = MenuPrincipal()
    app.mainloop()