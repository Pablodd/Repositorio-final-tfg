#!/bin/bash
# 1. Obtener la clave de los metadatos de Google
export STREAM_KEY=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/attributes/current_stream_key)

# 2. Parar y borrar contenedores viejos si existen
docker stop sync-container 2>/dev/null
docker rm sync-container 2>/dev/null

# 3. Construir la imagen (opcional si ya está construida, pero asegura frescura)
cd /home/pablo_perez92/stream-project
docker build -t streaming-image .

# 4. Arrancar el contenedor pasando la clave y montando la carpeta HLS
docker run -d \
  --name sync-container \
  -e STREAM_KEY=$STREAM_KEY \
  -v /home/pablo_perez92/stream-project/hls:/home/pablo_perez92/stream-project/hls \
  streaming-image
