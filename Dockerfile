FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del SO necesarias para psycopg2
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY app/ ./app/

# Variables de entorno
ENV FLASK_APP=app.main:create_app
# Las credenciales se pasan desde docker-compose.yml o .env

EXPOSE 5000

# Usar gunicorn para producción
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app.main:create_app()"]