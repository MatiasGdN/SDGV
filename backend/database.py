import sqlite3
import bcrypt

DB_NAME = 'gestor_deventas.db'

def obtener_conexion():
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON;")
    return conexion

def crear_admin_inicial(conexion):
    cursor = conexion.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin'")
    if cursor.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        hash_clave = bcrypt.hashpw(b"admin123", salt).decode('utf-8')
        
        cursor.execute('''
            INSERT INTO usuarios (nombre, apellido, nombre_usuario, clave_hash, rol, activo)
            VALUES ('Admin', 'Sistema', 'admin', ?, 'Administrador', 1)
        ''', (hash_clave,))
        print("-> Usuario administrador inicial creado (Usuario: admin | Clave: admin123).")

def inicializar_bd():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # 1. TABLA USUARIOS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            nombre_usuario TEXT NOT NULL UNIQUE,
            clave_hash TEXT NOT NULL,
            telefono TEXT,
            email TEXT,
            rol TEXT NOT NULL CHECK(rol IN ('Administrador', 'Supervisor', 'Vendedor')),
            activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0, 1))
        );
    ''')

    # 2. TABLA VENDEDORES
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS vendedores (
            id_vendedor INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL UNIQUE,
            zona TEXT NOT NULL,
            porcentaje_comision REAL NOT NULL DEFAULT 0.0 CHECK(porcentaje_comision >= 0),
            fecha_ingreso DATE NOT NULL DEFAULT (DATE('now')),
            activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0, 1)),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT
        );
    ''')

    # 3. TABLA CLIENTES (Se quita UNIQUE de cuit para manejar NULLs dinámicamente)
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT,
            razon_social TEXT,
            cuit TEXT,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            ciudad TEXT,
            provincia TEXT,
            fecha_alta DATE NOT NULL DEFAULT (DATE('now'))
        );
    ''')

    # Índice Único Parcial para CUIT (Solo valida unicidad si el CUIT no está vacío o nulo)
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_cuit_unique 
        ON clientes(cuit) 
        WHERE cuit IS NOT NULL AND cuit != '';
    ''')

    # 4. TABLA CATEGORIAS
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS categorias (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
    ''')

    # 5. TABLA PROVEEDORES
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            razon_social TEXT NOT NULL,
            cuit TEXT UNIQUE,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            ciudad TEXT,
            provincia TEXT,
            activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0, 1))
        );
    ''')

    # 6. TABLA PRODUCTOS
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria INTEGER NOT NULL,
            id_proveedor INTEGER,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio_compra REAL NOT NULL,
            precio_venta REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 1,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria),
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        );
    ''')

    # 7. TABLA INTERMEDIA PRODUCTO_PROVEEDOR
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS producto_proveedor (
            id_producto INTEGER NOT NULL,
            id_proveedor INTEGER NOT NULL,
            precio_compra_proveedor REAL NOT NULL CHECK(precio_compra_proveedor >= 0),
            codigo_producto_proveedor TEXT,
            fecha_ultima_compra DATE,
            PRIMARY KEY (id_producto, id_proveedor),
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT
        );
    ''')

    # 8. TABLA VENTAS
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS ventas (
            id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vendedor INTEGER NOT NULL,
            id_cliente INTEGER NOT NULL,
            fecha DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
            total REAL NOT NULL DEFAULT 0.0 CHECK(total >= 0),
            estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'Confirmada', 'Cancelada')),
            observaciones TEXT,
            FOREIGN KEY (id_vendedor) REFERENCES vendedores(id_vendedor) ON DELETE RESTRICT,
            FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT
        );
    ''')

    # 9. TABLA DETALLE_VENTAS
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            id_producto INTEGER NOT NULL,
            cantidad INTEGER NOT NULL CHECK(cantidad > 0),
            precio_unitario REAL NOT NULL CHECK(precio_unitario >= 0),
            subtotal REAL NOT NULL CHECK(subtotal >= 0),
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE RESTRICT
        );
    ''')

    # 10. TABLA COMISIONES
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS comisiones (
            id_comision INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vendedor INTEGER NOT NULL,
            id_venta INTEGER NOT NULL UNIQUE,
            porcentaje_comision REAL NOT NULL CHECK(porcentaje_comision >= 0),
            monto_comision REAL NOT NULL CHECK(monto_comision >= 0),
            fecha_generacion DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
            estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'Pagada', 'Anulada')),
            FOREIGN KEY (id_vendedor) REFERENCES vendedores(id_vendedor) ON DELETE RESTRICT,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE RESTRICT
        );
    ''')

    # 11. TABLA OBJETIVOS_VENTA
    cursor.execute('''  
        CREATE TABLE IF NOT EXISTS objetivos_venta (
            id_objetivo INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vendedor INTEGER NOT NULL,
            descripcion TEXT NOT NULL,
            fecha_inicio DATE NOT NULL,
            fecha_fin DATE NOT NULL,
            objetivo_monto REAL NOT NULL CHECK(objetivo_monto >= 0),
            objetivo_cantidad_ventas INTEGER NOT NULL CHECK(objetivo_cantidad_ventas >= 0),
            monto_alcanzado REAL NOT NULL DEFAULT 0.0 CHECK(monto_alcanzado >= 0),
            cantidad_ventas_alcanzadas INTEGER NOT NULL DEFAULT 0 CHECK(cantidad_ventas_alcanzadas >= 0),
            estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'En progreso', 'Cumplido', 'No cumplido')),
            FOREIGN KEY (id_vendedor) REFERENCES vendedores(id_vendedor) ON DELETE RESTRICT
        );
    ''')

    # ÍNDICES Y TRIGGERS
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS descontar_stock 
        AFTER INSERT ON detalle_ventas
        BEGIN
            UPDATE productos 
            SET stock = stock - NEW.cantidad 
            WHERE id_producto = NEW.id_producto;
        END;
    ''')

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(id_categoria);")

    crear_admin_inicial(conexion)

    conexion.commit()
    conexion.close()

if __name__ == "__main__":
    inicializar_bd()
    print("¡Base de datos inicializada con éxito!")