Flujo de Mensajería Pub/Sub
Este módulo gestiona la comunicación asíncrona del sistema:

Tópico (activar-streaming-topic): Recibe notificaciones del Cloud Scheduler cada minuto.

Suscripción (eventarc-sub): Dispara la Cloud Function orchestrator-func cuando llega un nuevo mensaje para levantar la infraestructura de streaming (VMs y portal web).
