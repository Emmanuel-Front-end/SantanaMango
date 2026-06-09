# modulos/configuracion.py - Gestión de usuarios y permisos (con contraseñas visibles)
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from database import ejecutar_consulta
from config import cargar_config, guardar_config, eliminar_config
from auth import tiene_permiso, cargar_permisos_usuario, cifrar_contrasena, descifrar_contrasena
import subprocess
import sys
import hashlib
import json
import random
import string
from datetime import datetime
from tkcalendar import DateEntry
from utils.tooltip import crear_tooltip

class VentanaConfiguracion(ctk.CTkFrame):
    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.usuario_seleccionado_id = None

        # Obtener rol del usuario actual (para restringir visualización de contraseñas)
        try:
            from auth import cargar_sesion
            self.rol_actual = cargar_sesion()[1]
        except:
            self.rol_actual = "operador"

        if not tiene_permiso(permisos, "configuracion", "leer"):
            ctk.CTkLabel(self, text="⚠️ No tiene permisos para acceder a Configuración",
                        font=("Arial", 20), text_color="red").pack(expand=True)
            return

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Barra de navegación
        nav_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("#e0e0e0", "#2a2a2a"))
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_columnconfigure(1, weight=1)

        self.btn_regresar = ctk.CTkButton(nav_bar, text="◀ REGRESAR", command=self.regresar_menu,
                                          width=150, height=35, fg_color="#8b0000", font=("Arial", 12, "bold"))
        self.btn_regresar.grid(row=0, column=0, padx=10, pady=5)
        crear_tooltip(self.btn_regresar, "Volver al menú principal")

        ctk.CTkLabel(nav_bar, text="⚙️ CONFIGURACIÓN DEL SISTEMA", font=("Arial", 20, "bold"),
                     text_color="#2e8b57").grid(row=0, column=1)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        ctk.CTkLabel(self.scroll_frame, text="Configuración del Sistema", font=("Arial", 24, "bold")).pack(pady=10)

        self.tabview = ctk.CTkTabview(self.scroll_frame, corner_radius=15)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        self.tab_red = self.tabview.add("🌐 Red y Servidor")
        self.tab_usuarios = self.tabview.add("👥 Usuarios y Permisos")
        self.tab_apariencia = self.tabview.add("🎨 Apariencia")
        self.tab_bascula = self.tabview.add("⚖️ Báscula")
        self.tab_backup = self.tabview.add("💾 Respaldo")
        self.tab_logs = self.tabview.add("📜 Logs")
        self.tab_info = self.tabview.add("ℹ️ Información")

        self._init_red()
        self._init_usuarios()
        self._init_apariencia()
        self._init_bascula()
        self._init_backup()
        self._init_logs()
        self._init_info()

    def regresar_menu(self):
        if self.on_regresar:
            self.on_regresar()
        self.destroy()

    # ---------- RED ----------
    def _init_red(self):
        frame = self.tab_red
        config = cargar_config()
        ctk.CTkLabel(frame, text="Configuración de conexión a PostgreSQL", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        form = ctk.CTkFrame(frame, fg_color="transparent")
        form.pack(pady=10, fill="x")
        campos = ["Host", "Puerto", "Base de datos", "Usuario", "Contraseña"]
        self.entries = {}
        for i, campo in enumerate(campos):
            ctk.CTkLabel(form, text=campo + ":").grid(row=i, column=0, padx=10, pady=5, sticky="e")
            entry = ctk.CTkEntry(form, width=250)
            entry.grid(row=i, column=1, padx=10, pady=5)
            self.entries[campo] = entry
            crear_tooltip(entry, f"Ingrese el {campo.lower()} de la base de datos")
        if config:
            self.entries["Host"].insert(0, config.get("db_host", ""))
            self.entries["Puerto"].insert(0, config.get("db_port", "5432"))
            self.entries["Base de datos"].insert(0, config.get("db_name", "santana_mango"))
            self.entries["Usuario"].insert(0, config.get("db_user", "postgres"))
            self.entries["Contraseña"].insert(0, config.get("db_password", ""))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        btn_probar = ctk.CTkButton(btn_frame, text="Probar conexión", command=self._probar_conexion)
        btn_probar.pack(side="left", padx=5)
        crear_tooltip(btn_probar, "Verificar si la configuración actual permite conectar a la base de datos")
        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar configuración", command=self._guardar_config_red, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=5)
        crear_tooltip(btn_guardar, "Guardar la configuración de red (requiere reinicio)")
        btn_resetear = ctk.CTkButton(btn_frame, text="Resetear configuración", command=self._resetear_config, fg_color="#8b0000")
        btn_resetear.pack(side="left", padx=5)
        crear_tooltip(btn_resetear, "Eliminar la configuración de red guardada")

    def _probar_conexion(self):
        from database import ejecutar_consulta
        try:
            resultado = ejecutar_consulta("SELECT 1", fetchone=True)
            if resultado:
                messagebox.showinfo("Conexión exitosa", "La conexión a la base de datos funciona correctamente.")
        except Exception as e:
            messagebox.showerror("Error de conexión", str(e))

    def _guardar_config_red(self):
        guardar_config(
            db_host=self.entries["Host"].get(),
            db_port=self.entries["Puerto"].get(),
            db_name=self.entries["Base de datos"].get(),
            db_user=self.entries["Usuario"].get(),
            db_password=self.entries["Contraseña"].get()
        )
        messagebox.showinfo("Guardado", "Configuración guardada. Reinicie la aplicación para aplicar cambios.")
        subprocess.Popen([sys.executable, __file__])
        sys.exit(0)

    def _resetear_config(self):
        if messagebox.askyesno("Confirmar", "¿Resetear configuración de red?"):
            eliminar_config()
            messagebox.showinfo("Reset", "Configuración eliminada. Reinicie la aplicación.")
            subprocess.Popen([sys.executable, __file__])
            sys.exit(0)

    # ---------- USUARIOS Y PERMISOS (CONTRASEÑAS VISIBLES) ----------
    def _init_usuarios(self):
        frame = self.tab_usuarios
        ctk.CTkLabel(frame, text="Gestión de Usuarios", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)

        btn_nuevo = ctk.CTkButton(btn_frame, text="➕ Nuevo usuario", command=self._nuevo_usuario, width=120)
        btn_nuevo.pack(side="left", padx=5)
        crear_tooltip(btn_nuevo, "Crear un nuevo usuario")

        btn_editar = ctk.CTkButton(btn_frame, text="✏️ Editar usuario", command=self._editar_usuario, width=120)
        btn_editar.pack(side="left", padx=5)
        crear_tooltip(btn_editar, "Editar el usuario seleccionado")

        btn_eliminar = ctk.CTkButton(btn_frame, text="🗑️ Eliminar usuario", command=self._eliminar_usuario, fg_color="#8b0000", width=120)
        btn_eliminar.pack(side="left", padx=5)
        crear_tooltip(btn_eliminar, "Eliminar el usuario seleccionado")

        # Tabla de usuarios con columna "Contraseña" (solo visible para admin)
        self.tree_usuarios = ttk.Treeview(frame, columns=("ID", "Usuario", "Rol", "Activo", "Contraseña"), show="headings", height=15)
        self.tree_usuarios.heading("ID", text="ID")
        self.tree_usuarios.heading("Usuario", text="Usuario")
        self.tree_usuarios.heading("Rol", text="Rol")
        self.tree_usuarios.heading("Activo", text="Activo")
        self.tree_usuarios.heading("Contraseña", text="Contraseña")
        self.tree_usuarios.column("Contraseña", width=120, anchor="center")
        self.tree_usuarios.pack(fill="both", expand=True, pady=10)
        crear_tooltip(self.tree_usuarios, "Lista de usuarios del sistema. Solo el administrador ve la contraseña real.")
        self.cargar_usuarios()

        ctk.CTkLabel(frame, text="Permisos del usuario seleccionado", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10,5))
        self.tree_permisos = ttk.Treeview(frame, columns=("Módulo", "Leer", "Crear", "Editar", "Eliminar"), show="headings", height=8)
        for col in self.tree_permisos["columns"]:
            self.tree_permisos.heading(col, text=col)
        self.tree_permisos.pack(fill="both", expand=True, pady=5)
        crear_tooltip(self.tree_permisos, "Permisos del usuario seleccionado (✅ = permitido, ❌ = denegado)")
        self.tree_usuarios.bind("<<TreeviewSelect>>", self.on_select_usuario)

    def cargar_usuarios(self):
        for row in self.tree_usuarios.get_children():
            self.tree_usuarios.delete(row)
        usuarios = ejecutar_consulta("SELECT id, nombre_usuario, rol, activo, contrasena_cifrada FROM usuarios", fetchall=True)
        for u in usuarios:
            activo = "Sí" if u[3] else "No"
            # Mostrar la contraseña descifrada solo si el usuario actual es admin
            if self.rol_actual == "admin":
                pass_real = descifrar_contrasena(u[4])
                self.tree_usuarios.insert("", "end", values=(u[0], u[1], u[2], activo, pass_real))
            else:
                # Para no administradores, ocultamos la columna o mostramos puntos
                self.tree_usuarios.insert("", "end", values=(u[0], u[1], u[2], activo, "●●●●"))
        # Si no es admin, ocultar la columna de contraseña (opcional)
        if self.rol_actual != "admin":
            self.tree_usuarios.column("Contraseña", width=0, stretch=False)

    def on_select_usuario(self, event):
        sel = self.tree_usuarios.selection()
        if sel:
            self.usuario_seleccionado_id = self.tree_usuarios.item(sel[0])["values"][0]
            self.cargar_permisos_usuario(self.usuario_seleccionado_id)

    def cargar_permisos_usuario(self, usuario_id):
        for row in self.tree_permisos.get_children():
            self.tree_permisos.delete(row)
        modulos = ejecutar_consulta("SELECT id, nombre_modulo FROM modulos_sistema ORDER BY orden", fetchall=True)
        for m in modulos:
            permiso = ejecutar_consulta("SELECT puede_leer, puede_crear, puede_editar, puede_eliminar FROM permisos_usuario WHERE usuario_id=%s AND modulo_id=%s",
                                        (usuario_id, m[0]), fetchone=True)
            if permiso:
                leer = "✅" if permiso[0] else "❌"
                crear = "✅" if permiso[1] else "❌"
                editar = "✅" if permiso[2] else "❌"
                eliminar = "✅" if permiso[3] else "❌"
            else:
                leer = crear = editar = eliminar = "❌"
            self.tree_permisos.insert("", "end", values=(m[1], leer, crear, editar, eliminar))

    def _nuevo_usuario(self):
        if not tiene_permiso(self.permisos, "configuracion", "crear"):
            messagebox.showerror("Acceso denegado", "No tiene permiso para crear usuarios")
            return
        self._formulario_usuario()

    def _editar_usuario(self):
        if not tiene_permiso(self.permisos, "configuracion", "editar"):
            messagebox.showerror("Acceso denegado", "No tiene permiso para editar usuarios")
            return
        if not self.usuario_seleccionado_id:
            messagebox.showwarning("Selección", "Seleccione un usuario de la lista")
            return
        datos = ejecutar_consulta("SELECT nombre_usuario, rol, activo FROM usuarios WHERE id=%s", (self.usuario_seleccionado_id,), fetchone=True)
        if datos:
            self._formulario_usuario(self.usuario_seleccionado_id, datos[0], datos[1], datos[2])

    def _eliminar_usuario(self):
        if not tiene_permiso(self.permisos, "configuracion", "eliminar"):
            messagebox.showerror("Acceso denegado", "No tiene permiso para eliminar usuarios")
            return
        if not self.usuario_seleccionado_id:
            messagebox.showwarning("Selección", "Seleccione un usuario")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este usuario?"):
            ejecutar_consulta("DELETE FROM permisos_usuario WHERE usuario_id=%s", (self.usuario_seleccionado_id,))
            ejecutar_consulta("DELETE FROM usuarios WHERE id=%s", (self.usuario_seleccionado_id,))
            self.cargar_usuarios()
            self.usuario_seleccionado_id = None
            for row in self.tree_permisos.get_children():
                self.tree_permisos.delete(row)

    # ----- Generador de contraseña aleatoria -----
    def _generar_contraseña_aleatoria(self, longitud=10):
        caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(caracteres) for _ in range(longitud))
        return password

    # -------------------- FORMULARIO DE USUARIO CON PERMISOS --------------------
    def _formulario_usuario(self, id_usuario=None, nombre="", rol="operador", activo=True):
        top = ctk.CTkToplevel(self)
        top.title("Nuevo Usuario" if not id_usuario else "Editar Usuario")
        top.geometry("880x750")
        top.grab_set()

        wizard_frame = ctk.CTkFrame(top, fg_color="transparent")
        wizard_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Paso 1: Datos básicos
        step1_frame = ctk.CTkFrame(wizard_frame, fg_color="transparent")
        step1_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(step1_frame, text="Paso 1 de 3: Datos básicos", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0,20))
        form_frame = ctk.CTkFrame(step1_frame, fg_color="transparent")
        form_frame.pack(pady=10)

        ctk.CTkLabel(form_frame, text="Nombre de usuario:", font=("Arial", 14)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        entry_nombre = ctk.CTkEntry(form_frame, width=300)
        entry_nombre.insert(0, nombre)
        entry_nombre.grid(row=0, column=1, padx=10, pady=10)
        crear_tooltip(entry_nombre, "Nombre único de usuario para iniciar sesión")

        # Campo contraseña
        ctk.CTkLabel(form_frame, text="Contraseña:", font=("Arial", 14)).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        entry_pass = ctk.CTkEntry(form_frame, width=300, show="•")
        entry_pass.grid(row=1, column=1, padx=10, pady=10)
        crear_tooltip(entry_pass, "Contraseña del usuario. Si está editando y deja vacío, se conserva la anterior.")

        # Botón generar
        def generar_aleatoria():
            nueva = self._generar_contraseña_aleatoria()
            entry_pass.delete(0, "end")
            entry_pass.insert(0, nueva)
            messagebox.showinfo("Contraseña generada", f"Se ha generado la contraseña: {nueva}\nGuárdela en un lugar seguro.")
        btn_generar = ctk.CTkButton(form_frame, text="🔑 Generar", command=generar_aleatoria, width=100)
        btn_generar.grid(row=1, column=2, padx=5, pady=10)
        crear_tooltip(btn_generar, "Generar una contraseña aleatoria segura")

        # Checkbox mostrar
        mostrar_pass_var = ctk.BooleanVar(value=False)
        def toggle_mostrar():
            if mostrar_pass_var.get():
                entry_pass.configure(show="")
            else:
                entry_pass.configure(show="•")
        cb_mostrar = ctk.CTkCheckBox(form_frame, text="Mostrar", variable=mostrar_pass_var, command=toggle_mostrar)
        cb_mostrar.grid(row=1, column=3, padx=5, pady=10)

        ctk.CTkLabel(form_frame, text="Confirmar:", font=("Arial", 14)).grid(row=2, column=0, padx=10, pady=10, sticky="e")
        entry_confirm = ctk.CTkEntry(form_frame, width=300, show="•")
        entry_confirm.grid(row=2, column=1, padx=10, pady=10)
        crear_tooltip(entry_confirm, "Vuelva a escribir la contraseña para confirmar")

        mostrar_confirm_var = ctk.BooleanVar(value=False)
        def toggle_mostrar_confirm():
            if mostrar_confirm_var.get():
                entry_confirm.configure(show="")
            else:
                entry_confirm.configure(show="•")
        cb_mostrar_confirm = ctk.CTkCheckBox(form_frame, text="Mostrar", variable=mostrar_confirm_var, command=toggle_mostrar_confirm)
        cb_mostrar_confirm.grid(row=2, column=3, padx=5, pady=10)

        self.pass_strength_label = ctk.CTkLabel(form_frame, text="", font=("Arial", 10))
        self.pass_strength_label.grid(row=1, column=4, padx=10, pady=10, sticky="w")
        self.pass_match_label = ctk.CTkLabel(form_frame, text="", font=("Arial", 10))
        self.pass_match_label.grid(row=2, column=4, padx=10, pady=10, sticky="w")

        def check_password_strength(event=None):
            pwd = entry_pass.get()
            if not pwd:
                self.pass_strength_label.configure(text="", text_color="gray")
                return
            strength = 0
            if len(pwd) >= 6: strength += 1
            if any(c.isdigit() for c in pwd): strength += 1
            if any(c.isupper() for c in pwd): strength += 1
            if any(c in "!@#$%^&*" for c in pwd): strength += 1
            if strength <= 1:
                self.pass_strength_label.configure(text="⚡ Débil", text_color="red")
            elif strength == 2:
                self.pass_strength_label.configure(text="⚡ Media", text_color="orange")
            else:
                self.pass_strength_label.configure(text="⚡ Fuerte", text_color="green")
            check_password_match()

        def check_password_match(event=None):
            pwd = entry_pass.get()
            conf = entry_confirm.get()
            if not pwd or not conf:
                self.pass_match_label.configure(text="")
                return
            if pwd == conf:
                self.pass_match_label.configure(text="✅ Coinciden", text_color="green")
            else:
                self.pass_match_label.configure(text="❌ No coinciden", text_color="red")

        entry_pass.bind("<KeyRelease>", check_password_strength)
        entry_confirm.bind("<KeyRelease>", check_password_match)

        ctk.CTkLabel(form_frame, text="Rol:", font=("Arial", 14)).grid(row=3, column=0, padx=10, pady=10, sticky="e")
        combo_rol = ttk.Combobox(form_frame, values=["admin", "operador", "supervisor"], width=30)
        combo_rol.set(rol)
        combo_rol.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(combo_rol, "Rol del usuario: admin (todos los permisos), supervisor (permisos ampliados), operador (permisos básicos)")

        activo_var = ctk.BooleanVar(value=activo)
        cb_activo = ctk.CTkCheckBox(form_frame, text="Usuario activo", variable=activo_var)
        cb_activo.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Si está activo, el usuario podrá iniciar sesión")

        # Paso 2: Selección de permisos (igual que antes)
        step2_frame = ctk.CTkFrame(wizard_frame, fg_color="transparent")
        step3_frame = ctk.CTkFrame(wizard_frame, fg_color="transparent")

        modulos_list = ejecutar_consulta("SELECT id, nombre_modulo FROM modulos_sistema ORDER BY orden", fetchall=True)
        permisos_vars = {}
        rows = {}
        search_entry = None

        def build_step2():
            nonlocal search_entry
            for w in step2_frame.winfo_children():
                w.destroy()

            top_perm = ctk.CTkFrame(step2_frame, fg_color="transparent")
            top_perm.pack(fill="x", pady=5)
            ctk.CTkLabel(top_perm, text="🔍 Buscar módulo:").pack(side="left", padx=5)
            search_entry = ctk.CTkEntry(top_perm, width=200)
            search_entry.pack(side="left", padx=5)
            crear_tooltip(search_entry, "Filtrar módulos por nombre")

            btn_frame = ctk.CTkFrame(step2_frame, fg_color="transparent")
            btn_frame.pack(fill="x", pady=5)

            btn_select_all = ctk.CTkButton(btn_frame, text="Seleccionar todos", command=lambda: select_all(), width=140)
            btn_select_all.pack(side="left", padx=5)
            crear_tooltip(btn_select_all, "Marcar todos los permisos para todos los módulos")

            btn_clear_all = ctk.CTkButton(btn_frame, text="Limpiar todos", command=lambda: clear_all(), width=140)
            btn_clear_all.pack(side="left", padx=5)
            crear_tooltip(btn_clear_all, "Desmarcar todos los permisos")

            btn_default = ctk.CTkButton(btn_frame, text="Permisos por defecto según rol", command=lambda: default_permissions(), width=200)
            btn_default.pack(side="left", padx=5)
            crear_tooltip(btn_default, "Asignar permisos típicos según el rol seleccionado")

            btn_copy = ctk.CTkButton(btn_frame, text="📋 Copiar permisos de...", command=lambda: copy_from_user(), width=180)
            btn_copy.pack(side="left", padx=5)
            crear_tooltip(btn_copy, "Copiar la configuración de permisos de otro usuario existente")

            scroll_perm = ctk.CTkScrollableFrame(step2_frame, height=400)
            scroll_perm.pack(fill="both", expand=True, pady=5)

            header = ctk.CTkFrame(scroll_perm, fg_color="transparent")
            header.pack(fill="x", pady=5)
            ctk.CTkLabel(header, text="Módulo", width=200, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Leer", width=60).pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Crear", width=60).pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Editar", width=60).pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Eliminar", width=60).pack(side="left", padx=5)

            perm_rows_frame = ctk.CTkFrame(scroll_perm, fg_color="transparent")
            perm_rows_frame.pack(fill="both", expand=True)

            rows.clear()
            for m in modulos_list:
                row_frame = ctk.CTkFrame(perm_rows_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(row_frame, text=m[1], width=200, anchor="w").pack(side="left", padx=5)

                puede_leer = ctk.BooleanVar(value=True)
                puede_crear = ctk.BooleanVar(value=False)
                puede_editar = ctk.BooleanVar(value=False)
                puede_eliminar = ctk.BooleanVar(value=False)

                if id_usuario:
                    perm = ejecutar_consulta("SELECT puede_leer, puede_crear, puede_editar, puede_eliminar FROM permisos_usuario WHERE usuario_id=%s AND modulo_id=%s",
                                             (id_usuario, m[0]), fetchone=True)
                    if perm:
                        puede_leer.set(perm[0])
                        puede_crear.set(perm[1])
                        puede_editar.set(perm[2])
                        puede_eliminar.set(perm[3])

                cb_leer = ctk.CTkCheckBox(row_frame, text="", variable=puede_leer, width=60)
                cb_leer.pack(side="left", padx=5)
                crear_tooltip(cb_leer, f"Permite leer datos en el módulo {m[1]}")

                cb_crear = ctk.CTkCheckBox(row_frame, text="", variable=puede_crear, width=60)
                cb_crear.pack(side="left", padx=5)
                crear_tooltip(cb_crear, f"Permite crear nuevos registros en el módulo {m[1]}")

                cb_editar = ctk.CTkCheckBox(row_frame, text="", variable=puede_editar, width=60)
                cb_editar.pack(side="left", padx=5)
                crear_tooltip(cb_editar, f"Permite editar registros en el módulo {m[1]}")

                cb_eliminar = ctk.CTkCheckBox(row_frame, text="", variable=puede_eliminar, width=60)
                cb_eliminar.pack(side="left", padx=5)
                crear_tooltip(cb_eliminar, f"Permite eliminar registros en el módulo {m[1]}")

                rows[m[1]] = (row_frame, puede_leer, puede_crear, puede_editar, puede_eliminar)
                permisos_vars[m[0]] = (puede_leer, puede_crear, puede_editar, puede_eliminar)

            def filter_modules(event=None):
                texto = search_entry.get().lower()
                for nombre_mod, (row_frame, _, _, _, _) in rows.items():
                    if texto in nombre_mod.lower():
                        row_frame.pack(fill="x", pady=2)
                    else:
                        row_frame.pack_forget()
            def select_all():
                for _, (_, l, c, e, d) in rows.items():
                    l.set(True); c.set(True); e.set(True); d.set(True)
            def clear_all():
                for _, (_, l, c, e, d) in rows.items():
                    l.set(False); c.set(False); e.set(False); d.set(False)
            def default_permissions():
                rol_actual = combo_rol.get()
                if rol_actual == "admin":
                    select_all()
                elif rol_actual == "supervisor":
                    for _, (_, l, c, e, d) in rows.items():
                        l.set(True); c.set(True); e.set(False); d.set(False)
                else:
                    lectura_modulos = ["catalogos", "recepcion", "pesaje_lavado", "pesaje_rezaga", "etiquetas", "reportes"]
                    for nombre_mod, (_, l, c, e, d) in rows.items():
                        if any(m in nombre_mod.lower() for m in lectura_modulos):
                            l.set(True)
                        else:
                            l.set(False)
                        c.set(False); e.set(False); d.set(False)
            def copy_from_user():
                usuarios = ejecutar_consulta("SELECT id, nombre_usuario FROM usuarios WHERE id != %s ORDER BY nombre_usuario" % (id_usuario if id_usuario else 0), fetchall=True)
                if not usuarios:
                    messagebox.showinfo("Info", "No hay otros usuarios para copiar permisos")
                    return
                top_copy = ctk.CTkToplevel(top)
                top_copy.title("Copiar permisos de")
                top_copy.geometry("400x200")
                top_copy.grab_set()
                ctk.CTkLabel(top_copy, text="Seleccionar usuario:").pack(pady=10)
                combo = ttk.Combobox(top_copy, values=[f"{u[1]}" for u in usuarios], width=30)
                combo.pack(pady=10)
                def aplicar():
                    selected = combo.get()
                    if not selected: return
                    for u_id, u_nom in usuarios:
                        if u_nom == selected:
                            origen_id = u_id
                            break
                    else:
                        return
                    for m_id, (l, c, e, d) in permisos_vars.items():
                        perm = ejecutar_consulta("SELECT puede_leer, puede_crear, puede_editar, puede_eliminar FROM permisos_usuario WHERE usuario_id=%s AND modulo_id=%s",
                                                 (origen_id, m_id), fetchone=True)
                        if perm:
                            l.set(perm[0]); c.set(perm[1]); e.set(perm[2]); d.set(perm[3])
                        else:
                            l.set(False); c.set(False); e.set(False); d.set(False)
                    top_copy.destroy()
                    messagebox.showinfo("Copiado", f"Permisos copiados desde {selected}")
                btn_copiar = ctk.CTkButton(top_copy, text="Copiar", command=aplicar)
                btn_copiar.pack(pady=10)

            search_entry.bind("<KeyRelease>", filter_modules)
            filter_modules()

        def build_step3():
            for w in step3_frame.winfo_children():
                w.destroy()
            ctk.CTkLabel(step3_frame, text="Paso 3 de 3: Resumen y confirmación", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0,20))
            data_frame = ctk.CTkFrame(step3_frame, fg_color="transparent")
            data_frame.pack(fill="x", pady=10)
            resumen = f"Nombre: {entry_nombre.get()}\nRol: {combo_rol.get()}\nActivo: {'Sí' if activo_var.get() else 'No'}"
            ctk.CTkLabel(data_frame, text=resumen, justify="left", font=("Arial", 12)).pack(anchor="w")
            ctk.CTkLabel(step3_frame, text="Permisos seleccionados:", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10,5))
            scroll_res = ctk.CTkScrollableFrame(step3_frame, height=300)
            scroll_res.pack(fill="both", expand=True, pady=5)
            for m_id, (l, c, e, d) in permisos_vars.items():
                nombre_modulo = next((mod[1] for mod in modulos_list if mod[0] == m_id), "Desconocido")
                texto = f"{nombre_modulo}: Leer={l.get()} Crear={c.get()} Editar={e.get()} Eliminar={d.get()}"
                ctk.CTkLabel(scroll_res, text=texto, anchor="w").pack(fill="x", pady=2)

        current_step = 1
        def show_step(step):
            nonlocal current_step
            current_step = step
            step1_frame.pack_forget()
            step2_frame.pack_forget()
            step3_frame.pack_forget()
            if step == 1:
                step1_frame.pack(fill="both", expand=True)
            elif step == 2:
                if not step2_frame.winfo_children():
                    build_step2()
                step2_frame.pack(fill="both", expand=True)
            elif step == 3:
                build_step3()
                step3_frame.pack(fill="both", expand=True)
            btn_prev.configure(state="normal" if step > 1 else "disabled")
            if step == 3:
                btn_next.configure(text="Guardar", command=finalizar)
            else:
                btn_next.configure(text="Siguiente →", command=lambda: show_step(step+1))

        def finalizar():
            nom = entry_nombre.get().strip()
            if not nom:
                messagebox.showerror("Error", "Nombre de usuario requerido")
                return
            pwd = entry_pass.get()
            if not id_usuario and not pwd:
                messagebox.showerror("Error", "Contraseña requerida")
                return
            if pwd and pwd != entry_confirm.get():
                messagebox.showerror("Error", "Las contraseñas no coinciden")
                return
            self._guardar_usuario(id_usuario, entry_nombre, entry_pass, combo_rol, activo_var, permisos_vars, top)
            messagebox.showinfo("Éxito", "Usuario guardado correctamente")
            top.destroy()

        nav_frame = ctk.CTkFrame(top, fg_color="transparent")
        nav_frame.pack(side="bottom", fill="x", pady=20)
        btn_prev = ctk.CTkButton(nav_frame, text="← Anterior", command=lambda: show_step(current_step-1), state="disabled", width=100)
        btn_prev.pack(side="left", padx=20)
        btn_next = ctk.CTkButton(nav_frame, text="Siguiente →", command=lambda: show_step(current_step+1), width=100)
        btn_next.pack(side="right", padx=20)

        show_step(1)

    def _guardar_usuario(self, id_usuario, entry_nombre, entry_pass, combo_rol, activo_var, permisos_vars, top):
        nom = entry_nombre.get().strip()
        pwd = entry_pass.get()
        hash_pass = hashlib.sha256(pwd.encode()).hexdigest() if pwd else None
        rol = combo_rol.get()
        activo = activo_var.get()

        contrasena_cifrada = cifrar_contrasena(pwd) if pwd else None

        if id_usuario:
            if hash_pass:
                ejecutar_consulta("""
                    UPDATE usuarios 
                    SET nombre_usuario=%s, contrasena_hash=%s, contrasena_cifrada=%s, rol=%s, activo=%s 
                    WHERE id=%s
                """, (nom, hash_pass, contrasena_cifrada, rol, activo, id_usuario))
            else:
                # No cambiar contraseña
                ejecutar_consulta("UPDATE usuarios SET nombre_usuario=%s, rol=%s, activo=%s WHERE id=%s",
                                  (nom, rol, activo, id_usuario))
            usuario_id = id_usuario
        else:
            ejecutar_consulta("""
                INSERT INTO usuarios (nombre_usuario, contrasena_hash, contrasena_cifrada, rol, activo) 
                VALUES (%s,%s,%s,%s,%s)
            """, (nom, hash_pass, contrasena_cifrada, rol, activo))
            usuario_id = ejecutar_consulta("SELECT lastval()", fetchone=True)[0]

        # Permisos
        ejecutar_consulta("DELETE FROM permisos_usuario WHERE usuario_id = %s", (usuario_id,))
        for modulo_id, (l, c, e, d) in permisos_vars.items():
            ejecutar_consulta("""
                INSERT INTO permisos_usuario (usuario_id, modulo_id, puede_leer, puede_crear, puede_editar, puede_eliminar)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (usuario_id, modulo_id, l.get(), c.get(), e.get(), d.get()))

        self.cargar_usuarios()
        if self.usuario_seleccionado_id == usuario_id:
            self.cargar_permisos_usuario(usuario_id)

    # ---------- APARIENCIA ----------
    def _init_apariencia(self):
        frame = self.tab_apariencia
        ctk.CTkLabel(frame, text="Tema de la aplicación", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        self.tema_var = ctk.StringVar(value=ctk.get_appearance_mode().lower())
        rb_claro = ctk.CTkRadioButton(frame, text="Claro", variable=self.tema_var, value="light", command=self._cambiar_tema)
        rb_claro.pack(anchor="w", padx=20, pady=5)
        rb_oscuro = ctk.CTkRadioButton(frame, text="Oscuro", variable=self.tema_var, value="dark", command=self._cambiar_tema)
        rb_oscuro.pack(anchor="w", padx=20, pady=5)

    def _cambiar_tema(self):
        ctk.set_appearance_mode(self.tema_var.get())
        from utils.theme_manager import guardar_tema
        guardar_tema(self.tema_var.get())

    # ---------- BÁSCULA ----------
    def _init_bascula(self):
        frame = self.tab_bascula
        ctk.CTkLabel(frame, text="Configuración de báscula", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(frame, text="Puerto serie:").pack(anchor="w", padx=20)
        self.puerto_bascula = ctk.CTkEntry(frame, width=150)
        self.puerto_bascula.pack(anchor="w", padx=20, pady=5)
        try:
            from utils.bascula import Bascula
            bascula = Bascula()
            puertos = bascula.listar_puertos()
            if puertos:
                self.puerto_combo = ctk.CTkComboBox(frame, values=puertos, width=150)
                self.puerto_combo.pack(anchor="w", padx=20, pady=5)
                self.puerto_combo.set(puertos[0] if puertos else "")
        except:
            pass
        btn_guardar_bascula = ctk.CTkButton(frame, text="Guardar configuración", command=self._guardar_puerto_bascula)
        btn_guardar_bascula.pack(pady=5)
        ctk.CTkLabel(frame, text="Ajustes de fecha y hora", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20,10))
        frame_fecha = ctk.CTkFrame(frame, fg_color="transparent")
        frame_fecha.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_fecha, text="Fecha actual:").pack(side="left", padx=5)
        self.fecha_actual_label = ctk.CTkLabel(frame_fecha, text="", font=("Arial", 12))
        self.fecha_actual_label.pack(side="left", padx=5)
        btn_cambiar_fecha = ctk.CTkButton(frame_fecha, text="📅 Cambiar fecha", command=self._cambiar_fecha)
        btn_cambiar_fecha.pack(side="left", padx=10)
        frame_hora = ctk.CTkFrame(frame, fg_color="transparent")
        frame_hora.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_hora, text="Hora actual:").pack(side="left", padx=5)
        self.hora_actual_label = ctk.CTkLabel(frame_hora, text="", font=("Arial", 12))
        self.hora_actual_label.pack(side="left", padx=5)
        btn_cambiar_hora = ctk.CTkButton(frame_hora, text="⏰ Cambiar hora", command=self._cambiar_hora)
        btn_cambiar_hora.pack(side="left", padx=10)
        self._actualizar_fecha_hora()

    def _actualizar_fecha_hora(self):
        ahora = datetime.now()
        self.fecha_actual_label.configure(text=ahora.strftime("%d/%m/%Y"))
        self.hora_actual_label.configure(text=ahora.strftime("%H:%M:%S"))
        self.after(1000, self._actualizar_fecha_hora)

    def _cambiar_fecha(self):
        top = ctk.CTkToplevel(self)
        top.title("Cambiar fecha del sistema")
        top.geometry("300x200")
        top.grab_set()
        ctk.CTkLabel(top, text="Seleccione nueva fecha:").pack(pady=10)
        cal = DateEntry(top, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        cal.pack(pady=10)
        def aplicar():
            nueva_fecha = cal.get_date()
            try:
                cmd = f'powershell Set-Date -Date "{nueva_fecha}"'
                subprocess.run(cmd, shell=True, check=True)
                messagebox.showinfo("Fecha", f"Fecha cambiada a {nueva_fecha}")
                top.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cambiar la fecha: {e}")
        btn_aplicar = ctk.CTkButton(top, text="Aplicar", command=aplicar)
        btn_aplicar.pack(pady=10)

    def _cambiar_hora(self):
        top = ctk.CTkToplevel(self)
        top.title("Cambiar hora del sistema")
        top.geometry("300x250")
        top.grab_set()
        ctk.CTkLabel(top, text="Hora (HH:MM:SS):").pack(pady=10)
        hora_entry = ctk.CTkEntry(top, width=100)
        hora_entry.pack(pady=5)
        hora_entry.insert(0, datetime.now().strftime("%H:%M:%S"))
        def aplicar():
            nueva_hora = hora_entry.get()
            try:
                datetime.strptime(nueva_hora, "%H:%M:%S")
                cmd = f'powershell Set-Date -Date "{datetime.now().strftime("%Y-%m-%d")} {nueva_hora}"'
                subprocess.run(cmd, shell=True, check=True)
                messagebox.showinfo("Hora", f"Hora cambiada a {nueva_hora}")
                top.destroy()
            except ValueError:
                messagebox.showerror("Error", "Formato incorrecto. Use HH:MM:SS")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cambiar la hora: {e}")
        btn_aplicar = ctk.CTkButton(top, text="Aplicar", command=aplicar)
        btn_aplicar.pack(pady=10)

    def _guardar_puerto_bascula(self):
        puerto = self.puerto_combo.get() if hasattr(self, 'puerto_combo') else self.puerto_bascula.get()
        with open("bascula_config.json", "w") as f:
            json.dump({"puerto": puerto}, f)
        messagebox.showinfo("Guardado", "Configuración de báscula guardada")

    # ---------- RESPALDO ----------
    def _init_backup(self):
        frame = self.tab_backup
        ctk.CTkLabel(frame, text="Respaldo de base de datos", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        btn_crear = ctk.CTkButton(frame, text="Crear respaldo", command=self._crear_backup)
        btn_crear.pack(pady=5)
        btn_restaurar = ctk.CTkButton(frame, text="Restaurar respaldo", command=self._restaurar_backup)
        btn_restaurar.pack(pady=5)

    def _crear_backup(self):
        archivo = filedialog.asksaveasfilename(defaultextension=".sql", filetypes=[("SQL files", "*.sql")])
        if archivo:
            config = cargar_config()
            if not config:
                messagebox.showerror("Error", "No hay configuración de red")
                return
            cmd = f'pg_dump -h {config["db_host"]} -p {config["db_port"]} -U {config["db_user"]} -d {config["db_name"]} -f "{archivo}"'
            try:
                subprocess.run(cmd, shell=True, check=True)
                messagebox.showinfo("Backup", f"Respaldo guardado en {archivo}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear el respaldo: {e}")

    def _restaurar_backup(self):
        archivo = filedialog.askopenfilename(filetypes=[("SQL files", "*.sql")])
        if archivo:
            config = cargar_config()
            if not config:
                messagebox.showerror("Error", "No hay configuración de red")
                return
            cmd = f'psql -h {config["db_host"]} -p {config["db_port"]} -U {config["db_user"]} -d {config["db_name"]} -f "{archivo}"'
            try:
                subprocess.run(cmd, shell=True, check=True)
                messagebox.showinfo("Restauración", "Base de datos restaurada correctamente.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo restaurar: {e}")

    # ---------- LOGS ----------
    def _init_logs(self):
        frame = self.tab_logs
        ctk.CTkLabel(frame, text="Registro de actividades", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        self.tree_logs = ttk.Treeview(frame, columns=("Fecha", "Usuario", "Acción"), show="headings", height=15)
        self.tree_logs.heading("Fecha", text="Fecha")
        self.tree_logs.heading("Usuario", text="Usuario")
        self.tree_logs.heading("Acción", text="Acción")
        self.tree_logs.pack(fill="both", expand=True, pady=10)
        self.cargar_logs()
        btn_refrescar_logs = ctk.CTkButton(frame, text="Refrescar", command=self.cargar_logs)
        btn_refrescar_logs.pack(pady=5)

    def cargar_logs(self):
        for row in self.tree_logs.get_children():
            self.tree_logs.delete(row)
        try:
            logs = ejecutar_consulta("SELECT fecha, usuario, accion FROM logs_sistema ORDER BY fecha DESC LIMIT 100", fetchall=True)
            for l in logs:
                self.tree_logs.insert("", "end", values=(l[0].strftime("%Y-%m-%d %H:%M:%S") if l[0] else "", l[1], l[2]))
        except:
            self.tree_logs.insert("", "end", values=("", "", "No hay registros disponibles"))

    # ---------- INFORMACIÓN ----------
    def _init_info(self):
        frame = self.tab_info
        ctk.CTkLabel(frame, text="Información del sistema", font=("Arial", 16, "bold")).pack(anchor="w", pady=10)
        version = "Santana Mango Manager v2.0"
        ctk.CTkLabel(frame, text=version, font=("Arial", 14)).pack(anchor="w", padx=20, pady=5)
        config = cargar_config()
        if config:
            info = f"Servidor: {config['db_host']}:{config['db_port']}\nBase de datos: {config['db_name']}\nUsuario: {config['db_user']}"
        else:
            info = "No conectado"
        ctk.CTkLabel(frame, text=info, font=("Arial", 12), justify="left").pack(anchor="w", padx=20, pady=5)
        try:
            total_variedades = ejecutar_consulta("SELECT COUNT(*) FROM variedades", fetchone=True)[0]
            total_productores = ejecutar_consulta("SELECT COUNT(*) FROM productores", fetchone=True)[0]
            stats = f"Variedades: {total_variedades} | Productores: {total_productores}"
            ctk.CTkLabel(frame, text=stats, font=("Arial", 12)).pack(anchor="w", padx=20, pady=5)
        except:
            
            pass