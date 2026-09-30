import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from flask_cors import CORS

DB_PATH = "catalog.db"
API_KEY = os.environ.get("API_KEY", "devkey")  # en Render se define como variable de entorno

app = Flask(__name__)
CORS(app)


# ---------- Base de datos ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Producto inicial para que GET /products no salga vacío
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO products(name, price, stock, created_at) VALUES (?, ?, ?, ?)",
                ("Lapicero", 12.5, 100, now_iso()),
            )


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# Se ejecuta al importar, así también funciona con gunicorn
init_db()


# ---------- Seguridad ----------
@app.before_request
def check_api_key():
    if request.method == "OPTIONS":  # preflight de CORS
        return None
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "API Key inválida o ausente"}), 401
    return None


# ---------- Utilidades ----------
def validate_product(data):
    """Regresa (datos_limpios, error)."""
    if not isinstance(data, dict):
        return None, "Se requiere un cuerpo JSON válido"
    name = data.get("name")
    price = data.get("price")
    stock = data.get("stock")
    if not isinstance(name, str) or not name.strip():
        return None, "El campo 'name' es obligatorio"
    if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
        return None, "El campo 'price' debe ser un número no negativo"
    if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
        return None, "El campo 'stock' debe ser un entero no negativo"
    return {"name": name.strip(), "price": float(price), "stock": stock}, None


# ---------- Endpoints CRUD ----------
@app.route("/products", methods=["GET"])
def list_products():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(dict(row)), 200


@app.route("/products", methods=["POST"])
def create_product():
    data, error = validate_product(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO products(name, price, stock, created_at) VALUES (?, ?, ?, ?)",
            (data["name"], data["price"], data["stock"], now_iso()),
        )
        row = conn.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    data, error = validate_product(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE products SET name = ?, price = ?, stock = ? WHERE id = ?",
            (data["name"], data["price"], data["stock"], product_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado"}), 404
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return jsonify(dict(row)), 200


@app.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    with get_db() as conn:
        cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    if cur.rowcount == 0:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"message": "Producto eliminado", "id": product_id}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)