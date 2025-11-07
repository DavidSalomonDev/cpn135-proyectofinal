FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# dependencias del SO necesarias para psycopg2
RUN apt-get update && apt-get install -y build-essential libpq-dev --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

# opcional: cargar variables de entorno desde archivo .env si se desea
ENV FLASK_APP=app.main:create_app

# usar gunicorn para producción
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app.main:create_app()"]
