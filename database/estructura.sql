-- database/estructura.sql
-- =====================================================
-- SANTANA MANGO MANAGER - ESQUEMA COMPLETO
-- =====================================================

-- 1. TABLAS PRINCIPALES
-- =====================================================

-- Usuarios y permisos
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
    contrasena_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) DEFAULT 'operador',
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso TIMESTAMP
);

CREATE TABLE IF NOT EXISTS modulos_sistema (
    id SERIAL PRIMARY KEY,
    nombre_modulo VARCHAR(50) UNIQUE NOT NULL,
    descripcion TEXT,
    orden INT DEFAULT 0,
    icono VARCHAR(10) DEFAULT '📦'
);

CREATE TABLE IF NOT EXISTS permisos_usuario (
    usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
    modulo_id INT REFERENCES modulos_sistema(id) ON DELETE CASCADE,
    puede_leer BOOLEAN DEFAULT TRUE,
    puede_crear BOOLEAN DEFAULT FALSE,
    puede_editar BOOLEAN DEFAULT FALSE,
    puede_eliminar BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (usuario_id, modulo_id)
);

-- Catálogos
CREATE TABLE IF NOT EXISTS productores (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    rfc VARCHAR(13),
    telefono VARCHAR(20),
    direccion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS variedades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) UNIQUE NOT NULL,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transportistas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    telefono VARCHAR(20),
    placas VARCHAR(20),
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS lotes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    id_productor INT REFERENCES productores(id),
    id_variedad INT REFERENCES variedades(id),
    fecha_ingreso DATE DEFAULT CURRENT_DATE,
    activo BOOLEAN DEFAULT TRUE
);

-- Módulo de Recepción
CREATE TABLE IF NOT EXISTS recepcion_carga (
    id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_productor INT REFERENCES productores(id),
    id_transportista INT REFERENCES transportistas(id),
    placas VARCHAR(20),
    id_variedad INT REFERENCES variedades(id),
    tarimas INT,
    kilos_bruto DECIMAL(10,2),
    kilos_tara DECIMAL(10,2),
    kilos_neto DECIMAL(10,2),
    observaciones TEXT,
    recibio VARCHAR(50),
    estatus VARCHAR(20) DEFAULT 'ACTIVO'
);

-- Módulo de Pesaje
CREATE TABLE IF NOT EXISTS pesaje_lavado (
    id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_recepcion INT REFERENCES recepcion_carga(id),
    kilos_entrada DECIMAL(10,2),
    kilos_salida DECIMAL(10,2),
    merma DECIMAL(10,2),
    operador VARCHAR(50),
    observaciones TEXT
);

CREATE TABLE IF NOT EXISTS pesaje_rezaga (
    id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_lote INT REFERENCES lotes(id),
    kilos_iniciales DECIMAL(10,2),
    kilos_rezaga DECIMAL(10,2),
    porcentaje_rezaga DECIMAL(5,2),
    operador VARCHAR(50),
    observaciones TEXT
);

-- Módulo de Calidad
CREATE TABLE IF NOT EXISTS calidad_muestras (
    id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_lote INT REFERENCES lotes(id),
    brix DECIMAL(4,1),
    ph DECIMAL(3,1),
    color_externo VARCHAR(20),
    color_interno VARCHAR(20),
    firmeza VARCHAR(20),
    danos_mecanicos INT,
    danos_fitosanitarios INT,
    grado_calidad VARCHAR(10),
    inspector VARCHAR(50),
    apto BOOLEAN DEFAULT TRUE,
    observaciones TEXT
);

-- Módulo de Hidrotérmico
CREATE TABLE IF NOT EXISTS hidrotermico_proceso (
    id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_lote INT REFERENCES lotes(id),
    temperatura_agua DECIMAL(5,2),
    tiempo_minutos INT,
    temperatura_pulpa DECIMAL(5,2),
    operador VARCHAR(50),
    observaciones TEXT
);

-- Módulo de Etiquetas
CREATE TABLE IF NOT EXISTS etiquetas_generadas (
    id SERIAL PRIMARY KEY,
    codigo_barras VARCHAR(50) UNIQUE NOT NULL,
    id_lote INT REFERENCES lotes(id),
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    impresa BOOLEAN DEFAULT FALSE,
    usuario_genero VARCHAR(50)
);

-- Módulo de Embarques
CREATE TABLE IF NOT EXISTS embarques (
    id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    destino VARCHAR(100),
    cliente VARCHAR(100),
    cajas INT,
    kilos_totales DECIMAL(10,2),
    id_transportista INT REFERENCES transportistas(id),
    placas VARCHAR(20),
    fecha_salida DATE,
    estatus VARCHAR(20) DEFAULT 'PREPARACION',
    usuario_registro VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS embarque_detalle (
    id SERIAL PRIMARY KEY,
    id_embarque INT REFERENCES embarques(id) ON DELETE CASCADE,
    id_lote INT REFERENCES lotes(id),
    cajas INT,
    kilos DECIMAL(10,2)
);

-- Taras y configuraciones
CREATE TABLE IF NOT EXISTS taras_jabas (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    kilos DECIMAL(6,2) NOT NULL,
    tipo VARCHAR(30),
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS logs_sistema (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario VARCHAR(50),
    accion TEXT,
    modulo VARCHAR(50),
    ip VARCHAR(45)
);

-- 2. DATOS INICIALES
-- =====================================================

-- Insertar módulos
INSERT INTO modulos_sistema (nombre_modulo, descripcion, orden, icono) VALUES
('catalogos', 'Gestión de catálogos (productores, variedades, transportistas)', 1, '📋'),
('recepcion', 'Recepción de mercancía', 2, '🚚'),
('pesaje_lavado', 'Pesaje de lavado', 3, '🧼'),
('pesaje_rezaga', 'Pesaje de rezaga', 4, '📉'),
('transportes', 'Gestión de transportes', 5, '🚛'),
('hidrotermico', 'Proceso hidrotérmico', 6, '💧'),
('etiquetas', 'Generación de etiquetas', 7, '🏷️'),
('embarques', 'Gestión de embarques', 8, '📦'),
('rezaga', 'Control de rezaga', 9, '⚠️'),
('calidad', 'Control de calidad', 10, '🐞'),
('reportes', 'Generación de reportes', 11, '📊'),
('configuracion', 'Configuración del sistema', 12, '⚙️')
ON CONFLICT (nombre_modulo) DO NOTHING;

-- Insertar usuario admin por defecto (contraseña: admin123)
INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol, activo) 
VALUES ('admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin', true)
ON CONFLICT (nombre_usuario) DO NOTHING;

-- Insertar catálogos de ejemplo
INSERT INTO variedades (nombre) VALUES ('Ataulfo'), ('Manila'), ('Haden'), ('Kent')
ON CONFLICT (nombre) DO NOTHING;

-- Asignar todos los permisos al admin
DO $$
DECLARE
    admin_id INT;
    mod_id INT;
BEGIN
    SELECT id INTO admin_id FROM usuarios WHERE nombre_usuario = 'admin';
    FOR mod_id IN SELECT id FROM modulos_sistema LOOP
        INSERT INTO permisos_usuario (usuario_id, modulo_id, puede_leer, puede_crear, puede_editar, puede_eliminar)
        VALUES (admin_id, mod_id, true, true, true, true)
        ON CONFLICT (usuario_id, modulo_id) DO NOTHING;
    END LOOP;
END $$;

-- Vistas útiles
CREATE OR REPLACE VIEW vista_resumen_diario AS
SELECT 
    DATE(r.fecha) as fecha,
    COUNT(DISTINCT r.id) as total_recepciones,
    SUM(r.kilos_neto) as kilos_recepcionados,
    COUNT(DISTINCT p.id) as total_pesajes
FROM recepcion_carga r
LEFT JOIN pesaje_lavado p ON r.id = p.id_recepcion
GROUP BY DATE(r.fecha)
ORDER BY fecha DESC;