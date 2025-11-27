import os
import logging
import socket

from flask import Flask, request, jsonify

from . import db as db_module

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from twilio.rest import Client as TwilioClient

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_server_ip() -> str:
    """
    Devuelve la IP del servidor que responde.
    Primero intenta leer SERVER_IP de variables de entorno y si no,
    intenta resolver la IP local.
    """
    env_ip = os.getenv("SERVER_IP")
    if env_ip:
        return env_ip

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "unknown"


def send_email(uuid_value: str, nombre: str, correo: str, server_ip: str) -> None:
    """
    Envía un correo utilizando Amazon SES con la info requerida por el examen.
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    source = os.getenv("SES_FROM_EMAIL")

    if not source:
        raise RuntimeError("SES_FROM_EMAIL no está configurado en variables de entorno")

    ses = boto3.client("ses", region_name=region)

    subject = "Notificación de registro CPN135"
    body = (
        f"Nombre: {nombre}\n"
        f"UUID: {uuid_value}\n"
        f"IP: {server_ip}\n"
    )

    try:
        ses.send_email(
            Source=source,
            Destination={"ToAddresses": [correo]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        logger.info("Correo enviado correctamente a %s", correo)
    except (BotoCoreError, ClientError):
        logger.exception("Error al enviar correo con SES")
        raise


def send_sms(uuid_value: str, nombre: str, telefono: str, server_ip: str) -> None:
    """
    Envía un SMS utilizando la API de Twilio con la info requerida por el examen.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number:
        raise RuntimeError(
            "Las variables TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y "
            "TWILIO_FROM_NUMBER deben estar configuradas"
        )

    client = TwilioClient(account_sid, auth_token)

    body = (
        f"Nombre: {nombre}\n"
        f"UUID: {uuid_value}\n"
        f"IP: {server_ip}"
    )

    try:
        client.messages.create(
            body=body,
            from_=from_number,
            to=telefono,
        )
        logger.info("SMS enviado correctamente a %s", telefono)
    except Exception:
        logger.exception("Error al enviar SMS con Twilio")
        raise


def create_routes(app: Flask) -> None:
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/registro", methods=["POST"])
    def registro():
        """
        Endpoint principal del examen.
        Recibe por POST un JSON con al menos:
        {
          "uuid": "...",
          "nombre": "...",
          "correo": "...",
          "telefono": "..."
        }
        1) Guarda la info en la BD
        2) Envía correo (SES)
        3) Envía SMS (Twilio)
        4) Responde con la info y la IP del servidor
        """
        data = request.get_json(silent=True) or {}

        uuid_value = data.get("uuid")
        nombre = data.get("nombre")
        correo = data.get("correo")
        telefono = data.get("telefono")

        if not uuid_value or not nombre or not correo or not telefono:
            return (
                jsonify(
                    {
                        "error": (
                            "uuid, nombre, correo y telefono son requeridos "
                            "en el JSON de entrada"
                        )
                    }
                ),
                400,
            )

        # 1. Guardar en BD
        try:
            conn = db_module.get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO registros (uuid, nombre, correo, telefono)
                VALUES (%s, %s, %s, %s)
                RETURNING id, creado_en
                """,
                (uuid_value, nombre, correo, telefono),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            logger.info("Registro almacenado en BD con id=%s", row[0])
        except Exception:
            logger.exception("Error al insertar registro en la base de datos")
            return jsonify({"error": "Error al almacenar en la base de datos"}), 500

        server_ip = get_server_ip()

        # 2. Enviar correo
        try:
            send_email(uuid_value, nombre, correo, server_ip)
        except Exception:
            # El examen exige envío de correo, así que si falla devolvemos error
            return jsonify({"error": "Error al enviar correo"}), 500

        # 3. Enviar SMS
        try:
            send_sms(uuid_value, nombre, telefono, server_ip)
        except Exception:
            return jsonify({"error": "Error al enviar SMS"}), 500

        # 4. Responder al cliente
        return (
            jsonify(
                {
                    "id": row[0],
                    "uuid": uuid_value,
                    "nombre": nombre,
                    "correo": correo,
                    "telefono": telefono,
                    "ip": server_ip,
                    "creado_en": row[1].isoformat(),
                }
            ),
            201,
        )


def create_app() -> Flask:
    app = Flask(__name__)

    # Genera una clave secreta si no está definida en variables de entorno
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(24).hex()

    db_module.init_db(app)
    create_routes(app)

    return app


if __name__ == "__main__":
    application = create_app()
    port = int(os.getenv("PORT", 5000))
    application.run(host="0.0.0.0", port=port)
