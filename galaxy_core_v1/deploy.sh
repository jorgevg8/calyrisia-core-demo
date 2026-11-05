#!/usr/bin/env bash
set -e

echo "=== [GALAXY CORE] INICIANDO DESPLIEGUE A PRODUCCIÓN ==="

# Descargar e instalar Docker si no existe en el servidor VPS
if ! [ -x "$(command -v docker)" ]; then
    echo "Instalando Docker Engine..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

echo "Construyendo contenedores y levantando PostgreSQL + FastAPI..."
docker compose down || true
docker compose up -d --build

echo "Esperando que el servicio API esté listo..."
sleep 8
curl -f http://127.0.0.1:8000/health/ready || (echo "Fallo de arranque de la API" && exit 1)

echo "=== [GALAXY CORE] SISTEMA EN LÍNEA Y OPERATIVO EN PRODUCCIÓN ==="