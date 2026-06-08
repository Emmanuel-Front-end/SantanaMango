import customtkinter as ctk

def crear_tooltip(widget, texto, retardo=500):
    """
    Crea un tooltip que aparece al pasar el mouse sobre el widget.
    Se destruye correctamente al salir, sin quedarse pegado.
    """
    tooltip = None
    after_id = None
    
    def on_enter(event=None):
        nonlocal after_id
        if after_id:
            widget.after_cancel(after_id)
        after_id = widget.after(retardo, mostrar)
    
    def on_leave(event=None):
        nonlocal after_id, tooltip
        if after_id:
            widget.after_cancel(after_id)
            after_id = None
        if tooltip:
            tooltip.destroy()
            tooltip = None
    
    def mostrar():
        nonlocal tooltip
        if tooltip:
            return
        tooltip = ctk.CTkToplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.attributes("-topmost", True)
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        tooltip.geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(tooltip, text=texto, fg_color="#333", text_color="white",
                             corner_radius=5, padx=8, pady=4)
        label.pack()
    
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)