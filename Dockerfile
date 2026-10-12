FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc y forzar salida stdout sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Instalar dependencias del sistema operativo requeridas para compilar psycopg y cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar manifiesto de dependencias e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente completo de la aplicación
COPY . .

# Crear usuario sin privilegios para evitar ejecutar el servidor como root
RUN addgroup --system appgroup && adduser --system --group appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Arranque en modo producción utilizando workers controlados
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]