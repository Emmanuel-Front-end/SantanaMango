# modulos/__init__.py
# Este archivo permite que Python reconozca la carpeta 'modulos' como un paquete
# Puede estar vacío o tener imports para facilitar la carga

from .catalogos import VentanaCatalogos
from .recepcion import VentanaRecepcion
from .configuracion import VentanaConfiguracion
from .reportes import VentanaReportes

# Los demás módulos se cargan dinámicamente con importlib