import os
from flask import request, jsonify
from flask import current_app as app
from . import db as db_module
from flask import Flask

def create_routes(app):
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/employees", methods=["POST"])
    def add_employee():
        data = request.get_json(silent=True) or {}
        # validaciones básicas
        name = data.get("name")
        email = data.get("email")
        position = data.get("position", "")
        salary = data.get("salary", None)

        if not name or not email:
            return jsonify({"error": "name y email son requeridos"}), 400

        try:
            conn = db_module.get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO employees (name, email, position, salary)
                VALUES (%s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (name, email, position, salary)
            )
            result = cur.fetchone()
            conn.commit()
            cur.close()
            return jsonify({
                "id": result[0],
                "created_at": result[1].isoformat()
            }), 201
        except Exception as e:
            # no exponer errores internos en producción
            return jsonify({"error": "error al insertar empleado", "detail": str(e)}), 500

def create_app():
    app = Flask(__name__)
    db_module.init_db(app)
    create_routes(app)
    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
