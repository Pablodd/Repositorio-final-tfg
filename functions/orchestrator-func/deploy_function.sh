#!/bin/bash
# Comando para desplegar el orquestador
gcloud run deploy orquestador-streaming \
  --source . \
  --region europe-southwest1 \
  --allow-unauthenticated
