import os
import logging
import uuid
from flask import request, jsonify
from flask import current_app as app
from . import db as db_module
from flask import Flask

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_routes(app):
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200
    
    # --- GET /employees ---
    @app.route("/employees", methods=["GET"])
    def get_employees():
        """Devuelve la lista de contactos.

        Cada elemento tiene la forma:
        {
          "uuid": "...",
          "nombre": "...",
          "correo": "...",
          "telefono": "..."
        }
        """
        try:
            conn = db_module.get_db()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    uuid,
                    nombre,
                    correo,
                    telefono
                FROM empleados
                ORDER BY creado_en ASC
                """
            )
            rows = cur.fetchall()
            cur.close()

            employees = []
            for row in rows:
                employees.append({
                    "uuid": row[0],
                    "nombre": row[1],
                    "correo": row[2],
                    "telefono": row[3]
                })

            return jsonify(employees), 200
        except Exception as e:
            logger.error(f"Error al obtener empleados: {str(e)}")
            return jsonify({"error": "Error al obtener empleados"}), 500

    @app.route("/employees", methods=["POST"])
    def add_employee():
        """Crea un empleado a partir de un payload con la forma:
        {
          "contacto": {
            "nombre": "Henry",
            "correo": "henry@example.com",
            "telefono": "+50371234567"
          }
        }

        El UUID ya no es obligatorio en el cuerpo: se genera
        automáticamente en el servidor usando uuid.uuid4().
        """
        data = request.get_json(silent=True) or {}

        contacto = data.get("contacto")
        if not isinstance(contacto, dict):
            return jsonify({"error": "El cuerpo debe incluir un objeto 'contacto'"}), 400

        nombre = contacto.get("nombre")
        correo = contacto.get("correo")
        telefono = contacto.get("telefono")

        # Validaciones básicas del nuevo formato
        if not nombre or not correo or not telefono:
            return jsonify({
                "error": "nombre, correo y telefono son requeridos dentro de 'contacto'"
            }), 400

        # Generar UUID automático para el contacto
        generated_uuid = str(uuid.uuid4())

        try:
            conn = db_module.get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO empleados (
                    uuid,
                    nombre,
                    correo,
                    telefono
                )
                VALUES (%s, %s, %s, %s)
                RETURNING uuid, creado_en
                """,
                (generated_uuid, nombre, correo, telefono)
            )
            result = cur.fetchone()
            conn.commit()
            cur.close()
            return jsonify({
                "uuid": result[0],
                "creado_en": result[1].isoformat(),
                "contacto": {
                    "uuid": result[0],
                    "nombre": nombre,
                    "correo": correo,
                    "telefono": telefono
                }
            }), 201
        except Exception as e:
            logger.error(f"Error al insertar empleado: {str(e)}")
            return jsonify({"error": "Error al insertar empleado"}), 500

def create_app():
    app = Flask(__name__)

    # Genera una clave secreta si no está definida en variables de entorno
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

    db_module.init_db(app)
    from . import main
    main.create_routes(app)

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)