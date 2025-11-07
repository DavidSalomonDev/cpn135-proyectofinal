import os
import psycopg2
from flask import g
from psycopg2.extras import RealDictCursor

def get_db():
    if "db" not in g:
        conn = psycopg2.connect(
            host="3.21.242.71",
            port=5432,
            dbname="empleados",
            user="admin",
            password="Password123",
            connect_timeout=5
        )
        g.db = conn
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    app.teardown_appcontext(close_db)
