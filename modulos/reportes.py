# modulos/reportes.py - Añadido reporte de Peso Promedio por Jaba (carga/lote/variedad)
import customtkinter as ctk
from tkinter import messagebox, filedialog
from tkinter import ttk
from database import ejecutar_consulta
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import os

class VentanaReportes(ctk.CTkFrame):
    def __init__(self, parent, permisos, on_regresar=None):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self.permisos = permisos
        self.on_regresar = on_regresar
        self.datos_actuales = []
        self.columnas_actuales = []
        
        # Barra de navegación
        nav_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("#e0e0e0", "#2a2a2a"))
        nav_bar.pack(fill="x")
        self.btn_regresar = ctk.CTkButton(nav_bar, text="◀ REGRESAR", command=self.regresar_menu,
                                          width=150, height=35, fg_color="#8b0000", font=("Arial", 12, "bold"))
        self.btn_regresar.pack(side="left", padx=10, pady=5)
        
        # Título
        ctk.CTkLabel(self, text="📊 Reportes del Sistema", font=("Arial", 24, "bold")).pack(pady=10)
        
        # Frame de filtros
        filtros_frame = ctk.CTkFrame(self)
        filtros_frame.pack(fill="x", padx=20, pady=10)
        
        # Tipo de reporte
        ctk.CTkLabel(filtros_frame, text="Tipo de reporte:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.tipo_reporte = ctk.CTkComboBox(
            filtros_frame,
            values=[
                "📦 Recepciones",
                "⚖️ Pesajes Lavado",
                "📉 Pesajes Rezaga",
                "🚛 Embarques",
                "🐞 Calidad",
                "📊 Resumen General",
                "📊 Peso Promedio por Jaba"   # NUEVO
            ],
            width=220
        )
        self.tipo_reporte.grid(row=0, column=1, padx=10, pady=10)
        self.tipo_reporte.set("📦 Recepciones")
        
        # Agrupar por (solo para el reporte de peso promedio)
        ctk.CTkLabel(filtros_frame, text="Agrupar por:", font=("Arial", 12)).grid(row=0, column=2, padx=10, pady=10, sticky="e")
        self.agrupar_por = ctk.CTkComboBox(
            filtros_frame,
            values=["N° Carga", "Lote", "Variedad"],
            width=120,
            state="readonly"
        )
        self.agrupar_por.grid(row=0, column=3, padx=10, pady=10)
        self.agrupar_por.set("N° Carga")
        # Ocultar inicialmente hasta que se seleccione el reporte de peso promedio
        self.agrupar_por.grid_remove()
        
        # Rango de fechas
        ctk.CTkLabel(filtros_frame, text="Fecha inicio:", font=("Arial", 12)).grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.fecha_inicio = ctk.CTkEntry(filtros_frame, placeholder_text="DD/MM/YYYY", width=120)
        self.fecha_inicio.grid(row=1, column=1, padx=10, pady=5)
        self.fecha_inicio.insert(0, (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y"))
        
        ctk.CTkLabel(filtros_frame, text="Fecha fin:", font=("Arial", 12)).grid(row=1, column=2, padx=10, pady=5, sticky="e")
        self.fecha_fin = ctk.CTkEntry(filtros_frame, placeholder_text="DD/MM/YYYY", width=120)
        self.fecha_fin.grid(row=1, column=3, padx=10, pady=5)
        self.fecha_fin.insert(0, datetime.now().strftime("%d/%m/%Y"))
        
        # Botones
        btn_frame = ctk.CTkFrame(filtros_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=4, pady=15)
        
        self.btn_generar = ctk.CTkButton(btn_frame, text="🔍 Generar", command=self.generar_reporte, width=120, fg_color="#2e8b57")
        self.btn_generar.pack(side="left", padx=10)
        self.btn_exportar_pdf = ctk.CTkButton(btn_frame, text="📄 Exportar PDF", command=self.exportar_pdf, width=120)
        self.btn_exportar_pdf.pack(side="left", padx=10)
        self.btn_exportar_excel = ctk.CTkButton(btn_frame, text="📊 Exportar Excel", command=self.exportar_excel, width=120)
        self.btn_exportar_excel.pack(side="left", padx=10)
        
        # Treeview para resultados
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tree = ttk.Treeview(self.tree_frame, show="headings", height=15)
        self.tree.pack(fill="both", expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        hsb.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Label de resumen
        self.label_resumen = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.label_resumen.pack(pady=10)
        
        # Mostrar/ocultar combo de agrupación según el tipo de reporte
        self.tipo_reporte.bind("<<ComboboxSelected>>", self.on_tipo_reporte_cambiado)
    
    def regresar_menu(self):
        if self.on_regresar:
            self.on_regresar()
        self.destroy()
    
    def on_tipo_reporte_cambiado(self, event=None):
        if "Peso Promedio" in self.tipo_reporte.get():
            self.agrupar_por.grid()
        else:
            self.agrupar_por.grid_remove()
    
    def _parse_fecha(self, fecha_str):
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y")
        except:
            return datetime.now()
    
    def generar_reporte(self):
        tipo = self.tipo_reporte.get()
        
        try:
            fecha_ini = self._parse_fecha(self.fecha_inicio.get())
            fecha_fin = self._parse_fecha(self.fecha_fin.get())
        except:
            messagebox.showerror("Error", "Formato de fecha incorrecto. Use DD/MM/YYYY")
            return
        
        # Limpiar tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Generar según tipo
        if "Recepciones" in tipo:
            self._reporte_recepciones(fecha_ini, fecha_fin)
        elif "Pesajes Lavado" in tipo:
            self._reporte_pesajes_lavado(fecha_ini, fecha_fin)
        elif "Pesajes Rezaga" in tipo:
            self._reporte_pesajes_rezaga(fecha_ini, fecha_fin)
        elif "Embarques" in tipo:
            self._reporte_embarques(fecha_ini, fecha_fin)
        elif "Calidad" in tipo:
            self._reporte_calidad(fecha_ini, fecha_fin)
        elif "Resumen" in tipo:
            self._reporte_resumen(fecha_ini, fecha_fin)
        elif "Peso Promedio" in tipo:
            self._reporte_peso_promedio(fecha_ini, fecha_fin)
    
    # ==================== REPORTES EXISTENTES (sin cambios) ====================
    def _reporte_recepciones(self, fecha_ini, fecha_fin):
        query = """
            SELECT r.folio, r.numero_carga, to_char(r.fecha_hora, 'DD/MM/YYYY') as fecha,
                   l.numero_lote, p.nombre as productor, v.nombre as variedad,
                   r.cajas_llenas, r.cajas_vacias, r.kilos_neto, r.estatus
            FROM recepcion_carga r
            LEFT JOIN lotes l ON r.lote_id = l.id
            LEFT JOIN productores p ON r.productor_id = p.id
            LEFT JOIN variedades v ON r.variedad = v.nombre
            WHERE DATE(r.fecha_hora) BETWEEN %s AND %s
            ORDER BY r.fecha_hora DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "N° Carga", "Fecha", "Lote", "Productor", "Variedad", "Cajas Llenas", "Cajas Vacías", "Kilos Neto", "Estatus"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_kilos = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_kilos += d[8] if d[8] else 0
        
        self.label_resumen.configure(text=f"Total de recepciones: {len(datos)} | Total kilos: {total_kilos:,.2f} kg")
    
    def _reporte_pesajes_lavado(self, fecha_ini, fecha_fin):
        query = """
            SELECT pl.folio, to_char(pl.fecha, 'DD/MM/YYYY') as fecha,
                   rc.numero_carga, l.numero_lote, rc.variedad,
                   pl.tanda_numero, pl.kilos_entrada, pl.num_jabas, pl.observaciones
            FROM pesaje_lavado pl
            JOIN recepcion_carga rc ON pl.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE DATE(pl.fecha) BETWEEN %s AND %s
            ORDER BY pl.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "N° Carga", "Lote", "Variedad", "Tanda #", "Kilos Neto", "Jabas", "Observaciones"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_kilos = 0
        total_jabas = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_kilos += d[6] if d[6] else 0
            total_jabas += d[7] if d[7] else 0
        
        self.label_resumen.configure(text=f"Total tandas: {len(datos)} | Total kilos: {total_kilos:,.2f} kg | Total jabas: {total_jabas}")
    
    def _reporte_pesajes_rezaga(self, fecha_ini, fecha_fin):
        query = """
            SELECT pr.folio, to_char(pr.fecha, 'DD/MM/YYYY') as fecha,
                   rc.numero_carga, l.numero_lote, rc.variedad,
                   pr.kilos_iniciales, pr.kilos_rezaga, pr.porcentaje_rezaga,
                   pr.observaciones, pr.danos
            FROM pesaje_rezaga pr
            JOIN recepcion_carga rc ON pr.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE DATE(pr.fecha) BETWEEN %s AND %s
            ORDER BY pr.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "N° Carga", "Lote", "Variedad", "Kilos Iniciales", "Kilos Rezaga", "% Rezaga", "Observaciones", "Daños"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_rezaga = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_rezaga += d[6] if d[6] else 0
        
        self.label_resumen.configure(text=f"Total registros: {len(datos)} | Rezaga total: {total_rezaga:,.2f} kg")
    
    def _reporte_embarques(self, fecha_ini, fecha_fin):
        query = """
            SELECT folio, to_char(fecha, 'DD/MM/YYYY') as fecha, destino, cliente,
                   cajas, kilos_totales, estatus
            FROM embarques
            WHERE DATE(fecha) BETWEEN %s AND %s
            ORDER BY fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "Destino", "Cliente", "Cajas", "Kilos Totales", "Estatus"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_kilos = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_kilos += d[5] if d[5] else 0
        
        self.label_resumen.configure(text=f"Total embarques: {len(datos)} | Kilos enviados: {total_kilos:,.2f} kg")
    
    def _reporte_calidad(self, fecha_ini, fecha_fin):
        query = """
            SELECT c.folio, to_char(c.fecha, 'DD/MM/YYYY') as fecha,
                   l.numero_lote, rc.variedad,
                   c.brix, c.ph, c.grado_calidad, c.apto, c.inspector
            FROM calidad_muestras c
            LEFT JOIN lotes l ON c.id_lote = l.id
            LEFT JOIN recepcion_carga rc ON c.id_recepcion = rc.id
            WHERE DATE(c.fecha) BETWEEN %s AND %s
            ORDER BY c.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "Lote", "Variedad", "Brix", "pH", "Grado", "Apto", "Inspector"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        aptos = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            valores[7] = "Sí" if valores[7] else "No"
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            if d[7]:
                aptos += 1
        
        self.label_resumen.configure(text=f"Total muestras: {len(datos)} | Aptas: {aptos} ({aptos*100//len(datos) if len(datos)>0 else 0}%)")
    
    def _reporte_resumen(self, fecha_ini, fecha_fin):
        recepciones = ejecutar_consulta("SELECT COUNT(*), SUM(kilos_neto) FROM recepcion_carga WHERE DATE(fecha_hora) BETWEEN %s AND %s", 
                                        (fecha_ini.date(), fecha_fin.date()), fetchone=True)
        pesajes = ejecutar_consulta("SELECT COUNT(*), SUM(kilos_entrada) FROM pesaje_lavado WHERE DATE(fecha) BETWEEN %s AND %s",
                                    (fecha_ini.date(), fecha_fin.date()), fetchone=True)
        rezaga = ejecutar_consulta("SELECT COUNT(*), SUM(kilos_rezaga) FROM pesaje_rezaga WHERE DATE(fecha) BETWEEN %s AND %s",
                                   (fecha_ini.date(), fecha_fin.date()), fetchone=True)
        embarques = ejecutar_consulta("SELECT COUNT(*), SUM(kilos_totales) FROM embarques WHERE DATE(fecha) BETWEEN %s AND %s",
                                      (fecha_ini.date(), fecha_fin.date()), fetchone=True)
        
        self.columnas_actuales = ["Concepto", "Cantidad", "Total Kilos"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200)
        
        self.datos_actuales = [
            ["Recepciones", recepciones[0] or 0, f"{recepciones[1] or 0:,.2f}"],
            ["Pesajes Lavado", pesajes[0] or 0, f"{pesajes[1] or 0:,.2f}"],
            ["Pesajes Rezaga", rezaga[0] or 0, f"{rezaga[1] or 0:,.2f}"],
            ["Embarques", embarques[0] or 0, f"{embarques[1] or 0:,.2f}"],
        ]
        
        for d in self.datos_actuales:
            self.tree.insert("", "end", values=d)
        
        self.label_resumen.configure(text=f"Resumen del período: {fecha_ini.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")
    
    # ==================== NUEVO REPORTE: PESO PROMEDIO POR JABA ====================
    def _reporte_peso_promedio(self, fecha_ini, fecha_fin):
        grupo = self.agrupar_por.get()
        
        # Construir la consulta según el grupo seleccionado
        if grupo == "N° Carga":
            select_col = "rc.numero_carga AS grupo"
            group_col = "rc.numero_carga"
        elif grupo == "Lote":
            select_col = "l.numero_lote AS grupo"
            group_col = "l.numero_lote"
        elif grupo == "Variedad":
            select_col = "rc.variedad AS grupo"
            group_col = "rc.variedad"
        else:
            select_col = "rc.numero_carga AS grupo"
            group_col = "rc.numero_carga"
        
        query = f"""
            SELECT {select_col},
                   COUNT(pl.id) AS total_tandas,
                   COALESCE(SUM(pl.kilos_entrada), 0) AS total_kilos,
                   COALESCE(SUM(pl.num_jabas), 0) AS total_jabas
            FROM pesaje_lavado pl
            JOIN recepcion_carga rc ON pl.id_recepcion = rc.id
            LEFT JOIN lotes l ON rc.lote_id = l.id
            WHERE DATE(pl.fecha) BETWEEN %s AND %s
              AND pl.num_jabas > 0
            GROUP BY {group_col}
            HAVING COALESCE(SUM(pl.num_jabas), 0) > 0
            ORDER BY total_kilos DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        if not datos:
            self.label_resumen.configure(text="No hay datos de pesaje lavado en el período seleccionado con jabas registradas.")
            self.columnas_actuales = []
            return
        
        # Calcular promedio por jaba para cada grupo
        resultados = []
        for d in datos:
            grupo_val = d[0]
            total_tandas = d[1]
            total_kilos = d[2]
            total_jabas = d[3]
            promedio = total_kilos / total_jabas if total_jabas > 0 else 0
            resultados.append([grupo_val, total_tandas, f"{total_kilos:.2f}", total_jabas, f"{promedio:.2f}"])
        
        self.columnas_actuales = [f"{grupo}", "Tandas", "Kilos Totales", "Jabas Totales", "Promedio kg/jaba"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor="center")
        
        self.datos_actuales = resultados
        for row in resultados:
            self.tree.insert("", "end", values=row)
        
        # Estadísticas generales
        total_kilos_gral = sum(float(r[2]) for r in resultados)
        total_jabas_gral = sum(r[3] for r in resultados)
        promedio_gral = total_kilos_gral / total_jabas_gral if total_jabas_gral > 0 else 0
        self.label_resumen.configure(
            text=f"Período: {fecha_ini.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')} | "
                 f"Total kilos: {total_kilos_gral:,.2f} kg | Total jabas: {total_jabas_gral} | "
                 f"Promedio general: {promedio_gral:.2f} kg/jaba"
        )
    
    # ==================== EXPORTACIONES ====================
    def exportar_excel(self):
        if not self.datos_actuales:
            messagebox.showwarning("Sin datos", "Genere un reporte primero")
            return
        
        archivo = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if archivo:
            df = pd.DataFrame(self.datos_actuales, columns=self.columnas_actuales)
            df.to_excel(archivo, index=False)
            messagebox.showinfo("Exportado", f"Reporte guardado en {archivo}")
    
    def exportar_pdf(self):
        if not self.datos_actuales:
            messagebox.showwarning("Sin datos", "Genere un reporte primero")
            return
        
        archivo = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if archivo:
            doc = SimpleDocTemplate(archivo, pagesize=landscape(letter))
            elementos = []
            
            styles = getSampleStyleSheet()
            titulo = Paragraph(f"<b>{self.tipo_reporte.get()}</b>", styles['Title'])
            elementos.append(titulo)
            elementos.append(Spacer(1, 20))
            
            fecha_texto = f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            elementos.append(Paragraph(fecha_texto, styles['Normal']))
            elementos.append(Spacer(1, 20))
            
            tabla_datos = [self.columnas_actuales] + self.datos_actuales
            tabla = Table(tabla_datos)
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elementos.append(tabla)
            
            elementos.append(Spacer(1, 20))
            elementos.append(Paragraph(self.label_resumen.cget("text"), styles['Normal']))
            
            doc.build(elementos)
            messagebox.showinfo("Exportado", f"PDF guardado en {archivo}")

if __name__ == "__main__":
    pass