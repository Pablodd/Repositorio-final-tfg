#!/bin/bash

# --- CONFIGURACIÓN DINÁMICA CON LIMPIEZA ---
# Extraemos la clave y eliminamos saltos de línea (\n), retornos (\r) y espacios
RAW_KEY=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/attributes/current_stream_key)
STREAM_KEY=$(echo "$RAW_KEY" | tr -d '\r\n' | xargs)

VM_NAME=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)

if [ -z "$STREAM_KEY" ]; then
    echo "❌ No se detectó STREAM_KEY. Abortando..."
    exit 1
fi

# --- CONFIGURACIÓN DE RUTAS ---
LOCAL_DIR="/home/pablo_perez92/stream-project/hls"
BUCKET="gs://tfg-stream-bucket-2026/hls/$STREAM_KEY"
PROJECT_ID="stream-cloud-tfg"
DB_HOST="10.0.1.7"
DB_USER="orquestador"
DB_PASS="tfg_password_2026"
DB_NAME="streaming_db"

IS_LIVE=false
ID_SESION=""

echo "🚀 Sincronización ACTIVA"
echo "🔑 Clave Limpia: '$STREAM_KEY'"
echo "📂 Buscando archivos en: $LOCAL_DIR"

while true; do
  # 1. Subida de fragmentos (.ts)
  if ls "$LOCAL_DIR"/*.ts >/dev/null 2>&1; then
    gsutil -m -q cp "$LOCAL_DIR"/*.ts "$BUCKET/" > /dev/null 2>&1
  fi

  # 2. Gestión del Manifiesto (.m3u8)
  # Usamos un comodín (*) para encontrar el archivo aunque tenga caracteres raros
  MANIFEST_PATH=$(ls "$LOCAL_DIR"/*.m3u8 2>/dev/null | head -n 1)

  if [ -f "$MANIFEST_PATH" ]; then
    
    # Subida al bucket SIEMPRE como index.m3u8 para que el Player lo encuentre
    gsutil -h "Cache-Control:no-store, no-cache, must-revalidate, max-age=0" \
           cp "$MANIFEST_PATH" "$BUCKET/index.m3u8" > /dev/null 2>&1
    
    if [ "$IS_LIVE" = false ]; then
        echo "✅ [$(date +%H:%M:%S)] ¡Directo detectado!"
        
        TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        ID_SESION="${STREAM_KEY}_$(date +%s)"
        TOKEN=$(gcloud auth print-access-token)

        # --- ACTUALIZAR FIRESTORE ---
        curl -s -X PATCH "https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/db-streaming/documents/sesiones/${ID_SESION}" \
             -H "Content-Type: application/json" \
             -H "Authorization: Bearer $TOKEN" \
             -d "{
               \"fields\": {
                 \"vm_id\": {\"stringValue\": \"$VM_NAME\"},
                 \"stream_key\": {\"stringValue\": \"$STREAM_KEY\"},
                 \"timestamp\": {\"timestampValue\": \"$TS\"},
                 \"url\": {\"stringValue\": \"https://storage.googleapis.com/tfg-stream-bucket-2026/hls/${STREAM_KEY}/index.m3u8\"},
                 \"status\": {\"stringValue\": \"online\"}
               }
             }" > /dev/null

        # --- ACTUALIZAR MARIADB ---
        mariadb -h $DB_HOST -u $DB_USER -p$DB_PASS $DB_NAME -e \
        "INSERT INTO sessions (user_id, status, start_time, hls_url, stream_key) 
         VALUES (1, 'LIVE', NOW(), 'https://storage.googleapis.com/tfg-stream-bucket-2026/hls/$STREAM_KEY/index.m3u8', '$STREAM_KEY');"

        IS_LIVE=true
    fi
  else
    # Si el archivo .m3u8 desaparece, cerramos sesión
    if [ "$IS_LIVE" = true ]; then
        echo "🛑 Finalizando directo..."
        TOKEN=$(gcloud auth print-access-token)
        
        # Update Firestore a Offline
        curl -s -X PATCH "https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/db-streaming/documents/sesiones/${ID_SESION}?updateMask.fieldPaths=status" \
             -H "Content-Type: application/json" \
             -H "Authorization: Bearer $TOKEN" \
             -d "{\"fields\": {\"status\": {\"stringValue\": \"offline\"}}}" > /dev/null

        # Update MariaDB
        mariadb -h $DB_HOST -u $DB_USER -p$DB_PASS $DB_NAME -e \
        "UPDATE sessions SET status='OFFLINE', end_time=NOW() WHERE stream_key='$STREAM_KEY' AND status='LIVE';"

        IS_LIVE=false
    fi
  fi

  # Limpieza fragmentos viejos
  find "$LOCAL_DIR" -name "*.ts" -mmin +2 -delete
  sleep 2
done
