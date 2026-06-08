# modulos/pesaje_lavado.py - Editor de tanda con pestañas (Peso + Jabas)
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import ejecutar_consulta
from datetime import datetime
from tkcalendar import DateEntry
import pandas as pd
from utils.tooltip import crear_tooltip
from utils.bascula import Bascula
from auth import tiene_permiso

class VentanaPesajeLavado(ctk.CTkFrame):
    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.pack(fill="both", expand=True)

        if not tiene_permiso(permisos, "pesaje_lavado", "leer"):
            ctk.CTkLabel(self, text="⚠️ No tiene permisos para acceder a Pesaje Lavado",
                        font=("Arial", 20), text_color="red").pack(expand=True)
            return

        # Variables internas
        self.id_recepcion = None
        self.variedad_actual = ""
        self.tandas_pendientes = []
        self.siguiente_tanda = 1
        self.bascula = Bascula()
        self.filtros_visibles = False
        self.search_after_id = None
        self.peso_jabas = {i: 5.0 for i in range(1, 8)}
        self.jabas_totales = 0
        self.lotes_por_carga = {}

        self._asegurar_tabla_pesaje()
        self._crear_tabla_configuracion()
        self.cargar_configuracion_pesaje()

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ---------- BARRA DE NAVEGACIÓN ----------
        nav_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("#e0e0e0", "#2a2a2a"))
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_columnconfigure(1, weight=1)

        self.btn_regresar = ctk.CTkButton(nav_bar, text="◀ REGRESAR", command=self.regresar_menu,
                                          width=150, height=35, fg_color="#8b0000", font=("Arial", 12, "bold"))
        self.btn_regresar.grid(row=0, column=0, padx=10, pady=5)
        crear_tooltip(self.btn_regresar, "Volver al menú principal")

        ctk.CTkLabel(nav_bar, text="🧼 PESAJE LAVADO", font=("Arial", 20, "bold"),
                     text_color="#2e8b57").grid(row=0, column=1)

        self.btn_refrescar = ctk.CTkButton(nav_bar, text="🔄", command=self.recargar_datos,
                                           width=40, height=35, fg_color="#3a6ea5")
        self.btn_refrescar.grid(row=0, column=2, padx=10, pady=5)
        crear_tooltip(self.btn_refrescar, "Refrescar catálogos y tabla")

        # ---------- BARRA DE ACCIONES ----------
        actions_bar = ctk.CTkFrame(self, height=40, fg_color="transparent")
        actions_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=5)

        self.btn_eliminar_registro = ctk.CTkButton(actions_bar, text="🗑️ Eliminar registro", command=self.eliminar_registro, width=130, fg_color="#8b0000")
        self.btn_eliminar_registro.pack(side="left", padx=5)
        crear_tooltip(self.btn_eliminar_registro, "Eliminar registro seleccionado del historial")

        self.btn_excel = ctk.CTkButton(actions_bar, text="📊 Exportar Excel", command=self.exportar_excel, width=120, fg_color="#3a6ea5")
        self.btn_excel.pack(side="left", padx=5)
        crear_tooltip(self.btn_excel, "Exportar el historial a Excel")

        self.btn_imprimir = ctk.CTkButton(actions_bar, text="🖨️ Imprimir Reporte", command=self.imprimir_reporte, width=130, fg_color="#2e8b57")
        self.btn_imprimir.pack(side="left", padx=5)
        crear_tooltip(self.btn_imprimir, "Imprimir reporte del pesaje seleccionado")

        self.btn_filtros = ctk.CTkButton(actions_bar, text="🔍 Búsqueda", command=self.toggle_filtros, width=100, fg_color="#1f6aa5")
        self.btn_filtros.pack(side="left", padx=5)
        crear_tooltip(self.btn_filtros, "Mostrar/ocultar filtros de búsqueda")

        # ---------- PANEL DE FILTROS ----------
        self.filtros_frame = ctk.CTkFrame(self, fg_color="#2a2a2a", corner_radius=10)
        self.filtros_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0,10))
        self.filtros_frame.grid_remove()

        search_frame = ctk.CTkFrame(self.filtros_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(search_frame, text="🔍 NÚMERO DE CARGA:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.buscar_carga_entry = ctk.CTkEntry(search_frame, width=200, placeholder_text="Ej: 12345")
        self.buscar_carga_entry.pack(side="left", padx=5)
        self.buscar_carga_entry.bind("<KeyRelease>", self.on_search_key_release)

        ctk.CTkLabel(search_frame, text="LOTE:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.buscar_lote_combo = ttk.Combobox(search_frame, width=150, state="readonly")
        self.buscar_lote_combo.pack(side="left", padx=5)
        self.cargar_lotes_combo()

        fecha_frame = ctk.CTkFrame(self.filtros_frame, fg_color="transparent")
        fecha_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(fecha_frame, text="📅 FECHA DESDE:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.filtro_fecha_desde = DateEntry(fecha_frame, width=12, date_pattern='yyyy-mm-dd')
        self.filtro_fecha_desde.set_date(datetime.now().replace(day=1))
        self.filtro_fecha_desde.pack(side="left", padx=5)
        self.filtro_fecha_desde.bind("<<DateEntrySelected>>", lambda e: self.aplicar_filtros())

        ctk.CTkLabel(fecha_frame, text="HASTA:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.filtro_fecha_hasta = DateEntry(fecha_frame, width=12, date_pattern='yyyy-mm-dd')
        self.filtro_fecha_hasta.set_date(datetime.now())
        self.filtro_fecha_hasta.pack(side="left", padx=5)
        self.filtro_fecha_hasta.bind("<<DateEntrySelected>>", lambda e: self.aplicar_filtros())

        btn_aplicar = ctk.CTkButton(fecha_frame, text="APLICAR FILTROS", command=self.aplicar_filtros, width=120, fg_color="#3a6ea5")
        btn_aplicar.pack(side="left", padx=10)
        crear_tooltip(btn_aplicar, "Filtrar el historial de pesajes")

        # ========== CONTENEDOR PRINCIPAL (TRES COLUMNAS) ==========
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)

        main_container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_columnconfigure(2, weight=1)

        # ---------- COLUMNA 1: DATOS GENERALES + BÁSCULA ----------
        col1 = ctk.CTkFrame(main_container, fg_color="transparent", corner_radius=15)
        col1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        frame_gen = self._crear_tarjeta(col1, "📋 DATOS GENERALES")
        grid_gen = ctk.CTkFrame(frame_gen, fg_color="transparent")
        grid_gen.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(grid_gen, text="FECHA:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.fecha_entry = DateEntry(grid_gen, width=12, date_pattern='yyyy-mm-dd')
        self.fecha_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.fecha_entry.set_date(datetime.now())

        ctk.CTkLabel(grid_gen, text="CARGA:", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.carga_combo = ttk.Combobox(grid_gen, width=20, state="normal")
        self.carga_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.carga_combo.bind("<<ComboboxSelected>>", self.on_carga_seleccionada)

        ctk.CTkLabel(grid_gen, text="LOTE:", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.lote_combo = ttk.Combobox(grid_gen, width=20, state="readonly")
        self.lote_combo.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.lote_combo.bind("<<ComboboxSelected>>", self.on_lote_seleccionado)

        ctk.CTkLabel(grid_gen, text="VARIEDAD:", font=("Arial", 12, "bold")).grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.variedad_combo = ttk.Combobox(grid_gen, width=20, state="readonly")
        self.variedad_combo.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(grid_gen, text="JABAS TOTALES:", font=("Arial", 12, "bold")).grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.lbl_jabas_ingresadas = ctk.CTkLabel(grid_gen, text="0", font=("Arial", 12, "bold"), text_color="#2e8b57")
        self.lbl_jabas_ingresadas.grid(row=4, column=1, padx=5, pady=5, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(frame_gen, width=200, height=10)
        self.progress_bar.pack(pady=5, padx=10)
        self.lbl_progreso = ctk.CTkLabel(frame_gen, text="0 / 0 jabas", font=("Arial", 10))
        self.lbl_progreso.pack(pady=2)

        frame_bascula = self._crear_tarjeta(col1, "⚖️ BÁSCULA")
        bascula_frame = ctk.CTkFrame(frame_bascula, fg_color="transparent")
        bascula_frame.pack(fill="x", padx=10, pady=5)

        self.peso_label = ctk.CTkLabel(bascula_frame, text="0.00", font=("Arial", 48, "bold"), text_color="#2e8b57")
        self.peso_label.pack(pady=10)
        ctk.CTkLabel(bascula_frame, text="kilogramos", font=("Arial", 12)).pack()

        btn_frame = ctk.CTkFrame(bascula_frame, fg_color="transparent")
        btn_frame.pack(pady=10)
        self.btn_obtener = ctk.CTkButton(btn_frame, text="🔄 OBTENER (F2)", command=self.obtener_y_agregar_con_deteccion, width=130)
        self.btn_obtener.pack(side="left", padx=5)
        self.btn_manual = ctk.CTkButton(btn_frame, text="📥 MANUAL (F3)", command=self.agregar_tanda, width=100)
        self.btn_manual.pack(side="left", padx=5)

        # ---------- COLUMNA 2: JABAS + OBSERVACIONES + TANDAS ----------
        col2 = ctk.CTkFrame(main_container, fg_color="transparent", corner_radius=15)
        col2.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        frame_jabas = self._crear_tarjeta(col2, "📦 JABAS")
        jabas_frame = ctk.CTkFrame(frame_jabas, fg_color="transparent")
        jabas_frame.pack(fill="x", padx=10, pady=5)

        self.jabas_buttons = []
        self.jabas_var = ctk.IntVar(value=1)
        for i in range(1, 8):
            btn = ctk.CTkButton(jabas_frame, text=str(i), width=50, height=40, font=("Arial", 14, "bold"),
                                command=lambda v=i: self.set_jabas(v))
            btn.pack(side="left", padx=3, pady=5)
            self.jabas_buttons.append(btn)
        self.resaltar_jabas(1)

        btn_config = ctk.CTkButton(jabas_frame, text="⚙️", width=40, command=self.configurar_peso_jaba)
        btn_config.pack(side="left", padx=5)
        crear_tooltip(btn_config, "Configurar peso de tara por jaba (solo para detección)")

        frame_obs = self._crear_tarjeta(col2, "📝 OBSERVACIONES")
        self.observaciones_entry = ctk.CTkEntry(frame_obs, width=250, placeholder_text="Observaciones para esta tanda")
        self.observaciones_entry.pack(padx=10, pady=5, fill="x")

        frame_tandas = self._crear_tarjeta(col2, "📋 TANDAS AGREGADAS")
        self.tandas_scroll = ctk.CTkScrollableFrame(frame_tandas, height=150, fg_color="transparent")
        self.tandas_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        self.actualizar_lista_tandas()

        # ---------- COLUMNA 3: TOTALES + ACCIONES ----------
        col3 = ctk.CTkFrame(main_container, fg_color="transparent", corner_radius=15)
        col3.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

        frame_totales = self._crear_tarjeta(col3, "📊 TOTALES")
        total_frame = ctk.CTkFrame(frame_totales, fg_color="transparent")
        total_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(total_frame, text="NETO:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.lbl_total_neto = ctk.CTkLabel(total_frame, text="0.00 kg", font=("Arial", 12, "bold"), text_color="#2e8b57")
        self.lbl_total_neto.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        ctk.CTkLabel(total_frame, text="JABAS:", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.lbl_total_jabas = ctk.CTkLabel(total_frame, text="0", font=("Arial", 12, "bold"), text_color="#2e8b57")
        self.lbl_total_jabas.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        ctk.CTkLabel(total_frame, text="TANDAS:", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=5, pady=2, sticky="e")
        self.lbl_total_tandas = ctk.CTkLabel(total_frame, text="0", font=("Arial", 12, "bold"), text_color="#2e8b57")
        self.lbl_total_tandas.grid(row=2, column=1, padx=5, pady=2, sticky="w")

        frame_acciones = self._crear_tarjeta(col3, "⚡ ACCIONES")
        acciones_frame = ctk.CTkFrame(frame_acciones, fg_color="transparent")
        acciones_frame.pack(fill="x", padx=10, pady=10)

        self.btn_agregar_manual = ctk.CTkButton(acciones_frame, text="➕ AGREGAR (F3)", command=self.agregar_tanda, fg_color="#2e8b57")
        self.btn_agregar_manual.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_agregar_manual, "Agregar tanda con el peso actual (F3)")

        self.btn_guardar = ctk.CTkButton(acciones_frame, text="💾 GUARDAR (F10)", command=self.guardar_pesaje, fg_color="#2e8b57")
        self.btn_guardar.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_guardar, "Guardar todas las tandas pendientes (F10)")

        self.btn_cancelar = ctk.CTkButton(acciones_frame, text="❌ CANCELAR TODO", command=self.cancelar_todo, fg_color="#8b0000")
        self.btn_cancelar.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_cancelar, "Cancelar y limpiar todas las tandas pendientes")

        # ---------- HISTORIAL ----------
        historial_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent", corner_radius=15)
        historial_frame.pack(fill="both", expand=True, pady=10)

        self._crear_tarjeta(historial_frame, "📜 HISTORIAL DE PESAJE LAVADO")

        tree_container = ctk.CTkFrame(historial_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=5)

        columnas_hist = ("ID", "Fecha", "N° Carga", "Lote", "Variedad", "Tandas", "Total Neto (kg)", "Jabas", "Usuario")
        self.tree_historial = ttk.Treeview(tree_container, columns=columnas_hist, show="headings", height=10)
        for col in columnas_hist:
            self.tree_historial.heading(col, text=col)
            self.tree_historial.column(col, width=100, anchor="center")
        self.tree_historial.column("Total Neto (kg)", width=120)
        self.tree_historial.column("Jabas", width=80)
        self.tree_historial.pack(side="left", fill="both", expand=True)

        vsb_hist = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_historial.yview)
        vsb_hist.pack(side="right", fill="y")
        self.tree_historial.configure(yscrollcommand=vsb_hist.set)

        self.bind("<F2>", lambda e: self.obtener_y_agregar_con_deteccion())
        self.bind("<F3>", lambda e: self.agregar_tanda())
        self.bind("<F10>", lambda e: self.guardar_pesaje())
        self.bind("<Delete>", lambda e: self.eliminar_ultima_tanda())

        self.cargar_lista_cargas()
        self.cargar_historial()
        self.peso_manual = 0.0

    # ========== FUNCIONES AUXILIARES ==========
    def _crear_tarjeta(self, parent, titulo):
        frame = ctk.CTkFrame(parent, fg_color=("#f5f5f5", "#2a2a2a"), corner_radius=10, border_width=1, border_color="#2e8b57")
        frame.pack(fill="x", pady=5, padx=5)
        ctk.CTkLabel(frame, text=titulo, font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", padx=10, pady=(5,0))
        return frame

    def _asegurar_tabla_pesaje(self):
        try:
            ejecutar_consulta("ALTER TABLE pesaje_lavado ADD COLUMN IF NOT EXISTS num_jabas INTEGER DEFAULT 0")
        except: pass

    def _crear_tabla_configuracion(self):
        ejecutar_consulta("""
            CREATE TABLE IF NOT EXISTS configuracion_pesaje (
                id INTEGER PRIMARY KEY DEFAULT 1,
                jabas_1 DECIMAL(10,2) DEFAULT 5.0,
                jabas_2 DECIMAL(10,2) DEFAULT 5.0,
                jabas_3 DECIMAL(10,2) DEFAULT 5.0,
                jabas_4 DECIMAL(10,2) DEFAULT 5.0,
                jabas_5 DECIMAL(10,2) DEFAULT 5.0,
                jabas_6 DECIMAL(10,2) DEFAULT 5.0,
                jabas_7 DECIMAL(10,2) DEFAULT 5.0
            )
        """)

    def cargar_lista_cargas(self):
        query = "SELECT DISTINCT numero_carga FROM recepcion_carga WHERE estatus != 'CANCELADA' ORDER BY numero_carga DESC"
        res = ejecutar_consulta(query, fetchall=True)
        self.carga_combo['values'] = [r[0] for r in res] if res else []

    def cargar_lotes_por_carga(self, numero_carga):
        query = """
            SELECT r.id, l.numero_lote, r.variedad, r.cajas_llenas
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            WHERE r.numero_carga = %s AND r.estatus != 'CANCELADA'
            ORDER BY l.numero_lote
        """
        res = ejecutar_consulta(query, (numero_carga,), fetchall=True)
        lotes = []
        for r in res:
            if r[1]:
                lotes.append({"id_recepcion": r[0], "numero_lote": r[1], "variedad": r[2] or "", "cajas_llenas": r[3] or 0})
        return lotes

    def on_carga_seleccionada(self, event=None):
        nueva_carga = self.carga_combo.get().strip()
        if not nueva_carga:
            return
        if self.tandas_pendientes:
            resp = messagebox.askyesnocancel("Tandas pendientes",
                "Hay tandas sin guardar. ¿Desea guardarlas antes de cambiar de carga?")
            if resp is None:
                self.carga_combo.set(self.carga_anterior if hasattr(self, 'carga_anterior') else "")
                return
            elif resp:
                self.guardar_pesaje()
            else:
                self.cancelar_todo()
        self.carga_anterior = nueva_carga
        self.id_recepcion = None
        self.variedad_actual = ""
        self.lote_combo.set('')
        self.variedad_combo.set('')
        self.lbl_jabas_ingresadas.configure(text="0")
        self.jabas_totales = 0
        self.actualizar_progreso()
        self.lotes_por_carga.clear()

        lotes = self.cargar_lotes_por_carga(nueva_carga)
        if not lotes:
            messagebox.showwarning("Sin lotes", f"La carga '{nueva_carga}' no tiene lotes registrados o está cancelada.")
            self.lote_combo['values'] = []
            return

        valores_combo = []
        for lote in lotes:
            texto = lote["numero_lote"]
            self.lotes_por_carga[texto] = {
                "id_recepcion": lote["id_recepcion"],
                "variedad": lote["variedad"],
                "cajas_llenas": lote["cajas_llenas"]
            }
            valores_combo.append(texto)
        self.lote_combo['values'] = valores_combo
        if valores_combo:
            self.lote_combo.set(valores_combo[0])
            self.on_lote_seleccionado()

    def on_lote_seleccionado(self, event=None):
        sel = self.lote_combo.get()
        if sel in self.lotes_por_carga:
            datos = self.lotes_por_carga[sel]
            self.id_recepcion = datos["id_recepcion"]
            self.variedad_actual = datos["variedad"]
            self.variedad_combo.set(datos["variedad"].title() if datos["variedad"] else "")
            self.jabas_totales = datos["cajas_llenas"]
            self.lbl_jabas_ingresadas.configure(text=str(self.jabas_totales))
            self.actualizar_progreso()

    def cargar_configuracion_pesaje(self):
        res = ejecutar_consulta("SELECT jabas_1,jabas_2,jabas_3,jabas_4,jabas_5,jabas_6,jabas_7 FROM configuracion_pesaje WHERE id=1", fetchone=True)
        if res:
            for i in range(1,8):
                self.peso_jabas[i] = float(res[i-1]) if res[i-1] is not None else 5.0
        else:
            ejecutar_consulta("INSERT INTO configuracion_pesaje (id) VALUES (1)")

    def guardar_configuracion_pesaje(self, valores):
        ejecutar_consulta("UPDATE configuracion_pesaje SET jabas_1=%s, jabas_2=%s, jabas_3=%s, jabas_4=%s, jabas_5=%s, jabas_6=%s, jabas_7=%s WHERE id=1", valores)
        for i, v in enumerate(valores, start=1):
            self.peso_jabas[i] = v

    def configurar_peso_jaba(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Configurar peso de tara por jaba (solo para detección)")
        modal.geometry("400x350")
        modal.grab_set()
        ctk.CTkLabel(modal, text="Peso de tara (kg) para cada número de jabas:", font=("Arial", 14)).pack(pady=10)
        entries = {}
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(pady=10, padx=20, fill="both", expand=True)
        for i in range(1,8):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=f"{i} jaba{'s' if i>1 else ''}:", width=80).pack(side="left", padx=5)
            entry = ctk.CTkEntry(row, width=100)
            entry.insert(0, str(self.peso_jabas[i]))
            entry.pack(side="left", padx=5)
            entries[i] = entry
        def guardar():
            nuevos = []
            try:
                for i in range(1,8):
                    val = float(entries[i].get())
                    if val < 0: raise ValueError
                    nuevos.append(val)
                self.guardar_configuracion_pesaje(nuevos)
                messagebox.showinfo("Configuración", "Pesos de tara actualizados.")
                modal.destroy()
            except:
                messagebox.showerror("Error", "Ingrese valores numéricos válidos (≥0).")
        ctk.CTkButton(modal, text="Guardar", command=guardar, fg_color="#2e8b57", width=100).pack(pady=20)

    def set_jabas(self, valor):
        self.jabas_var.set(valor)
        self.resaltar_jabas(valor)

    def resaltar_jabas(self, seleccionado):
        for i, btn in enumerate(self.jabas_buttons, start=1):
            btn.configure(fg_color="#2e8b57" if i == seleccionado else ("#3a3a3a", "#565656"),
                          hover_color="#236b43" if i == seleccionado else ("#4a4a4a", "#6a6a6a"))

    def obtener_y_agregar_con_deteccion(self):
        if not self.bascula.conexion or not self.bascula.conexion.is_open:
            exito, _ = self.bascula.conectar()
            if not exito:
                messagebox.showerror("Error", "No se pudo conectar a la báscula.")
                return
        peso, _ = self.bascula.leer_peso()
        if peso is None:
            messagebox.showwarning("Sin lectura", "No se detectó peso.")
            return
        self.peso_label.configure(text=f"{peso:.2f}")
        self.peso_manual = peso
        self.detectar_y_ajustar_jabas(peso)
        self.agregar_tanda()

    def detectar_y_ajustar_jabas(self, peso_neto):
        if self.id_recepcion is None: return
        variedad = self.variedad_actual.lower()
        peso_neto_por_jaba = 18.0 if "ataulfo" in variedad else 16.0
        mejor_n = 1
        menor = float('inf')
        for n in range(1,8):
            esperado = n * peso_neto_por_jaba
            diff = abs(peso_neto - esperado)
            if diff < menor:
                menor = diff
                mejor_n = n
        self.set_jabas(mejor_n)

    def agregar_tanda(self):
        if self.id_recepcion is None:
            messagebox.showerror("Recepción requerida", "Seleccione carga y lote.")
            return
        neto = getattr(self, 'peso_manual', 0.0)
        if neto == 0.0:
            if messagebox.askyesno("Peso no detectado", "¿Ingresar peso manualmente?"):
                self.pedir_peso_manual()
            return
        jabas = self.jabas_var.get()
        obs = self.observaciones_entry.get().strip()
        tanda_num = self.siguiente_tanda
        for p in self.tandas_pendientes:
            if p["tanda"] == tanda_num:
                messagebox.showerror("Duplicado", f"Tanda {tanda_num} ya agregada.")
                return
        self.tandas_pendientes.append({
            "tanda": tanda_num,
            "neto": neto,
            "jabas": jabas,
            "observaciones": obs
        })
        self.siguiente_tanda += 1
        self.actualizar_lista_tandas()
        self.actualizar_totales()
        self.peso_label.configure(text="0.00")
        self.peso_manual = 0.0
        self.observaciones_entry.delete(0, "end")
        self.set_jabas(1)
        messagebox.showinfo("Agregado", f"Tanda {tanda_num} agregada.")

    def pedir_peso_manual(self):
        peso = simpledialog.askfloat("Peso manual", "Ingrese peso neto (kg):", parent=self, minvalue=0.0)
        if peso is not None:
            self.peso_label.configure(text=f"{peso:.2f}")
            self.peso_manual = peso
            self.detectar_y_ajustar_jabas(peso)
            self.agregar_tanda()

    def actualizar_lista_tandas(self):
        for w in self.tandas_scroll.winfo_children():
            w.destroy()
        for idx, p in enumerate(self.tandas_pendientes):
            frame = ctk.CTkFrame(self.tandas_scroll, fg_color="transparent", corner_radius=8)
            frame.pack(fill="x", pady=2)
            texto = f"Tanda {p['tanda']}: {p['neto']:.2f} kg ({p['jabas']} jabas)"
            if p['observaciones']:
                texto += f" - {p['observaciones']}"
            lbl = ctk.CTkLabel(frame, text=texto, anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=5, pady=2)
            # Botón editar (usará nueva ventana con pestañas)
            btn_edit = ctk.CTkButton(frame, text="✏️", width=30, command=lambda i=idx: self.editar_tanda(i))
            btn_edit.pack(side="right", padx=2)
            # Botón eliminar
            btn_del = ctk.CTkButton(frame, text="✖", width=30, command=lambda i=idx: self.eliminar_tanda_individual(i))
            btn_del.pack(side="right", padx=2)
            crear_tooltip(btn_edit, "Editar tanda (peso, jabas, observaciones)")
            crear_tooltip(btn_del, "Eliminar esta tanda")

    # ========== NUEVO EDITOR DE TANDA CON PESTAÑAS (PESO + JABAS) ==========
    def editar_tanda(self, idx):
        if idx < 0 or idx >= len(self.tandas_pendientes):
            return
        tanda = self.tandas_pendientes[idx]
        top = ctk.CTkToplevel(self)
        top.title(f"Editar Tanda {tanda['tanda']}")
        top.geometry("550x500")
        top.grab_set()
        top.resizable(False, False)

        # Variables temporales
        temp_peso = ctk.DoubleVar(value=tanda['neto'])
        temp_jabas = ctk.IntVar(value=tanda['jabas'])
        temp_obs = ctk.StringVar(value=tanda['observaciones'])

        # Repesaje con báscula
        def repesar():
            if not self.bascula.conexion or not self.bascula.conexion.is_open:
                exito, _ = self.bascula.conectar()
                if not exito:
                    messagebox.showerror("Error", "No se pudo conectar a la báscula.")
                    return
            peso_leido, _ = self.bascula.leer_peso()
            if peso_leido is None:
                messagebox.showwarning("Sin lectura", "No se detectó peso en la báscula.")
                return
            temp_peso.set(peso_leido)
            entry_peso.delete(0, "end")
            entry_peso.insert(0, f"{peso_leido:.2f}")
            if self.id_recepcion:
                variedad_temp = self.variedad_actual.lower()
                peso_neto_por_jaba = 18.0 if "ataulfo" in variedad_temp else 16.0
                mejor_n = 1
                menor = float('inf')
                for n in range(1, 8):
                    esperado = n * peso_neto_por_jaba
                    diff = abs(peso_leido - esperado)
                    if diff < menor:
                        menor = diff
                        mejor_n = n
                temp_jabas.set(mejor_n)
                for btn in botones_jabas:
                    if int(btn.cget("text")) == mejor_n:
                        btn.configure(fg_color="#2e8b57", hover_color="#236b43")
                    else:
                        btn.configure(fg_color=("#3a3a3a", "#565656"), hover_color=("#4a4a4a", "#6a6a6a"))

        # Crear Tabview
        tabview = ctk.CTkTabview(top, width=500, height=380)
        tabview.pack(padx=20, pady=(20,10), fill="both", expand=True)
        tab_peso = tabview.add("⚖️ Peso")
        tab_jabas = tabview.add("📦 Jabas")

        # ========== PESTAÑA PESO ==========
        frame_peso = ctk.CTkFrame(tab_peso, fg_color="transparent")
        frame_peso.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame_peso, text="Peso neto (kg):", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0,5))
        entry_peso = ctk.CTkEntry(frame_peso, width=150, textvariable=temp_peso)
        entry_peso.pack(anchor="w", pady=5)
        btn_repesar = ctk.CTkButton(frame_peso, text="🔄 Obtener peso de báscula", command=repesar, width=200)
        btn_repesar.pack(anchor="w", pady=10)

        ctk.CTkLabel(frame_peso, text="Observaciones:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(15,5))
        entry_obs = ctk.CTkEntry(frame_peso, width=400, textvariable=temp_obs, placeholder_text="Observaciones")
        entry_obs.pack(anchor="w", fill="x", pady=5)

        # ========== PESTAÑA JABAS (botones en cuadrícula 2x4) ==========
        frame_jabas_tab = ctk.CTkFrame(tab_jabas, fg_color="transparent")
        frame_jabas_tab.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame_jabas_tab, text="Número de jabas:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0,10))

        grid_frame = ctk.CTkFrame(frame_jabas_tab, fg_color="transparent")
        grid_frame.pack(anchor="center", pady=10)

        botones_jabas = []
        def seleccionar_jabas_btn(valor):
            temp_jabas.set(valor)
            for btn in botones_jabas:
                if int(btn.cget("text")) == valor:
                    btn.configure(fg_color="#2e8b57", hover_color="#236b43")
                else:
                    btn.configure(fg_color=("#3a3a3a", "#565656"), hover_color=("#4a4a4a", "#6a6a6a"))

        for i in range(1, 8):
            btn = ctk.CTkButton(grid_frame, text=str(i), width=70, height=70, font=("Arial", 18, "bold"),
                                command=lambda v=i: seleccionar_jabas_btn(v))
            fila = 0 if i <= 4 else 1
            col = (i-1) % 4
            btn.grid(row=fila, column=col, padx=5, pady=5)
            botones_jabas.append(btn)
        # Inicializar resaltado
        seleccionar_jabas_btn(temp_jabas.get())
        # Sincronizar cuando temp_jabas cambie por repesaje
        def on_temp_jabas_change(*args):
            seleccionar_jabas_btn(temp_jabas.get())
        temp_jabas.trace_add("write", on_temp_jabas_change)

        # ========== BOTONES GUARDAR Y CANCELAR ==========
        btn_frame = ctk.CTkFrame(top, fg_color="transparent")
        btn_frame.pack(pady=15, fill="x")
        btn_guardar = ctk.CTkButton(btn_frame, text="Guardar cambios", command=lambda: guardar_edicion(), fg_color="#2e8b57", width=120)
        btn_guardar.pack(side="right", padx=10)
        btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=top.destroy, fg_color="#8b0000", width=100)
        btn_cancelar.pack(side="right", padx=10)

        def guardar_edicion():
            try:
                nuevo_peso = temp_peso.get()
                if nuevo_peso < 0:
                    raise ValueError
            except:
                messagebox.showerror("Error", "Peso inválido.")
                return
            nuevas_jabas = temp_jabas.get()
            nueva_obs = temp_obs.get().strip()
            self.tandas_pendientes[idx]["neto"] = nuevo_peso
            self.tandas_pendientes[idx]["jabas"] = nuevas_jabas
            self.tandas_pendientes[idx]["observaciones"] = nueva_obs
            self.actualizar_lista_tandas()
            self.actualizar_totales()
            top.destroy()
            messagebox.showinfo("Editado", "Tanda actualizada correctamente.")

    def eliminar_tanda_individual(self, idx):
        del self.tandas_pendientes[idx]
        for i, p in enumerate(self.tandas_pendientes):
            p["tanda"] = i+1
        self.siguiente_tanda = len(self.tandas_pendientes)+1
        self.actualizar_lista_tandas()
        self.actualizar_totales()

    def eliminar_ultima_tanda(self):
        if self.tandas_pendientes:
            self.tandas_pendientes.pop()
            self.siguiente_tanda = len(self.tandas_pendientes)+1
            self.actualizar_lista_tandas()
            self.actualizar_totales()
            messagebox.showinfo("Eliminada", "Última tanda eliminada.")
        else:
            messagebox.showwarning("Sin tandas", "No hay tandas pendientes.")

    def actualizar_totales(self):
        total_neto = sum(p["neto"] for p in self.tandas_pendientes)
        total_jabas = sum(p["jabas"] for p in self.tandas_pendientes)
        cant = len(self.tandas_pendientes)
        self.lbl_total_neto.configure(text=f"{total_neto:.2f} kg")
        self.lbl_total_jabas.configure(text=str(total_jabas))
        self.lbl_total_tandas.configure(text=str(cant))
        self.actualizar_progreso()

    def actualizar_progreso(self):
        if self.jabas_totales == 0:
            self.progress_bar.set(0)
            self.lbl_progreso.configure(text="0 / 0 jabas")
            return
        procesadas = sum(p["jabas"] for p in self.tandas_pendientes)
        if procesadas > self.jabas_totales:
            procesadas = self.jabas_totales
        self.progress_bar.set(procesadas / self.jabas_totales)
        self.lbl_progreso.configure(text=f"{procesadas} / {self.jabas_totales} jabas")

    def guardar_pesaje(self):
        if self.id_recepcion is None:
            messagebox.showerror("Error", "Seleccione carga y lote.")
            return
        if not self.tandas_pendientes:
            messagebox.showwarning("Sin tandas", "No hay tandas para guardar.")
            return
        fecha = self.fecha_entry.get_date()
        usuario = "admin"
        try:
            with open("session_user.txt","r") as f:
                usuario = f.read().strip().split("|")[0]
        except: pass
        try:
            for p in self.tandas_pendientes:
                ejecutar_consulta("""
                    INSERT INTO pesaje_lavado
                    (id_recepcion, fecha, tanda_numero, bruto, tara, neto, num_jabas, observaciones, usuario_creacion, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (self.id_recepcion, fecha, p["tanda"], p["neto"], 0, p["neto"],
                      p["jabas"], p["observaciones"], usuario, datetime.now()))
            messagebox.showinfo("Éxito", f"Se guardaron {len(self.tandas_pendientes)} tanda(s).")
            self.cancelar_todo()
            self.cargar_historial()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {str(e)}")

    def cancelar_todo(self):
        self.id_recepcion = None
        self.variedad_actual = ""
        self.carga_combo.set("")
        self.lote_combo['values'] = []
        self.lote_combo.set("")
        self.variedad_combo['values'] = []
        self.variedad_combo.set("")
        self.lbl_jabas_ingresadas.configure(text="0")
        self.jabas_totales = 0
        self.tandas_pendientes.clear()
        self.siguiente_tanda = 1
        self.actualizar_lista_tandas()
        self.actualizar_totales()
        self.peso_label.configure(text="0.00")
        self.peso_manual = 0.0
        self.observaciones_entry.delete(0,"end")
        self.set_jabas(1)
        self.progress_bar.set(0)
        self.lbl_progreso.configure(text="0 / 0 jabas")
        self.fecha_entry.set_date(datetime.now())
        self.lotes_por_carga.clear()

    def cargar_historial(self, filtros=None):
        for item in self.tree_historial.get_children():
            self.tree_historial.delete(item)
        cond = []
        params = []
        if filtros:
            if filtros.get("carga"):
                cond.append("rc.numero_carga ILIKE %s")
                params.append(f"%{filtros['carga']}%")
            if filtros.get("lote"):
                cond.append("l.numero_lote = %s")
                params.append(filtros['lote'])
            if filtros.get("fecha_desde") and filtros.get("fecha_hasta"):
                cond.append("pl.fecha BETWEEN %s AND %s")
                params.append(filtros['fecha_desde'])
                params.append(filtros['fecha_hasta'])
        where = " AND ".join(cond) if cond else "1=1"
        query = f"""
            SELECT pl.id, pl.fecha, rc.numero_carga, l.numero_lote, rc.variedad,
                   COUNT(*) as tandas, SUM(pl.neto) as total_neto, SUM(pl.num_jabas) as total_jabas,
                   pl.usuario_creacion
            FROM pesaje_lavado pl
            JOIN recepcion_carga rc ON pl.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE {where}
            GROUP BY pl.id, pl.fecha, rc.numero_carga, l.numero_lote, rc.variedad, pl.usuario_creacion
            ORDER BY pl.fecha DESC
        """
        res = ejecutar_consulta(query, tuple(params), fetchall=True)
        for r in res:
            self.tree_historial.insert("", "end", values=(
                r[0], r[1].strftime("%d/%m/%Y") if r[1] else "", r[2], r[3] or "",
                r[4].title() if r[4] else "", r[5], f"{r[6]:.2f}", r[7] or 0, r[8] or "admin"
            ), tags=(r[0],))

    def aplicar_filtros(self):
        filtros = {}
        carga = self.buscar_carga_entry.get().strip()
        if carga: filtros["carga"] = carga
        lote = self.buscar_lote_combo.get()
        if lote: filtros["lote"] = lote
        if self.filtro_fecha_desde.get_date() and self.filtro_fecha_hasta.get_date():
            filtros["fecha_desde"] = self.filtro_fecha_desde.get_date()
            filtros["fecha_hasta"] = self.filtro_fecha_hasta.get_date()
        self.cargar_historial(filtros)

    def on_search_key_release(self, event):
        if self.search_after_id:
            self.after_cancel(self.search_after_id)
        self.search_after_id = self.after(500, self.aplicar_filtros)

    def toggle_filtros(self):
        if self.filtros_visibles:
            self.filtros_frame.grid_remove()
            self.filtros_visibles = False
            self.btn_filtros.configure(text="🔍 Búsqueda", fg_color="#1f6aa5")
        else:
            self.filtros_frame.grid()
            self.filtros_visibles = True
            self.btn_filtros.configure(text="✖ Ocultar", fg_color="#8b0000")

    def recargar_datos(self):
        self.cargar_historial()
        self.cargar_lista_cargas()
        self.cargar_lotes_combo()
        messagebox.showinfo("Actualizado", "Datos actualizados.")

    def cargar_lotes_combo(self):
        res = ejecutar_consulta("SELECT DISTINCT l.numero_lote FROM lotes l JOIN recepcion_carga rc ON rc.lote_id = l.id", fetchall=True)
        self.buscar_lote_combo['values'] = [r[0] for r in res] if res else []

    def eliminar_registro(self):
        if not tiene_permiso(self.permisos, "pesaje_lavado", "eliminar"):
            messagebox.showerror("Permiso", "No tiene permiso.")
            return
        sel = self.tree_historial.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un registro.")
            return
        id_ = self.tree_historial.item(sel[0])['tags'][0]
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro y todas sus tandas?"):
            try:
                ejecutar_consulta("DELETE FROM pesaje_lavado WHERE id = %s", (id_,))
                messagebox.showinfo("Eliminado", "Registro eliminado.")
                self.cargar_historial()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def exportar_excel(self):
        datos = self.tree_historial.get_children()
        if not datos:
            messagebox.showwarning("Sin datos", "No hay registros.")
            return
        cols = [self.tree_historial.heading(c)['text'] for c in self.tree_historial["columns"]]
        filas = [self.tree_historial.item(item)["values"] for item in datos]
        df = pd.DataFrame(filas, columns=cols)
        archivo = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel","*.xlsx")])
        if archivo:
            df.to_excel(archivo, index=False)
            messagebox.showinfo("Exportado", f"Guardado en {archivo}")

    def imprimir_reporte(self):
        messagebox.showinfo("Reporte", "Funcionalidad en desarrollo.")

    def regresar_menu(self):
        if self.on_regresar:
            self.on_regresar()
        self.destroy()

if __name__ == "__main__":
    pass