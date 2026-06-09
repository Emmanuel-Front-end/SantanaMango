# modulos/recepcion.py - Versión final con autocompletado, gestión de estados y variedades desde BD
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import ejecutar_consulta
from datetime import datetime
from tkcalendar import DateEntry
import pandas as pd
import hashlib
import re
import os
import subprocess
import smtplib
import webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from utils.tooltip import crear_tooltip
from reportlab.lib.pagesizes import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from auth import tiene_permiso

MEDIA_CARTA_VERTICAL = (5.5 * inch, 8.5 * inch)

class VentanaRecepcion(ctk.CTkFrame):
    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.modo_edicion = False
        self.recepcion_id = None
        self.mostrar_filtros = False
        self.search_after_id = None

        self.pack(fill="both", expand=True)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.bind("<F11>", self.toggle_fullscreen)

        self._asegurar_columnas_timestamp()
        self._asegurar_estatus()

        # ---------- BARRA DE NAVEGACIÓN ----------
        nav_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("#e0e0e0", "#2a2a2a"))
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_columnconfigure(1, weight=1)

        self.btn_regresar = ctk.CTkButton(nav_bar, text="◀ REGRESAR", command=self.regresar_menu,
                                          width=150, height=35, fg_color="#8b0000", font=("Arial", 12, "bold"))
        self.btn_regresar.grid(row=0, column=0, padx=10, pady=5)
        crear_tooltip(self.btn_regresar, "Volver al menú principal")

        ctk.CTkLabel(nav_bar, text="🚚 RECEPCIÓN DE CARGA", font=("Arial", 20, "bold"),
                     text_color="#2e8b57").grid(row=0, column=1)

        self.btn_refrescar = ctk.CTkButton(nav_bar, text="🔄", command=self.recargar_datos,
                                           width=40, height=35, fg_color="#3a6ea5")
        self.btn_refrescar.grid(row=0, column=2, padx=10, pady=5)
        crear_tooltip(self.btn_refrescar, "Refrescar catálogos y tabla")

        # ---------- SCROLLABLE (todo el contenido) ----------
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        # --- FORMULARIO DE CAPTURA (se oculta al buscar) ---
        self.form_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.form_container.pack(fill="both", expand=True)

        main_container = self.form_container

        col1 = ctk.CTkFrame(main_container, fg_color="transparent")
        col1.pack(side="left", fill="both", expand=True, padx=(0, 5))
        col2 = ctk.CTkFrame(main_container, fg_color="transparent")
        col2.pack(side="left", fill="both", expand=True, padx=5)
        col3 = ctk.CTkFrame(main_container, fg_color="transparent")
        col3.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # Tarjeta DATOS GENERALES
        card_gen = self._crear_tarjeta(col1, "📋 DATOS GENERALES")
        grid_gen = ctk.CTkFrame(card_gen, fg_color="transparent")
        grid_gen.pack(fill="x", padx=15, pady=10)
        grid_gen.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_gen, text="FOLIO:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.folio_entry = ctk.CTkEntry(grid_gen, width=160, state="readonly")
        self.folio_entry.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.folio_entry, "Folio autogenerado de la recepción")

        ctk.CTkLabel(grid_gen, text="NO. CARGA (*):", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        self.numero_carga_combo = ttk.Combobox(grid_gen, width=25, state="normal")
        self.numero_carga_combo.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        self.numero_carga_combo.bind("<<ComboboxSelected>>", self.on_carga_seleccionada)
        self.numero_carga_combo.bind("<FocusOut>", self.on_carga_focusout)
        self.numero_carga_combo.bind("<KeyRelease>", lambda e: self._to_upper(self.numero_carga_combo))
        crear_tooltip(self.numero_carga_combo, "Número de carga. Si ya existe, se autocompletan los datos")

        ctk.CTkLabel(grid_gen, text="FECHA RECEPCIÓN:", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.fecha_recep_entry = DateEntry(grid_gen, width=18, date_pattern='yyyy-mm-dd')
        self.fecha_recep_entry.set_date(datetime.now())
        self.fecha_recep_entry.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.fecha_recep_entry, "Fecha en que se recibe la carga")

        ctk.CTkLabel(grid_gen, text="LOTE (*):", font=("Arial", 12, "bold")).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.lote_combo = ttk.Combobox(grid_gen, width=25, state="normal")
        self.lote_combo.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.lote_combo.bind("<FocusOut>", self._normalizar_lote)
        self.lote_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.lote_combo))
        crear_tooltip(self.lote_combo, "Número de lote (ej: L-001). Puede repetir número de carga con diferente lote.")

        ctk.CTkLabel(grid_gen, text="FECHA CORTE:", font=("Arial", 12, "bold")).grid(row=4, column=0, padx=5, pady=6, sticky="e")
        self.fecha_corte_entry = DateEntry(grid_gen, width=18, date_pattern='yyyy-mm-dd')
        self.fecha_corte_entry.set_date(datetime.now())
        self.fecha_corte_entry.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.fecha_corte_entry, "Fecha de corte del producto")

        # Tarjeta ORIGEN
        card_ori = self._crear_tarjeta(col1, "🌾 ORIGEN")
        grid_ori = ctk.CTkFrame(card_ori, fg_color="transparent")
        grid_ori.pack(fill="x", padx=15, pady=10)
        grid_ori.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_ori, text="CENTRO ABASTECIMIENTO:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.centro_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.centro_combo.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        self.centro_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.centro_combo))
        crear_tooltip(self.centro_combo, "Centro de abastecimiento del producto")

        ctk.CTkLabel(grid_ori, text="PRODUCTOR:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        self.productor_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.productor_combo.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        self.productor_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.productor_combo))
        crear_tooltip(self.productor_combo, "Nombre del productor")

        ctk.CTkLabel(grid_ori, text="CAMPO (HUERTO):", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.campo_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.campo_combo.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        self.campo_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.campo_combo))
        crear_tooltip(self.campo_combo, "Campo o huerto de procedencia")

        ctk.CTkLabel(grid_ori, text="REGISTRO HUERTO:", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.registro_huerto_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.registro_huerto_combo.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.registro_huerto_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.registro_huerto_combo))
        crear_tooltip(self.registro_huerto_combo, "Registro del huerto")

        # Tarjeta PRODUCTO
        card_prod = self._crear_tarjeta(col2, "📦 PRODUCTO")
        grid_prod = ctk.CTkFrame(card_prod, fg_color="transparent")
        grid_prod.pack(fill="x", padx=15, pady=10)
        grid_prod.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_prod, text="PRODUCTO:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        prod_entry = ctk.CTkEntry(grid_prod, width=160, state="readonly")
        prod_entry.insert(0, "Mango")
        prod_entry.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(prod_entry, "Producto (fijo: Mango)")

        ctk.CTkLabel(grid_prod, text="VARIEDAD:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        # Cargar variedades desde la BD (valores vacíos inicialmente, se llenarán en cargar_catalogos)
        self.variedad_combo = ttk.Combobox(grid_prod, width=28, values=[], state="readonly")
        self.variedad_combo.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.variedad_combo, "Variedad del mango (cargada desde catálogo)")

        ctk.CTkLabel(grid_prod, text="TIPO DE CAJA:", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.tipo_caja_combo = ttk.Combobox(grid_prod, width=28, values=["GRANDE", "CHICA"], state="readonly")
        self.tipo_caja_combo.set("GRANDE")
        self.tipo_caja_combo.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.tipo_caja_combo, "Tamaño de la caja")

        ctk.CTkLabel(grid_prod, text="CAJAS LLENAS:", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.cajas_llenas_entry = ctk.CTkEntry(grid_prod, width=120)
        self.cajas_llenas_entry.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.cajas_llenas_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.cajas_llenas_entry))
        self.cajas_llenas_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.cajas_llenas_entry, "Número de cajas llenas")

        ctk.CTkLabel(grid_prod, text="CAJAS VACÍAS:", font=("Arial", 12)).grid(row=4, column=0, padx=5, pady=6, sticky="e")
        self.cajas_vacias_entry = ctk.CTkEntry(grid_prod, width=120)
        self.cajas_vacias_entry.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        self.cajas_vacias_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.cajas_vacias_entry))
        self.cajas_vacias_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.cajas_vacias_entry, "Número de cajas vacías")

        # Tarjeta ORGANIZACIÓN
        card_org = self._crear_tarjeta(col2, "✅ ORGANIZACIÓN")
        grid_org = ctk.CTkFrame(card_org, fg_color="transparent")
        grid_org.pack(fill="x", padx=15, pady=10)
        grid_org.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_org, text="CULTIVO:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        cultivo_frame = ctk.CTkFrame(grid_org, fg_color="transparent")
        cultivo_frame.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        self.cultivo_var = ctk.StringVar(value="CONVENCIONAL")
        ctk.CTkRadioButton(cultivo_frame, text="ORGANICO", variable=self.cultivo_var, value="ORGANICO").pack(side="left", padx=5)
        ctk.CTkRadioButton(cultivo_frame, text="CONVENCIONAL", variable=self.cultivo_var, value="CONVENCIONAL").pack(side="left", padx=5)
        crear_tooltip(cultivo_frame, "Tipo de cultivo (Orgánico o Convencional)")

        self.fair_trade_var = ctk.BooleanVar()
        cb_fair = ctk.CTkCheckBox(grid_org, text="FAIR TRADE", variable=self.fair_trade_var)
        cb_fair.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(cb_fair, "Certificación Fair Trade")

        # Tarjeta TRANSPORTE
        card_trans = self._crear_tarjeta(col3, "🚛 TRANSPORTE")
        grid_trans = ctk.CTkFrame(card_trans, fg_color="transparent")
        grid_trans.pack(fill="x", padx=15, pady=10)
        grid_trans.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_trans, text="CHOFER:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.chofer_combo = ttk.Combobox(grid_trans, width=40, state="normal")
        self.chofer_combo.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        self.chofer_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.chofer_combo))
        crear_tooltip(self.chofer_combo, "Nombre del chofer")

        ctk.CTkLabel(grid_trans, text="PLACAS VEHÍCULO:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        self.placas_entry = ctk.CTkEntry(grid_trans, width=200)
        self.placas_entry.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        self.placas_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.placas_entry))
        self.placas_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.placas_entry, "Placas del vehículo")

        ctk.CTkLabel(grid_trans, text="REMOLQUE:", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.remolque_entry = ctk.CTkEntry(grid_trans, width=200)
        self.remolque_entry.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        self.remolque_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.remolque_entry))
        self.remolque_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.remolque_entry, "Número de remolque o caja")

        ctk.CTkLabel(grid_trans, text="CUADRILLAS:", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.cuadrillas_entry = ctk.CTkEntry(grid_trans, width=300)
        self.cuadrillas_entry.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.cuadrillas_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.cuadrillas_entry))
        self.cuadrillas_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.cuadrillas_entry, "Nombre o identificación de cuadrillas")

        ctk.CTkLabel(grid_trans, text="INSPECTOR:", font=("Arial", 12)).grid(row=4, column=0, padx=5, pady=6, sticky="e")
        self.inspector_entry = ctk.CTkEntry(grid_trans, width=300)
        self.inspector_entry.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        self.inspector_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.inspector_entry))
        self.inspector_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.inspector_entry, "Nombre del inspector")

        # Tarjeta OBSERVACIONES
        card_obs = self._crear_tarjeta(col3, "📝 OBSERVACIONES")
        self.observaciones_text = ctk.CTkTextbox(card_obs, height=150)
        self.observaciones_text.pack(fill="x", padx=15, pady=10)
        self.observaciones_text.bind("<FocusOut>", self._textbox_to_upper)
        crear_tooltip(self.observaciones_text, "Observaciones adicionales")

        # --- Botón GUARDAR ---
        btn_guardar_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        btn_guardar_frame.pack(fill="x", pady=20)
        self.btn_guardar = ctk.CTkButton(btn_guardar_frame, text="💾 GUARDAR RECEPCIÓN", command=self.guardar_recepcion,
                                         fg_color="#2e8b57", height=50, font=("Arial", 16, "bold"), width=350)
        self.btn_guardar.pack()
        crear_tooltip(self.btn_guardar, "Guardar la recepción en la base de datos")

        # --- BARRA DE ACCIONES ---
        actions_bar = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        actions_bar.pack(fill="x", pady=(0, 10))

        self.btn_editar = ctk.CTkButton(actions_bar, text="✏️ Editar", command=self.editar_recepcion, width=100)
        self.btn_editar.pack(side="left", padx=5)
        crear_tooltip(self.btn_editar, "Editar recepción seleccionada")

        self.btn_eliminar = ctk.CTkButton(actions_bar, text="🗑️ Eliminar", command=self.eliminar_recepcion, width=100, fg_color="#8b0000")
        self.btn_eliminar.pack(side="left", padx=5)
        crear_tooltip(self.btn_eliminar, "Eliminar recepción seleccionada")

        self.btn_excel = ctk.CTkButton(actions_bar, text="📊 Exportar Excel", command=self.exportar_excel, width=120, fg_color="#3a6ea5")
        self.btn_excel.pack(side="left", padx=5)
        crear_tooltip(self.btn_excel, "Exportar tabla a Excel")

        self.btn_imprimir = ctk.CTkButton(actions_bar, text="🖨️ Imprimir Boleta", command=self.imprimir_boleta, width=130, fg_color="#2e8b57")
        self.btn_imprimir.pack(side="left", padx=5)
        crear_tooltip(self.btn_imprimir, "Imprimir boleta de la recepción seleccionada")

        self.btn_enviar_email = ctk.CTkButton(actions_bar, text="📧 Enviar Boleta", command=self.enviar_boleta_email, width=130, fg_color="#e69500")
        self.btn_enviar_email.pack(side="left", padx=5)
        crear_tooltip(self.btn_enviar_email, "Enviar boleta por correo electrónico")

        self.btn_filtros = ctk.CTkButton(actions_bar, text="🔍 Búsqueda", command=self.toggle_filtros, width=100, fg_color="#1f6aa5")
        self.btn_filtros.pack(side="left", padx=5)
        crear_tooltip(self.btn_filtros, "Mostrar/ocultar búsqueda rápida")

        # --- PANEL DE BÚSQUEDA (oculto inicialmente) ---
        self.filtros_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2a2a2a", corner_radius=10)

        search_frame = ctk.CTkFrame(self.filtros_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(search_frame, text="🔍 BÚSQUEDA RÁPIDA:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.buscar_entry = ctk.CTkEntry(search_frame, width=400, placeholder_text="Folio, N° Carga, Lote, Productor, Chofer, Centro, Campo...")
        self.buscar_entry.pack(side="left", padx=5, fill="x", expand=True)
        crear_tooltip(self.buscar_entry, "Escribe para buscar automáticamente (oculta el formulario)")
        self.buscar_entry.bind("<KeyRelease>", self.on_search_key_release)
        self.buscar_entry.bind("<Return>", lambda e: self.aplicar_filtros())

        ctk.CTkLabel(search_frame, text="Ej: L-001, JUAN, REC-20260604, etc.", font=("Arial", 9), text_color="gray").pack(side="left", padx=10)

        fecha_frame = ctk.CTkFrame(self.filtros_frame, fg_color="transparent")
        fecha_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(fecha_frame, text="📅 RANGO DE FECHAS:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.filtro_fecha_desde = DateEntry(fecha_frame, width=12, date_pattern='yyyy-mm-dd')
        self.filtro_fecha_desde.set_date(datetime.now().replace(day=1))
        self.filtro_fecha_desde.pack(side="left", padx=5)
        self.filtro_fecha_desde.bind("<<DateEntrySelected>>", lambda e: self.aplicar_filtros_con_ocultar())
        crear_tooltip(self.filtro_fecha_desde, "Fecha de inicio del rango")

        ctk.CTkLabel(fecha_frame, text="HASTA", font=("Arial", 12)).pack(side="left", padx=2)
        self.filtro_fecha_hasta = DateEntry(fecha_frame, width=12, date_pattern='yyyy-mm-dd')
        self.filtro_fecha_hasta.set_date(datetime.now())
        self.filtro_fecha_hasta.pack(side="left", padx=5)
        self.filtro_fecha_hasta.bind("<<DateEntrySelected>>", lambda e: self.aplicar_filtros_con_ocultar())
        crear_tooltip(self.filtro_fecha_hasta, "Fecha de fin del rango")

        btn_aplicar_fecha = ctk.CTkButton(fecha_frame, text="APLICAR RANGO", command=self.aplicar_filtros_con_ocultar, width=120, fg_color="#3a6ea5")
        btn_aplicar_fecha.pack(side="left", padx=10)
        crear_tooltip(btn_aplicar_fecha, "Aplicar filtro por rango de fechas")

        # --- TABLA DE RECEPCIONES RECIENTES ---
        self.table_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("#f0f0f0", "#2a2a2a"), corner_radius=15)
        self.table_frame.pack(fill="both", expand=True, pady=20)

        ctk.CTkLabel(self.table_frame, text="📋 RECEPCIONES RECIENTES", font=("Arial", 16, "bold"), text_color="#2e8b57").pack(anchor="w", padx=20, pady=(10,5))

        tree_container = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=20, pady=10)

        columnas = ("Carga", "Lote", "Fecha", "Hora", "Productor", "Cajas", "Estado")
        self.tree = ttk.Treeview(tree_container, columns=columnas, show="headings", height=6)

        self.tree.heading("Carga", text="No. Carga")
        self.tree.heading("Lote", text="Lote")
        self.tree.heading("Fecha", text="Fecha")
        self.tree.heading("Hora", text="Hora")
        self.tree.heading("Productor", text="Productor")
        self.tree.heading("Cajas", text="Cajas Llenas")
        self.tree.heading("Estado", text="Estado")

        self.tree.column("Carga", width=100, anchor="center")
        self.tree.column("Lote", width=100, anchor="center")
        self.tree.column("Fecha", width=100, anchor="center")
        self.tree.column("Hora", width=80, anchor="center")
        self.tree.column("Productor", width=180, anchor="center")
        self.tree.column("Cajas", width=80, anchor="center")
        self.tree.column("Estado", width=100, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        crear_tooltip(vsb, "Barra de desplazamiento vertical")

        info_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=5)
        self.lbl_modificacion = ctk.CTkLabel(info_frame, text="", font=("Arial", 10, "italic"), text_color="gray")
        self.lbl_modificacion.pack(anchor="w")
        crear_tooltip(self.lbl_modificacion, "Fecha y hora de la última modificación")

        self.tree.bind("<<TreeviewSelect>>", self.on_seleccionar_fila)
        self.tree.bind("<Double-1>", self.abrir_detalles_desde_tabla)

        self.generar_folio()
        self.cargar_catalogos()
        self.cargar_recepciones_recientes()
        self.cargar_lista_numeros_carga()

        # Guardar referencias
        self.btn_guardar_frame = btn_guardar_frame
        self.actions_bar = actions_bar

    # ========== FUNCIONES AUXILIARES ==========
    def toggle_fullscreen(self, event=None):
        current_state = self.winfo_toplevel().attributes('-fullscreen')
        self.winfo_toplevel().attributes('-fullscreen', not current_state)

    def _to_upper(self, entry_widget):
        contenido = entry_widget.get()
        if contenido != contenido.upper():
            entry_widget.delete(0, "end")
            entry_widget.insert(0, contenido.upper())

    def _combo_to_upper(self, combo_widget):
        texto = combo_widget.get()
        if texto != texto.upper():
            combo_widget.set(texto.upper())

    def _textbox_to_upper(self, event=None):
        contenido = self.observaciones_text.get("1.0", "end-1c")
        if contenido != contenido.upper():
            self.observaciones_text.delete("1.0", "end")
            self.observaciones_text.insert("1.0", contenido.upper())

    def _crear_tarjeta(self, parent, titulo):
        frame = ctk.CTkFrame(parent, fg_color=("#f5f5f5", "#2a2a2a"), corner_radius=15, border_width=1, border_color="#2e8b57")
        frame.pack(fill="x", pady=8)
        ctk.CTkLabel(frame, text=titulo, font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", padx=20, pady=(10,5))
        return frame

    def regresar_menu(self):
        if self.on_regresar:
            self.on_regresar()
        self.destroy()

    def generar_folio(self):
        fecha = datetime.now().strftime("%Y%m%d")
        try:
            count = ejecutar_consulta("SELECT COUNT(*) FROM recepcion_carga WHERE folio LIKE %s", (f"REC-{fecha}-%",), fetchone=True)[0]
            folio = f"REC-{fecha}-{count+1:03d}"
        except:
            folio = f"REC-{fecha}-001"
        self.folio_entry.configure(state="normal")
        self.folio_entry.delete(0, "end")
        self.folio_entry.insert(0, folio)
        self.folio_entry.configure(state="readonly")

    def _normalizar_lote(self, event=None):
        texto = self.lote_combo.get().strip()
        if not texto:
            return
        texto = texto.upper()
        match = re.search(r'(\d+)', texto)
        if match:
            numero = int(match.group(1))
            lote_formateado = f"L-{numero:03d}"
        else:
            lote_formateado = texto
        if lote_formateado != texto:
            self.lote_combo.set(lote_formateado)

    def cargar_catalogos(self):
        try:
            centros = ejecutar_consulta("SELECT nombre FROM centros_abastecimiento WHERE activo=true", fetchall=True)
            self.centro_combo['values'] = [c[0] for c in centros] if centros else []
        except:
            self.centro_combo['values'] = []
        try:
            lotes = ejecutar_consulta("SELECT numero_lote FROM lotes WHERE activo=true ORDER BY numero_lote", fetchall=True)
            self.lote_combo['values'] = [l[0] for l in lotes] if lotes else []
        except:
            self.lote_combo['values'] = []
        try:
            productores = ejecutar_consulta("SELECT nombre FROM productores WHERE activo=true ORDER BY nombre", fetchall=True)
            self.productor_combo['values'] = [p[0] for p in productores] if productores else []
        except:
            self.productor_combo['values'] = []
        try:
            choferes = ejecutar_consulta("SELECT nombre FROM choferes WHERE activo=true ORDER BY nombre", fetchall=True)
            self.chofer_combo['values'] = [c[0] for c in choferes] if choferes else []
        except:
            self.chofer_combo['values'] = []
        try:
            campos = ejecutar_consulta("SELECT nombre FROM campos WHERE activo=true ORDER BY nombre", fetchall=True)
            self.campo_combo['values'] = [c[0] for c in campos] if campos else []
        except:
            self.campo_combo['values'] = []
        try:
            registros = ejecutar_consulta("SELECT nombre FROM registros_huerto WHERE activo=true ORDER BY nombre", fetchall=True)
            self.registro_huerto_combo['values'] = [r[0] for r in registros] if registros else []
        except:
            self.registro_huerto_combo['values'] = []
        # === Cargar variedades desde la base de datos ===
        try:
            variedades = ejecutar_consulta("SELECT nombre FROM variedades WHERE activo=true ORDER BY nombre", fetchall=True)
            self.variedad_combo['values'] = [v[0] for v in variedades] if variedades else []
            if self.variedad_combo['values'] and not self.variedad_combo.get():
                self.variedad_combo.set(self.variedad_combo['values'][0])
        except Exception as e:
            print(f"Error cargando variedades: {e}")
            self.variedad_combo['values'] = []

    def cargar_lista_numeros_carga(self):
        try:
            resultados = ejecutar_consulta("SELECT DISTINCT numero_carga FROM recepcion_carga ORDER BY numero_carga", fetchall=True)
            self.numero_carga_combo['values'] = [r[0] for r in resultados] if resultados else []
        except:
            self.numero_carga_combo['values'] = []

    def on_carga_seleccionada(self, event=None):
        self.cargar_datos_por_numero_carga()

    def on_carga_focusout(self, event=None):
        self.cargar_datos_por_numero_carga()

    def cargar_datos_por_numero_carga(self):
        numero_carga = self.numero_carga_combo.get().strip().upper()
        if not numero_carga:
            return
        query = """
            SELECT centro_abastecimiento_id, productor_id, campo_id, registro_huerto_id,
                   tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                   cuadrillas, inspector, fecha_corte, fecha_hora
            FROM recepcion_carga
            WHERE numero_carga = %s
            LIMIT 1
        """
        datos = ejecutar_consulta(query, (numero_carga,), fetchone=True)
        if datos:
            if datos[0]:
                centro_nombre = ejecutar_consulta("SELECT nombre FROM centros_abastecimiento WHERE id = %s", (datos[0],), fetchone=True)
                self.centro_combo.set(centro_nombre[0] if centro_nombre else "")
            else:
                self.centro_combo.set("")
            if datos[1]:
                prod_nombre = ejecutar_consulta("SELECT nombre FROM productores WHERE id = %s", (datos[1],), fetchone=True)
                self.productor_combo.set(prod_nombre[0] if prod_nombre else "")
            else:
                self.productor_combo.set("")
            if datos[2]:
                campo_nombre = ejecutar_consulta("SELECT nombre FROM campos WHERE id = %s", (datos[2],), fetchone=True)
                self.campo_combo.set(campo_nombre[0] if campo_nombre else "")
            else:
                self.campo_combo.set("")
            if datos[3]:
                rh_nombre = ejecutar_consulta("SELECT nombre FROM registros_huerto WHERE id = %s", (datos[3],), fetchone=True)
                self.registro_huerto_combo.set(rh_nombre[0] if rh_nombre else "")
            else:
                self.registro_huerto_combo.set("")
            if datos[4]:
                self.cultivo_var.set(datos[4])
            if datos[5] is not None:
                self.fair_trade_var.set(datos[5])
            if datos[6]:
                chofer_nombre = ejecutar_consulta("SELECT nombre FROM choferes WHERE id = %s", (datos[6],), fetchone=True)
                self.chofer_combo.set(chofer_nombre[0] if chofer_nombre else "")
            else:
                self.chofer_combo.set("")
            self.placas_entry.delete(0, "end")
            self.placas_entry.insert(0, datos[7] or "")
            self.remolque_entry.delete(0, "end")
            self.remolque_entry.insert(0, datos[8] or "")
            self.cuadrillas_entry.delete(0, "end")
            self.cuadrillas_entry.insert(0, datos[9] or "")
            self.inspector_entry.delete(0, "end")
            self.inspector_entry.insert(0, datos[10] or "")
            if datos[11]:
                self.fecha_corte_entry.set_date(datos[11])
            if datos[12]:
                self.fecha_recep_entry.set_date(datos[12])
            self.lote_combo.set("")
            # No modificar variedad para no sobreescribir la selección del usuario
            # self.variedad_combo.set("ATAULFO")  # <-- eliminado para mantener la lista de BD
            self.tipo_caja_combo.set("GRANDE")
            self.cajas_llenas_entry.delete(0, "end")
            self.cajas_vacias_entry.delete(0, "end")
            self.observaciones_text.delete("1.0", "end")
            self.modo_edicion = False
            self.recepcion_id = None
            self.generar_folio()

    def _asegurar_columnas_timestamp(self):
        try:
            ejecutar_consulta("ALTER TABLE recepcion_carga ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ejecutar_consulta("ALTER TABLE recepcion_carga ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception as e:
            print(f"Error con timestamps: {e}")

    def _asegurar_estatus(self):
        try:
            ejecutar_consulta("ALTER TABLE recepcion_carga ADD COLUMN IF NOT EXISTS estatus VARCHAR(20) DEFAULT 'PENDIENTE'")
        except Exception as e:
            print(f"Error con estatus: {e}")

    # ========== MÉTODOS PARA OCULTAR/MOSTRAR FORMULARIO ==========
    def ocultar_formulario(self):
        if self.form_container.winfo_ismapped():
            self.form_container.pack_forget()

    def mostrar_formulario(self):
        if not self.form_container.winfo_ismapped():
            self.form_container.pack(fill="both", expand=True, before=self.btn_guardar_frame)

    def on_search_key_release(self, event):
        if self.search_after_id:
            self.after_cancel(self.search_after_id)
        self.ocultar_formulario()
        self.search_after_id = self.after(500, self.aplicar_filtros)

    def aplicar_filtros_con_ocultar(self):
        self.ocultar_formulario()
        self.aplicar_filtros()

    def toggle_filtros(self):
        if self.mostrar_filtros:
            self.filtros_frame.pack_forget()
            self.mostrar_filtros = False
            self.btn_filtros.configure(text="🔍 BÚSQUEDA", fg_color="#1f6aa5")
            self.mostrar_formulario()
        else:
            self.filtros_frame.pack(fill="x", padx=0, pady=(5, 10), before=self.table_frame)
            self.mostrar_filtros = True
            self.btn_filtros.configure(text="✖ OCULTAR", fg_color="#8b0000")

    # ========== MÉTODOS DE TABLA ==========
    def cargar_recepciones_recientes(self, sql_extra="", params=()):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            query = """
                SELECT r.id, r.numero_carga,
                       l.numero_lote,
                       to_char(r.created_at, 'DD/MM/YYYY') as fecha,
                       to_char(r.created_at, 'HH24:MI:SS') as hora,
                       p.nombre as productor,
                       r.cajas_llenas,
                       r.estatus
                FROM recepcion_carga r
                LEFT JOIN lotes l ON r.lote_id = l.id
                LEFT JOIN productores p ON r.productor_id = p.id
                LEFT JOIN choferes ch ON r.chofer_id = ch.id
                LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
                LEFT JOIN campos ca ON r.campo_id = ca.id
                LEFT JOIN registros_huerto rh ON r.registro_huerto_id = rh.id
            """
            if sql_extra:
                query += " WHERE " + sql_extra
            query += " ORDER BY r.created_at DESC LIMIT 100"
            resultados = ejecutar_consulta(query, params, fetchall=True)
            for r in resultados:
                productor = r[5].title() if r[5] else ""
                self.tree.insert("", "end", values=(r[1], r[2] or "", r[3], r[4], productor, r[6] or 0, r[7] or "PENDIENTE"), tags=(r[0],))
        except Exception as e:
            print(f"Error cargando recepciones: {e}")

    def aplicar_filtros(self):
        buscar_texto = self.buscar_entry.get().strip()
        condiciones = []
        params = []
        if buscar_texto:
            condiciones.append("""
                (r.folio ILIKE %s OR 
                 r.numero_carga ILIKE %s OR 
                 l.numero_lote ILIKE %s OR 
                 p.nombre ILIKE %s OR 
                 ch.nombre ILIKE %s OR 
                 c.nombre ILIKE %s OR 
                 ca.nombre ILIKE %s OR 
                 rh.nombre ILIKE %s)
            """)
            like = f"%{buscar_texto}%"
            params.extend([like] * 8)
        if self.filtro_fecha_desde.get_date() and self.filtro_fecha_hasta.get_date():
            condiciones.append("DATE(r.created_at) BETWEEN %s AND %s")
            params.append(self.filtro_fecha_desde.get_date())
            params.append(self.filtro_fecha_hasta.get_date())
        sql_extra = " AND ".join(condiciones) if condiciones else ""
        self.cargar_recepciones_recientes(sql_extra, tuple(params))

    def on_seleccionar_fila(self, event):
        seleccion = self.tree.selection()
        if not seleccion:
            self.lbl_modificacion.configure(text="")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            res = ejecutar_consulta("SELECT to_char(updated_at, 'DD/MM/YYYY HH24:MI:SS') FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
            if res:
                self.lbl_modificacion.configure(text=f"Última modificación: {res[0]}")
            else:
                self.lbl_modificacion.configure(text="")
        else:
            self.lbl_modificacion.configure(text="")

    def abrir_detalles_desde_tabla(self, event):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            self.mostrar_formulario()
            self.mostrar_modal_detalles_por_id(recepcion_id)
        else:
            messagebox.showerror("Error", "No se pudo identificar la recepción")

    def mostrar_modal_detalles_por_id(self, recepcion_id):
        query = """
            SELECT r.folio, r.numero_carga, to_char(r.fecha_hora, 'DD/MM/YYYY') as fecha_recep,
                   to_char(r.fecha_corte, 'DD/MM/YYYY') as fecha_corte,
                   l.numero_lote, c.nombre as centro, p.nombre as productor,
                   ca.nombre as campo, rh.nombre as registro_huerto,
                   r.variedad, r.tipo_caja, r.cajas_llenas, r.cajas_vacias,
                   r.tipo_cultivo, r.fair_trade, ch.nombre as chofer,
                   r.placas_tractor, r.placas_caja, r.cuadrillas, r.inspector,
                   r.produccion, r.estatus,
                   to_char(r.created_at, 'DD/MM/YYYY') as creado_fecha,
                   to_char(r.created_at, 'HH24:MI:SS') as creado_hora,
                   to_char(r.updated_at, 'DD/MM/YYYY') as mod_fecha,
                   to_char(r.updated_at, 'HH24:MI:SS') as mod_hora
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
            LEFT JOIN productores p ON r.productor_id = p.id
            LEFT JOIN campos ca ON r.campo_id = ca.id
            LEFT JOIN registros_huerto rh ON r.registro_huerto_id = rh.id
            LEFT JOIN choferes ch ON r.chofer_id = ch.id
            WHERE r.id = %s
        """
        datos = ejecutar_consulta(query, (recepcion_id,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", "No se encontraron datos")
            return
        modal = ctk.CTkToplevel(self)
        modal.title(f"DETALLES DE RECEPCIÓN - {datos[0]}")
        modal.geometry("850x800")
        modal.grab_set()
        main_frame = ctk.CTkFrame(modal, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        col_left = ctk.CTkFrame(main_frame, fg_color="transparent")
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        col_right = ctk.CTkFrame(main_frame, fg_color="transparent")
        col_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        folio = datos[0]
        carga = datos[1]
        fecha_recep = datos[2]
        fecha_corte = datos[3]
        lote = datos[4] or ""
        centro = datos[5].title() if datos[5] else ""
        productor = datos[6].title() if datos[6] else ""
        campo = datos[7].title() if datos[7] else ""
        registro_huerto = datos[8].title() if datos[8] else ""
        variedad = datos[9].title() if datos[9] else ""
        tipo_caja = datos[10].title() if datos[10] else ""
        cajas_llenas = datos[11] or 0
        cajas_vacias = datos[12] or 0
        cultivo = datos[13].title() if datos[13] else ""
        fair_trade = "Sí" if datos[14] else "No"
        chofer = datos[15].title() if datos[15] else ""
        placas = datos[16].upper() if datos[16] else ""
        remolque = datos[17].title() if datos[17] else ""
        cuadrillas = datos[18].title() if datos[18] else ""
        inspector = datos[19].title() if datos[19] else ""
        observaciones = datos[20].title() if datos[20] else ""
        estado = datos[21] if datos[21] else "PENDIENTE"
        creado_fecha = datos[22]
        creado_hora = datos[23]
        mod_fecha = datos[24]
        mod_hora = datos[25]

        ctk.CTkLabel(col_left, text="📋 DATOS GENERALES", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(0,10))
        ctk.CTkLabel(col_left, text=f"FOLIO: {folio}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"NO. CARGA: {carga}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"FECHA RECEPCIÓN: {fecha_recep}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"LOTE: {lote}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"FECHA CORTE: {fecha_corte}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"ESTADO: {estado}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text="\n🌾 ORIGEN", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(15,5))
        ctk.CTkLabel(col_left, text=f"CENTRO: {centro}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"PRODUCTOR: {productor}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"CAMPO: {campo}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"REGISTRO HUERTO: {registro_huerto}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text="📦 PRODUCTO", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(0,10))
        ctk.CTkLabel(col_right, text=f"PRODUCTO: Mango", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"VARIEDAD: {variedad}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"TIPO CAJA: {tipo_caja}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CAJAS LLENAS: {cajas_llenas}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CAJAS VACÍAS: {cajas_vacias}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CULTIVO: {cultivo}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"FAIR TRADE: {fair_trade}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text="\n🚛 TRANSPORTE", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(15,5))
        ctk.CTkLabel(col_right, text=f"CHOFER: {chofer}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"PLACAS: {placas}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"REMOLQUE: {remolque}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CUADRILLAS: {cuadrillas}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"INSPECTOR: {inspector}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(modal, text="📝 OBSERVACIONES", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", padx=20, pady=(10,5))
        obs_text = ctk.CTkTextbox(modal, height=100)
        obs_text.pack(fill="x", padx=20, pady=(0,10))
        obs_text.insert("1.0", observaciones)
        obs_text.configure(state="disabled")
        timestamp_frame = ctk.CTkFrame(modal, fg_color="transparent")
        timestamp_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(timestamp_frame, text=f"CREADO EL: {creado_fecha} A LAS {creado_hora}", font=("Arial", 10, "italic")).pack(anchor="w")
        ctk.CTkLabel(timestamp_frame, text=f"ÚLTIMA MODIFICACIÓN: {mod_fecha} A LAS {mod_hora}", font=("Arial", 10, "italic")).pack(anchor="w")
        btn_modal = ctk.CTkFrame(modal, fg_color="transparent")
        btn_modal.pack(fill="x", pady=10)
        btn_editar_modal = ctk.CTkButton(btn_modal, text="✏️ EDITAR", command=lambda: self.editar_por_id(recepcion_id, modal), width=100)
        btn_editar_modal.pack(side="left", padx=20)
        crear_tooltip(btn_editar_modal, "Editar esta recepción")
        btn_imprimir_modal = ctk.CTkButton(btn_modal, text="🖨️ IMPRIMIR BOLETA", command=lambda: self.imprimir_boleta_por_id(recepcion_id), width=130)
        btn_imprimir_modal.pack(side="left", padx=20)
        crear_tooltip(btn_imprimir_modal, "Imprimir boleta de esta recepción")
        btn_email_modal = ctk.CTkButton(btn_modal, text="📧 ENVIAR POR EMAIL", command=lambda: self.enviar_boleta_por_id(recepcion_id), width=130, fg_color="#e69500")
        btn_email_modal.pack(side="left", padx=20)
        crear_tooltip(btn_email_modal, "Enviar boleta por correo electrónico")
        btn_cerrar_modal = ctk.CTkButton(btn_modal, text="CERRAR", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cerrar_modal.pack(side="right", padx=20)
        crear_tooltip(btn_cerrar_modal, "Cerrar esta ventana")

    def editar_por_id(self, recepcion_id, modal):
        modal.destroy()
        self.mostrar_formulario()
        self.cargar_recepcion_para_editar_por_id(recepcion_id)

    # ========== EDICIÓN ==========
    def editar_recepcion(self):
        if not tiene_permiso(self.permisos, "recepcion", "editar"):
            if not self._verificar_password_admin():
                return
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            self.mostrar_formulario()
            self.cargar_recepcion_para_editar_por_id(recepcion_id)
        else:
            messagebox.showerror("Error", "No se pudo identificar la recepción")

    def cargar_recepcion_para_editar_por_id(self, recepcion_id):
        query = """
            SELECT r.id, r.numero_carga, r.fecha_hora, r.fecha_corte,
                   l.id as lote_id, l.numero_lote,
                   c.id as centro_id, c.nombre as centro,
                   p.id as productor_id, p.nombre as productor,
                   ca.id as campo_id, ca.nombre as campo,
                   rh.id as rh_id, rh.nombre as registro_huerto,
                   r.variedad, r.tipo_caja, r.cajas_llenas, r.cajas_vacias,
                   r.tipo_cultivo, r.fair_trade,
                   ch.id as chofer_id, ch.nombre as chofer,
                   r.placas_tractor, r.placas_caja, r.cuadrillas, r.inspector,
                   r.produccion, r.estatus
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
            LEFT JOIN productores p ON r.productor_id = p.id
            LEFT JOIN campos ca ON r.campo_id = ca.id
            LEFT JOIN registros_huerto rh ON r.registro_huerto_id = rh.id
            LEFT JOIN choferes ch ON r.chofer_id = ch.id
            WHERE r.id = %s
        """
        datos = ejecutar_consulta(query, (recepcion_id,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", "No se encontraron datos para esta recepción")
            return
        self.modo_edicion = True
        self.recepcion_id = datos[0]
        self.numero_carga_combo.set(datos[1])
        self.fecha_recep_entry.set_date(datos[2])
        self.fecha_corte_entry.set_date(datos[3])
        self.lote_combo.set(datos[5] if datos[5] else "")
        self.centro_combo.set(datos[7] if datos[7] else "")
        self.productor_combo.set(datos[9] if datos[9] else "")
        self.campo_combo.set(datos[11] if datos[11] else "")
        self.registro_huerto_combo.set(datos[13] if datos[13] else "")
        # Ahora la variedad se carga desde la BD, pero se asigna el valor guardado
        if datos[14]:
            self.variedad_combo.set(datos[14].title())
        self.tipo_caja_combo.set(datos[15].upper() if datos[15] else "GRANDE")
        self.cajas_llenas_entry.delete(0, "end")
        self.cajas_llenas_entry.insert(0, str(datos[16]) if datos[16] else "")
        self.cajas_vacias_entry.delete(0, "end")
        self.cajas_vacias_entry.insert(0, str(datos[17]) if datos[17] else "")
        self.cultivo_var.set(datos[18].upper() if datos[18] else "CONVENCIONAL")
        self.fair_trade_var.set(datos[19] if datos[19] else False)
        self.chofer_combo.set(datos[21] if datos[21] else "")
        self.placas_entry.delete(0, "end")
        self.placas_entry.insert(0, datos[22] if datos[22] else "")
        self.remolque_entry.delete(0, "end")
        self.remolque_entry.insert(0, datos[23] if datos[23] else "")
        self.cuadrillas_entry.delete(0, "end")
        self.cuadrillas_entry.insert(0, datos[24] if datos[24] else "")
        self.inspector_entry.delete(0, "end")
        self.inspector_entry.insert(0, datos[25] if datos[25] else "")
        self.observaciones_text.delete("1.0", "end")
        self.observaciones_text.insert("1.0", datos[26] if datos[26] else "")
        messagebox.showinfo("Editar", "Recepción cargada para edición")

    # ========== GUARDADO ==========
    def _obtener_o_crear_id(self, tabla, campo_busqueda, valor, valores_extra=None):
        if not valor or not valor.strip():
            return None
        if tabla in ['productores', 'centros_abastecimiento', 'campos', 'registros_huerto', 'choferes']:
            valor = valor.strip().upper()
        else:
            valor = valor.strip().upper()
        query = f"SELECT id FROM {tabla} WHERE {campo_busqueda} = %s"
        resultado = ejecutar_consulta(query, (valor,), fetchone=True)
        if resultado:
            return resultado[0]
        campos = [campo_busqueda]
        valores_placeholder = [valor]
        if valores_extra:
            for k, v in valores_extra.items():
                campos.append(k)
                valores_placeholder.append(v)
        placeholders = ", ".join(["%s"] * len(campos))
        insert_query = f"INSERT INTO {tabla} ({', '.join(campos)}) VALUES ({placeholders})"
        try:
            ejecutar_consulta(insert_query, tuple(valores_placeholder))
            nuevo_id = ejecutar_consulta(f"SELECT id FROM {tabla} WHERE {campo_busqueda} = %s", (valor,), fetchone=True)[0]
            return nuevo_id
        except Exception as e:
            print(f"Error al insertar en {tabla}: {e}")
            resultado = ejecutar_consulta(query, (valor,), fetchone=True)
            return resultado[0] if resultado else None

    def _validar_carga_unica(self, numero_carga, lote_id, id_actual=None):
        if id_actual:
            query = "SELECT id FROM recepcion_carga WHERE numero_carga = %s AND lote_id = %s AND id != %s"
            resultado = ejecutar_consulta(query, (numero_carga, lote_id, id_actual), fetchone=True)
        else:
            query = "SELECT id FROM recepcion_carga WHERE numero_carga = %s AND lote_id = %s"
            resultado = ejecutar_consulta(query, (numero_carga, lote_id), fetchone=True)
        return resultado is None

    def _verificar_consistencia_con_carga_existente(self, numero_carga, datos_actuales):
        query = """
            SELECT id, lote_id, 
                   centro_abastecimiento_id, productor_id, campo_id,
                   registro_huerto_id, tipo_cultivo, fair_trade, chofer_id,
                   placas_tractor, placas_caja, cuadrillas, inspector, fecha_corte
            FROM recepcion_carga
            WHERE numero_carga = %s AND lote_id != %s
            LIMIT 1
        """
        resultado = ejecutar_consulta(query, (numero_carga, datos_actuales["lote_id"]), fetchone=True)
        if not resultado:
            return True, ""

        campos = {
            2: ("centro_abastecimiento_id", "Centro de Abastecimiento"),
            3: ("productor_id", "Productor"),
            4: ("campo_id", "Campo"),
            5: ("registro_huerto_id", "Registro de Huerto"),
            6: ("tipo_cultivo", "Tipo de Cultivo"),
            7: ("fair_trade", "Fair Trade"),
            8: ("chofer_id", "Chofer"),
            9: ("placas_tractor", "Placas del Tractor"),
            10: ("placas_caja", "Placas de la Caja"),
            11: ("cuadrillas", "Cuadrillas"),
            12: ("inspector", "Inspector"),
            13: ("fecha_corte", "Fecha de Corte")
        }

        for idx, (campo_bd, nombre_campo) in campos.items():
            valor_bd = resultado[idx]
            valor_actual = datos_actuales.get(campo_bd)
            if valor_bd != valor_actual:
                mensaje = (f"El número de carga '{numero_carga}' ya tiene otra recepción con lote diferente.\n"
                           f"El campo '{nombre_campo}' no coincide con el registro existente.\n"
                           f"Para usar el mismo número de carga, solo puede cambiar el lote. Los demás datos deben ser idénticos.")
                return False, mensaje

        return True, ""

    def guardar_recepcion(self):
        numero_carga = self.numero_carga_combo.get().strip().upper()
        if not numero_carga:
            messagebox.showerror("Error", "El número de carga es obligatorio")
            return
        self._normalizar_lote()
        lote_texto = self.lote_combo.get().strip().upper()
        if not lote_texto:
            messagebox.showerror("Error", "Debe ingresar un lote")
            return
        if not re.match(r'^L-\d{3}$', lote_texto):
            messagebox.showerror("Error", "El lote debe tener el formato L-XXX (ejemplo: L-001).")
            return
        
        lote_id = self._obtener_o_crear_id('lotes', 'numero_lote', lote_texto, {'activo': True})
        
        if not self._validar_carga_unica(numero_carga, lote_id, self.recepcion_id if self.modo_edicion else None):
            messagebox.showerror("Error", f"Ya existe una recepción con el número de carga '{numero_carga}' y el lote '{lote_texto}'.\nPuede usar el mismo número de carga solo si el lote es diferente.")
            self.numero_carga_combo.focus()
            return
        
        centro_texto = self.centro_combo.get().strip().upper()
        centro_id = self._obtener_o_crear_id('centros_abastecimiento', 'nombre', centro_texto, {'activo': True}) if centro_texto else None
        productor_nombre = self.productor_combo.get().strip().upper()
        productor_id = self._obtener_o_crear_id('productores', 'nombre', productor_nombre, {'activo': True}) if productor_nombre else None
        campo_nombre = self.campo_combo.get().strip().upper()
        campo_id = self._obtener_o_crear_id('campos', 'nombre', campo_nombre, {'activo': True}) if campo_nombre else None
        rh_nombre = self.registro_huerto_combo.get().strip().upper()
        rh_id = self._obtener_o_crear_id('registros_huerto', 'nombre', rh_nombre, {'activo': True}) if rh_nombre else None
        chofer_nombre = self.chofer_combo.get().strip().upper()
        chofer_id = self._obtener_o_crear_id('choferes', 'nombre', chofer_nombre, {'activo': True}) if chofer_nombre else None
        tipo_cultivo = self.cultivo_var.get().upper()
        fair_trade = self.fair_trade_var.get()
        placas_tractor = self.placas_entry.get().strip().upper() or None
        placas_caja = self.remolque_entry.get().strip().upper() or None
        cuadrillas = self.cuadrillas_entry.get().strip().upper() or None
        inspector = self.inspector_entry.get().strip().upper() or None
        fecha_corte = self.fecha_corte_entry.get_date()

        datos_actuales = {
            "lote_id": lote_id,
            "centro_abastecimiento_id": centro_id,
            "productor_id": productor_id,
            "campo_id": campo_id,
            "registro_huerto_id": rh_id,
            "tipo_cultivo": tipo_cultivo,
            "fair_trade": fair_trade,
            "chofer_id": chofer_id,
            "placas_tractor": placas_tractor,
            "placas_caja": placas_caja,
            "cuadrillas": cuadrillas,
            "inspector": inspector,
            "fecha_corte": fecha_corte
        }

        if not self.modo_edicion:
            consistente, msg_error = self._verificar_consistencia_con_carga_existente(numero_carga, datos_actuales)
            if not consistente:
                messagebox.showerror("Inconsistencia en los datos", msg_error)
                return

        try:
            cajas_llenas = int(self.cajas_llenas_entry.get()) if self.cajas_llenas_entry.get().strip() else 0
            if cajas_llenas < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Cajas llenas debe ser un número entero positivo")
            self.cajas_llenas_entry.focus()
            return
        try:
            cajas_vacias = int(self.cajas_vacias_entry.get()) if self.cajas_vacias_entry.get().strip() else 0
            if cajas_vacias < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Cajas vacías debe ser un número entero positivo")
            self.cajas_vacias_entry.focus()
            return
        
        folio = self.folio_entry.get()
        fecha_recepcion = self.fecha_recep_entry.get_date()
        variedad = self.variedad_combo.get().upper()
        tipo_caja = self.tipo_caja_combo.get().upper()
        observaciones = self.observaciones_text.get("1.0", "end-1c").strip().upper()
        now = datetime.now()
        usuario = "admin"
        try:
            with open("session_user.txt", "r") as f:
                contenido = f.read().strip()
                if "|" in contenido:
                    usuario = contenido.split("|")[0]
                else:
                    usuario = contenido
        except:
            pass
        
        if self.modo_edicion and self.recepcion_id:
            query = """
                UPDATE recepcion_carga SET
                    numero_carga=%s, fecha_hora=%s, lote_id=%s, centro_abastecimiento_id=%s,
                    productor_id=%s, campo_id=%s, registro_huerto_id=%s,
                    variedad=%s, tipo_caja=%s, cajas_llenas=%s, cajas_vacias=%s,
                    tipo_cultivo=%s, fair_trade=%s, chofer_id=%s, placas_tractor=%s, placas_caja=%s,
                    cuadrillas=%s, inspector=%s, produccion=%s, fecha_corte=%s,
                    updated_at = %s
                WHERE id=%s
            """
            params = (numero_carga, fecha_recepcion, lote_id, centro_id,
                      productor_id, campo_id, rh_id,
                      variedad, tipo_caja, cajas_llenas, cajas_vacias,
                      tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                      cuadrillas, inspector, observaciones, fecha_corte,
                      now, self.recepcion_id)
            ejecutar_consulta(query, params)
            messagebox.showinfo("Éxito", f"Recepción {folio} actualizada correctamente")
        else:
            query = """
                INSERT INTO recepcion_carga 
                (folio, numero_carga, fecha_hora, lote_id, centro_abastecimiento_id,
                 productor_id, campo_id, registro_huerto_id,
                 variedad, tipo_caja, cajas_llenas, cajas_vacias,
                 tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                 cuadrillas, inspector, produccion, usuario_creacion, fecha_corte,
                 estatus, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (folio, numero_carga, fecha_recepcion, lote_id, centro_id,
                      productor_id, campo_id, rh_id,
                      variedad, tipo_caja, cajas_llenas, cajas_vacias,
                      tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                      cuadrillas, inspector, observaciones, usuario, fecha_corte,
                      "PENDIENTE", now, now)
            ejecutar_consulta(query, params)
            messagebox.showinfo("Éxito", f"Recepción {folio} guardada correctamente")
        
        self.limpiar_formulario()
        self.generar_folio()
        self.cargar_catalogos()
        self.cargar_recepciones_recientes()
        self.cargar_lista_numeros_carga()
        self.modo_edicion = False
        self.recepcion_id = None

    def limpiar_formulario(self):
        self.numero_carga_combo.set("")
        self.lote_combo.set("")
        self.fecha_recep_entry.set_date(datetime.now())
        self.fecha_corte_entry.set_date(datetime.now())
        self.centro_combo.set("")
        self.productor_combo.set("")
        self.campo_combo.set("")
        self.registro_huerto_combo.set("")
        # Mantener la variedad seleccionada? mejor dejarla como está o poner el primer valor
        if self.variedad_combo['values']:
            self.variedad_combo.set(self.variedad_combo['values'][0])
        else:
            self.variedad_combo.set("")
        self.tipo_caja_combo.set("GRANDE")
        self.cajas_llenas_entry.delete(0, "end")
        self.cajas_vacias_entry.delete(0, "end")
        self.cultivo_var.set("CONVENCIONAL")
        self.fair_trade_var.set(False)
        self.chofer_combo.set("")
        self.placas_entry.delete(0, "end")
        self.remolque_entry.delete(0, "end")
        self.cuadrillas_entry.delete(0, "end")
        self.inspector_entry.delete(0, "end")
        self.observaciones_text.delete("1.0", "end")

    # ========== ELIMINAR ==========
    def eliminar_recepcion(self):
        if not tiene_permiso(self.permisos, "recepcion", "eliminar"):
            if not self._verificar_password_admin():
                return
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        carga = item['values'][0] if item['values'] else "?"
        if not recepcion_id:
            messagebox.showerror("Error", "No se pudo identificar la recepción")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar la recepción con carga {carga}?\nEsta acción no se puede deshacer."):
            try:
                ejecutar_consulta("DELETE FROM recepcion_carga WHERE id = %s", (recepcion_id,))
                messagebox.showinfo("Eliminado", "Recepción eliminada correctamente")
                if self.modo_edicion and self.recepcion_id == recepcion_id:
                    self.limpiar_formulario()
                    self.generar_folio()
                    self.modo_edicion = False
                    self.recepcion_id = None
                self.cargar_recepciones_recientes()
                self.cargar_lista_numeros_carga()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar: {e}")

    # ========== EXPORTAR EXCEL ==========
    def exportar_excel(self):
        datos = self.tree.get_children()
        if not datos:
            messagebox.showwarning("Sin datos", "No hay datos para exportar")
            return
        columnas = ["No. Carga", "Lote", "Fecha", "Hora", "Productor", "Cajas Llenas", "Estado"]
        filas = [self.tree.item(item)["values"] for item in datos]
        df = pd.DataFrame(filas, columns=columnas)
        archivo = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if archivo:
            df.to_excel(archivo, index=False)
            messagebox.showinfo("Éxito", f"Exportado a {archivo}")

    def recargar_datos(self):
        self.cargar_catalogos()
        self.cargar_recepciones_recientes()
        self.cargar_lista_numeros_carga()
        self.generar_folio()
        messagebox.showinfo("Actualizado", "Datos actualizados correctamente")

    def _verificar_password_admin(self):
        password = simpledialog.askstring("Autorización requerida", 
                                          "Esta acción requiere permisos de administrador.\nIngrese la contraseña del administrador:", 
                                          show='*')
        if not password:
            return False
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        admin_hash = ejecutar_consulta("SELECT contrasena_hash FROM usuarios WHERE rol = 'admin' LIMIT 1", fetchone=True)
        if admin_hash and admin_hash[0] == hash_pass:
            return True
        messagebox.showerror("Acceso denegado", "Contraseña incorrecta. No tiene permiso para realizar esta acción.")
        return False

    # ========== BOLETA PDF ==========
    def _to_title_case(self, texto):
        if not texto:
            return ""
        return texto.title()

    def imprimir_boleta(self, folio=None):
        if not folio:
            seleccion = self.tree.selection()
            if not seleccion:
                messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
                return
            item = self.tree.item(seleccion[0])
            recepcion_id = item['tags'][0] if item['tags'] else None
            if not recepcion_id:
                messagebox.showerror("Error", "No se pudo identificar la recepción")
                return
            folio = ejecutar_consulta("SELECT folio FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
            if folio:
                folio = folio[0]
        pdf_path = self._generar_pdf_boleta_por_folio(folio)
        if pdf_path and os.path.exists(pdf_path):
            try:
                webbrowser.open(pdf_path)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el PDF: {e}")

    def imprimir_boleta_por_id(self, recepcion_id):
        folio = ejecutar_consulta("SELECT folio FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
        if folio:
            pdf_path = self._generar_pdf_boleta_por_folio(folio[0])
            if pdf_path and os.path.exists(pdf_path):
                try:
                    webbrowser.open(pdf_path)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo abrir el PDF: {e}")

    def _generar_pdf_boleta_por_folio(self, folio):
        query = """
            SELECT r.folio, r.numero_carga, 
                   to_char(r.fecha_corte, 'DD/MM/YYYY') as fecha_corte,
                   to_char(r.fecha_hora, 'DD/MM/YYYY') as fecha_recepcion,
                   l.numero_lote,
                   c.nombre as centro,
                   p.nombre as productor,
                   r.campo_id,
                   r.registro_huerto_id,
                   r.variedad, r.tipo_caja, r.cajas_llenas, r.cajas_vacias,
                   r.tipo_cultivo, r.fair_trade
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
            LEFT JOIN productores p ON r.productor_id = p.id
            WHERE r.folio = %s
        """
        datos = ejecutar_consulta(query, (folio,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", f"No se encontró la recepción con folio {folio}")
            return None

        campo_nombre = ""
        if datos[7]:
            res = ejecutar_consulta("SELECT nombre FROM campos WHERE id = %s", (datos[7],), fetchone=True)
            if res:
                campo_nombre = self._to_title_case(res[0])
        rh_nombre = ""
        if datos[8]:
            res = ejecutar_consulta("SELECT nombre FROM registros_huerto WHERE id = %s", (datos[8],), fetchone=True)
            if res:
                rh_nombre = self._to_title_case(res[0])

        fair_trade_valor = "Sí" if datos[14] else "No"

        boleta_data = {
            "folio": datos[0],
            "carga": datos[1],
            "fecha_corte": datos[2],
            "fecha_recepcion": datos[3],
            "lote": datos[4],
            "centro": self._to_title_case(datos[5] if datos[5] else ""),
            "productor": self._to_title_case(datos[6] if datos[6] else ""),
            "campo": campo_nombre,
            "registro_huerto": rh_nombre,
            "variedad": self._to_title_case(datos[9] if datos[9] else ""),
            "tipo_caja": self._to_title_case(datos[10] if datos[10] else ""),
            "cajas_llenas": datos[11] or 0,
            "cajas_vacias": datos[12] or 0,
            "tipo_cultivo": self._to_title_case(datos[13] if datos[13] else ""),
            "fair_trade": fair_trade_valor
        }
        return self.generar_pdf_boleta(boleta_data)

    def generar_pdf_boleta(self, data):
        os.makedirs("reportes", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join("reportes", f"Boleta_{data['folio']}_{timestamp}.pdf")

        doc = SimpleDocTemplate(archivo, pagesize=MEDIA_CARTA_VERTICAL,
                                topMargin=0.6*cm, bottomMargin=0.6*cm,
                                leftMargin=0.6*cm, rightMargin=0.6*cm)
        styles = getSampleStyleSheet()
        estilo_titulo = ParagraphStyle('Titulo', parent=styles['Title'],
                                       fontSize=10, alignment=1, spaceAfter=4)
        estilo_seccion = ParagraphStyle('Seccion', parent=styles['Normal'],
                                        fontSize=8, alignment=0, spaceAfter=3, spaceBefore=4,
                                        fontName='Helvetica-Bold')
        estilo_normal = ParagraphStyle('Normal', parent=styles['Normal'],
                                       fontSize=7, leading=9, allowHtml=True)
        estilo_linea = ParagraphStyle('Linea', parent=styles['Normal'],
                                      fontSize=7, leading=8, alignment=0)

        elementos = []
        elementos.append(Paragraph("RECEPCIÓN Y ASIGNACIÓN DE LOTE", estilo_titulo))
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.15*cm))

        cabecera = [
            [f"FECHA DE CORTE    : {data['fecha_corte']}", f"NO. CARGA    : {data['carga']}"],
            [f"FECHA RECEPCIÓN   : {data['fecha_recepcion']}", f"NO. : {data['lote']}"]
        ]
        tabla_cab = Table(cabecera, colWidths=[5*cm, 5*cm])
        tabla_cab.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        elementos.append(tabla_cab)
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.2*cm))

        elementos.append(Paragraph(" DATOS DE ORIGEN", estilo_seccion))
        origen = [
            f"  CENTRO DE ABASTECIMIENTO : {data['centro']}",
            f"  PRODUCTOR                 : {data['productor']}",
            f"  CAMPO                     : {data['campo']}",
            f"  R. DE HUERTO              : {data['registro_huerto']}"
        ]
        for line in origen:
            elementos.append(Paragraph(line, estilo_normal))
            elementos.append(Spacer(1, 0.1*cm))
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.2*cm))

        elementos.append(Paragraph("DATOS DE PRODUCTO", estilo_seccion))
        producto_texto = "Mango"
        tipo_caja_texto = data['tipo_caja']
        cultivo_texto = data['tipo_cultivo']
        fair_trade_texto = data['fair_trade']
        producto_tabla = [
            [f"PRODUCTO      : {producto_texto}", f"VARIEDAD      : {data['variedad']}"],
            [f"TIPO CAJA     : {tipo_caja_texto}", f"CAJAS CON PROD: {data['cajas_llenas']}"],
            [f"CAJAS VACÍAS  : {data['cajas_vacias']}", f"CULTIVO       : {cultivo_texto}"],
            [f"FAIR TRADE    : {fair_trade_texto}", ""]
        ]
        tabla_prod = Table(producto_tabla, colWidths=[5*cm, 5*cm])
        tabla_prod.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        elementos.append(tabla_prod)
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.3*cm))

        elementos.append(Paragraph("ELABORÓ", ParagraphStyle('Elaboro', parent=styles['Normal'],
                                                             alignment=1, fontSize=7, spaceAfter=2)))
        elementos.append(Paragraph("_________________________", ParagraphStyle('Firma', parent=styles['Normal'],
                                                                               alignment=1, fontSize=9)))
        doc.build(elementos)
        return archivo

    # ========== ENVÍO DE CORREO ==========
    def enviar_boleta_email(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            self.enviar_boleta_por_id(recepcion_id)
        else:
            messagebox.showerror("Error", "No se pudo identificar la recepción")

    def enviar_boleta_por_id(self, recepcion_id):
        folio = ejecutar_consulta("SELECT folio FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
        if not folio:
            messagebox.showerror("Error", "No se encontró la recepción")
            return
        folio = folio[0]
        pdf_path = self._generar_pdf_boleta_por_folio(folio)
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("Error", "No se pudo generar el PDF")
            return
        email_to = simpledialog.askstring("Enviar Boleta", "Ingrese la dirección de correo electrónico del destinatario:")
        if not email_to:
            return
        try:
            from_addr = "santana.mango.sistema@gmail.com"
            password = simpledialog.askstring("Contraseña", "Ingrese la contraseña del correo emisor:", show='*')
            if not password:
                return
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = email_to
            msg['Subject'] = f"Boleta de recepción {folio}"
            body = f"Adjunto encontrará la boleta de la recepción {folio}.\n\nGracias por usar Santana Mango Manager."
            msg.attach(MIMEText(body, 'plain'))
            with open(pdf_path, "rb") as adj:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(adj.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename=Boleta_{folio}.pdf')
                msg.attach(part)
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(from_addr, password)
            server.send_message(msg)
            server.quit()
            messagebox.showinfo("Enviado", f"Boleta enviada a {email_to}")
        except Exception as e:
            messagebox.showerror("Error de envío", f"No se pudo enviar el correo: {e}")

if __name__ == "__main__":
    pass    # modulos/recepcion.py - Versión final con autocompletado, gestión de estados y variedades desde BD
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import ejecutar_consulta
from datetime import datetime
from tkcalendar import DateEntry
import pandas as pd
import hashlib
import re
import os
import subprocess
import smtplib
import webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from utils.tooltip import crear_tooltip
from reportlab.lib.pagesizes import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from auth import tiene_permiso

MEDIA_CARTA_VERTICAL = (5.5 * inch, 8.5 * inch)

class VentanaRecepcion(ctk.CTkFrame):
    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.modo_edicion = False
        self.recepcion_id = None
        self.mostrar_filtros = False
        self.search_after_id = None

        self.pack(fill="both", expand=True)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.bind("<F11>", self.toggle_fullscreen)

        self._asegurar_columnas_timestamp()
        self._asegurar_estatus()

        # ---------- BARRA DE NAVEGACIÓN ----------
        nav_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("#e0e0e0", "#2a2a2a"))
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_columnconfigure(1, weight=1)

        self.btn_regresar = ctk.CTkButton(nav_bar, text="◀ REGRESAR", command=self.regresar_menu,
                                          width=150, height=35, fg_color="#8b0000", font=("Arial", 12, "bold"))
        self.btn_regresar.grid(row=0, column=0, padx=10, pady=5)
        crear_tooltip(self.btn_regresar, "Volver al menú principal")

        ctk.CTkLabel(nav_bar, text="🚚 RECEPCIÓN DE CARGA", font=("Arial", 20, "bold"),
                     text_color="#2e8b57").grid(row=0, column=1)

        self.btn_refrescar = ctk.CTkButton(nav_bar, text="🔄", command=self.recargar_datos,
                                           width=40, height=35, fg_color="#3a6ea5")
        self.btn_refrescar.grid(row=0, column=2, padx=10, pady=5)
        crear_tooltip(self.btn_refrescar, "Refrescar catálogos y tabla")

        # ---------- SCROLLABLE (todo el contenido) ----------
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        # --- FORMULARIO DE CAPTURA (se oculta al buscar) ---
        self.form_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.form_container.pack(fill="both", expand=True)

        main_container = self.form_container

        col1 = ctk.CTkFrame(main_container, fg_color="transparent")
        col1.pack(side="left", fill="both", expand=True, padx=(0, 5))
        col2 = ctk.CTkFrame(main_container, fg_color="transparent")
        col2.pack(side="left", fill="both", expand=True, padx=5)
        col3 = ctk.CTkFrame(main_container, fg_color="transparent")
        col3.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # Tarjeta DATOS GENERALES
        card_gen = self._crear_tarjeta(col1, "📋 DATOS GENERALES")
        grid_gen = ctk.CTkFrame(card_gen, fg_color="transparent")
        grid_gen.pack(fill="x", padx=15, pady=10)
        grid_gen.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_gen, text="FOLIO:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.folio_entry = ctk.CTkEntry(grid_gen, width=160, state="readonly")
        self.folio_entry.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.folio_entry, "Folio autogenerado de la recepción")

        ctk.CTkLabel(grid_gen, text="NO. CARGA (*):", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        self.numero_carga_combo = ttk.Combobox(grid_gen, width=25, state="normal")
        self.numero_carga_combo.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        self.numero_carga_combo.bind("<<ComboboxSelected>>", self.on_carga_seleccionada)
        self.numero_carga_combo.bind("<FocusOut>", self.on_carga_focusout)
        self.numero_carga_combo.bind("<KeyRelease>", lambda e: self._to_upper(self.numero_carga_combo))
        crear_tooltip(self.numero_carga_combo, "Número de carga. Si ya existe, se autocompletan los datos")

        ctk.CTkLabel(grid_gen, text="FECHA RECEPCIÓN:", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.fecha_recep_entry = DateEntry(grid_gen, width=18, date_pattern='yyyy-mm-dd')
        self.fecha_recep_entry.set_date(datetime.now())
        self.fecha_recep_entry.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.fecha_recep_entry, "Fecha en que se recibe la carga")

        ctk.CTkLabel(grid_gen, text="LOTE (*):", font=("Arial", 12, "bold")).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.lote_combo = ttk.Combobox(grid_gen, width=25, state="normal")
        self.lote_combo.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.lote_combo.bind("<FocusOut>", self._normalizar_lote)
        self.lote_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.lote_combo))
        crear_tooltip(self.lote_combo, "Número de lote (ej: L-001). Puede repetir número de carga con diferente lote.")

        ctk.CTkLabel(grid_gen, text="FECHA CORTE:", font=("Arial", 12, "bold")).grid(row=4, column=0, padx=5, pady=6, sticky="e")
        self.fecha_corte_entry = DateEntry(grid_gen, width=18, date_pattern='yyyy-mm-dd')
        self.fecha_corte_entry.set_date(datetime.now())
        self.fecha_corte_entry.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.fecha_corte_entry, "Fecha de corte del producto")

        # Tarjeta ORIGEN
        card_ori = self._crear_tarjeta(col1, "🌾 ORIGEN")
        grid_ori = ctk.CTkFrame(card_ori, fg_color="transparent")
        grid_ori.pack(fill="x", padx=15, pady=10)
        grid_ori.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_ori, text="CENTRO ABASTECIMIENTO:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.centro_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.centro_combo.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        self.centro_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.centro_combo))
        crear_tooltip(self.centro_combo, "Centro de abastecimiento del producto")

        ctk.CTkLabel(grid_ori, text="PRODUCTOR:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        self.productor_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.productor_combo.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        self.productor_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.productor_combo))
        crear_tooltip(self.productor_combo, "Nombre del productor")

        ctk.CTkLabel(grid_ori, text="CAMPO (HUERTO):", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.campo_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.campo_combo.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        self.campo_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.campo_combo))
        crear_tooltip(self.campo_combo, "Campo o huerto de procedencia")

        ctk.CTkLabel(grid_ori, text="REGISTRO HUERTO:", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.registro_huerto_combo = ttk.Combobox(grid_ori, width=40, state="normal")
        self.registro_huerto_combo.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.registro_huerto_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.registro_huerto_combo))
        crear_tooltip(self.registro_huerto_combo, "Registro del huerto")

        # Tarjeta PRODUCTO
        card_prod = self._crear_tarjeta(col2, "📦 PRODUCTO")
        grid_prod = ctk.CTkFrame(card_prod, fg_color="transparent")
        grid_prod.pack(fill="x", padx=15, pady=10)
        grid_prod.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_prod, text="PRODUCTO:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        prod_entry = ctk.CTkEntry(grid_prod, width=160, state="readonly")
        prod_entry.insert(0, "Mango")
        prod_entry.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(prod_entry, "Producto (fijo: Mango)")

        ctk.CTkLabel(grid_prod, text="VARIEDAD:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        # Cargar variedades desde la BD (valores vacíos inicialmente, se llenarán en cargar_catalogos)
        self.variedad_combo = ttk.Combobox(grid_prod, width=28, values=[], state="readonly")
        self.variedad_combo.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.variedad_combo, "Variedad del mango (cargada desde catálogo)")

        ctk.CTkLabel(grid_prod, text="TIPO DE CAJA:", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.tipo_caja_combo = ttk.Combobox(grid_prod, width=28, values=["GRANDE", "CHICA"], state="readonly")
        self.tipo_caja_combo.set("GRANDE")
        self.tipo_caja_combo.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(self.tipo_caja_combo, "Tamaño de la caja")

        ctk.CTkLabel(grid_prod, text="CAJAS LLENAS:", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.cajas_llenas_entry = ctk.CTkEntry(grid_prod, width=120)
        self.cajas_llenas_entry.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.cajas_llenas_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.cajas_llenas_entry))
        self.cajas_llenas_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.cajas_llenas_entry, "Número de cajas llenas")

        ctk.CTkLabel(grid_prod, text="CAJAS VACÍAS:", font=("Arial", 12)).grid(row=4, column=0, padx=5, pady=6, sticky="e")
        self.cajas_vacias_entry = ctk.CTkEntry(grid_prod, width=120)
        self.cajas_vacias_entry.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        self.cajas_vacias_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.cajas_vacias_entry))
        self.cajas_vacias_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.cajas_vacias_entry, "Número de cajas vacías")

        # Tarjeta ORGANIZACIÓN
        card_org = self._crear_tarjeta(col2, "✅ ORGANIZACIÓN")
        grid_org = ctk.CTkFrame(card_org, fg_color="transparent")
        grid_org.pack(fill="x", padx=15, pady=10)
        grid_org.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_org, text="CULTIVO:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        cultivo_frame = ctk.CTkFrame(grid_org, fg_color="transparent")
        cultivo_frame.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        self.cultivo_var = ctk.StringVar(value="CONVENCIONAL")
        ctk.CTkRadioButton(cultivo_frame, text="ORGANICO", variable=self.cultivo_var, value="ORGANICO").pack(side="left", padx=5)
        ctk.CTkRadioButton(cultivo_frame, text="CONVENCIONAL", variable=self.cultivo_var, value="CONVENCIONAL").pack(side="left", padx=5)
        crear_tooltip(cultivo_frame, "Tipo de cultivo (Orgánico o Convencional)")

        self.fair_trade_var = ctk.BooleanVar()
        cb_fair = ctk.CTkCheckBox(grid_org, text="FAIR TRADE", variable=self.fair_trade_var)
        cb_fair.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        crear_tooltip(cb_fair, "Certificación Fair Trade")

        # Tarjeta TRANSPORTE
        card_trans = self._crear_tarjeta(col3, "🚛 TRANSPORTE")
        grid_trans = ctk.CTkFrame(card_trans, fg_color="transparent")
        grid_trans.pack(fill="x", padx=15, pady=10)
        grid_trans.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid_trans, text="CHOFER:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.chofer_combo = ttk.Combobox(grid_trans, width=40, state="normal")
        self.chofer_combo.grid(row=0, column=1, padx=5, pady=6, sticky="w")
        self.chofer_combo.bind("<KeyRelease>", lambda e: self._combo_to_upper(self.chofer_combo))
        crear_tooltip(self.chofer_combo, "Nombre del chofer")

        ctk.CTkLabel(grid_trans, text="PLACAS VEHÍCULO:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=6, sticky="e")
        self.placas_entry = ctk.CTkEntry(grid_trans, width=200)
        self.placas_entry.grid(row=1, column=1, padx=5, pady=6, sticky="w")
        self.placas_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.placas_entry))
        self.placas_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.placas_entry, "Placas del vehículo")

        ctk.CTkLabel(grid_trans, text="REMOLQUE:", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=6, sticky="e")
        self.remolque_entry = ctk.CTkEntry(grid_trans, width=200)
        self.remolque_entry.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        self.remolque_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.remolque_entry))
        self.remolque_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.remolque_entry, "Número de remolque o caja")

        ctk.CTkLabel(grid_trans, text="CUADRILLAS:", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=6, sticky="e")
        self.cuadrillas_entry = ctk.CTkEntry(grid_trans, width=300)
        self.cuadrillas_entry.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        self.cuadrillas_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.cuadrillas_entry))
        self.cuadrillas_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.cuadrillas_entry, "Nombre o identificación de cuadrillas")

        ctk.CTkLabel(grid_trans, text="INSPECTOR:", font=("Arial", 12)).grid(row=4, column=0, padx=5, pady=6, sticky="e")
        self.inspector_entry = ctk.CTkEntry(grid_trans, width=300)
        self.inspector_entry.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        self.inspector_entry.bind("<KeyRelease>", lambda e: self._to_upper(self.inspector_entry))
        self.inspector_entry.bind("<Return>", lambda e: self.guardar_recepcion())
        crear_tooltip(self.inspector_entry, "Nombre del inspector")

        # Tarjeta OBSERVACIONES
        card_obs = self._crear_tarjeta(col3, "📝 OBSERVACIONES")
        self.observaciones_text = ctk.CTkTextbox(card_obs, height=150)
        self.observaciones_text.pack(fill="x", padx=15, pady=10)
        self.observaciones_text.bind("<FocusOut>", self._textbox_to_upper)
        crear_tooltip(self.observaciones_text, "Observaciones adicionales")

        # --- Botón GUARDAR ---
        btn_guardar_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        btn_guardar_frame.pack(fill="x", pady=20)
        self.btn_guardar = ctk.CTkButton(btn_guardar_frame, text="💾 GUARDAR RECEPCIÓN", command=self.guardar_recepcion,
                                         fg_color="#2e8b57", height=50, font=("Arial", 16, "bold"), width=350)
        self.btn_guardar.pack()
        crear_tooltip(self.btn_guardar, "Guardar la recepción en la base de datos")

        # --- BARRA DE ACCIONES ---
        actions_bar = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        actions_bar.pack(fill="x", pady=(0, 10))

        self.btn_editar = ctk.CTkButton(actions_bar, text="✏️ Editar", command=self.editar_recepcion, width=100)
        self.btn_editar.pack(side="left", padx=5)
        crear_tooltip(self.btn_editar, "Editar recepción seleccionada")

        self.btn_eliminar = ctk.CTkButton(actions_bar, text="🗑️ Eliminar", command=self.eliminar_recepcion, width=100, fg_color="#8b0000")
        self.btn_eliminar.pack(side="left", padx=5)
        crear_tooltip(self.btn_eliminar, "Eliminar recepción seleccionada")

        self.btn_excel = ctk.CTkButton(actions_bar, text="📊 Exportar Excel", command=self.exportar_excel, width=120, fg_color="#3a6ea5")
        self.btn_excel.pack(side="left", padx=5)
        crear_tooltip(self.btn_excel, "Exportar tabla a Excel")

        self.btn_imprimir = ctk.CTkButton(actions_bar, text="🖨️ Imprimir Boleta", command=self.imprimir_boleta, width=130, fg_color="#2e8b57")
        self.btn_imprimir.pack(side="left", padx=5)
        crear_tooltip(self.btn_imprimir, "Imprimir boleta de la recepción seleccionada")

        self.btn_enviar_email = ctk.CTkButton(actions_bar, text="📧 Enviar Boleta", command=self.enviar_boleta_email, width=130, fg_color="#e69500")
        self.btn_enviar_email.pack(side="left", padx=5)
        crear_tooltip(self.btn_enviar_email, "Enviar boleta por correo electrónico")

        self.btn_filtros = ctk.CTkButton(actions_bar, text="🔍 Búsqueda", command=self.toggle_filtros, width=100, fg_color="#1f6aa5")
        self.btn_filtros.pack(side="left", padx=5)
        crear_tooltip(self.btn_filtros, "Mostrar/ocultar búsqueda rápida")

        # --- PANEL DE BÚSQUEDA (oculto inicialmente) ---
        self.filtros_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2a2a2a", corner_radius=10)

        search_frame = ctk.CTkFrame(self.filtros_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(search_frame, text="🔍 BÚSQUEDA RÁPIDA:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.buscar_entry = ctk.CTkEntry(search_frame, width=400, placeholder_text="Folio, N° Carga, Lote, Productor, Chofer, Centro, Campo...")
        self.buscar_entry.pack(side="left", padx=5, fill="x", expand=True)
        crear_tooltip(self.buscar_entry, "Escribe para buscar automáticamente (oculta el formulario)")
        self.buscar_entry.bind("<KeyRelease>", self.on_search_key_release)
        self.buscar_entry.bind("<Return>", lambda e: self.aplicar_filtros())

        ctk.CTkLabel(search_frame, text="Ej: L-001, JUAN, REC-20260604, etc.", font=("Arial", 9), text_color="gray").pack(side="left", padx=10)

        fecha_frame = ctk.CTkFrame(self.filtros_frame, fg_color="transparent")
        fecha_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(fecha_frame, text="📅 RANGO DE FECHAS:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.filtro_fecha_desde = DateEntry(fecha_frame, width=12, date_pattern='yyyy-mm-dd')
        self.filtro_fecha_desde.set_date(datetime.now().replace(day=1))
        self.filtro_fecha_desde.pack(side="left", padx=5)
        self.filtro_fecha_desde.bind("<<DateEntrySelected>>", lambda e: self.aplicar_filtros_con_ocultar())
        crear_tooltip(self.filtro_fecha_desde, "Fecha de inicio del rango")

        ctk.CTkLabel(fecha_frame, text="HASTA", font=("Arial", 12)).pack(side="left", padx=2)
        self.filtro_fecha_hasta = DateEntry(fecha_frame, width=12, date_pattern='yyyy-mm-dd')
        self.filtro_fecha_hasta.set_date(datetime.now())
        self.filtro_fecha_hasta.pack(side="left", padx=5)
        self.filtro_fecha_hasta.bind("<<DateEntrySelected>>", lambda e: self.aplicar_filtros_con_ocultar())
        crear_tooltip(self.filtro_fecha_hasta, "Fecha de fin del rango")

        btn_aplicar_fecha = ctk.CTkButton(fecha_frame, text="APLICAR RANGO", command=self.aplicar_filtros_con_ocultar, width=120, fg_color="#3a6ea5")
        btn_aplicar_fecha.pack(side="left", padx=10)
        crear_tooltip(btn_aplicar_fecha, "Aplicar filtro por rango de fechas")

        # --- TABLA DE RECEPCIONES RECIENTES ---
        self.table_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("#f0f0f0", "#2a2a2a"), corner_radius=15)
        self.table_frame.pack(fill="both", expand=True, pady=20)

        ctk.CTkLabel(self.table_frame, text="📋 RECEPCIONES RECIENTES", font=("Arial", 16, "bold"), text_color="#2e8b57").pack(anchor="w", padx=20, pady=(10,5))

        tree_container = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=20, pady=10)

        columnas = ("Carga", "Lote", "Fecha", "Hora", "Productor", "Cajas", "Estado")
        self.tree = ttk.Treeview(tree_container, columns=columnas, show="headings", height=6)

        self.tree.heading("Carga", text="No. Carga")
        self.tree.heading("Lote", text="Lote")
        self.tree.heading("Fecha", text="Fecha")
        self.tree.heading("Hora", text="Hora")
        self.tree.heading("Productor", text="Productor")
        self.tree.heading("Cajas", text="Cajas Llenas")
        self.tree.heading("Estado", text="Estado")

        self.tree.column("Carga", width=100, anchor="center")
        self.tree.column("Lote", width=100, anchor="center")
        self.tree.column("Fecha", width=100, anchor="center")
        self.tree.column("Hora", width=80, anchor="center")
        self.tree.column("Productor", width=180, anchor="center")
        self.tree.column("Cajas", width=80, anchor="center")
        self.tree.column("Estado", width=100, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        crear_tooltip(vsb, "Barra de desplazamiento vertical")

        info_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=5)
        self.lbl_modificacion = ctk.CTkLabel(info_frame, text="", font=("Arial", 10, "italic"), text_color="gray")
        self.lbl_modificacion.pack(anchor="w")
        crear_tooltip(self.lbl_modificacion, "Fecha y hora de la última modificación")

        self.tree.bind("<<TreeviewSelect>>", self.on_seleccionar_fila)
        self.tree.bind("<Double-1>", self.abrir_detalles_desde_tabla)

        self.generar_folio()
        self.cargar_catalogos()
        self.cargar_recepciones_recientes()
        self.cargar_lista_numeros_carga()

        # Guardar referencias
        self.btn_guardar_frame = btn_guardar_frame
        self.actions_bar = actions_bar

    # ========== FUNCIONES AUXILIARES ==========
    def toggle_fullscreen(self, event=None):
        current_state = self.winfo_toplevel().attributes('-fullscreen')
        self.winfo_toplevel().attributes('-fullscreen', not current_state)

    def _to_upper(self, entry_widget):
        contenido = entry_widget.get()
        if contenido != contenido.upper():
            entry_widget.delete(0, "end")
            entry_widget.insert(0, contenido.upper())

    def _combo_to_upper(self, combo_widget):
        texto = combo_widget.get()
        if texto != texto.upper():
            combo_widget.set(texto.upper())

    def _textbox_to_upper(self, event=None):
        contenido = self.observaciones_text.get("1.0", "end-1c")
        if contenido != contenido.upper():
            self.observaciones_text.delete("1.0", "end")
            self.observaciones_text.insert("1.0", contenido.upper())

    def _crear_tarjeta(self, parent, titulo):
        frame = ctk.CTkFrame(parent, fg_color=("#f5f5f5", "#2a2a2a"), corner_radius=15, border_width=1, border_color="#2e8b57")
        frame.pack(fill="x", pady=8)
        ctk.CTkLabel(frame, text=titulo, font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", padx=20, pady=(10,5))
        return frame

    def regresar_menu(self):
        if self.on_regresar:
            self.on_regresar()
        self.destroy()

    def generar_folio(self):
        fecha = datetime.now().strftime("%Y%m%d")
        try:
            count = ejecutar_consulta("SELECT COUNT(*) FROM recepcion_carga WHERE folio LIKE %s", (f"REC-{fecha}-%",), fetchone=True)[0]
            folio = f"REC-{fecha}-{count+1:03d}"
        except:
            folio = f"REC-{fecha}-001"
        self.folio_entry.configure(state="normal")
        self.folio_entry.delete(0, "end")
        self.folio_entry.insert(0, folio)
        self.folio_entry.configure(state="readonly")

    def _normalizar_lote(self, event=None):
        texto = self.lote_combo.get().strip()
        if not texto:
            return
        texto = texto.upper()
        match = re.search(r'(\d+)', texto)
        if match:
            numero = int(match.group(1))
            lote_formateado = f"L-{numero:03d}"
        else:
            lote_formateado = texto
        if lote_formateado != texto:
            self.lote_combo.set(lote_formateado)

    def cargar_catalogos(self):
        try:
            centros = ejecutar_consulta("SELECT nombre FROM centros_abastecimiento WHERE activo=true", fetchall=True)
            self.centro_combo['values'] = [c[0] for c in centros] if centros else []
        except:
            self.centro_combo['values'] = []
        try:
            lotes = ejecutar_consulta("SELECT numero_lote FROM lotes WHERE activo=true ORDER BY numero_lote", fetchall=True)
            self.lote_combo['values'] = [l[0] for l in lotes] if lotes else []
        except:
            self.lote_combo['values'] = []
        try:
            productores = ejecutar_consulta("SELECT nombre FROM productores WHERE activo=true ORDER BY nombre", fetchall=True)
            self.productor_combo['values'] = [p[0] for p in productores] if productores else []
        except:
            self.productor_combo['values'] = []
        try:
            choferes = ejecutar_consulta("SELECT nombre FROM choferes WHERE activo=true ORDER BY nombre", fetchall=True)
            self.chofer_combo['values'] = [c[0] for c in choferes] if choferes else []
        except:
            self.chofer_combo['values'] = []
        try:
            campos = ejecutar_consulta("SELECT nombre FROM campos WHERE activo=true ORDER BY nombre", fetchall=True)
            self.campo_combo['values'] = [c[0] for c in campos] if campos else []
        except:
            self.campo_combo['values'] = []
        try:
            registros = ejecutar_consulta("SELECT nombre FROM registros_huerto WHERE activo=true ORDER BY nombre", fetchall=True)
            self.registro_huerto_combo['values'] = [r[0] for r in registros] if registros else []
        except:
            self.registro_huerto_combo['values'] = []
        # === Cargar variedades desde la base de datos ===
        try:
            variedades = ejecutar_consulta("SELECT nombre FROM variedades WHERE activo=true ORDER BY nombre", fetchall=True)
            self.variedad_combo['values'] = [v[0] for v in variedades] if variedades else []
            if self.variedad_combo['values'] and not self.variedad_combo.get():
                self.variedad_combo.set(self.variedad_combo['values'][0])
        except Exception as e:
            print(f"Error cargando variedades: {e}")
            self.variedad_combo['values'] = []

    def cargar_lista_numeros_carga(self):
        try:
            resultados = ejecutar_consulta("SELECT DISTINCT numero_carga FROM recepcion_carga ORDER BY numero_carga", fetchall=True)
            self.numero_carga_combo['values'] = [r[0] for r in resultados] if resultados else []
        except:
            self.numero_carga_combo['values'] = []

    def on_carga_seleccionada(self, event=None):
        self.cargar_datos_por_numero_carga()

    def on_carga_focusout(self, event=None):
        self.cargar_datos_por_numero_carga()

    def cargar_datos_por_numero_carga(self):
        numero_carga = self.numero_carga_combo.get().strip().upper()
        if not numero_carga:
            return
        query = """
            SELECT centro_abastecimiento_id, productor_id, campo_id, registro_huerto_id,
                   tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                   cuadrillas, inspector, fecha_corte, fecha_hora
            FROM recepcion_carga
            WHERE numero_carga = %s
            LIMIT 1
        """
        datos = ejecutar_consulta(query, (numero_carga,), fetchone=True)
        if datos:
            if datos[0]:
                centro_nombre = ejecutar_consulta("SELECT nombre FROM centros_abastecimiento WHERE id = %s", (datos[0],), fetchone=True)
                self.centro_combo.set(centro_nombre[0] if centro_nombre else "")
            else:
                self.centro_combo.set("")
            if datos[1]:
                prod_nombre = ejecutar_consulta("SELECT nombre FROM productores WHERE id = %s", (datos[1],), fetchone=True)
                self.productor_combo.set(prod_nombre[0] if prod_nombre else "")
            else:
                self.productor_combo.set("")
            if datos[2]:
                campo_nombre = ejecutar_consulta("SELECT nombre FROM campos WHERE id = %s", (datos[2],), fetchone=True)
                self.campo_combo.set(campo_nombre[0] if campo_nombre else "")
            else:
                self.campo_combo.set("")
            if datos[3]:
                rh_nombre = ejecutar_consulta("SELECT nombre FROM registros_huerto WHERE id = %s", (datos[3],), fetchone=True)
                self.registro_huerto_combo.set(rh_nombre[0] if rh_nombre else "")
            else:
                self.registro_huerto_combo.set("")
            if datos[4]:
                self.cultivo_var.set(datos[4])
            if datos[5] is not None:
                self.fair_trade_var.set(datos[5])
            if datos[6]:
                chofer_nombre = ejecutar_consulta("SELECT nombre FROM choferes WHERE id = %s", (datos[6],), fetchone=True)
                self.chofer_combo.set(chofer_nombre[0] if chofer_nombre else "")
            else:
                self.chofer_combo.set("")
            self.placas_entry.delete(0, "end")
            self.placas_entry.insert(0, datos[7] or "")
            self.remolque_entry.delete(0, "end")
            self.remolque_entry.insert(0, datos[8] or "")
            self.cuadrillas_entry.delete(0, "end")
            self.cuadrillas_entry.insert(0, datos[9] or "")
            self.inspector_entry.delete(0, "end")
            self.inspector_entry.insert(0, datos[10] or "")
            if datos[11]:
                self.fecha_corte_entry.set_date(datos[11])
            if datos[12]:
                self.fecha_recep_entry.set_date(datos[12])
            self.lote_combo.set("")
            # No modificar variedad para no sobreescribir la selección del usuario
            # self.variedad_combo.set("ATAULFO")  # <-- eliminado para mantener la lista de BD
            self.tipo_caja_combo.set("GRANDE")
            self.cajas_llenas_entry.delete(0, "end")
            self.cajas_vacias_entry.delete(0, "end")
            self.observaciones_text.delete("1.0", "end")
            self.modo_edicion = False
            self.recepcion_id = None
            self.generar_folio()

    def _asegurar_columnas_timestamp(self):
        try:
            ejecutar_consulta("ALTER TABLE recepcion_carga ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ejecutar_consulta("ALTER TABLE recepcion_carga ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception as e:
            print(f"Error con timestamps: {e}")

    def _asegurar_estatus(self):
        try:
            ejecutar_consulta("ALTER TABLE recepcion_carga ADD COLUMN IF NOT EXISTS estatus VARCHAR(20) DEFAULT 'PENDIENTE'")
        except Exception as e:
            print(f"Error con estatus: {e}")

    # ========== MÉTODOS PARA OCULTAR/MOSTRAR FORMULARIO ==========
    def ocultar_formulario(self):
        if self.form_container.winfo_ismapped():
            self.form_container.pack_forget()

    def mostrar_formulario(self):
        if not self.form_container.winfo_ismapped():
            self.form_container.pack(fill="both", expand=True, before=self.btn_guardar_frame)

    def on_search_key_release(self, event):
        if self.search_after_id:
            self.after_cancel(self.search_after_id)
        self.ocultar_formulario()
        self.search_after_id = self.after(500, self.aplicar_filtros)

    def aplicar_filtros_con_ocultar(self):
        self.ocultar_formulario()
        self.aplicar_filtros()

    def toggle_filtros(self):
        if self.mostrar_filtros:
            self.filtros_frame.pack_forget()
            self.mostrar_filtros = False
            self.btn_filtros.configure(text="🔍 BÚSQUEDA", fg_color="#1f6aa5")
            self.mostrar_formulario()
        else:
            self.filtros_frame.pack(fill="x", padx=0, pady=(5, 10), before=self.table_frame)
            self.mostrar_filtros = True
            self.btn_filtros.configure(text="✖ OCULTAR", fg_color="#8b0000")

    # ========== MÉTODOS DE TABLA ==========
    def cargar_recepciones_recientes(self, sql_extra="", params=()):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            query = """
                SELECT r.id, r.numero_carga,
                       l.numero_lote,
                       to_char(r.created_at, 'DD/MM/YYYY') as fecha,
                       to_char(r.created_at, 'HH24:MI:SS') as hora,
                       p.nombre as productor,
                       r.cajas_llenas,
                       r.estatus
                FROM recepcion_carga r
                LEFT JOIN lotes l ON r.lote_id = l.id
                LEFT JOIN productores p ON r.productor_id = p.id
                LEFT JOIN choferes ch ON r.chofer_id = ch.id
                LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
                LEFT JOIN campos ca ON r.campo_id = ca.id
                LEFT JOIN registros_huerto rh ON r.registro_huerto_id = rh.id
            """
            if sql_extra:
                query += " WHERE " + sql_extra
            query += " ORDER BY r.created_at DESC LIMIT 100"
            resultados = ejecutar_consulta(query, params, fetchall=True)
            for r in resultados:
                productor = r[5].title() if r[5] else ""
                self.tree.insert("", "end", values=(r[1], r[2] or "", r[3], r[4], productor, r[6] or 0, r[7] or "PENDIENTE"), tags=(r[0],))
        except Exception as e:
            print(f"Error cargando recepciones: {e}")

    def aplicar_filtros(self):
        buscar_texto = self.buscar_entry.get().strip()
        condiciones = []
        params = []
        if buscar_texto:
            condiciones.append("""
                (r.folio ILIKE %s OR 
                 r.numero_carga ILIKE %s OR 
                 l.numero_lote ILIKE %s OR 
                 p.nombre ILIKE %s OR 
                 ch.nombre ILIKE %s OR 
                 c.nombre ILIKE %s OR 
                 ca.nombre ILIKE %s OR 
                 rh.nombre ILIKE %s)
            """)
            like = f"%{buscar_texto}%"
            params.extend([like] * 8)
        if self.filtro_fecha_desde.get_date() and self.filtro_fecha_hasta.get_date():
            condiciones.append("DATE(r.created_at) BETWEEN %s AND %s")
            params.append(self.filtro_fecha_desde.get_date())
            params.append(self.filtro_fecha_hasta.get_date())
        sql_extra = " AND ".join(condiciones) if condiciones else ""
        self.cargar_recepciones_recientes(sql_extra, tuple(params))

    def on_seleccionar_fila(self, event):
        seleccion = self.tree.selection()
        if not seleccion:
            self.lbl_modificacion.configure(text="")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            res = ejecutar_consulta("SELECT to_char(updated_at, 'DD/MM/YYYY HH24:MI:SS') FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
            if res:
                self.lbl_modificacion.configure(text=f"Última modificación: {res[0]}")
            else:
                self.lbl_modificacion.configure(text="")
        else:
            self.lbl_modificacion.configure(text="")

    def abrir_detalles_desde_tabla(self, event):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            self.mostrar_formulario()
            self.mostrar_modal_detalles_por_id(recepcion_id)
        else:
            messagebox.showerror("Error", "No se pudo identificar la recepción")

    def mostrar_modal_detalles_por_id(self, recepcion_id):
        query = """
            SELECT r.folio, r.numero_carga, to_char(r.fecha_hora, 'DD/MM/YYYY') as fecha_recep,
                   to_char(r.fecha_corte, 'DD/MM/YYYY') as fecha_corte,
                   l.numero_lote, c.nombre as centro, p.nombre as productor,
                   ca.nombre as campo, rh.nombre as registro_huerto,
                   r.variedad, r.tipo_caja, r.cajas_llenas, r.cajas_vacias,
                   r.tipo_cultivo, r.fair_trade, ch.nombre as chofer,
                   r.placas_tractor, r.placas_caja, r.cuadrillas, r.inspector,
                   r.produccion, r.estatus,
                   to_char(r.created_at, 'DD/MM/YYYY') as creado_fecha,
                   to_char(r.created_at, 'HH24:MI:SS') as creado_hora,
                   to_char(r.updated_at, 'DD/MM/YYYY') as mod_fecha,
                   to_char(r.updated_at, 'HH24:MI:SS') as mod_hora
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
            LEFT JOIN productores p ON r.productor_id = p.id
            LEFT JOIN campos ca ON r.campo_id = ca.id
            LEFT JOIN registros_huerto rh ON r.registro_huerto_id = rh.id
            LEFT JOIN choferes ch ON r.chofer_id = ch.id
            WHERE r.id = %s
        """
        datos = ejecutar_consulta(query, (recepcion_id,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", "No se encontraron datos")
            return
        modal = ctk.CTkToplevel(self)
        modal.title(f"DETALLES DE RECEPCIÓN - {datos[0]}")
        modal.geometry("850x800")
        modal.grab_set()
        main_frame = ctk.CTkFrame(modal, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        col_left = ctk.CTkFrame(main_frame, fg_color="transparent")
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        col_right = ctk.CTkFrame(main_frame, fg_color="transparent")
        col_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        folio = datos[0]
        carga = datos[1]
        fecha_recep = datos[2]
        fecha_corte = datos[3]
        lote = datos[4] or ""
        centro = datos[5].title() if datos[5] else ""
        productor = datos[6].title() if datos[6] else ""
        campo = datos[7].title() if datos[7] else ""
        registro_huerto = datos[8].title() if datos[8] else ""
        variedad = datos[9].title() if datos[9] else ""
        tipo_caja = datos[10].title() if datos[10] else ""
        cajas_llenas = datos[11] or 0
        cajas_vacias = datos[12] or 0
        cultivo = datos[13].title() if datos[13] else ""
        fair_trade = "Sí" if datos[14] else "No"
        chofer = datos[15].title() if datos[15] else ""
        placas = datos[16].upper() if datos[16] else ""
        remolque = datos[17].title() if datos[17] else ""
        cuadrillas = datos[18].title() if datos[18] else ""
        inspector = datos[19].title() if datos[19] else ""
        observaciones = datos[20].title() if datos[20] else ""
        estado = datos[21] if datos[21] else "PENDIENTE"
        creado_fecha = datos[22]
        creado_hora = datos[23]
        mod_fecha = datos[24]
        mod_hora = datos[25]

        ctk.CTkLabel(col_left, text="📋 DATOS GENERALES", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(0,10))
        ctk.CTkLabel(col_left, text=f"FOLIO: {folio}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"NO. CARGA: {carga}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"FECHA RECEPCIÓN: {fecha_recep}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"LOTE: {lote}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"FECHA CORTE: {fecha_corte}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"ESTADO: {estado}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text="\n🌾 ORIGEN", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(15,5))
        ctk.CTkLabel(col_left, text=f"CENTRO: {centro}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"PRODUCTOR: {productor}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"CAMPO: {campo}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_left, text=f"REGISTRO HUERTO: {registro_huerto}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text="📦 PRODUCTO", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(0,10))
        ctk.CTkLabel(col_right, text=f"PRODUCTO: Mango", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"VARIEDAD: {variedad}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"TIPO CAJA: {tipo_caja}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CAJAS LLENAS: {cajas_llenas}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CAJAS VACÍAS: {cajas_vacias}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CULTIVO: {cultivo}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"FAIR TRADE: {fair_trade}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text="\n🚛 TRANSPORTE", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", pady=(15,5))
        ctk.CTkLabel(col_right, text=f"CHOFER: {chofer}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"PLACAS: {placas}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"REMOLQUE: {remolque}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"CUADRILLAS: {cuadrillas}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(col_right, text=f"INSPECTOR: {inspector}", font=("Arial", 12)).pack(anchor="w", pady=3)
        ctk.CTkLabel(modal, text="📝 OBSERVACIONES", font=("Arial", 14, "bold"), text_color="#2e8b57").pack(anchor="w", padx=20, pady=(10,5))
        obs_text = ctk.CTkTextbox(modal, height=100)
        obs_text.pack(fill="x", padx=20, pady=(0,10))
        obs_text.insert("1.0", observaciones)
        obs_text.configure(state="disabled")
        timestamp_frame = ctk.CTkFrame(modal, fg_color="transparent")
        timestamp_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(timestamp_frame, text=f"CREADO EL: {creado_fecha} A LAS {creado_hora}", font=("Arial", 10, "italic")).pack(anchor="w")
        ctk.CTkLabel(timestamp_frame, text=f"ÚLTIMA MODIFICACIÓN: {mod_fecha} A LAS {mod_hora}", font=("Arial", 10, "italic")).pack(anchor="w")
        btn_modal = ctk.CTkFrame(modal, fg_color="transparent")
        btn_modal.pack(fill="x", pady=10)
        btn_editar_modal = ctk.CTkButton(btn_modal, text="✏️ EDITAR", command=lambda: self.editar_por_id(recepcion_id, modal), width=100)
        btn_editar_modal.pack(side="left", padx=20)
        crear_tooltip(btn_editar_modal, "Editar esta recepción")
        btn_imprimir_modal = ctk.CTkButton(btn_modal, text="🖨️ IMPRIMIR BOLETA", command=lambda: self.imprimir_boleta_por_id(recepcion_id), width=130)
        btn_imprimir_modal.pack(side="left", padx=20)
        crear_tooltip(btn_imprimir_modal, "Imprimir boleta de esta recepción")
        btn_email_modal = ctk.CTkButton(btn_modal, text="📧 ENVIAR POR EMAIL", command=lambda: self.enviar_boleta_por_id(recepcion_id), width=130, fg_color="#e69500")
        btn_email_modal.pack(side="left", padx=20)
        crear_tooltip(btn_email_modal, "Enviar boleta por correo electrónico")
        btn_cerrar_modal = ctk.CTkButton(btn_modal, text="CERRAR", command=modal.destroy, width=100, fg_color="#8b0000")
        btn_cerrar_modal.pack(side="right", padx=20)
        crear_tooltip(btn_cerrar_modal, "Cerrar esta ventana")

    def editar_por_id(self, recepcion_id, modal):
        modal.destroy()
        self.mostrar_formulario()
        self.cargar_recepcion_para_editar_por_id(recepcion_id)

    # ========== EDICIÓN ==========
    def editar_recepcion(self):
        if not tiene_permiso(self.permisos, "recepcion", "editar"):
            if not self._verificar_password_admin():
                return
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            self.mostrar_formulario()
            self.cargar_recepcion_para_editar_por_id(recepcion_id)
        else:
            messagebox.showerror("Error", "No se pudo identificar la recepción")

    def cargar_recepcion_para_editar_por_id(self, recepcion_id):
        query = """
            SELECT r.id, r.numero_carga, r.fecha_hora, r.fecha_corte,
                   l.id as lote_id, l.numero_lote,
                   c.id as centro_id, c.nombre as centro,
                   p.id as productor_id, p.nombre as productor,
                   ca.id as campo_id, ca.nombre as campo,
                   rh.id as rh_id, rh.nombre as registro_huerto,
                   r.variedad, r.tipo_caja, r.cajas_llenas, r.cajas_vacias,
                   r.tipo_cultivo, r.fair_trade,
                   ch.id as chofer_id, ch.nombre as chofer,
                   r.placas_tractor, r.placas_caja, r.cuadrillas, r.inspector,
                   r.produccion, r.estatus
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
            LEFT JOIN productores p ON r.productor_id = p.id
            LEFT JOIN campos ca ON r.campo_id = ca.id
            LEFT JOIN registros_huerto rh ON r.registro_huerto_id = rh.id
            LEFT JOIN choferes ch ON r.chofer_id = ch.id
            WHERE r.id = %s
        """
        datos = ejecutar_consulta(query, (recepcion_id,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", "No se encontraron datos para esta recepción")
            return
        self.modo_edicion = True
        self.recepcion_id = datos[0]
        self.numero_carga_combo.set(datos[1])
        self.fecha_recep_entry.set_date(datos[2])
        self.fecha_corte_entry.set_date(datos[3])
        self.lote_combo.set(datos[5] if datos[5] else "")
        self.centro_combo.set(datos[7] if datos[7] else "")
        self.productor_combo.set(datos[9] if datos[9] else "")
        self.campo_combo.set(datos[11] if datos[11] else "")
        self.registro_huerto_combo.set(datos[13] if datos[13] else "")
        # Ahora la variedad se carga desde la BD, pero se asigna el valor guardado
        if datos[14]:
            self.variedad_combo.set(datos[14].title())
        self.tipo_caja_combo.set(datos[15].upper() if datos[15] else "GRANDE")
        self.cajas_llenas_entry.delete(0, "end")
        self.cajas_llenas_entry.insert(0, str(datos[16]) if datos[16] else "")
        self.cajas_vacias_entry.delete(0, "end")
        self.cajas_vacias_entry.insert(0, str(datos[17]) if datos[17] else "")
        self.cultivo_var.set(datos[18].upper() if datos[18] else "CONVENCIONAL")
        self.fair_trade_var.set(datos[19] if datos[19] else False)
        self.chofer_combo.set(datos[21] if datos[21] else "")
        self.placas_entry.delete(0, "end")
        self.placas_entry.insert(0, datos[22] if datos[22] else "")
        self.remolque_entry.delete(0, "end")
        self.remolque_entry.insert(0, datos[23] if datos[23] else "")
        self.cuadrillas_entry.delete(0, "end")
        self.cuadrillas_entry.insert(0, datos[24] if datos[24] else "")
        self.inspector_entry.delete(0, "end")
        self.inspector_entry.insert(0, datos[25] if datos[25] else "")
        self.observaciones_text.delete("1.0", "end")
        self.observaciones_text.insert("1.0", datos[26] if datos[26] else "")
        messagebox.showinfo("Editar", "Recepción cargada para edición")

    # ========== GUARDADO ==========
    def _obtener_o_crear_id(self, tabla, campo_busqueda, valor, valores_extra=None):
        if not valor or not valor.strip():
            return None
        if tabla in ['productores', 'centros_abastecimiento', 'campos', 'registros_huerto', 'choferes']:
            valor = valor.strip().upper()
        else:
            valor = valor.strip().upper()
        query = f"SELECT id FROM {tabla} WHERE {campo_busqueda} = %s"
        resultado = ejecutar_consulta(query, (valor,), fetchone=True)
        if resultado:
            return resultado[0]
        campos = [campo_busqueda]
        valores_placeholder = [valor]
        if valores_extra:
            for k, v in valores_extra.items():
                campos.append(k)
                valores_placeholder.append(v)
        placeholders = ", ".join(["%s"] * len(campos))
        insert_query = f"INSERT INTO {tabla} ({', '.join(campos)}) VALUES ({placeholders})"
        try:
            ejecutar_consulta(insert_query, tuple(valores_placeholder))
            nuevo_id = ejecutar_consulta(f"SELECT id FROM {tabla} WHERE {campo_busqueda} = %s", (valor,), fetchone=True)[0]
            return nuevo_id
        except Exception as e:
            print(f"Error al insertar en {tabla}: {e}")
            resultado = ejecutar_consulta(query, (valor,), fetchone=True)
            return resultado[0] if resultado else None

    def _validar_carga_unica(self, numero_carga, lote_id, id_actual=None):
        if id_actual:
            query = "SELECT id FROM recepcion_carga WHERE numero_carga = %s AND lote_id = %s AND id != %s"
            resultado = ejecutar_consulta(query, (numero_carga, lote_id, id_actual), fetchone=True)
        else:
            query = "SELECT id FROM recepcion_carga WHERE numero_carga = %s AND lote_id = %s"
            resultado = ejecutar_consulta(query, (numero_carga, lote_id), fetchone=True)
        return resultado is None

    def _verificar_consistencia_con_carga_existente(self, numero_carga, datos_actuales):
        query = """
            SELECT id, lote_id, 
                   centro_abastecimiento_id, productor_id, campo_id,
                   registro_huerto_id, tipo_cultivo, fair_trade, chofer_id,
                   placas_tractor, placas_caja, cuadrillas, inspector, fecha_corte
            FROM recepcion_carga
            WHERE numero_carga = %s AND lote_id != %s
            LIMIT 1
        """
        resultado = ejecutar_consulta(query, (numero_carga, datos_actuales["lote_id"]), fetchone=True)
        if not resultado:
            return True, ""

        campos = {
            2: ("centro_abastecimiento_id", "Centro de Abastecimiento"),
            3: ("productor_id", "Productor"),
            4: ("campo_id", "Campo"),
            5: ("registro_huerto_id", "Registro de Huerto"),
            6: ("tipo_cultivo", "Tipo de Cultivo"),
            7: ("fair_trade", "Fair Trade"),
            8: ("chofer_id", "Chofer"),
            9: ("placas_tractor", "Placas del Tractor"),
            10: ("placas_caja", "Placas de la Caja"),
            11: ("cuadrillas", "Cuadrillas"),
            12: ("inspector", "Inspector"),
            13: ("fecha_corte", "Fecha de Corte")
        }

        for idx, (campo_bd, nombre_campo) in campos.items():
            valor_bd = resultado[idx]
            valor_actual = datos_actuales.get(campo_bd)
            if valor_bd != valor_actual:
                mensaje = (f"El número de carga '{numero_carga}' ya tiene otra recepción con lote diferente.\n"
                           f"El campo '{nombre_campo}' no coincide con el registro existente.\n"
                           f"Para usar el mismo número de carga, solo puede cambiar el lote. Los demás datos deben ser idénticos.")
                return False, mensaje

        return True, ""

    def guardar_recepcion(self):
        numero_carga = self.numero_carga_combo.get().strip().upper()
        if not numero_carga:
            messagebox.showerror("Error", "El número de carga es obligatorio")
            return
        self._normalizar_lote()
        lote_texto = self.lote_combo.get().strip().upper()
        if not lote_texto:
            messagebox.showerror("Error", "Debe ingresar un lote")
            return
        if not re.match(r'^L-\d{3}$', lote_texto):
            messagebox.showerror("Error", "El lote debe tener el formato L-XXX (ejemplo: L-001).")
            return
        
        lote_id = self._obtener_o_crear_id('lotes', 'numero_lote', lote_texto, {'activo': True})
        
        if not self._validar_carga_unica(numero_carga, lote_id, self.recepcion_id if self.modo_edicion else None):
            messagebox.showerror("Error", f"Ya existe una recepción con el número de carga '{numero_carga}' y el lote '{lote_texto}'.\nPuede usar el mismo número de carga solo si el lote es diferente.")
            self.numero_carga_combo.focus()
            return
        
        centro_texto = self.centro_combo.get().strip().upper()
        centro_id = self._obtener_o_crear_id('centros_abastecimiento', 'nombre', centro_texto, {'activo': True}) if centro_texto else None
        productor_nombre = self.productor_combo.get().strip().upper()
        productor_id = self._obtener_o_crear_id('productores', 'nombre', productor_nombre, {'activo': True}) if productor_nombre else None
        campo_nombre = self.campo_combo.get().strip().upper()
        campo_id = self._obtener_o_crear_id('campos', 'nombre', campo_nombre, {'activo': True}) if campo_nombre else None
        rh_nombre = self.registro_huerto_combo.get().strip().upper()
        rh_id = self._obtener_o_crear_id('registros_huerto', 'nombre', rh_nombre, {'activo': True}) if rh_nombre else None
        chofer_nombre = self.chofer_combo.get().strip().upper()
        chofer_id = self._obtener_o_crear_id('choferes', 'nombre', chofer_nombre, {'activo': True}) if chofer_nombre else None
        tipo_cultivo = self.cultivo_var.get().upper()
        fair_trade = self.fair_trade_var.get()
        placas_tractor = self.placas_entry.get().strip().upper() or None
        placas_caja = self.remolque_entry.get().strip().upper() or None
        cuadrillas = self.cuadrillas_entry.get().strip().upper() or None
        inspector = self.inspector_entry.get().strip().upper() or None
        fecha_corte = self.fecha_corte_entry.get_date()

        datos_actuales = {
            "lote_id": lote_id,
            "centro_abastecimiento_id": centro_id,
            "productor_id": productor_id,
            "campo_id": campo_id,
            "registro_huerto_id": rh_id,
            "tipo_cultivo": tipo_cultivo,
            "fair_trade": fair_trade,
            "chofer_id": chofer_id,
            "placas_tractor": placas_tractor,
            "placas_caja": placas_caja,
            "cuadrillas": cuadrillas,
            "inspector": inspector,
            "fecha_corte": fecha_corte
        }

        if not self.modo_edicion:
            consistente, msg_error = self._verificar_consistencia_con_carga_existente(numero_carga, datos_actuales)
            if not consistente:
                messagebox.showerror("Inconsistencia en los datos", msg_error)
                return

        try:
            cajas_llenas = int(self.cajas_llenas_entry.get()) if self.cajas_llenas_entry.get().strip() else 0
            if cajas_llenas < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Cajas llenas debe ser un número entero positivo")
            self.cajas_llenas_entry.focus()
            return
        try:
            cajas_vacias = int(self.cajas_vacias_entry.get()) if self.cajas_vacias_entry.get().strip() else 0
            if cajas_vacias < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Cajas vacías debe ser un número entero positivo")
            self.cajas_vacias_entry.focus()
            return
        
        folio = self.folio_entry.get()
        fecha_recepcion = self.fecha_recep_entry.get_date()
        variedad = self.variedad_combo.get().upper()
        tipo_caja = self.tipo_caja_combo.get().upper()
        observaciones = self.observaciones_text.get("1.0", "end-1c").strip().upper()
        now = datetime.now()
        usuario = "admin"
        try:
            with open("session_user.txt", "r") as f:
                contenido = f.read().strip()
                if "|" in contenido:
                    usuario = contenido.split("|")[0]
                else:
                    usuario = contenido
        except:
            pass
        
        if self.modo_edicion and self.recepcion_id:
            query = """
                UPDATE recepcion_carga SET
                    numero_carga=%s, fecha_hora=%s, lote_id=%s, centro_abastecimiento_id=%s,
                    productor_id=%s, campo_id=%s, registro_huerto_id=%s,
                    variedad=%s, tipo_caja=%s, cajas_llenas=%s, cajas_vacias=%s,
                    tipo_cultivo=%s, fair_trade=%s, chofer_id=%s, placas_tractor=%s, placas_caja=%s,
                    cuadrillas=%s, inspector=%s, produccion=%s, fecha_corte=%s,
                    updated_at = %s
                WHERE id=%s
            """
            params = (numero_carga, fecha_recepcion, lote_id, centro_id,
                      productor_id, campo_id, rh_id,
                      variedad, tipo_caja, cajas_llenas, cajas_vacias,
                      tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                      cuadrillas, inspector, observaciones, fecha_corte,
                      now, self.recepcion_id)
            ejecutar_consulta(query, params)
            messagebox.showinfo("Éxito", f"Recepción {folio} actualizada correctamente")
        else:
            query = """
                INSERT INTO recepcion_carga 
                (folio, numero_carga, fecha_hora, lote_id, centro_abastecimiento_id,
                 productor_id, campo_id, registro_huerto_id,
                 variedad, tipo_caja, cajas_llenas, cajas_vacias,
                 tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                 cuadrillas, inspector, produccion, usuario_creacion, fecha_corte,
                 estatus, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (folio, numero_carga, fecha_recepcion, lote_id, centro_id,
                      productor_id, campo_id, rh_id,
                      variedad, tipo_caja, cajas_llenas, cajas_vacias,
                      tipo_cultivo, fair_trade, chofer_id, placas_tractor, placas_caja,
                      cuadrillas, inspector, observaciones, usuario, fecha_corte,
                      "PENDIENTE", now, now)
            ejecutar_consulta(query, params)
            messagebox.showinfo("Éxito", f"Recepción {folio} guardada correctamente")
        
        self.limpiar_formulario()
        self.generar_folio()
        self.cargar_catalogos()
        self.cargar_recepciones_recientes()
        self.cargar_lista_numeros_carga()
        self.modo_edicion = False
        self.recepcion_id = None

    def limpiar_formulario(self):
        self.numero_carga_combo.set("")
        self.lote_combo.set("")
        self.fecha_recep_entry.set_date(datetime.now())
        self.fecha_corte_entry.set_date(datetime.now())
        self.centro_combo.set("")
        self.productor_combo.set("")
        self.campo_combo.set("")
        self.registro_huerto_combo.set("")
        # Mantener la variedad seleccionada? mejor dejarla como está o poner el primer valor
        if self.variedad_combo['values']:
            self.variedad_combo.set(self.variedad_combo['values'][0])
        else:
            self.variedad_combo.set("")
        self.tipo_caja_combo.set("GRANDE")
        self.cajas_llenas_entry.delete(0, "end")
        self.cajas_vacias_entry.delete(0, "end")
        self.cultivo_var.set("CONVENCIONAL")
        self.fair_trade_var.set(False)
        self.chofer_combo.set("")
        self.placas_entry.delete(0, "end")
        self.remolque_entry.delete(0, "end")
        self.cuadrillas_entry.delete(0, "end")
        self.inspector_entry.delete(0, "end")
        self.observaciones_text.delete("1.0", "end")

    # ========== ELIMINAR ==========
    def eliminar_recepcion(self):
        if not tiene_permiso(self.permisos, "recepcion", "eliminar"):
            if not self._verificar_password_admin():
                return
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        carga = item['values'][0] if item['values'] else "?"
        if not recepcion_id:
            messagebox.showerror("Error", "No se pudo identificar la recepción")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar la recepción con carga {carga}?\nEsta acción no se puede deshacer."):
            try:
                ejecutar_consulta("DELETE FROM recepcion_carga WHERE id = %s", (recepcion_id,))
                messagebox.showinfo("Eliminado", "Recepción eliminada correctamente")
                if self.modo_edicion and self.recepcion_id == recepcion_id:
                    self.limpiar_formulario()
                    self.generar_folio()
                    self.modo_edicion = False
                    self.recepcion_id = None
                self.cargar_recepciones_recientes()
                self.cargar_lista_numeros_carga()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar: {e}")

    # ========== EXPORTAR EXCEL ==========
    def exportar_excel(self):
        datos = self.tree.get_children()
        if not datos:
            messagebox.showwarning("Sin datos", "No hay datos para exportar")
            return
        columnas = ["No. Carga", "Lote", "Fecha", "Hora", "Productor", "Cajas Llenas", "Estado"]
        filas = [self.tree.item(item)["values"] for item in datos]
        df = pd.DataFrame(filas, columns=columnas)
        archivo = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if archivo:
            df.to_excel(archivo, index=False)
            messagebox.showinfo("Éxito", f"Exportado a {archivo}")

    def recargar_datos(self):
        self.cargar_catalogos()
        self.cargar_recepciones_recientes()
        self.cargar_lista_numeros_carga()
        self.generar_folio()
        messagebox.showinfo("Actualizado", "Datos actualizados correctamente")

    def _verificar_password_admin(self):
        password = simpledialog.askstring("Autorización requerida", 
                                          "Esta acción requiere permisos de administrador.\nIngrese la contraseña del administrador:", 
                                          show='*')
        if not password:
            return False
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        admin_hash = ejecutar_consulta("SELECT contrasena_hash FROM usuarios WHERE rol = 'admin' LIMIT 1", fetchone=True)
        if admin_hash and admin_hash[0] == hash_pass:
            return True
        messagebox.showerror("Acceso denegado", "Contraseña incorrecta. No tiene permiso para realizar esta acción.")
        return False

    # ========== BOLETA PDF ==========
    def _to_title_case(self, texto):
        if not texto:
            return ""
        return texto.title()

    def imprimir_boleta(self, folio=None):
        if not folio:
            seleccion = self.tree.selection()
            if not seleccion:
                messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
                return
            item = self.tree.item(seleccion[0])
            recepcion_id = item['tags'][0] if item['tags'] else None
            if not recepcion_id:
                messagebox.showerror("Error", "No se pudo identificar la recepción")
                return
            folio = ejecutar_consulta("SELECT folio FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
            if folio:
                folio = folio[0]
        pdf_path = self._generar_pdf_boleta_por_folio(folio)
        if pdf_path and os.path.exists(pdf_path):
            try:
                webbrowser.open(pdf_path)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el PDF: {e}")

    def imprimir_boleta_por_id(self, recepcion_id):
        folio = ejecutar_consulta("SELECT folio FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
        if folio:
            pdf_path = self._generar_pdf_boleta_por_folio(folio[0])
            if pdf_path and os.path.exists(pdf_path):
                try:
                    webbrowser.open(pdf_path)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo abrir el PDF: {e}")

    def _generar_pdf_boleta_por_folio(self, folio):
        query = """
            SELECT r.folio, r.numero_carga, 
                   to_char(r.fecha_corte, 'DD/MM/YYYY') as fecha_corte,
                   to_char(r.fecha_hora, 'DD/MM/YYYY') as fecha_recepcion,
                   l.numero_lote,
                   c.nombre as centro,
                   p.nombre as productor,
                   r.campo_id,
                   r.registro_huerto_id,
                   r.variedad, r.tipo_caja, r.cajas_llenas, r.cajas_vacias,
                   r.tipo_cultivo, r.fair_trade
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN centros_abastecimiento c ON r.centro_abastecimiento_id = c.id
            LEFT JOIN productores p ON r.productor_id = p.id
            WHERE r.folio = %s
        """
        datos = ejecutar_consulta(query, (folio,), fetchone=True)
        if not datos:
            messagebox.showerror("Error", f"No se encontró la recepción con folio {folio}")
            return None

        campo_nombre = ""
        if datos[7]:
            res = ejecutar_consulta("SELECT nombre FROM campos WHERE id = %s", (datos[7],), fetchone=True)
            if res:
                campo_nombre = self._to_title_case(res[0])
        rh_nombre = ""
        if datos[8]:
            res = ejecutar_consulta("SELECT nombre FROM registros_huerto WHERE id = %s", (datos[8],), fetchone=True)
            if res:
                rh_nombre = self._to_title_case(res[0])

        fair_trade_valor = "Sí" if datos[14] else "No"

        boleta_data = {
            "folio": datos[0],
            "carga": datos[1],
            "fecha_corte": datos[2],
            "fecha_recepcion": datos[3],
            "lote": datos[4],
            "centro": self._to_title_case(datos[5] if datos[5] else ""),
            "productor": self._to_title_case(datos[6] if datos[6] else ""),
            "campo": campo_nombre,
            "registro_huerto": rh_nombre,
            "variedad": self._to_title_case(datos[9] if datos[9] else ""),
            "tipo_caja": self._to_title_case(datos[10] if datos[10] else ""),
            "cajas_llenas": datos[11] or 0,
            "cajas_vacias": datos[12] or 0,
            "tipo_cultivo": self._to_title_case(datos[13] if datos[13] else ""),
            "fair_trade": fair_trade_valor
        }
        return self.generar_pdf_boleta(boleta_data)

    def generar_pdf_boleta(self, data):
        os.makedirs("reportes", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join("reportes", f"Boleta_{data['folio']}_{timestamp}.pdf")

        doc = SimpleDocTemplate(archivo, pagesize=MEDIA_CARTA_VERTICAL,
                                topMargin=0.6*cm, bottomMargin=0.6*cm,
                                leftMargin=0.6*cm, rightMargin=0.6*cm)
        styles = getSampleStyleSheet()
        estilo_titulo = ParagraphStyle('Titulo', parent=styles['Title'],
                                       fontSize=10, alignment=1, spaceAfter=4)
        estilo_seccion = ParagraphStyle('Seccion', parent=styles['Normal'],
                                        fontSize=8, alignment=0, spaceAfter=3, spaceBefore=4,
                                        fontName='Helvetica-Bold')
        estilo_normal = ParagraphStyle('Normal', parent=styles['Normal'],
                                       fontSize=7, leading=9, allowHtml=True)
        estilo_linea = ParagraphStyle('Linea', parent=styles['Normal'],
                                      fontSize=7, leading=8, alignment=0)

        elementos = []
        elementos.append(Paragraph("RECEPCIÓN Y ASIGNACIÓN DE LOTE", estilo_titulo))
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.15*cm))

        cabecera = [
            [f"FECHA DE CORTE    : {data['fecha_corte']}", f"NO. CARGA    : {data['carga']}"],
            [f"FECHA RECEPCIÓN   : {data['fecha_recepcion']}", f"NO. : {data['lote']}"]
        ]
        tabla_cab = Table(cabecera, colWidths=[5*cm, 5*cm])
        tabla_cab.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        elementos.append(tabla_cab)
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.2*cm))

        elementos.append(Paragraph(" DATOS DE ORIGEN", estilo_seccion))
        origen = [
            f"  CENTRO DE ABASTECIMIENTO : {data['centro']}",
            f"  PRODUCTOR                 : {data['productor']}",
            f"  CAMPO                     : {data['campo']}",
            f"  R. DE HUERTO              : {data['registro_huerto']}"
        ]
        for line in origen:
            elementos.append(Paragraph(line, estilo_normal))
            elementos.append(Spacer(1, 0.1*cm))
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.2*cm))

        elementos.append(Paragraph("DATOS DE PRODUCTO", estilo_seccion))
        producto_texto = "Mango"
        tipo_caja_texto = data['tipo_caja']
        cultivo_texto = data['tipo_cultivo']
        fair_trade_texto = data['fair_trade']
        producto_tabla = [
            [f"PRODUCTO      : {producto_texto}", f"VARIEDAD      : {data['variedad']}"],
            [f"TIPO CAJA     : {tipo_caja_texto}", f"CAJAS CON PROD: {data['cajas_llenas']}"],
            [f"CAJAS VACÍAS  : {data['cajas_vacias']}", f"CULTIVO       : {cultivo_texto}"],
            [f"FAIR TRADE    : {fair_trade_texto}", ""]
        ]
        tabla_prod = Table(producto_tabla, colWidths=[5*cm, 5*cm])
        tabla_prod.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        elementos.append(tabla_prod)
        elementos.append(Paragraph("." * 60, estilo_linea))
        elementos.append(Spacer(1, 0.3*cm))

        elementos.append(Paragraph("ELABORÓ", ParagraphStyle('Elaboro', parent=styles['Normal'],
                                                             alignment=1, fontSize=7, spaceAfter=2)))
        elementos.append(Paragraph("_________________________", ParagraphStyle('Firma', parent=styles['Normal'],
                                                                               alignment=1, fontSize=9)))
        doc.build(elementos)
        return archivo

    # ========== ENVÍO DE CORREO ==========
    def enviar_boleta_email(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione una recepción de la lista")
            return
        item = self.tree.item(seleccion[0])
        recepcion_id = item['tags'][0] if item['tags'] else None
        if recepcion_id:
            self.enviar_boleta_por_id(recepcion_id)
        else:
            messagebox.showerror("Error", "No se pudo identificar la recepción")

    def enviar_boleta_por_id(self, recepcion_id):
        folio = ejecutar_consulta("SELECT folio FROM recepcion_carga WHERE id = %s", (recepcion_id,), fetchone=True)
        if not folio:
            messagebox.showerror("Error", "No se encontró la recepción")
            return
        folio = folio[0]
        pdf_path = self._generar_pdf_boleta_por_folio(folio)
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("Error", "No se pudo generar el PDF")
            return
        email_to = simpledialog.askstring("Enviar Boleta", "Ingrese la dirección de correo electrónico del destinatario:")
        if not email_to:
            return
        try:
            from_addr = "santana.mango.sistema@gmail.com"
            password = simpledialog.askstring("Contraseña", "Ingrese la contraseña del correo emisor:", show='*')
            if not password:
                return
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = email_to
            msg['Subject'] = f"Boleta de recepción {folio}"
            body = f"Adjunto encontrará la boleta de la recepción {folio}.\n\nGracias por usar Santana Mango Manager."
            msg.attach(MIMEText(body, 'plain'))
            with open(pdf_path, "rb") as adj:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(adj.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename=Boleta_{folio}.pdf')
                msg.attach(part)
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(from_addr, password)
            server.send_message(msg)
            server.quit()
            messagebox.showinfo("Enviado", f"Boleta enviada a {email_to}")
        except Exception as e:
            messagebox.showerror("Error de envío", f"No se pudo enviar el correo: {e}")

if __name__ == "__main__":
    pass    