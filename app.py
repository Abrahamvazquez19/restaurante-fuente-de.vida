import sqlite3
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates")
DB_FILE = "restaurante.db"


def init_db():
    """Crea las tablas e inserta los datos iniciales (mesas y dos meseros por defecto)."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # 1. Tabla de Mesas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mesas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                estado TEXT DEFAULT 'Libre'
            )
        """
        )

        # 2. Tabla de Usuarios / Meseros
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT
            )
        """
        )

        # 3. Tabla de Comandas (AHORA INCLUYE EL MESERO QUE TOMÓ EL PEDIDO)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comandas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mesa_id INTEGER,
                producto TEXT,
                precio REAL,
                cantidad INTEGER,
                notas TEXT DEFAULT '',
                mesero TEXT DEFAULT ''
            )
        """
        )

        # Inicializar 8 mesas si está vacía
        cursor.execute("SELECT COUNT(*) FROM mesas")
        if cursor.fetchone()[0] == 0:
            mesas_iniciales = [(f"Mesa {i}",) for i in range(1, 9)]
            cursor.executemany(
                "INSERT INTO mesas (nombre) VALUES (?)", mesas_iniciales
            )

        # Inicializar los primeros 2 meseros si la tabla está vacía
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            meseros_iniciales = [("Abraham",), ("Daniel",)]
            cursor.executemany(
                "INSERT INTO usuarios (nombre) VALUES (?)", meseros_iniciales
            )

        conn.commit()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/estado", methods=["GET"])
def obtener_estado():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # 1. Traer Mesas
        cursor.execute("SELECT id, nombre, estado FROM mesas")
        mesas_data = cursor.fetchall()

        # 2. Traer Lista de Meseros (para llenar el selector de la app)
        cursor.execute("SELECT nombre FROM usuarios")
        lista_meseros = [row[0] for row in cursor.fetchall()]

        respuesta_mesas = []
        for m_id, m_nombre, m_estado in mesas_data:
            # Traemos también la columna 'mesero'
            cursor.execute(
                "SELECT id, producto, precio, cantidad, notas, mesero FROM comandas WHERE mesa_id = ?",
                (m_id,),
            )
            comandas = [
                {
                    "id": c_id,
                    "producto": p,
                    "precio": pr,
                    "cantidad": c,
                    "notas": n,
                    "mesero": m,
                }
                for c_id, p, pr, c, n, m in cursor.fetchall()
            ]
            total = sum(item["precio"] * item["cantidad"] for item in comandas)

            respuesta_mesas.append(
                {
                    "id": m_id,
                    "nombre": m_nombre,
                    "estado": m_estado,
                    "comandas": comandas,
                    "total": total,
                }
            )

        # Devolvemos tanto el estado de las mesas como la lista actualizada de meseros
        return jsonify({"mesas": respuesta_mesas, "meseros": lista_meseros})


@app.route("/api/pedido", methods=["POST"])
def agregar_pedido():
    data = request.json
    mesa_id = data.get("mesa_id")
    producto = data.get("producto")
    precio = float(data.get("precio"))
    cantidad = int(data.get("cantidad"))
    text_notas = data.get("notas", "")
    mesero = data.get("mesero", "Desconocido")  # Recibe quién lo atiende

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO comandas (mesa_id, producto, precio, cantidad, notas, mesero) VALUES (?, ?, ?, ?, ?, ?)",
            (mesa_id, producto, precio, cantidad, text_notas, mesero),
        )
        cursor.execute(
            "UPDATE mesas SET estado = 'Ocupada' WHERE id = ?", (mesa_id,)
        )
        conn.commit()
    return jsonify({"status": "success"})


@app.route("/api/liberar", methods=["POST"])
def liberar_mesa():
    data = request.json
    mesa_id = data.get("mesa_id")

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comandas WHERE mesa_id = ?", (mesa_id,))
        cursor.execute(
            "UPDATE mesas SET estado = 'Libre' WHERE id = ?", (mesa_id,)
        )
        conn.commit()
    return jsonify({"status": "success"})


@app.route("/api/cancelar-producto", methods=["POST"])
def cancelar_producto():
    data = request.json
    comanda_id = data.get("comanda_id")
    mesa_id = data.get("mesa_id")

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comandas WHERE id = ?", (comanda_id,))

        cursor.execute(
            "SELECT COUNT(*) FROM comandas WHERE mesa_id = ?", (mesa_id,)
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "UPDATE mesas SET estado = 'Libre' WHERE id = ?", (mesa_id,)
            )

        conn.commit()
    return jsonify({"status": "success"})


@app.route("/api/nueva-mesa", methods=["POST"])
def crear_mesa():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mesas")
        siguiente_numero = cursor.fetchone()[0] + 1
        nombre_nueva_mesa = f"Mesa {siguiente_numero}"
        cursor.execute(
            "INSERT INTO mesas (nombre) VALUES (?)", (nombre_nueva_mesa,)
        )
        conn.commit()
    return jsonify({"status": "success", "nombre": nombre_nueva_mesa})


# NUEVA RUTA: Agrega un mesero nuevo a la base de datos
@app.route("/api/nuevo-mesero", methods=["POST"])
def crear_mesero():
    data = request.json
    nombre_mesero = data.get("nombre")

    if not nombre_mesero or nombre_mesero.strip() == "":
        return jsonify({"status": "error", "message": "Nombre inválido"}), 400

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (nombre) VALUES (?)", (nombre_mesero.strip(),)
        )
        conn.commit()
    return jsonify({"status": "success", "nombre": nombre_mesero})


# INICIALIZACIÓN AUTOMÁTICA (Para la Nube / Gunicorn)
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
