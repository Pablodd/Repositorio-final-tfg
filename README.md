🚀 Sistema de Streaming Cloud TFG
Este repositorio contiene la infraestructura completa y el código fuente para un sistema de streaming de baja latencia escalable en Google Cloud Platform.

🏗️ Arquitectura del Sistema
El proyecto se basa en una arquitectura de microservicios orquestada mediante eventos:

Ingesta: VM con Nginx RTMP/SRT.

Procesamiento: Cloud Functions (Python) para orquestación.

Almacenamiento: Cloud Storage (HLS fragments).

Base de Datos: MariaDB (Relacional) y Firestore (NoSQL).

Frontend: Portal Web en Cloud Run.

🛠️ Requisitos Previos
Una cuenta activa de Google Cloud Platform.

Google Cloud SDK (gcloud) instalado.

Repositorio de GitHub clonado en Cloud Shell.

🚀 Guía de Despliegue (Paso a Paso)
1. Configuración de Red e Infraestructura
Primero, debemos preparar el terreno (VPC, Firewall y Almacenamiento):

Bash
# Aplicar reglas de red y firewall
gcloud compute networks create $(cat infrastructure/network/vpc-config.yaml | grep name)
# (Opcional) Importar reglas de firewall
gcloud compute firewall-rules create tfg-firewall --allow=tcp:80,tcp:443,tcp:1935,udp:6000
2. Despliegue de Base de Datos
Crear la instancia de VM según vms/db-server-config.yaml.

Instalar Docker y levantar MariaDB:

Bash
cd database/mariadb
docker-compose up -d
# Importar el esquema
docker exec -i mariadb_container mysql -u root -p < esquema_tablas.sql
3. Servidores de Video (Streaming & SRT Relay)
Desplegar las instancias streaming-server-tfg y srt-relay-tfg usando las configuraciones en /vms y ejecutar los scripts de inicio:

Configurar Nginx con vms/scripts/streaming-server/conf/nginx.conf.

Levantar el Relay con el docker-compose.yml en vms/scripts/srt-relay/.

4. Orquestador y Microservicios
Desplegar la lógica serverless:

Bash
cd functions/orchestrator-func
bash deploy_function.sh
📁 Estructura del Repositorio
/services: Código de los microservicios de cliente y web.

/infrastructure: Configuración de Pub/Sub, Scheduler y Redes.

/database: Esquemas SQL y definiciones de Firestore.

/vms: Planos técnicos y scripts internos de los servidores.
