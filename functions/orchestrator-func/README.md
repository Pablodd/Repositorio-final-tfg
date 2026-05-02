Orquestador de Streaming
Esta función es el núcleo lógico del proyecto. Se activa mediante un evento de Pub/Sub y realiza las siguientes tareas:

Consulta MariaDB: Verifica los detalles del evento que debe activarse.

Despliegue Dinámico: Utiliza la API de google-cloud-run para levantar un nuevo servicio de "Portal Web" específico para el cliente.

Gestión de VMs: (Próximamente/En desarrollo) Lanza la instancia de Compute Engine con el motor de streaming
