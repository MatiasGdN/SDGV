from flask import Flask, jsonify, request
from flask_cors import CORS
import bcrypt
import sqlite3
from database import inicializar_bd, obtener_conexion

app = Flask(__name__)
CORS(app)  # Habilitar CORS para toda la aplicación

# Crear tablas y usuario admin inicial si no existen
inicializar_bd()


@app.route("/", methods=["GET"])
def inicio():
    return jsonify({"mensaje": "API del Sistema de Ventas con Flask funcionando correctamente"})


# ==========================================
# 1. RUTAS DE AUTENTICACIÓN / LOGIN
# ==========================================

@app.route("/api/login", methods=["POST"])
def login():
    datos = request.get_json() or {}
    nombre_usuario = datos.get("nombre_usuario")
    clave = datos.get("clave")

    if not nombre_usuario or not clave:
        return jsonify({"error": "Usuario y contraseña son requeridos"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE nombre_usuario = ? AND activo = 1", (nombre_usuario,))
    usuario = cursor.fetchone()
    conexion.close()

    if usuario:
        hash_guardado = usuario['clave_hash'].encode('utf-8') if isinstance(usuario['clave_hash'], str) else usuario['clave_hash']
        
        if bcrypt.checkpw(clave.encode('utf-8'), hash_guardado):
            return jsonify({
                "mensaje": "Inicio de sesión exitoso",
                "usuario": {
                    "id_usuario": usuario["id_usuario"],
                    "nombre_usuario": usuario["nombre_usuario"],
                    "nombre": usuario["nombre"],
                    "apellido": usuario["apellido"],
                    "rol": usuario["rol"]
                }
            }), 200

    return jsonify({"error": "Credenciales inválidas o usuario inactivo"}), 401


# ==========================================
# 2. RUTAS DE USUARIOS
# ==========================================

@app.route("/api/usuarios", methods=["GET"])
def listar_usuarios():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT id_usuario, nombre_usuario, nombre, apellido, telefono, email, rol, activo FROM usuarios")
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/usuarios", methods=["POST"])
def crear_usuario():
    datos = request.get_json() or {}

    campos_obligatorios = ["nombre_usuario", "nombre", "apellido", "rol", "clave_plana"]
    for campo in campos_obligatorios:
        if campo not in datos or not datos[campo]:
            return jsonify({"error": f"El campo '{campo}' es requerido"}), 400

    roles_validos = ['Administrador', 'Supervisor', 'Vendedor']
    if datos["rol"] not in roles_validos:
        return jsonify({"error": f"Rol inválido. Debe ser uno de: {roles_validos}"}), 400

    sal = bcrypt.gensalt()
    clave_hash = bcrypt.hashpw(datos["clave_plana"].encode('utf-8'), sal).decode('utf-8')

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute('''
            INSERT INTO usuarios (nombre_usuario, nombre, apellido, telefono, email, clave_hash, rol)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datos["nombre_usuario"],
            datos["nombre"],
            datos["apellido"],
            datos.get("telefono"),
            datos.get("email"),
            clave_hash,
            datos["rol"]
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({
            "id_usuario": nuevo_id,
            "nombre_usuario": datos["nombre_usuario"],
            "nombre": datos["nombre"],
            "apellido": datos["apellido"],
            "rol": datos["rol"]
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "El nombre de usuario ya existe"}), 400
    finally:
        conexion.close()


@app.route("/api/usuarios/<int:id_usuario>", methods=["PUT", "DELETE"])
def gestionar_usuario(id_usuario):
    conn = obtener_conexion()
    cursor = conn.cursor()

    try:
        if request.method == "DELETE":
            cursor.execute("UPDATE usuarios SET activo = 0 WHERE id_usuario = ?", (id_usuario,))
            conn.commit()
            return jsonify({"mensaje": "Usuario desactivado correctamente"})

        if request.method == "PUT":
            data = request.get_json() or {}
            
            # Validación simple de campos mínimos
            if not data.get('nombre') or not data.get('apellido') or not data.get('rol'):
                return jsonify({"error": "Nombre, apellido y rol son obligatorios"}), 400

            clave_plana = data.get('clave_plana')

            if clave_plana and clave_plana.strip() != "":
                salt = bcrypt.gensalt()
                clave_hash = bcrypt.hashpw(clave_plana.encode('utf-8'), salt).decode('utf-8')
                
                cursor.execute("""
                    UPDATE usuarios 
                    SET nombre = ?, apellido = ?, email = ?, telefono = ?, rol = ?, clave_hash = ?
                    WHERE id_usuario = ?
                """, (data['nombre'], data['apellido'], data.get('email'), data.get('telefono'), data['rol'], clave_hash, id_usuario))
            else:
                cursor.execute("""
                    UPDATE usuarios 
                    SET nombre = ?, apellido = ?, email = ?, telefono = ?, rol = ?
                    WHERE id_usuario = ?
                """, (data['nombre'], data['apellido'], data.get('email'), data.get('telefono'), data['rol'], id_usuario))

            conn.commit()
            return jsonify({"mensaje": "Usuario actualizado correctamente"})
    finally:
        conn.close()


# ==========================================
# 3. RUTAS DE VENDEDORES
# ==========================================

@app.route("/api/vendedores", methods=["GET"])
def listar_vendedores():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # LEFT JOIN para traer el vendedor aunque la relación en usuarios tenga detalles
    cursor.execute('''
        SELECT v.id_vendedor, v.id_usuario, 
               COALESCE(u.nombre || ' ' || u.apellido, u.nombre_usuario, 'Vendedor #' || v.id_vendedor) AS nombre_completo,
               v.zona, v.porcentaje_comision
        FROM vendedores v
        LEFT JOIN usuarios u ON v.id_usuario = u.id_usuario
        ORDER BY v.id_vendedor DESC
    ''')
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/vendedores", methods=["POST"])
def crear_vendedor():
    datos = request.get_json() or {}

    if "id_usuario" not in datos or "zona" not in datos:
        return jsonify({"error": "Los campos 'id_usuario' y 'zona' son obligatorios"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute('''
            INSERT INTO vendedores (id_usuario, zona, porcentaje_comision)
            VALUES (?, ?, ?)
        ''', (
            datos["id_usuario"],
            datos["zona"],
            datos.get("porcentaje_comision", 0.0)
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({"id_vendedor": nuevo_id, "mensaje": "Vendedor registrado con éxito"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "El usuario ya está registrado como vendedor o el id_usuario no existe"}), 400
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500
    finally:
        conexion.close()


@app.route("/api/vendedores/<int:id_vendedor>", methods=["PUT", "DELETE"])
def gestionar_vendedor(id_vendedor):
    conn = obtener_conexion()
    cursor = conn.cursor()

    try:
        if request.method == "DELETE":
            cursor.execute("DELETE FROM vendedores WHERE id_vendedor = ?", (id_vendedor,))
            conn.commit()
            return jsonify({"mensaje": "Vendedor eliminado correctamente"})

        if request.method == "PUT":
            data = request.get_json() or {}
            if "zona" not in data:
                return jsonify({"error": "El campo 'zona' es obligatorio"}), 400

            cursor.execute("""
                UPDATE vendedores 
                SET zona = ?, porcentaje_comision = ?
                WHERE id_vendedor = ?
            """, (data["zona"], data.get("porcentaje_comision", 0.0), id_vendedor))

            conn.commit()
            return jsonify({"mensaje": "Vendedor actualizado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al actualizar: {str(e)}"}), 500
    finally:
        conn.close()


# ==========================================
# 4. RUTAS DE CLIENTES
# ==========================================

@app.route("/api/clientes", methods=["GET"])
def listar_clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id_cliente, nombre, cuit, telefono, email, direccion 
        FROM clientes 
        ORDER BY id_cliente DESC
    """)
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/clientes", methods=["POST"])
def crear_cliente():
    datos = request.get_json() or {}

    nombre = str(datos.get("nombre", "")).strip()
    if not nombre:
        return jsonify({"error": "El nombre / razón social es obligatorio"}), 400

    # Procesar CUIT: si viene vacío o espacios, se envía None (NULL)
    cuit_raw = datos.get("cuit") or datos.get("cuit_dni")
    cuit_str = str(cuit_raw).strip() if cuit_raw is not None else ""
    cuit_final = cuit_str if cuit_str != "" else None

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute('''
            INSERT INTO clientes (nombre, cuit, telefono, email, direccion)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            nombre,
            cuit_final,
            datos.get("telefono"),
            datos.get("email"),
            datos.get("direccion")
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({"id_cliente": nuevo_id, "nombre": nombre}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"El CUIT '{cuit_final}' ya pertenece a otro cliente registrado."}), 400
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500
    finally:
        conexion.close()


@app.route("/api/clientes/<int:id_cliente>", methods=["PUT", "DELETE"])
def gestionar_cliente(id_cliente):
    conn = obtener_conexion()
    cursor = conn.cursor()

    try:
        if request.method == "DELETE":
            cursor.execute("DELETE FROM clientes WHERE id_cliente = ?", (id_cliente,))
            conn.commit()
            return jsonify({"mensaje": "Cliente eliminado correctamente"})

        if request.method == "PUT":
            data = request.get_json() or {}
            
            nombre = str(data.get("nombre", "")).strip()
            if not nombre:
                return jsonify({"error": "El nombre es obligatorio"}), 400

            cuit_raw = data.get('cuit') or data.get('cuit_dni')
            cuit_str = str(cuit_raw).strip() if cuit_raw is not None else ""
            cuit_final = cuit_str if cuit_str != "" else None

            cursor.execute("""
                UPDATE clientes 
                SET nombre = ?, cuit = ?, telefono = ?, email = ?, direccion = ?
                WHERE id_cliente = ?
            """, (
                nombre, 
                cuit_final, 
                data.get('telefono'), 
                data.get('email'), 
                data.get('direccion'), 
                id_cliente
            ))

            conn.commit()
            return jsonify({"mensaje": "Cliente actualizado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al actualizar: {str(e)}"}), 500
    finally:
        conn.close()




# ==========================================
# 5. RUTAS DE PROVEEDORES
# ==========================================

@app.route("/api/proveedores", methods=["GET"])
def listar_proveedores():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM proveedores")
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/proveedores", methods=["POST"])
def crear_proveedor():
    datos = request.get_json() or {}

    nombre = datos.get("nombre") or datos.get("razon_social")
    if not nombre:
        return jsonify({"error": "El nombre / razón social es obligatorio"}), 400

    cuit_val = datos.get("cuit")
    cuit_final = cuit_val if cuit_val and str(cuit_val).strip() != "" else None

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute('''
            INSERT INTO proveedores (razon_social, cuit, telefono, email, direccion, ciudad, provincia)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            nombre,
            cuit_final,
            datos.get("telefono"),
            datos.get("email"),
            datos.get("direccion"),
            datos.get("ciudad"),
            datos.get("provincia")
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({"id_proveedor": nuevo_id, "razon_social": nombre}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "El CUIT ya pertenece a otro proveedor"}), 400
    finally:
        conexion.close()


@app.route("/api/proveedores/<int:id_proveedor>", methods=["PUT", "DELETE"])
def gestionar_proveedor(id_proveedor):
    conn = obtener_conexion()
    cursor = conn.cursor()

    try:
        if request.method == "DELETE":
            cursor.execute("UPDATE proveedores SET activo = 0 WHERE id_proveedor = ?", (id_proveedor,))
            conn.commit()
            return jsonify({"mensaje": "Proveedor desactivado correctamente"})

        if request.method == "PUT":
            data = request.get_json() or {}

            nombre = data.get('nombre') or data.get('razon_social')
            if not nombre:
                return jsonify({"error": "El nombre es obligatorio"}), 400

            cuit_val = data.get('cuit')
            cuit_final = cuit_val if cuit_val and str(cuit_val).strip() != "" else None

            cursor.execute("""
                UPDATE proveedores 
                SET razon_social = ?, cuit = ?, email = ?, telefono = ?, direccion = ?
                WHERE id_proveedor = ?
            """, (
                nombre, 
                cuit_final, 
                data.get('email'), 
                data.get('telefono'), 
                data.get('direccion'), 
                id_proveedor
            ))

            conn.commit()
            return jsonify({"mensaje": "Proveedor actualizado correctamente"})
    finally:
        conn.close()


# ==========================================
# 6. RUTAS DE CATEGORÍAS
# ==========================================

@app.route("/api/categorias", methods=["GET"])
def listar_categorias():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM categorias")
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/categorias", methods=["POST"])
def crear_categoria():
    datos = request.get_json() or {}

    if "nombre" not in datos or not datos["nombre"]:
        return jsonify({"error": "El nombre de la categoría es obligatorio"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute('''
            INSERT INTO categorias (nombre, descripcion)
            VALUES (?, ?)
        ''', (datos["nombre"], datos.get("descripcion")))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({"id_categoria": nuevo_id, "nombre": datos["nombre"]}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "La categoría ya existe"}), 400
    finally:
        conexion.close()


# ==========================================
# 7. RUTAS DE PRODUCTOS
# ==========================================

@app.route("/api/productos", methods=["GET"])
def listar_productos():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('''
        SELECT p.id_producto, p.codigo, p.nombre, p.descripcion, p.precio_compra, p.precio_venta, 
               p.stock, p.stock_minimo, 
               c.nombre AS categoria, p.id_categoria,
               pr.razon_social AS proveedor, p.id_proveedor
        FROM productos p
        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
        LEFT JOIN proveedores pr ON p.id_proveedor = pr.id_proveedor
        WHERE p.activo = 1
    ''')
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/productos", methods=["POST"])
def crear_producto():
    datos = request.get_json() or {}

    campos = ["id_categoria", "codigo", "nombre", "precio_compra", "precio_venta"]
    for campo in campos:
        if campo not in datos:
            return jsonify({"error": f"El campo '{campo}' es obligatorio"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute('''
            INSERT INTO productos (id_categoria, id_proveedor, codigo, nombre, descripcion, precio_compra, precio_venta, stock, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datos["id_categoria"],
            datos.get("id_proveedor"),
            datos["codigo"],
            datos["nombre"],
            datos.get("descripcion"),
            datos["precio_compra"],
            datos["precio_venta"],
            datos.get("stock", 0),
            datos.get("stock_minimo", 1)
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({"id_producto": nuevo_id, "nombre": datos["nombre"]}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Código de producto duplicado, o categoría/proveedor inexistente"}), 400
    finally:
        conexion.close()


@app.route("/api/productos/<int:id_producto>", methods=["PUT", "DELETE"])
def gestionar_producto(id_producto):
    conn = obtener_conexion()
    cursor = conn.cursor()

    try:
        if request.method == "DELETE":
            cursor.execute("UPDATE productos SET activo = 0 WHERE id_producto = ?", (id_producto,))
            conn.commit()
            return jsonify({"mensaje": "Producto desactivado correctamente"})

        if request.method == "PUT":
            data = request.get_json() or {}
            cursor.execute("""
                UPDATE productos 
                SET id_categoria = ?, id_proveedor = ?, codigo = ?, nombre = ?, descripcion = ?, precio_compra = ?, precio_venta = ?, stock = ?, stock_minimo = ?
                WHERE id_producto = ?
            """, (
                data.get('id_categoria'), 
                data.get('id_proveedor'), 
                data.get('codigo'), 
                data.get('nombre'), 
                data.get('descripcion'), 
                data.get('precio_compra'), 
                data.get('precio_venta'), 
                data.get('stock'), 
                data.get('stock_minimo'), 
                id_producto
            ))
            conn.commit()
            return jsonify({"mensaje": "Producto actualizado correctamente"})
    finally:
        conn.close()


# ==========================================
# 8. RUTAS DE VENTAS (CON ACTUALIZACIÓN DE STOCK)
# ==========================================

@app.route("/api/ventas", methods=["GET"])
def listar_ventas():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('''
        SELECT v.id_venta, c.nombre || ' ' || c.apellido AS cliente, 
               u.nombre || ' ' || u.apellido AS vendedor, 
               v.fecha, v.total, v.estado
        FROM ventas v
        INNER JOIN clientes c ON v.id_cliente = c.id_cliente
        INNER JOIN vendedores ve ON v.id_vendedor = ve.id_vendedor
        INNER JOIN usuarios u ON ve.id_usuario = u.id_usuario
        ORDER BY v.id_venta DESC
    ''')
    filas = cursor.fetchall()
    conexion.close()
    return jsonify([dict(fila) for fila in filas]), 200


@app.route("/api/ventas/<int:id_venta>", methods=["GET"])
def obtener_detalle_venta(id_venta):
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute('''
        SELECT v.*, c.nombre || ' ' || c.apellido AS cliente, u.nombre || ' ' || u.apellido AS vendedor
        FROM ventas v
        INNER JOIN clientes c ON v.id_cliente = c.id_cliente
        INNER JOIN vendedores ve ON v.id_vendedor = ve.id_vendedor
        INNER JOIN usuarios u ON ve.id_usuario = u.id_usuario
        WHERE v.id_venta = ?
    ''', (id_venta,))
    venta = cursor.fetchone()

    if not venta:
        conexion.close()
        return jsonify({"error": "Venta no encontrada"}), 404

    cursor.execute('''
        SELECT d.id_detalle, d.id_producto, p.nombre AS producto, d.cantidad, d.precio_unitario, d.subtotal
        FROM detalle_ventas d
        INNER JOIN productos p ON d.id_producto = p.id_producto
        WHERE d.id_venta = ?
    ''', (id_venta,))
    detalles = cursor.fetchall()

    conexion.close()

    resultado = dict(venta)
    resultado["items"] = [dict(d) for d in detalles]
    return jsonify(resultado), 200


@app.route("/api/ventas", methods=["POST"])
def registrar_venta():
    datos = request.get_json() or {}

    if "id_cliente" not in datos or "id_vendedor" not in datos or "detalles" not in datos:
        return jsonify({"error": "id_cliente, id_vendedor y la lista de detalles son obligatorios"}), 400

    detalles = datos["detalles"]
    if not detalles or len(detalles) == 0:
        return jsonify({"error": "La venta debe incluir al menos un producto"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        # 1. Verificar stock disponible antes de procesar la venta
        for item in detalles:
            cursor.execute("SELECT stock, nombre FROM productos WHERE id_producto = ?", (item["id_producto"],))
            prod = cursor.fetchone()
            if not prod:
                conexion.close()
                return jsonify({"error": f"El producto con ID {item['id_producto']} no existe"}), 400
            if prod["stock"] < item["cantidad"]:
                conexion.close()
                return jsonify({"error": f"Stock insuficiente para '{prod['nombre']}'. Disponible: {prod['stock']}"}), 400

        total_calculado = sum(item["cantidad"] * item["precio_unitario"]*1260 for item in detalles)

        # 2. Insertar encabezado de la venta
        cursor.execute('''
            INSERT INTO ventas (id_cliente, id_vendedor, total, estado, observaciones)
            VALUES (?, ?, ?, 'Confirmada', ?)
        ''', (
            datos["id_cliente"],
            datos["id_vendedor"],
            total_calculado,
            datos.get("observaciones")
        ))
        id_venta = cursor.lastrowid

        # 3. Insertar detalle de la venta y restar stock
        for item in detalles:
            subtotal = item["cantidad"] * item["precio_unitario"]*1260
            cursor.execute('''
                INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
            ''', (id_venta, item["id_producto"], item["cantidad"], item["precio_unitario"], subtotal))

            # Restar stock del producto
            cursor.execute('''
                UPDATE productos 
                SET stock = stock - ? 
                WHERE id_producto = ?
            ''', (item["cantidad"], item["id_producto"]))

        conexion.commit()

        return jsonify({
            "id_venta": id_venta,
            "mensaje": "Venta realizada con éxito y stock actualizado",
            "total": total_calculado
        }), 201

    except sqlite3.IntegrityError as e:
        conexion.rollback()
        return jsonify({"error": f"Error de integridad en la base de datos: {str(e)}"}), 400
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error inesperado al procesar la venta: {str(e)}"}), 500
    finally:
        conexion.close()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
    
