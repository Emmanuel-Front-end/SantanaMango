# modulos/pesaje_rezaga.py - Versión mejorada con edición de tandas guardadas y detección automática de jabas
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import ejecutar_consulta
from datetime import datetime
from tkcalendar import DateEntry
import pandas as pd
from utils.tooltip import crear_tooltip
from utils.bascula import Bascula
from auth import tiene_permiso

class VentanaPesajeRezaga(ctk.CTkFrame):
    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.pack(fill="both", expand=True)

        if not tiene_permiso(permisos, "pesaje_rezaga", "leer"):
            ctk.CTkLabel(self, text="⚠️ No tiene permisos para acceder a Pesaje Rezaga",
                        font=("Arial", 20), text_color="red").pack(expand=True)
            return

        # Variables internas
        self.id_recepcion = None
        self.variedad_actual = ""
        self.tandas_pendientes = []      # Para tandas nuevas (pendientes de guardar)
        self.siguiente_tanda = 1
        self.bascula = Bascula()
        self.filtros_visibles = False
        self.search_after_id = None
        self.peso_jabas = {i: 5.0 for i in range(1, 8)}
        self.jabas_totales = 0
        self.lotes_por_carga = {}
        self.danos_texto = ""
        self.modo_edicion = False        # True cuando se está editando una tanda existente
        self.id_tanda_edicion = None     # ID de la tanda que se está editando

        self._asegurar_tabla_rezaga()
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

        ctk.CTkLabel(nav_bar, text="📉 PESAJE REZAGA", font=("Arial", 20, "bold"),
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

        self.btn_editar_registro = ctk.CTkButton(actions_bar, text="✏️ Editar", command=self.cargar_tanda_para_editar, width=100, fg_color="#2e8b57")
        self.btn_editar_registro.pack(side="left", padx=5)
        crear_tooltip(self.btn_editar_registro, "Cargar la tanda seleccionada en el formulario para editarla")

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
        self.carga_combo = ttk.Combobox(grid_gen, width=20, state="readonly")
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

        # Frame para peso (label normal y entry editable para edición)
        frame_bascula = self._crear_tarjeta(col1, "⚖️ BÁSCULA")
        bascula_frame = ctk.CTkFrame(frame_bascula, fg_color="transparent")
        bascula_frame.pack(fill="x", padx=10, pady=5)

        self.peso_label = ctk.CTkLabel(bascula_frame, text="0.00", font=("Arial", 48, "bold"), text_color="#2e8b57")
        self.peso_label.pack(pady=10)

        # Entry para editar peso (oculto inicialmente)
        self.peso_edit_entry = ctk.CTkEntry(bascula_frame, font=("Arial", 48), justify="center", fg_color="#2a2a2a", text_color="#2e8b57")
        self.peso_edit_entry.pack(pady=10)
        self.peso_edit_entry.pack_forget()

        ctk.CTkLabel(bascula_frame, text="kilogramos", font=("Arial", 12)).pack()

        btn_frame = ctk.CTkFrame(bascula_frame, fg_color="transparent")
        btn_frame.pack(pady=10)
        self.btn_obtener = ctk.CTkButton(btn_frame, text="🔄 OBTENER (F2)", command=self.obtener_peso_edicion_o_nuevo, width=130)
        self.btn_obtener.pack(side="left", padx=5)
        self.btn_manual = ctk.CTkButton(btn_frame, text="📥 MANUAL (F3)", command=self.manual_peso_edicion_o_nuevo, width=100)
        self.btn_manual.pack(side="left", padx=5)

        # ---------- COLUMNA 2: JABAS + OBSERVACIONES + TANDAS PENDIENTES ----------
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

        frame_tandas = self._crear_tarjeta(col2, "📋 TANDAS POR GUARDAR")
        self.tandas_scroll = ctk.CTkScrollableFrame(frame_tandas, height=150, fg_color="transparent")
        self.tandas_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        self.actualizar_lista_tandas()

        # ---------- COLUMNA 3: DAÑOS + TOTALES + ACCIONES ----------
        col3 = ctk.CTkFrame(main_container, fg_color="transparent", corner_radius=15)
        col3.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

        frame_danos = self._crear_tarjeta(col3, "🌿 DAÑOS DEL LOTE")
        danos_frame = ctk.CTkFrame(frame_danos, fg_color="transparent")
        danos_frame.pack(fill="x", padx=10, pady=5)
        self.danos_resumen_label = ctk.CTkLabel(danos_frame, text="Ninguno", font=("Arial", 11), text_color="gray")
        self.danos_resumen_label.pack(anchor="w", pady=2)
        self.btn_danos = ctk.CTkButton(danos_frame, text="🌿 Seleccionar daños", command=self.seleccionar_danos, width=150)
        self.btn_danos.pack(anchor="w", pady=5)
        crear_tooltip(self.btn_danos, "Seleccionar daños para esta tanda")

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

        self.btn_guardar = ctk.CTkButton(acciones_frame, text="💾 GUARDAR (F10)", command=self.guardar_o_actualizar, fg_color="#2e8b57")
        self.btn_guardar.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_guardar, "Guardar nueva tanda o actualizar la existente (F10)")

        self.btn_cancelar_edicion = ctk.CTkButton(acciones_frame, text="❌ CANCELAR EDICIÓN", command=self.cancelar_edicion, fg_color="#8b0000")
        self.btn_cancelar_edicion.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_cancelar_edicion, "Cancelar edición y limpiar formulario")
        self.btn_cancelar_edicion.pack_forget()

        self.btn_agregar_nueva = ctk.CTkButton(acciones_frame, text="➕ NUEVA TANDA", command=self.nueva_tanda, fg_color="#2e8b57")
        self.btn_agregar_nueva.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_agregar_nueva, "Limpiar formulario para ingresar una nueva tanda")

        self.btn_cancelar_todo = ctk.CTkButton(acciones_frame, text="❌ CANCELAR TODO", command=self.cancelar_todo, fg_color="#8b0000")
        self.btn_cancelar_todo.pack(side="top", padx=5, pady=5, fill="x")
        crear_tooltip(self.btn_cancelar_todo, "Cancelar todas las tandas pendientes")

        # ---------- HISTORIAL ----------
        historial_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent", corner_radius=15)
        historial_frame.pack(fill="both", expand=True, pady=10)

        self._crear_tarjeta(historial_frame, "📜 HISTORIAL DE PESAJE REZAGA")

        tree_container = ctk.CTkFrame(historial_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=5)

        columnas_hist = ("ID", "Fecha", "N° Carga", "Lote", "Kilos Iniciales", "Kilos Rezaga", "% Rezaga", "Operador", "Daños")
        self.tree_historial = ttk.Treeview(tree_container, columns=columnas_hist, show="headings", height=10)
        for col in columnas_hist:
            self.tree_historial.heading(col, text=col)
            self.tree_historial.column(col, width=100, anchor="center")
        self.tree_historial.column("Kilos Iniciales", width=120)
        self.tree_historial.column("Kilos Rezaga", width=120)
        self.tree_historial.column("Daños", width=200)
        self.tree_historial.pack(side="left", fill="both", expand=True)

        vsb_hist = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_historial.yview)
        vsb_hist.pack(side="right", fill="y")
        self.tree_historial.configure(yscrollcommand=vsb_hist.set)

        # Doble clic -> mostrar detalles (con opción de editar)
        self.tree_historial.bind("<Double-1>", self.mostrar_detalles_tanda)

        self.bind("<F2>", lambda e: self.obtener_peso_edicion_o_nuevo())
        self.bind("<F3>", lambda e: self.manual_peso_edicion_o_nuevo())
        self.bind("<F10>", lambda e: self.guardar_o_actualizar())
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

    def _asegurar_tabla_rezaga(self):
        try:
            ejecutar_consulta("ALTER TABLE pesaje_rezaga ADD COLUMN IF NOT EXISTS danos TEXT")
            ejecutar_consulta("ALTER TABLE pesaje_rezaga ADD COLUMN IF NOT EXISTS id_recepcion INTEGER REFERENCES recepcion_carga(id)")
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
        if self.carga_combo['values'] and not self.carga_combo.get():
            self.carga_combo.set(self.carga_combo['values'][0])
            self.on_carga_seleccionada()

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
        if self.tandas_pendientes and not self.modo_edicion:
            resp = messagebox.askyesnocancel("Tandas pendientes",
                "Hay tandas sin guardar. ¿Desea guardarlas antes de cambiar de carga?")
            if resp is None:
                self.carga_combo.set(self.carga_anterior if hasattr(self, 'carga_anterior') else "")
                return
            elif resp:
                self.guardar_o_actualizar()
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

    # ========== MÉTODOS PARA PESO EN EDICIÓN O NUEVA TANDA ==========
    def obtener_peso_edicion_o_nuevo(self):
        """Obtiene peso de la báscula y actualiza el campo correspondiente (label o entry) y recalcula jabas."""
        if not self.bascula.conexion or not self.bascula.conexion.is_open:
            exito, _ = self.bascula.conectar()
            if not exito:
                messagebox.showerror("Error", "No se pudo conectar a la báscula.")
                return
        peso, _ = self.bascula.leer_peso()
        if peso is None:
            messagebox.showwarning("Sin lectura", "No se detectó peso en la báscula.")
            return
        self.actualizar_peso_y_jabas(peso)

    def manual_peso_edicion_o_nuevo(self):
        """Solicita peso manual y actualiza el campo correspondiente y recalcula jabas."""
        peso = simpledialog.askfloat("Peso manual", "Ingrese peso neto (kg):", parent=self, minvalue=0.0)
        if peso is not None:
            self.actualizar_peso_y_jabas(peso)

    def actualizar_peso_y_jabas(self, peso):
        """Actualiza el widget de peso (label o entry) y recalcula jabas según la variedad."""
        if self.modo_edicion:
            self.peso_edit_entry.delete(0, "end")
            self.peso_edit_entry.insert(0, f"{peso:.2f}")
            self.peso_manual = peso
        else:
            self.peso_label.configure(text=f"{peso:.2f}")
            self.peso_manual = peso
        # Recalcular jabas
        if self.id_recepcion:
            variedad = self.variedad_actual.lower()
            peso_neto_por_jaba = 18.0 if "ataulfo" in variedad else 16.0
            mejor_n = 1
            menor = float('inf')
            for n in range(1, 8):
                esperado = n * peso_neto_por_jaba
                diff = abs(peso - esperado)
                if diff < menor:
                    menor = diff
                    mejor_n = n
            self.set_jabas(mejor_n)

    # ========== TANDAS PENDIENTES (modo normal) ==========
    def agregar_tanda(self):
        if self.modo_edicion:
            messagebox.showinfo("Edición activa", "Complete la edición actual o cancele antes de agregar una nueva tanda.")
            return
        if self.id_recepcion is None:
            messagebox.showerror("Recepción requerida", "Seleccione carga y lote.")
            return
        neto = getattr(self, 'peso_manual', 0.0)
        if neto == 0.0:
            if messagebox.askyesno("Peso no detectado", "¿Ingresar peso manualmente?"):
                self.manual_peso_edicion_o_nuevo()
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
        if self.modo_edicion:
            self.peso_edit_entry.delete(0, "end")
            self.peso_edit_entry.insert(0, "0.00")
        else:
            self.peso_label.configure(text="0.00")
        self.peso_manual = 0.0
        self.observaciones_entry.delete(0, "end")
        self.set_jabas(1)
        messagebox.showinfo("Agregado", f"Tanda {tanda_num} agregada.")

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
            btn_edit = ctk.CTkButton(frame, text="✏️", width=30, command=lambda i=idx: self.editar_tanda_pendiente(i))
            btn_edit.pack(side="right", padx=2)
            btn_del = ctk.CTkButton(frame, text="✖", width=30, command=lambda i=idx: self.eliminar_tanda_individual(i))
            btn_del.pack(side="right", padx=2)
            crear_tooltip(btn_edit, "Editar tanda pendiente")
            crear_tooltip(btn_del, "Eliminar tanda pendiente")

    def editar_tanda_pendiente(self, idx):
        if self.modo_edicion:
            messagebox.showinfo("Edición activa", "Termine de editar la tanda actual o cancele.")
            return
        tanda = self.tandas_pendientes[idx]
        if self.modo_edicion:
            self.peso_edit_entry.delete(0, "end")
            self.peso_edit_entry.insert(0, f"{tanda['neto']:.2f}")
        else:
            self.peso_label.configure(text=f"{tanda['neto']:.2f}")
        self.peso_manual = tanda['neto']
        self.set_jabas(tanda['jabas'])
        self.observaciones_entry.delete(0, "end")
        self.observaciones_entry.insert(0, tanda['observaciones'])
        del self.tandas_pendientes[idx]
        self.siguiente_tanda = len(self.tandas_pendientes) + 1
        self.actualizar_lista_tandas()
        self.actualizar_totales()
        messagebox.showinfo("Editar", "Puede modificar peso, jabas y observaciones, luego presione GUARDAR.")

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

    # ========== VENTANA DE DETALLES (Doble clic) ==========
    def mostrar_detalles_tanda(self, event):
        seleccion = self.tree_historial.selection()
        if not seleccion:
            return
        id_tanda = self.tree_historial.item(seleccion[0])['tags'][0]
        # Obtener datos completos con fechas de creación y modificación
        datos = ejecutar_consulta("""
            SELECT pr.id, pr.fecha, rc.numero_carga, l.numero_lote, rc.variedad,
                   pr.kilos_iniciales, pr.kilos_rezaga, pr.porcentaje_rezaga,
                   pr.observaciones, pr.operador, pr.created_at, pr.updated_at, pr.danos
            FROM pesaje_rezaga pr
            JOIN recepcion_carga rc ON pr.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE pr.id = %s
        """, (id_tanda,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", "No se encontraron datos.")
            return
        modal = ctk.CTkToplevel(self)
        modal.title(f"Detalles de la Tanda - Carga {datos[2]}")
        modal.geometry("600x550")
        modal.grab_set()
        main_frame = ctk.CTkFrame(modal, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="📋 INFORMACIÓN DE LA TANDA", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0,10))
        info = [
            f"Fecha: {datos[1].strftime('%d/%m/%Y') if datos[1] else '-'}",
            f"N° Carga: {datos[2]}",
            f"Lote: {datos[3] or '-'}",
            f"Variedad: {datos[4].title() if datos[4] else '-'}",
            f"Kilos Iniciales: {datos[5]:.2f} kg",
            f"Kilos Rezaga: {datos[6]:.2f} kg",
            f"% Rezaga: {datos[7]:.2f}%",
            f"Observaciones: {datos[8] or 'Ninguna'}",
            f"Operador: {datos[9] or 'admin'}",
            f"Daños: {datos[12] or 'Ninguno'}",
            f"Creado: {datos[10].strftime('%d/%m/%Y %H:%M:%S') if datos[10] else '-'}",
            f"Última modificación: {datos[11].strftime('%d/%m/%Y %H:%M:%S') if datos[11] else '-'}"
        ]
        for linea in info:
            ctk.CTkLabel(main_frame, text=linea, font=("Arial", 12), anchor="w").pack(fill="x", pady=2)
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        if tiene_permiso(self.permisos, "pesaje_rezaga", "editar"):
            btn_editar = ctk.CTkButton(btn_frame, text="✏️ Editar tanda", command=lambda: self._editar_desde_detalles(id_tanda, modal), width=120, fg_color="#2e8b57")
            btn_editar.pack(side="left", padx=10)
        btn_cerrar = ctk.CTkButton(btn_frame, text="Cerrar", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cerrar.pack(side="right", padx=10)

    def _editar_desde_detalles(self, id_tanda, modal):
        modal.destroy()
        self.cargar_tanda_para_editar_por_id(id_tanda)

    # ========== EDICIÓN DE TANDAS EXISTENTES ==========
    def cargar_tanda_para_editar(self):
        seleccion = self.tree_historial.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una tanda del historial.")
            return
        item = self.tree_historial.item(seleccion[0])
        id_tanda = item['tags'][0] if item['tags'] else None
        if not id_tanda:
            messagebox.showerror("Error", "No se pudo identificar la tanda.")
            return
        self.cargar_tanda_para_editar_por_id(id_tanda)

    def cargar_tanda_para_editar_por_id(self, id_tanda):
        # Obtener datos de la tanda
        datos = ejecutar_consulta("""
            SELECT pr.id, pr.fecha, rc.numero_carga, l.numero_lote, rc.variedad,
                   pr.kilos_iniciales, pr.observaciones, pr.danos, pr.id_recepcion
            FROM pesaje_rezaga pr
            JOIN recepcion_carga rc ON pr.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE pr.id = %s
        """, (id_tanda,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", "No se encontraron datos de la tanda.")
            return

        # Limpiar cualquier tanda pendiente
        self.cancelar_todo()
        self.modo_edicion = True
        self.id_tanda_edicion = id_tanda

        # Cargar datos en los controles superiores
        self.fecha_entry.set_date(datos[1])
        carga = datos[2]
        self.carga_combo.set(carga)
        self.on_carga_seleccionada()
        lote = datos[3] or ""
        if lote in self.lote_combo['values']:
            self.lote_combo.set(lote)
            self.on_lote_seleccionado()
        # Cargar peso, jabas (se calcula a partir del peso)
        peso = datos[5]
        # Determinar jabas según el peso y la variedad
        variedad = self.variedad_actual.lower()
        peso_neto_por_jaba = 18.0 if "ataulfo" in variedad else 16.0
        mejor_n = 1
        menor = float('inf')
        for n in range(1, 8):
            esperado = n * peso_neto_por_jaba
            diff = abs(peso - esperado)
            if diff < menor:
                menor = diff
                mejor_n = n
        self.set_jabas(mejor_n)
        # Mostrar entry editable y ocultar label
        self.peso_label.pack_forget()
        self.peso_edit_entry.pack(pady=10)
        self.peso_edit_entry.delete(0, "end")
        self.peso_edit_entry.insert(0, f"{peso:.2f}")
        self.peso_manual = peso
        self.observaciones_entry.delete(0, "end")
        self.observaciones_entry.insert(0, datos[6] or "")
        self.danos_texto = datos[7] or ""
        self.danos_resumen_label.configure(text=self.danos_texto if self.danos_texto else "Ninguno",
                                           text_color="#2e8b57" if self.danos_texto else "gray")

        # Habilitar combos para editar carga/lote
        self.carga_combo.configure(state="readonly")
        self.lote_combo.configure(state="readonly")
        self.fecha_entry.configure(state="normal")

        # Cambiar interfaz
        self.btn_guardar.configure(text="💾 ACTUALIZAR TANDA", fg_color="#e69500")
        self.btn_cancelar_edicion.pack(side="top", padx=5, pady=5, fill="x")
        self.btn_agregar_nueva.pack_forget()
        self.btn_cancelar_todo.pack_forget()
        messagebox.showinfo("Edición", "Puede modificar carga, lote, fecha, peso, jabas, observaciones y daños. Luego presione ACTUALIZAR.")

    def cancelar_edicion(self):
        self.modo_edicion = False
        self.id_tanda_edicion = None
        self.carga_combo.configure(state="readonly")
        self.lote_combo.configure(state="readonly")
        self.fecha_entry.configure(state="normal")
        # Volver a mostrar label y ocultar entry
        self.peso_edit_entry.pack_forget()
        self.peso_label.pack(pady=10)
        self.limpiar_formulario()
        self.btn_guardar.configure(text="💾 GUARDAR (F10)", fg_color="#2e8b57")
        self.btn_cancelar_edicion.pack_forget()
        self.btn_agregar_nueva.pack(side="top", padx=5, pady=5, fill="x")
        self.btn_cancelar_todo.pack(side="top", padx=5, pady=5, fill="x")
        self.cargar_historial()

    def guardar_o_actualizar(self):
        if self.modo_edicion:
            self.actualizar_tanda_existente()
        else:
            self.guardar_tandas_pendientes()

    def actualizar_tanda_existente(self):
        if not self.modo_edicion or self.id_tanda_edicion is None:
            return
        try:
            nuevo_neto = float(self.peso_edit_entry.get())
            nuevas_jabas = self.jabas_var.get()
            nuevas_obs = self.observaciones_entry.get().strip()
            nueva_fecha = self.fecha_entry.get_date()
            nueva_carga = self.carga_combo.get().strip()
            nuevo_lote = self.lote_combo.get().strip()
        except:
            messagebox.showerror("Error", "Verifique los datos ingresados.")
            return

        if not nueva_carga or not nuevo_lote:
            messagebox.showerror("Error", "Debe seleccionar carga y lote.")
            return
        # Buscar el id_recepcion correspondiente a la nueva carga+lote
        res = ejecutar_consulta("""
            SELECT r.id FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            WHERE r.numero_carga = %s AND l.numero_lote = %s
        """, (nueva_carga, nuevo_lote), fetchone=True)
        if not res:
            messagebox.showerror("Error", f"No se encontró la combinación de carga '{nueva_carga}' y lote '{nuevo_lote}'.")
            return
        nuevo_id_recepcion = res[0]

        if nueva_fecha > datetime.now().date():
            if not messagebox.askyesno("Fecha futura", "La fecha ingresada es futura. ¿Desea continuar?"):
                return

        # Calcular porcentaje de rezaga (siempre 100%? según el código original, se guarda kilos_rezaga = neto y porcentaje 100%)
        porcentaje = 100.0 if nuevo_neto > 0 else 0.0

        try:
            ejecutar_consulta("""
                UPDATE pesaje_rezaga
                SET id_recepcion = %s, fecha = %s, kilos_iniciales = %s, kilos_rezaga = %s,
                    porcentaje_rezaga = %s, observaciones = %s, danos = %s, updated_at = %s
                WHERE id = %s
            """, (nuevo_id_recepcion, nueva_fecha, nuevo_neto, nuevo_neto, porcentaje,
                  nuevas_obs, self.danos_texto, datetime.now(), self.id_tanda_edicion))
            messagebox.showinfo("Éxito", "Tanda actualizada correctamente.")
            self.cancelar_edicion()
            self.cargar_historial()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar: {str(e)}")

    def guardar_tandas_pendientes(self):
        if self.id_recepcion is None:
            messagebox.showerror("Error", "Seleccione carga y lote.")
            return
        if not self.tandas_pendientes:
            messagebox.showwarning("Sin tandas", "No hay tandas para guardar.")
            return
        fecha = self.fecha_entry.get_date()
        operador = "admin"
        try:
            with open("session_user.txt","r") as f:
                operador = f.read().strip().split("|")[0]
        except: pass
        try:
            for p in self.tandas_pendientes:
                folio = f"REZ-{datetime.now().strftime('%Y%m%d')}-{self._get_next_sequence()}"
                ejecutar_consulta("""
                    INSERT INTO pesaje_rezaga
                    (folio, fecha, id_recepcion, kilos_iniciales, kilos_rezaga, porcentaje_rezaga,
                     observaciones, operador, created_at, danos)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (folio, fecha, self.id_recepcion, p["neto"], p["neto"],
                      100.0 if p["neto"]>0 else 0,
                      p["observaciones"], operador, datetime.now(), self.danos_texto))
            messagebox.showinfo("Éxito", f"Se guardaron {len(self.tandas_pendientes)} registro(s).")
            self.cancelar_todo()
            self.cargar_historial()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {str(e)}")

    def _get_next_sequence(self):
        try:
            count = ejecutar_consulta("SELECT COUNT(*) FROM pesaje_rezaga", fetchone=True)[0]
            return count + 1
        except:
            return 1

    def nueva_tanda(self):
        if self.modo_edicion:
            self.cancelar_edicion()
        else:
            self.limpiar_formulario()
        self.cargar_lista_cargas()

    def limpiar_formulario(self):
        self.carga_combo.set("")
        self.lote_combo.set("")
        self.variedad_combo.set("")
        self.lbl_jabas_ingresadas.configure(text="0")
        self.jabas_totales = 0
        if self.modo_edicion:
            self.peso_edit_entry.delete(0, "end")
            self.peso_edit_entry.insert(0, "0.00")
        else:
            self.peso_label.configure(text="0.00")
        self.peso_manual = 0.0
        self.observaciones_entry.delete(0, "end")
        self.set_jabas(1)
        self.fecha_entry.set_date(datetime.now())
        self.id_recepcion = None
        self.variedad_actual = ""
        self.progress_bar.set(0)
        self.lbl_progreso.configure(text="0 / 0 jabas")
        self.tandas_pendientes.clear()
        self.siguiente_tanda = 1
        self.actualizar_lista_tandas()
        self.actualizar_totales()
        self.danos_texto = ""
        self.danos_resumen_label.configure(text="Ninguno", text_color="gray")

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
        if self.modo_edicion:
            self.peso_edit_entry.delete(0, "end")
            self.peso_edit_entry.insert(0, "0.00")
        else:
            self.peso_label.configure(text="0.00")
        self.peso_manual = 0.0
        self.observaciones_entry.delete(0,"end")
        self.set_jabas(1)
        self.progress_bar.set(0)
        self.lbl_progreso.configure(text="0 / 0 jabas")
        self.fecha_entry.set_date(datetime.now())
        self.lotes_por_carga.clear()
        self.danos_texto = ""
        self.danos_resumen_label.configure(text="Ninguno", text_color="gray")
        if self.modo_edicion:
            self.cancelar_edicion()

    # ========== DAÑOS ==========
    def seleccionar_danos(self):
        danos_huerto = [
            "Acaro","Antracnosis","Asoleado","Quemado por sol","Escama","Fumagina",
            "Deforme","Deficiencia","Lacrado","Lenticelas","Minador","Pudrición de hueso",
            "Pudrición peduncular","Roña","Rozamiento","Trips"
        ]
        danos_corte = ["Daño por herramienta","Daño por sol","Golpe","Latex","Maduro","Pequeño","Rajado"]
        danos_empaque = ["Daño mecánico","Golpe","Quemado hidrotermico"]
        top = ctk.CTkToplevel(self)
        top.title("Seleccionar daños del lote")
        top.geometry("550x600")
        top.grab_set()
        top.resizable(True, True)
        main = ctk.CTkFrame(top, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=10)
        scroll = ctk.CTkScrollableFrame(main, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        vars_ = {}
        def agregar(titulo, lista):
            lbl = ctk.CTkLabel(scroll, text=titulo, font=("Arial",14,"bold"), text_color="#2e8b57")
            lbl.pack(anchor="w", pady=(10,5))
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", pady=5)
            for idx, d in enumerate(lista):
                var = ctk.BooleanVar(value=d in self.danos_texto.split(", "))
                vars_[d] = var
                cb = ctk.CTkCheckBox(f, text=d, variable=var, font=("Arial",11))
                cb.grid(row=idx//3, column=idx%3, padx=10, pady=2, sticky="w")
        agregar("🌿 Daño de huerto", danos_huerto)
        agregar("✂️ Daño de corte", danos_corte)
        agregar("📦 Daño de empaque", danos_empaque)
        def guardar():
            selec = [d for d, var in vars_.items() if var.get()]
            self.danos_texto = ", ".join(selec)
            self.danos_resumen_label.configure(text=self.danos_texto if self.danos_texto else "Ninguno",
                                               text_color="#2e8b57" if self.danos_texto else "gray")
            top.destroy()
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        ctk.CTkButton(btn_frame, text="✓ Aceptar", command=guardar, width=100, fg_color="#2e8b57").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="✗ Cancelar", command=top.destroy, width=100, fg_color="#8b0000").pack(side="left", padx=10)

    # ========== HISTORIAL (carga) ==========
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
                cond.append("pr.fecha BETWEEN %s AND %s")
                params.append(filtros['fecha_desde'])
                params.append(filtros['fecha_hasta'])
        where = " AND ".join(cond) if cond else "1=1"
        query = f"""
            SELECT pr.id, pr.fecha, rc.numero_carga, l.numero_lote,
                   pr.kilos_iniciales, pr.kilos_rezaga, pr.porcentaje_rezaga,
                   pr.operador, pr.danos
            FROM pesaje_rezaga pr
            JOIN recepcion_carga rc ON pr.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE {where}
            ORDER BY pr.fecha DESC
        """
        res = ejecutar_consulta(query, tuple(params), fetchall=True)
        for r in res:
            danos_str = r[8] if r[8] else ""
            if len(danos_str) > 50:
                danos_str = danos_str[:47] + "..."
            self.tree_historial.insert("", "end", values=(
                r[0], r[1].strftime("%d/%m/%Y") if r[1] else "", r[2], r[3] or "",
                f"{r[4]:.2f}", f"{r[5]:.2f}", f"{r[6]:.2f}%", r[7] or "admin", danos_str
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
        if not tiene_permiso(self.permisos, "pesaje_rezaga", "eliminar"):
            messagebox.showerror("Permiso", "No tiene permiso.")
            return
        sel = self.tree_historial.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un registro.")
            return
        id_ = self.tree_historial.item(sel[0])['tags'][0]
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro?"):
            try:
                ejecutar_consulta("DELETE FROM pesaje_rezaga WHERE id = %s", (id_,))
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