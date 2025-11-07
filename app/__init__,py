from flask import Flask
from .db import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_envvar("APP_SETTINGS", silent=True)  # opcional
    init_db(app)
    return app
