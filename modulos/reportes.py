# modulos/reportes.py
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
    def __init__(self, parent, permisos):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self.permisos = permisos
        self.datos_actuales = []
        self.columnas_actuales = []
        
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
                "📊 Resumen General"
            ],
            width=200
        )
        self.tipo_reporte.grid(row=0, column=1, padx=10, pady=10)
        self.tipo_reporte.set("📦 Recepciones")
        
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
        
        ctk.CTkButton(btn_frame, text="🔍 Generar", command=self.generar_reporte, width=120, fg_color="#2e8b57").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="📄 Exportar PDF", command=self.exportar_pdf, width=120).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="📊 Exportar Excel", command=self.exportar_excel, width=120).pack(side="left", padx=10)
        
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
    
    def _reporte_recepciones(self, fecha_ini, fecha_fin):
        query = """
            SELECT r.folio, r.fecha, p.nombre as productor, v.nombre as variedad,
                   r.tarimas, r.kilos_neto, r.observaciones
            FROM recepcion_carga r
            LEFT JOIN productores p ON r.id_productor = p.id
            LEFT JOIN variedades v ON r.id_variedad = v.id
            WHERE DATE(r.fecha) BETWEEN %s AND %s
            ORDER BY r.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "Productor", "Variedad", "Tarimas", "Kilos Neto", "Observaciones"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_kilos = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            valores[1] = valores[1].strftime("%d/%m/%Y %H:%M") if valores[1] else ""
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_kilos += d[5] if d[5] else 0
        
        self.label_resumen.configure(text=f"Total de recepciones: {len(datos)} | Total kilos: {total_kilos:,.2f} kg")
    
    def _reporte_pesajes_lavado(self, fecha_ini, fecha_fin):
        query = """
            SELECT p.folio, p.fecha, r.folio as recepcion, p.kilos_entrada, 
                   p.kilos_salida, p.merma, p.operador
            FROM pesaje_lavado p
            JOIN recepcion_carga r ON p.id_recepcion = r.id
            WHERE DATE(p.fecha) BETWEEN %s AND %s
            ORDER BY p.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "Recepción", "Kilos Entrada", "Kilos Salida", "Merma", "Operador"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_merma = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            valores[1] = valores[1].strftime("%d/%m/%Y %H:%M") if valores[1] else ""
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_merma += d[5] if d[5] else 0
        
        self.label_resumen.configure(text=f"Total pesajes: {len(datos)} | Merma total: {total_merma:,.2f} kg")
    
    def _reporte_pesajes_rezaga(self, fecha_ini, fecha_fin):
        query = """
            SELECT pr.folio, pr.fecha, l.codigo as lote, pr.kilos_iniciales, 
                   pr.kilos_rezaga, pr.porcentaje_rezaga, pr.operador
            FROM pesaje_rezaga pr
            JOIN lotes l ON pr.id_lote = l.id
            WHERE DATE(pr.fecha) BETWEEN %s AND %s
            ORDER BY pr.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "Lote", "Kilos Iniciales", "Kilos Rezaga", "% Rezaga", "Operador"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        total_rezaga = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            valores[1] = valores[1].strftime("%d/%m/%Y %H:%M") if valores[1] else ""
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_rezaga += d[4] if d[4] else 0
        
        self.label_resumen.configure(text=f"Total registros: {len(datos)} | Rezaga total: {total_rezaga:,.2f} kg")
    
    def _reporte_embarques(self, fecha_ini, fecha_fin):
        query = """
            SELECT e.folio, e.fecha, e.destino, e.cliente, e.cajas, 
                   e.kilos_totales, e.estatus
            FROM embarques e
            WHERE DATE(e.fecha) BETWEEN %s AND %s
            ORDER BY e.fecha DESC
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
            valores[1] = valores[1].strftime("%d/%m/%Y %H:%M") if valores[1] else ""
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            total_kilos += d[5] if d[5] else 0
        
        self.label_resumen.configure(text=f"Total embarques: {len(datos)} | Kilos enviados: {total_kilos:,.2f} kg")
    
    def _reporte_calidad(self, fecha_ini, fecha_fin):
        query = """
            SELECT c.folio, c.fecha, l.codigo as lote, c.brix, c.ph, 
                   c.grado_calidad, c.apto, c.inspector
            FROM calidad_muestras c
            JOIN lotes l ON c.id_lote = l.id
            WHERE DATE(c.fecha) BETWEEN %s AND %s
            ORDER BY c.fecha DESC
        """
        datos = ejecutar_consulta(query, (fecha_ini.date(), fecha_fin.date()), fetchall=True)
        
        self.columnas_actuales = ["Folio", "Fecha", "Lote", "Brix", "pH", "Grado", "Apto", "Inspector"]
        self.tree["columns"] = self.columnas_actuales
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        aptos = 0
        self.datos_actuales = []
        for d in datos:
            valores = list(d)
            valores[1] = valores[1].strftime("%d/%m/%Y %H:%M") if valores[1] else ""
            valores[6] = "Sí" if valores[6] else "No"
            self.tree.insert("", "end", values=valores)
            self.datos_actuales.append(valores)
            if d[6]:
                aptos += 1
        
        self.label_resumen.configure(text=f"Total muestras: {len(datos)} | Aptas: {aptos} ({aptos*100//len(datos) if len(datos)>0 else 0}%)")
    
    def _reporte_resumen(self, fecha_ini, fecha_fin):
        # Resumen general
        recepciones = ejecutar_consulta("SELECT COUNT(*), SUM(kilos_neto) FROM recepcion_carga WHERE DATE(fecha) BETWEEN %s AND %s", 
                                        (fecha_ini.date(), fecha_fin.date()), fetchone=True)
        pesajes = ejecutar_consulta("SELECT COUNT(*), SUM(merma) FROM pesaje_lavado WHERE DATE(fecha) BETWEEN %s AND %s",
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
            ["Pesajes Lavado", pesajes[0] or 0, f"Merma: {(pesajes[1] or 0):,.2f}"],
            ["Embarques", embarques[0] or 0, f"{embarques[1] or 0:,.2f}"],
        ]
        
        for d in self.datos_actuales:
            self.tree.insert("", "end", values=d)
        
        self.label_resumen.configure(text=f"Resumen del período: {fecha_ini.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")
    
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
            
            # Título
            styles = getSampleStyleSheet()
            titulo = Paragraph(f"<b>{self.tipo_reporte.get()}</b>", styles['Title'])
            elementos.append(titulo)
            elementos.append(Spacer(1, 20))
            
            # Fecha
            fecha_texto = f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            elementos.append(Paragraph(fecha_texto, styles['Normal']))
            elementos.append(Spacer(1, 20))
            
            # Tabla de datos
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
            
            # Resumen
            elementos.append(Spacer(1, 20))
            elementos.append(Paragraph(self.label_resumen.cget("text"), styles['Normal']))
            
            doc.build(elementos)
            messagebox.showinfo("Exportado", f"PDF guardado en {archivo}")