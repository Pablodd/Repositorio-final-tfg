#!/bin/bash
# 1. Obtener la clave de la instancia
STREAM_KEY=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/attributes/current_stream_key)

# 2. Ir a la carpeta del proyecto
cd /home/pablo_perez92/stream-project

# 3. Levantar el Docker (aquí ajustaremos según si usas docker run o compose)
# Si es docker run:
docker run -d --name sync-bucket -e STREAM_KEY=$STREAM_KEY -v $(pwd)/hls:/data tu-imagen-docker
