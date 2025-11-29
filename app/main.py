import os
import logging
import socket
import smtplib
from email.message import EmailMessage

from flask import Flask, request, jsonify
from dotenv import load_dotenv

from . import db as db_module
from twilio.rest import Client as TwilioClient

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_server_ip() -> str:
    """
    Obtiene la IP del servidor. Si existe la variable de entorno SERVER_IP,
    se usa esa (por si quieres forzar una IP pública específica).
    """
    env_ip = os.getenv("SERVER_IP")
    if env_ip:
        return env_ip

    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except Exception:
        logger.exception("No se pudo obtener la IP del servidor")
        return "0.0.0.0"


def send_email(uuid_value: str, nombre: str, correo: str, server_ip: str) -> None:
    """
    Envía un correo utilizando Amazon SES vía SMTP.

    Requiere variables de entorno:

    - AWS_REGION (ej: us-east-1)
    - SES_FROM_EMAIL  (remitente verificado en SES)
    - SES_SMTP_HOST   (ej: email-smtp.us-east-1.amazonaws.com)
    - SES_SMTP_PORT   (normalmente 587)
    - SES_SMTP_USERNAME
    - SES_SMTP_PASSWORD
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    source = os.getenv("SES_FROM_EMAIL")

    smtp_host = os.getenv("SES_SMTP_HOST") or f"email-smtp.{region}.amazonaws.com"
    smtp_port = int(os.getenv("SES_SMTP_PORT", "587"))
    smtp_user = os.getenv("SES_SMTP_USERNAME")
    smtp_pass = os.getenv("SES_SMTP_PASSWORD")

    if not source:
        raise RuntimeError("SES_FROM_EMAIL no está configurado en variables de entorno")

    if not smtp_user or not smtp_pass:
        raise RuntimeError(
            "SES_SMTP_USERNAME y SES_SMTP_PASSWORD deben estar configurados"
        )

    subject = "Notificación de registro CPN135"
    body = (
        f"Nombre: {nombre}\n"
        f"UUID: {uuid_value}\n"
        f"IP del servidor: {server_ip}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = source
    msg["To"] = correo
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Correo enviado correctamente a %s", correo)
    except Exception:
        logger.exception("Error al enviar correo con SES (SMTP)")
        raise


def send_sms(uuid_value: str, nombre: str, telefono: str, server_ip: str) -> None:
    """
    Envía un SMS utilizando Twilio.

    Requiere variables de entorno:
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_FROM_NUMBER
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number:
        raise RuntimeError(
            "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_FROM_NUMBER "
            "deben estar configurados"
        )

    client = TwilioClient(account_sid, auth_token)

    message_body = (
        f"Registro CPN135:\n"
        f"Nombre: {nombre}\n"
        f"UUID: {uuid_value}\n"
        f"IP servidor: {server_ip}"
    )

    try:
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=telefono,
        )
        logger.info("SMS enviado correctamente a %s, SID=%s", telefono, message.sid)
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
        Endpoint principal:

        Recibe JSON:
        {
          "uuid": "....",
          "nombre": "....",
          "correo": "....",
          "telefono": "...."
        }

        1) Guarda la info en la tabla 'registros'
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

        # Obtener conexión a BD
        conn = db_module.get_db()
        server_ip = get_server_ip()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO registros (uuid, nombre, correo, telefono)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, creado_en;
                    """,
                    (uuid_value, nombre, correo, telefono),
                )
                row = cur.fetchone()
            conn.commit()
        except Exception:
            logger.exception("Error al insertar en la tabla 'registros'")
            conn.rollback()
            return jsonify({"error": "Error al insertar en la base de datos"}), 500

        # Enviar correo y SMS
        try:
            send_email(uuid_value, nombre, correo, server_ip)
        except Exception:
            # Opcional: puedes decidir si esto debe romper o no el flujo
            return jsonify({"error": "Error enviando correo con SES"}), 500

        try:
            send_sms(uuid_value, nombre, telefono, server_ip)
        except Exception:
            return jsonify({"error": "Error enviando SMS con Twilio"}), 500

        response = {
            "id": row["id"] if row and "id" in row else None,
            "uuid": uuid_value,
            "nombre": nombre,
            "correo": correo,
            "telefono": telefono,
            "server_ip": server_ip,
        }

        return jsonify(response), 201


def create_app() -> Flask:
    """
    Factory de la aplicación Flask.
    """
    # Cargar variables de entorno de un archivo .env (si existe)
    load_dotenv()

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
