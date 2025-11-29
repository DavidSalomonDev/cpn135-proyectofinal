import os
import psycopg2
from flask import g
from psycopg2.extras import RealDictCursor


def get_db():
    """
    Retorna una conexión global a la base de datos PostgreSQL
    usando variables de entorno:

    - DB_HOST
    - DB_PORT (opcional, por defecto 5432)
    - DB_NAME
    - DB_USER
    - DB_PASSWORD
    """
    if "db" not in g:
        required_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            raise ValueError(
                f"Variables de entorno faltantes para la BD: {', '.join(missing)}"
            )

        host = os.getenv("DB_HOST")
        port = int(os.getenv("DB_PORT", "5432"))
        dbname = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")

        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5,
            cursor_factory=RealDictCursor,
        )
        g.db = conn

    return g.db


def close_db(e=None):
    """
    Cierra la conexión guardada en el contexto de Flask, si existe.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """
    Registra el teardown en la app de Flask para cerrar la conexión
    al final de cada request.
    """
    app.teardown_appcontext(close_db)
