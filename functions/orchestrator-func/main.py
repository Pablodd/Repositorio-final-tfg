import mysql.connector
from googleapiclient import discovery
from datetime import datetime
import pytz 
from google.cloud import run_v2
import time

def deploy_portal_cloud_run(project_id, location, stream_key):
    client = run_v2.ServicesClient()
    parent = f"projects/{project_id}/locations/{location}"
    service_id = f"portal-{stream_key.lower().replace('_', '-')}"
    
    service = run_v2.Service()
    service.template.containers = [{
        "image": "europe-southwest1-docker.pkg.dev/stream-cloud-tfg/cloud-run-source-deploy/frontend-dinamico",
        "ports": [{"container_port": 8080}]
    }]
    service.template.scaling.max_instance_count = 3

    print(f"Capa 4: Lanzando creación de Cloud Run {service_id}...")
    
    try:
        operation = client.create_service(parent=parent, service=service, service_id=service_id)
        response = operation.result()
        
        # IAM para hacerlo público
        from google.iam.v1 import iam_policy_pb2, policy_pb2
        get_policy_request = iam_policy_pb2.GetIamPolicyRequest(resource=response.name)
        policy = client.get_iam_policy(request=get_policy_request)
        
        new_binding = policy_pb2.Binding(role="roles/run.invoker", members=["allUsers"])
        policy.bindings.append(new_binding)
        
        set_policy_request = iam_policy_pb2.SetIamPolicyRequest(resource=response.name, policy=policy)
        client.set_iam_policy(request=set_policy_request)

        print(f"✅ Portal {service_id} público en: {response.uri}")
        # DEVOLVEMOS EL RESPONSE COMPLETO para capturar la URI
        return response
    except Exception as e:
        print(f"⚠️ Error en deploy Cloud Run: {e}")
        raise e

def check_and_start_vm(event, context=None):
    project = 'stream-cloud-tfg'
    region = 'europe-southwest1'
    zone = 'europe-southwest1-a'
    
    db_config = {
        'user': 'orquestador',
        'password': 'tfg_password_2026',
        'host': '10.0.1.7', 
        'database': 'streaming_db',
        'connect_timeout': 5
    }

    try:
        print("--- INICIO DE DIAGNÓSTICO ---")
        print(f"DEBUG: Hora del sistema (UTC): {datetime.now()}")
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT NOW() as hora_db, UTC_TIMESTAMP() as hora_utc")
        db_time = cursor.fetchone()
        
        query = """
            SELECT id, stream_key, hora_arranque, status 
            FROM eventos 
            WHERE status = 'programado' 
            AND hora_arranque <= DATE_ADD(NOW(), INTERVAL 2 HOUR)
        """
        
        print(f"Capa 1: Ejecutando consulta de eventos...")
        cursor.execute(query)
        eventos = cursor.fetchall()
        
        print(f"Capa 2: Eventos encontrados para procesar: {len(eventos)}")

        if eventos:
            compute = discovery.build('compute', 'v1')
            template = f"projects/{project}/regions/{region}/instanceTemplates/template-streaming-tfg-v6"

            for evento in eventos:
                s_key = evento['stream_key']
                vm_unique_name = f"stream-vm-{s_key.lower().replace('_', '-')}-{int(time.time())}"
                
                # 1. Crear VM
                config = {
                    'name': vm_unique_name,
                    'metadata': {'items': [{'key': 'current_stream_key', 'value': s_key}]}
                }
                compute.instances().insert(
                    project=project, zone=zone, sourceInstanceTemplate=template, body=config
                ).execute()

                # --- LÓGICA CORREGIDA: Capturar IP EXTERNA (Pública) ---
                print(f"Capa 3.1: Esperando IP Pública para {vm_unique_name}...")
                
                vm_external_ip = None
                retries = 5
                while retries > 0:
                    time.sleep(2) # Espera un poco a que GCP asigne la IP externa
                    vm_data = compute.instances().get(project=project, zone=zone, instance=vm_unique_name).execute()
                    
                    try:
                        # Intentamos acceder a la configuración de acceso (donde reside la IP externa)
                        interfaces = vm_data.get('networkInterfaces', [])
                        if interfaces:
                            access_configs = interfaces[0].get('accessConfigs', [])
                            if access_configs:
                                vm_external_ip = access_configs[0].get('natIP')
                                if vm_external_ip:
                                    break
                    except (KeyError, IndexError):
                        pass
                    
                    retries -= 1
                    print(f"Reintentando obtener IP pública... ({5-retries}/5)")

                if not vm_external_ip:
                    # Si falla la externa, al menos guardamos la interna para que no rompa, 
                    # pero lanzamos aviso
                    vm_external_ip = vm_data['networkInterfaces'][0]['networkIP']
                    print(f"⚠️ No se obtuvo IP Pública, usando Interna: {vm_external_ip}")
                else:
                    print(f"✅ IP PÚBLICA capturada: {vm_external_ip}")
                # -------------------------------------------------------

                # 2. Lanzar Cloud Run (se mantiene igual)
                portal_url = None
                try:
                    run_response = deploy_portal_cloud_run(project, region, s_key)
                    portal_url = run_response.uri
                except Exception as e_run:
                    print(f"⚠️ Salto Cloud Run: {e_run}")

                # 3. Actualizar status, URL y la IP PÚBLICA
                update_query = """
                    UPDATE eventos 
                    SET status = 'encendiendo', 
                        vm_name = %s, 
                        url_emision = %s,
                        vm_ip = %s 
                    WHERE id = %s
                """
                # Ahora pasamos vm_external_ip en lugar de vm_internal_ip
                cursor.execute(update_query, (vm_unique_name, portal_url, vm_external_ip, evento['id']))
        
        conn.commit()
        print("--- FIN DE PROCESO ---")
        cursor.close()
        conn.close()
        return "OK", 200

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}")
        return f"Error: {e}", 500
