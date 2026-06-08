# modulos/catalogos.py - Gestión de catálogos con redirección a registros asociados (con tooltips)
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import ejecutar_consulta
from datetime import datetime
from tkcalendar import DateEntry
import pandas as pd
import hashlib
from utils.tooltip import crear_tooltip
from auth import tiene_permiso

class VentanaCatalogos(ctk.CTkFrame):
    _ventanas_activas = {}

    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.pack(fill="both", expand=True)

        if not tiene_permiso(permisos, "catalogos", "leer"):
            ctk.CTkLabel(self, text="⚠️ No tiene permisos para acceder a Catálogos",
                        font=("Arial", 20), text_color="red").pack(expand=True)
            return

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        nav_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("#e0e0e0", "#2a2a2a"))
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_columnconfigure(1, weight=1)

        self.btn_regresar = ctk.CTkButton(nav_bar, text="◀ REGRESAR", command=self.regresar_menu,
                                          width=150, height=35, fg_color="#8b0000", font=("Arial", 12, "bold"))
        self.btn_regresar.grid(row=0, column=0, padx=10, pady=5)
        crear_tooltip(self.btn_regresar, "Volver al menú principal")

        self.lbl_titulo = ctk.CTkLabel(nav_bar, text="📦 CATÁLOGOS", font=("Arial", 20, "bold"),
                                       text_color="#2e8b57")
        self.lbl_titulo.grid(row=0, column=1)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        self.mostrar_nivel_recepcion()

    def regresar_menu(self):
        if self.on_regresar:
            self.on_regresar()
        self.destroy()

    def limpiar_contenido(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

    def _enfocar_ventana(self, ventana):
        if ventana and ventana.winfo_exists():
            ventana.lift()
            ventana.focus_force()
            ventana.after(10, lambda: ventana.focus_force())
            ventana.update_idletasks()

    def _verificar_password_admin(self, parent_window=None):
        password = simpledialog.askstring("Autorización requerida",
                                          "Esta acción requiere permisos de administrador.\nIngrese la contraseña del administrador:",
                                          show='*', parent=parent_window if parent_window else self)
        if not password:
            if parent_window:
                self._enfocar_ventana(parent_window)
            return False
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        admin_hash = ejecutar_consulta("SELECT contrasena_hash FROM usuarios WHERE rol = 'admin' LIMIT 1", fetchone=True)
        if admin_hash and admin_hash[0] == hash_pass:
            return True
        messagebox.showerror("Acceso denegado", "Contraseña incorrecta.")
        if parent_window:
            self._enfocar_ventana(parent_window)
        return False

    # ---------- FUNCIÓN PARA MOSTRAR RECEPCIONES ASOCIADAS ----------
    def _mostrar_recepciones_asociadas(self, tabla, id_registro, nombre_campo_id, nombre_campo_texto=None):
        """
        Muestra una ventana con las recepciones que referencian un registro de catálogo.
        tabla: nombre de la tabla de catálogo (ej: 'lotes')
        id_registro: ID del registro que se intenta eliminar
        nombre_campo_id: nombre de la columna FK en recepcion_carga (ej: 'lote_id')
        nombre_campo_texto: nombre del campo para mostrar el valor del catálogo (ej: 'numero_lote')
        """
        # Obtener el nombre del registro para mostrarlo en el título
        if nombre_campo_texto:
            query_nombre = f"SELECT {nombre_campo_texto} FROM {tabla} WHERE id = %s"
            nombre_valor = ejecutar_consulta(query_nombre, (id_registro,), fetchone=True)
            nombre_registro = nombre_valor[0] if nombre_valor else f"ID {id_registro}"
        else:
            nombre_registro = f"ID {id_registro}"

        # Consultar las recepciones que usan este registro
        query = """
            SELECT r.folio, r.numero_carga, to_char(r.fecha_hora, 'DD/MM/YYYY') as fecha,
                   l.numero_lote, p.nombre as productor, r.cajas_llenas
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN productores p ON r.productor_id = p.id
            WHERE r.{} = %s
            ORDER BY r.fecha_hora DESC
        """.format(nombre_campo_id)
        resultados = ejecutar_consulta(query, (id_registro,), fetchall=True)

        # Crear ventana
        ventana = ctk.CTkToplevel(self)
        ventana.title(f"Recepciones que usan {nombre_registro}")
        ventana.geometry("800x400")
        ventana.grab_set()

        frame = ctk.CTkFrame(ventana, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text=f"Registros encontrados: {len(resultados)}", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)

        if resultados:
            # Crear Treeview
            columnas = ("Folio", "No. Carga", "Fecha", "Lote", "Productor", "Cajas Llenas")
            tree = ttk.Treeview(frame, columns=columnas, show="headings", height=15)
            for col in columnas:
                tree.heading(col, text=col)
                tree.column(col, width=120, anchor="center")
            tree.pack(fill="both", expand=True)

            for r in resultados:
                tree.insert("", "end", values=r)

            # Scrollbars
            vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            vsb.pack(side="right", fill="y")
            tree.configure(yscrollcommand=vsb.set)
        else:
            ctk.CTkLabel(frame, text="No se encontraron recepciones asociadas.", font=("Arial", 12)).pack(pady=20)

        btn_cerrar = ctk.CTkButton(frame, text="Cerrar", command=ventana.destroy, width=100)
        btn_cerrar.pack(pady=10)
        crear_tooltip(btn_cerrar, "Cerrar esta ventana")

        self._enfocar_ventana(ventana)

    # ---------- MÉTODO PARA MANEJAR ERROR DE CLAVE FORÁNEA ----------
    def _manejar_error_eliminacion(self, parent_ventana, e, tabla, id_registro, nombre_campo_id, nombre_campo_texto):
        if "viola la llave foránea" in str(e) or "foreign key constraint" in str(e):
            respuesta = messagebox.askyesno(
                "No se puede eliminar",
                f"Este registro está siendo utilizado en una o más recepciones.\n\n¿Desea ver los registros asociados?"
            )
            if respuesta:
                self._mostrar_recepciones_asociadas(tabla, id_registro, nombre_campo_id, nombre_campo_texto)
            else:
                messagebox.showinfo("Información", "No se eliminó el registro.")
        else:
            messagebox.showerror("Error", f"No se pudo eliminar: {e}")
        self._enfocar_ventana(parent_ventana)

    # ---------- NIVELES ----------
    def mostrar_nivel_recepcion(self):
        self.limpiar_contenido()
        self.lbl_titulo.configure(text="📦 CATÁLOGOS")
        center_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        center_frame.pack(expand=True, fill="both")
        card = ctk.CTkFrame(center_frame, corner_radius=20, border_width=2,
                           border_color="#2e8b57", fg_color=("#f0f0f0", "#2a2a2a"),
                           width=350, height=200)
        card.pack(expand=True, pady=50)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text="📦", font=("Segoe UI", 64)).pack(pady=(30, 10))
        ctk.CTkLabel(card, text="RECEPCIÓN", font=("Arial", 24, "bold")).pack()
        ctk.CTkLabel(card, text="Gestionar catálogos utilizados en recepción",
                    font=("Arial", 12), text_color="gray").pack(pady=5)
        btn = ctk.CTkButton(card, text="Acceder", command=self.mostrar_nivel_catalogos,
                           width=150, height=40, fg_color="#2e8b57", font=("Arial", 14, "bold"))
        btn.pack(pady=20)
        crear_tooltip(btn, "Ver todos los catálogos de recepción")

    def mostrar_nivel_catalogos(self):
        self.limpiar_contenido()
        self.lbl_titulo.configure(text="📦 CATÁLOGOS DE RECEPCIÓN")
        back_btn = ctk.CTkButton(self.scroll_frame, text="◀ Volver a Catálogos",
                                 command=self.mostrar_nivel_recepcion,
                                 width=180, height=35, fg_color="#3a6ea5")
        back_btn.pack(anchor="w", pady=(0, 10))
        crear_tooltip(back_btn, "Regresar a la pantalla principal de catálogos")

        grid_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)

        catalogos = [
            ("📦", "Lotes", self.gestion_lotes),
            ("🥭", "Variedades", self.gestion_variedades),
            ("🚗", "Choferes", self.gestion_choferes),
            ("📍", "Centros de Abastecimiento", self.gestion_centros),
            ("👨‍🌾", "Productores", self.gestion_productores),
            ("🌾", "Campos (Huertos)", self.gestion_campos),
            ("🌿", "Registros de Huerto", self.gestion_registros_huerto)
        ]

        fila, col = 0, 0
        columnas = 3
        for icono, texto, funcion in catalogos:
            tabla = self._obtener_tabla_por_texto(texto)
            try:
                count = ejecutar_consulta(f"SELECT COUNT(*) FROM {tabla} WHERE activo=true", fetchone=True)[0]
            except:
                count = 0
            card = ctk.CTkFrame(grid_frame, corner_radius=15, border_width=1,
                               border_color="#2e8b57", fg_color=("#f0f0f0", "#2a2a2a"),
                               width=250, height=180)
            card.grid(row=fila, column=col, padx=15, pady=15, sticky="nsew")
            card.grid_propagate(False)
            ctk.CTkLabel(card, text=icono, font=("Segoe UI", 48)).pack(pady=(15, 5))
            ctk.CTkLabel(card, text=texto, font=("Arial", 16, "bold")).pack()
            ctk.CTkLabel(card, text=f"{count} registros activos", font=("Arial", 11), text_color="gray").pack(pady=5)
            btn = ctk.CTkButton(card, text="Gestionar", command=funcion, width=120, height=32, fg_color="#2e8b57")
            btn.pack(pady=10)
            crear_tooltip(btn, f"Administrar {texto}")
            col += 1
            if col >= columnas:
                col = 0
                fila += 1

        for i in range(columnas):
            grid_frame.grid_columnconfigure(i, weight=1)

    def _obtener_tabla_por_texto(self, texto):
        mapping = {
            "Lotes": "lotes",
            "Variedades": "variedades",
            "Choferes": "choferes",
            "Centros de Abastecimiento": "centros_abastecimiento",
            "Productores": "productores",
            "Campos (Huertos)": "campos",
            "Registros de Huerto": "registros_huerto"
        }
        return mapping.get(texto, "")

    # ---------- CONTROL DE VENTANAS ----------
    def _abrir_ventana_gestion(self, nombre_clave, crear_ventana_func):
        if nombre_clave in self._ventanas_activas:
            ventana = self._ventanas_activas[nombre_clave]
            try:
                if ventana.winfo_exists():
                    self._enfocar_ventana(ventana)
                    return
                else:
                    del self._ventanas_activas[nombre_clave]
            except:
                del self._ventanas_activas[nombre_clave]
        ventana = crear_ventana_func()
        self._ventanas_activas[nombre_clave] = ventana
        ventana.protocol("WM_DELETE_WINDOW", lambda: self._cerrar_ventana_gestion(nombre_clave, ventana))

    def _cerrar_ventana_gestion(self, nombre_clave, ventana):
        ventana.destroy()
        if nombre_clave in self._ventanas_activas:
            del self._ventanas_activas[nombre_clave]

    # ---------- CONFIGURACIÓN DE VENTANA DE GESTIÓN ----------
    def _configurar_ventana_gestion(self, ventana, cargar_func, nuevo_func, editar_func, eliminar_func, exportar_nombre, permiso_modulo):
        main_frame = ctk.CTkFrame(ventana, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        toolbar = ctk.CTkFrame(main_frame, fg_color="transparent", height=40)
        toolbar.pack(fill="x", pady=5)

        btn_nuevo = ctk.CTkButton(toolbar, text="➕ Nuevo", command=lambda: nuevo_func(ventana, tree), width=100)
        btn_nuevo.pack(side="left", padx=5)
        crear_tooltip(btn_nuevo, "Crear un nuevo registro")

        btn_editar = ctk.CTkButton(toolbar, text="✏️ Editar", command=lambda: editar_func(ventana, tree), width=100)
        btn_editar.pack(side="left", padx=5)
        crear_tooltip(btn_editar, "Editar el registro seleccionado")

        btn_eliminar = ctk.CTkButton(toolbar, text="🗑️ Eliminar", command=lambda: eliminar_func(ventana, tree), width=100, fg_color="#8b0000")
        btn_eliminar.pack(side="left", padx=5)
        crear_tooltip(btn_eliminar, "Eliminar el registro seleccionado")

        btn_refrescar = ctk.CTkButton(toolbar, text="🔄 Refrescar", command=lambda: cargar_func(tree), width=100, fg_color="#3a6ea5")
        btn_refrescar.pack(side="left", padx=5)
        crear_tooltip(btn_refrescar, "Recargar la lista de registros")

        btn_exportar = ctk.CTkButton(toolbar, text="📊 Exportar Excel", command=lambda: self._exportar_excel(tree, exportar_nombre), width=120, fg_color="#2e8b57")
        btn_exportar.pack(side="left", padx=5)
        crear_tooltip(btn_exportar, "Exportar los datos a un archivo Excel")

        search_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(search_frame, text="🔍 Buscar:", font=("Arial", 12)).pack(side="left", padx=5)
        search_entry = ctk.CTkEntry(search_frame, width=250)
        search_entry.pack(side="left", padx=5)
        crear_tooltip(search_entry, "Escribe el texto a buscar y presiona el botón Buscar")

        def buscar():
            texto = search_entry.get()
            if not texto:
                return
            for item in tree.get_children():
                valores = tree.item(item)["values"]
                if any(texto.lower() in str(v).lower() for v in valores):
                    tree.selection_set(item)
                    tree.see(item)
                    return
            messagebox.showinfo("Buscar", "No se encontraron coincidencias")

        btn_buscar = ctk.CTkButton(search_frame, text="Buscar", command=buscar, width=80)
        btn_buscar.pack(side="left", padx=5)
        crear_tooltip(btn_buscar, "Buscar la primera coincidencia del texto")

        btn_mostrar = ctk.CTkButton(search_frame, text="Mostrar todos", command=lambda: cargar_func(tree), width=100)
        btn_mostrar.pack(side="left", padx=5)
        crear_tooltip(btn_mostrar, "Mostrar todos los registros sin filtro")

        columnas = self._obtener_columnas_por_exportar(exportar_nombre)
        tree = self._crear_tabla_centrada(main_frame, columnas)
        cargar_func(tree)

        ventana.tree = tree
        ventana.cargar_func = cargar_func

    def _obtener_columnas_por_exportar(self, nombre):
        mapping = {
            "Lotes": ("ID", "Número de Lote", "Fecha Ingreso", "Activo"),
            "Variedades": ("ID", "Nombre", "Activo"),
            "Choferes": ("ID", "Nombre", "Activo"),
            "Centros": ("ID", "Nombre", "Activo"),
            "Productores": ("ID", "Nombre", "Activo"),
            "Campos": ("ID", "Nombre", "Ubicación", "Activo"),
            "RegistrosHuerto": ("ID", "Nombre", "Activo")
        }
        return mapping.get(nombre, ("ID", "Nombre", "Activo"))

    def _crear_tabla_centrada(self, parent, columnas, altura=15):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, pady=10)
        tree = ttk.Treeview(frame, columns=columnas, show="headings", height=altura)
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, width=120, minwidth=80, anchor="center")
        tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        hsb.pack(side="bottom", fill="x")
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        crear_tooltip(vsb, "Barra de desplazamiento vertical")
        crear_tooltip(hsb, "Barra de desplazamiento horizontal")
        return tree

    def _exportar_excel(self, tree, nombre_archivo):
        datos = tree.get_children()
        if not datos:
            messagebox.showwarning("Sin datos", "No hay datos para exportar")
            return
        columnas = list(tree["columns"])
        filas = [tree.item(item)["values"] for item in datos]
        df = pd.DataFrame(filas, columns=columnas)
        archivo = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"{nombre_archivo}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        if archivo:
            df.to_excel(archivo, index=False)
            messagebox.showinfo("Éxito", f"Exportado a {archivo}")

    # ==================== LOTES ====================
    def gestion_lotes(self):
        self._abrir_ventana_gestion("lotes", self._crear_ventana_lotes)

    def _crear_ventana_lotes(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Lotes")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_lotes_tree,
                                         self._nuevo_lote, self._editar_lote_ui, self._eliminar_lote_ui,
                                         "Lotes", "lotes")
        return ventana

    def _cargar_lotes_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        query = "SELECT id, numero_lote, fecha_ingreso, activo FROM lotes ORDER BY fecha_ingreso DESC"
        resultados = ejecutar_consulta(query, fetchall=True)
        for r in resultados:
            activo = "Sí" if r[3] else "No"
            fecha = r[2].strftime("%d/%m/%Y") if r[2] else ""
            tree.insert("", "end", values=(r[0], r[1], fecha, activo), tags=(r[0],))

    def _nuevo_lote(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_lote(parent_ventana, tree, None)

    def _editar_lote_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un lote para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_lote(parent_ventana, tree, id_registro)

    def _eliminar_lote_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un lote para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este lote? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM lotes WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Lote eliminado correctamente")
            self._cargar_lotes_tree(tree)
        except Exception as e:
            self._manejar_error_eliminacion(parent_ventana, e, "lotes", id_registro, "lote_id", "numero_lote")
        self._enfocar_ventana(parent_ventana)

    def _formulario_lote(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Lote" if id_registro else "Nuevo Lote"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x350")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Número de Lote (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        numero_entry = ctk.CTkEntry(frame, width=250)
        numero_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(numero_entry, "Número de lote (ej: L-001)")

        ctk.CTkLabel(frame, text="Fecha Ingreso:", font=("Arial", 12)).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        fecha_entry = DateEntry(frame, width=15, date_pattern='yyyy-mm-dd')
        fecha_entry.set_date(datetime.now())
        fecha_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(fecha_entry, "Fecha de ingreso del lote")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si el lote está activo")

        if id_registro:
            datos = ejecutar_consulta("SELECT numero_lote, fecha_ingreso, activo FROM lotes WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                numero_entry.insert(0, datos[0])
                fecha_entry.set_date(datos[1])
                activo_var.set(datos[2])

        def guardar():
            numero = numero_entry.get().strip()
            if not numero:
                messagebox.showerror("Error", "El número de lote es obligatorio")
                return
            fecha_ing = fecha_entry.get_date()
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE lotes SET numero_lote=%s, fecha_ingreso=%s, activo=%s WHERE id=%s",
                                     (numero, fecha_ing, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Lote actualizado correctamente")
                else:
                    ejecutar_consulta("INSERT INTO lotes (numero_lote, fecha_ingreso, activo) VALUES (%s, %s, %s)",
                                     (numero, fecha_ing, activo))
                    messagebox.showinfo("Guardado", "Lote creado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_lotes_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")

    # ==================== VARIEDADES (no tiene FK directa, pero se deja igual) ====================
    def gestion_variedades(self):
        self._abrir_ventana_gestion("variedades", self._crear_ventana_variedades)

    def _crear_ventana_variedades(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Variedades")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_variedades_tree,
                                         self._nuevo_variedad, self._editar_variedad_ui, self._eliminar_variedad_ui,
                                         "Variedades", "variedades")
        return ventana

    def _cargar_variedades_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        resultados = ejecutar_consulta("SELECT id, nombre, activo FROM variedades ORDER BY nombre", fetchall=True)
        for r in resultados:
            activo = "Sí" if r[2] else "No"
            tree.insert("", "end", values=(r[0], r[1], activo), tags=(r[0],))

    def _nuevo_variedad(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_variedad(parent_ventana, tree, None)

    def _editar_variedad_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una variedad para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_variedad(parent_ventana, tree, id_registro)

    def _eliminar_variedad_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una variedad para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar esta variedad? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM variedades WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Variedad eliminada correctamente")
            self._cargar_variedades_tree(tree)
        except Exception as e:
            # No hay FK esperada, pero manejamos igual
            if "viola la llave foránea" in str(e) or "foreign key constraint" in str(e):
                messagebox.showerror("No se puede eliminar", "Esta variedad está siendo utilizada en recepciones (campo variedad).")
            else:
                messagebox.showerror("Error", f"No se pudo eliminar: {e}")
        self._enfocar_ventana(parent_ventana)

    def _formulario_variedad(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Variedad" if id_registro else "Nueva Variedad"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x300")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nombre (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        nombre_entry = ctk.CTkEntry(frame, width=250)
        nombre_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(nombre_entry, "Nombre de la variedad (ej: Ataulfo, Manila)")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si la variedad está activa")

        if id_registro:
            datos = ejecutar_consulta("SELECT nombre, activo FROM variedades WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                nombre_entry.insert(0, datos[0])
                activo_var.set(datos[1])

        def guardar():
            nombre = nombre_entry.get().strip()
            if not nombre:
                messagebox.showerror("Error", "El nombre es obligatorio")
                return
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE variedades SET nombre=%s, activo=%s WHERE id=%s", (nombre, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Variedad actualizada correctamente")
                else:
                    ejecutar_consulta("INSERT INTO variedades (nombre, activo) VALUES (%s, %s)", (nombre, activo))
                    messagebox.showinfo("Guardado", "Variedad creada correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_variedades_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")

    # ==================== CHOFERES ====================
    def gestion_choferes(self):
        self._abrir_ventana_gestion("choferes", self._crear_ventana_choferes)

    def _crear_ventana_choferes(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Choferes")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_choferes_tree,
                                         self._nuevo_chofer, self._editar_chofer_ui, self._eliminar_chofer_ui,
                                         "Choferes", "choferes")
        return ventana

    def _cargar_choferes_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        resultados = ejecutar_consulta("SELECT id, nombre, activo FROM choferes ORDER BY nombre", fetchall=True)
        for r in resultados:
            activo = "Sí" if r[2] else "No"
            tree.insert("", "end", values=(r[0], r[1], activo), tags=(r[0],))

    def _nuevo_chofer(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_chofer(parent_ventana, tree, None)

    def _editar_chofer_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un chofer para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_chofer(parent_ventana, tree, id_registro)

    def _eliminar_chofer_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un chofer para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este chofer? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM choferes WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Chofer eliminado correctamente")
            self._cargar_choferes_tree(tree)
        except Exception as e:
            self._manejar_error_eliminacion(parent_ventana, e, "choferes", id_registro, "chofer_id", "nombre")
        self._enfocar_ventana(parent_ventana)

    def _formulario_chofer(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Chofer" if id_registro else "Nuevo Chofer"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x300")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nombre (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        nombre_entry = ctk.CTkEntry(frame, width=250)
        nombre_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(nombre_entry, "Nombre completo del chofer")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si el chofer está activo")

        if id_registro:
            datos = ejecutar_consulta("SELECT nombre, activo FROM choferes WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                nombre_entry.insert(0, datos[0])
                activo_var.set(datos[1])

        def guardar():
            nombre = nombre_entry.get().strip()
            if not nombre:
                messagebox.showerror("Error", "El nombre es obligatorio")
                return
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE choferes SET nombre=%s, activo=%s WHERE id=%s", (nombre, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Chofer actualizado correctamente")
                else:
                    ejecutar_consulta("INSERT INTO choferes (nombre, activo) VALUES (%s, %s)", (nombre, activo))
                    messagebox.showinfo("Guardado", "Chofer creado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_choferes_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")

    # ==================== CENTROS DE ABASTECIMIENTO ====================
    def gestion_centros(self):
        self._abrir_ventana_gestion("centros", self._crear_ventana_centros)

    def _crear_ventana_centros(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Centros de Abastecimiento")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_centros_tree,
                                         self._nuevo_centro, self._editar_centro_ui, self._eliminar_centro_ui,
                                         "Centros", "centros")
        return ventana

    def _cargar_centros_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        resultados = ejecutar_consulta("SELECT id, nombre, activo FROM centros_abastecimiento ORDER BY nombre", fetchall=True)
        for r in resultados:
            activo = "Sí" if r[2] else "No"
            tree.insert("", "end", values=(r[0], r[1], activo), tags=(r[0],))

    def _nuevo_centro(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_centro(parent_ventana, tree, None)

    def _editar_centro_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un centro para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_centro(parent_ventana, tree, id_registro)

    def _eliminar_centro_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un centro para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este centro? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM centros_abastecimiento WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Centro eliminado correctamente")
            self._cargar_centros_tree(tree)
        except Exception as e:
            self._manejar_error_eliminacion(parent_ventana, e, "centros_abastecimiento", id_registro, "centro_abastecimiento_id", "nombre")
        self._enfocar_ventana(parent_ventana)

    def _formulario_centro(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Centro" if id_registro else "Nuevo Centro"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x300")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nombre (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        nombre_entry = ctk.CTkEntry(frame, width=250)
        nombre_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(nombre_entry, "Nombre del centro de abastecimiento")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si el centro está activo")

        if id_registro:
            datos = ejecutar_consulta("SELECT nombre, activo FROM centros_abastecimiento WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                nombre_entry.insert(0, datos[0])
                activo_var.set(datos[1])

        def guardar():
            nombre = nombre_entry.get().strip()
            if not nombre:
                messagebox.showerror("Error", "El nombre es obligatorio")
                return
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE centros_abastecimiento SET nombre=%s, activo=%s WHERE id=%s", (nombre, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Centro actualizado correctamente")
                else:
                    ejecutar_consulta("INSERT INTO centros_abastecimiento (nombre, activo) VALUES (%s, %s)", (nombre, activo))
                    messagebox.showinfo("Guardado", "Centro creado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_centros_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")

    # ==================== PRODUCTORES ====================
    def gestion_productores(self):
        self._abrir_ventana_gestion("productores", self._crear_ventana_productores)

    def _crear_ventana_productores(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Productores")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_productores_tree,
                                         self._nuevo_productor, self._editar_productor_ui, self._eliminar_productor_ui,
                                         "Productores", "productores")
        return ventana

    def _cargar_productores_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        resultados = ejecutar_consulta("SELECT id, nombre, activo FROM productores ORDER BY nombre", fetchall=True)
        for r in resultados:
            activo = "Sí" if r[2] else "No"
            tree.insert("", "end", values=(r[0], r[1], activo), tags=(r[0],))

    def _nuevo_productor(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_productor(parent_ventana, tree, None)

    def _editar_productor_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un productor para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_productor(parent_ventana, tree, id_registro)

    def _eliminar_productor_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un productor para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este productor? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM productores WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Productor eliminado correctamente")
            self._cargar_productores_tree(tree)
        except Exception as e:
            self._manejar_error_eliminacion(parent_ventana, e, "productores", id_registro, "productor_id", "nombre")
        self._enfocar_ventana(parent_ventana)

    def _formulario_productor(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Productor" if id_registro else "Nuevo Productor"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x300")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nombre (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        nombre_entry = ctk.CTkEntry(frame, width=250)
        nombre_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(nombre_entry, "Nombre completo del productor")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si el productor está activo")

        if id_registro:
            datos = ejecutar_consulta("SELECT nombre, activo FROM productores WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                nombre_entry.insert(0, datos[0])
                activo_var.set(datos[1])

        def guardar():
            nombre = nombre_entry.get().strip()
            if not nombre:
                messagebox.showerror("Error", "El nombre es obligatorio")
                return
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE productores SET nombre=%s, activo=%s WHERE id=%s", (nombre, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Productor actualizado correctamente")
                else:
                    ejecutar_consulta("INSERT INTO productores (nombre, activo) VALUES (%s, %s)", (nombre, activo))
                    messagebox.showinfo("Guardado", "Productor creado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_productores_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")

    # ==================== CAMPOS ====================
    def gestion_campos(self):
        self._abrir_ventana_gestion("campos", self._crear_ventana_campos)

    def _crear_ventana_campos(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Campos (Huertos)")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_campos_tree,
                                         self._nuevo_campo, self._editar_campo_ui, self._eliminar_campo_ui,
                                         "Campos", "campos")
        return ventana

    def _cargar_campos_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        resultados = ejecutar_consulta("SELECT id, nombre, ubicacion, activo FROM campos ORDER BY nombre", fetchall=True)
        for r in resultados:
            activo = "Sí" if r[3] else "No"
            ubicacion = r[2] or ""
            tree.insert("", "end", values=(r[0], r[1], ubicacion, activo), tags=(r[0],))

    def _nuevo_campo(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_campo(parent_ventana, tree, None)

    def _editar_campo_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un campo para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_campo(parent_ventana, tree, id_registro)

    def _eliminar_campo_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un campo para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este campo? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM campos WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Campo eliminado correctamente")
            self._cargar_campos_tree(tree)
        except Exception as e:
            self._manejar_error_eliminacion(parent_ventana, e, "campos", id_registro, "campo_id", "nombre")
        self._enfocar_ventana(parent_ventana)

    def _formulario_campo(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Campo" if id_registro else "Nuevo Campo"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x350")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nombre (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        nombre_entry = ctk.CTkEntry(frame, width=250)
        nombre_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(nombre_entry, "Nombre del campo o huerto")

        ctk.CTkLabel(frame, text="Ubicación:", font=("Arial", 12)).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        ubicacion_entry = ctk.CTkEntry(frame, width=250)
        ubicacion_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(ubicacion_entry, "Ubicación geográfica del campo")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si el campo está activo")

        if id_registro:
            datos = ejecutar_consulta("SELECT nombre, ubicacion, activo FROM campos WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                nombre_entry.insert(0, datos[0])
                ubicacion_entry.insert(0, datos[1] or "")
                activo_var.set(datos[2])

        def guardar():
            nombre = nombre_entry.get().strip()
            if not nombre:
                messagebox.showerror("Error", "El nombre es obligatorio")
                return
            ubicacion = ubicacion_entry.get().strip() or None
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE campos SET nombre=%s, ubicacion=%s, activo=%s WHERE id=%s",
                                     (nombre, ubicacion, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Campo actualizado correctamente")
                else:
                    ejecutar_consulta("INSERT INTO campos (nombre, ubicacion, activo) VALUES (%s, %s, %s)",
                                     (nombre, ubicacion, activo))
                    messagebox.showinfo("Guardado", "Campo creado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_campos_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")

    # ==================== REGISTROS DE HUERTO ====================
    def gestion_registros_huerto(self):
        self._abrir_ventana_gestion("registros_huerto", self._crear_ventana_registros_huerto)

    def _crear_ventana_registros_huerto(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Gestión de Registros de Huerto")
        ventana.geometry("900x550")
        ventana.grab_set()
        self._configurar_ventana_gestion(ventana, self._cargar_registros_huerto_tree,
                                         self._nuevo_registro_huerto, self._editar_registro_huerto_ui, self._eliminar_registro_huerto_ui,
                                         "RegistrosHuerto", "registros_huerto")
        return ventana

    def _cargar_registros_huerto_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        resultados = ejecutar_consulta("SELECT id, nombre, activo FROM registros_huerto ORDER BY nombre", fetchall=True)
        for r in resultados:
            activo = "Sí" if r[2] else "No"
            tree.insert("", "end", values=(r[0], r[1], activo), tags=(r[0],))

    def _nuevo_registro_huerto(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "crear"):
            if not self._verificar_password_admin(parent_ventana):
                return
        self._formulario_registro_huerto(parent_ventana, tree, None)

    def _editar_registro_huerto_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "editar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un registro para editar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        self._formulario_registro_huerto(parent_ventana, tree, id_registro)

    def _eliminar_registro_huerto_ui(self, parent_ventana, tree):
        if not tiene_permiso(self.permisos, "catalogos", "eliminar"):
            if not self._verificar_password_admin(parent_ventana):
                return
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un registro para eliminar")
            self._enfocar_ventana(parent_ventana)
            return
        id_registro = tree.item(seleccion[0])['tags'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este registro de huerto? Esta acción no se puede deshacer."):
            self._enfocar_ventana(parent_ventana)
            return
        try:
            ejecutar_consulta("DELETE FROM registros_huerto WHERE id=%s", (id_registro,))
            messagebox.showinfo("Eliminado", "Registro eliminado correctamente")
            self._cargar_registros_huerto_tree(tree)
        except Exception as e:
            self._manejar_error_eliminacion(parent_ventana, e, "registros_huerto", id_registro, "registro_huerto_id", "nombre")
        self._enfocar_ventana(parent_ventana)

    def _formulario_registro_huerto(self, parent_ventana, tree, id_registro=None):
        titulo = "Editar Registro de Huerto" if id_registro else "Nuevo Registro de Huerto"
        modal = ctk.CTkToplevel(parent_ventana)
        modal.title(titulo)
        modal.geometry("450x300")
        modal.grab_set()
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Nombre (*):", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        nombre_entry = ctk.CTkEntry(frame, width=250)
        nombre_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(nombre_entry, "Nombre del registro de huerto")

        activo_var = ctk.BooleanVar(value=True)
        cb_activo = ctk.CTkCheckBox(frame, text="Activo", variable=activo_var)
        cb_activo.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        crear_tooltip(cb_activo, "Indica si el registro está activo")

        if id_registro:
            datos = ejecutar_consulta("SELECT nombre, activo FROM registros_huerto WHERE id=%s", (id_registro,), fetchone=True)
            if datos:
                nombre_entry.insert(0, datos[0])
                activo_var.set(datos[1])

        def guardar():
            nombre = nombre_entry.get().strip()
            if not nombre:
                messagebox.showerror("Error", "El nombre es obligatorio")
                return
            activo = activo_var.get()
            try:
                if id_registro:
                    ejecutar_consulta("UPDATE registros_huerto SET nombre=%s, activo=%s WHERE id=%s", (nombre, activo, id_registro))
                    messagebox.showinfo("Actualizado", "Registro actualizado correctamente")
                else:
                    ejecutar_consulta("INSERT INTO registros_huerto (nombre, activo) VALUES (%s, %s)", (nombre, activo))
                    messagebox.showinfo("Guardado", "Registro creado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")
                return
            modal.destroy()
            self._cargar_registros_huerto_tree(tree)
            self._enfocar_ventana(parent_ventana)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar", command=guardar, width=100, fg_color="#2e8b57")
        btn_guardar.pack(side="left", padx=10)
        crear_tooltip(btn_guardar, "Guardar los cambios")

        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cancelar.pack(side="left", padx=10)
        crear_tooltip(btn_cancelar, "Cancelar y cerrar")