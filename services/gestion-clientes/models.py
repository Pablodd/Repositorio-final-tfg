import mysql.connector
import uuid
import logging
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
# Nuevos imports para la destrucción de recursos
from googleapiclient import discovery
from google.cloud import run_v2

class EventoModel:
    def __init__(self):
        self.config = {
            'user': 'orquestador',
            'password': 'tfg_password_2026',
            'host': '10.0.1.7',
            'database': 'streaming_db'
        }
        self.db = firestore.Client(project="stream-cloud-tfg", database="db-streaming")
        
        # Configuración de GCP para la destrucción
        self.project_id = 'stream-cloud-tfg'
        self.region = 'europe-southwest1'
        self.zone = 'europe-southwest1-a'

    def _get_connection(self):
        return mysql.connector.connect(**self.config)

    def validar_usuario(self, username, password):
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, username FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user

    def get_eventos_por_usuario(self, usuario_id):
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM eventos WHERE usuario_id = %s ORDER BY hora_arranque DESC", (usuario_id,))
        eventos = cursor.fetchall()
        cursor.close()
        conn.close()
        return eventos

    def crear_reserva(self, usuario_id, nombre, email, fecha, hora):
        fecha_hora = f"{fecha} {hora}:00"
        stream_key = f"tfg_{uuid.uuid4().hex[:8]}"
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO eventos 
                (usuario_id, nombre_evento, cliente_email, fecha_inicio, hora_arranque, stream_key, status) 
                VALUES (%s, %s, %s, %s, %s, %s, 'programado')
            """
            cursor.execute(query, (usuario_id, nombre, email, fecha_hora, fecha_hora, stream_key))
            conn.commit()
            cursor.close()
            conn.close()
            return stream_key
        except Exception as e:
            print(f"ERROR DB: {e}")
            return None

    def obtener_evento_por_key(self, stream_key):
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM eventos WHERE stream_key = %s"
            cursor.execute(query, (stream_key,))
            evento = cursor.fetchone()
            cursor.close()
            conn.close()
            return evento
        except Exception as e:
            print(f"ERROR DB: {e}")
            return None

    def finalizar_evento(self, key):
        print(f">>> Intentando finalizar evento y destruir recursos: {key}")
        
        # 1. FIRESTORE
        try:
            docs = self.db.collection("sesiones").where(filter=FieldFilter("stream_key", "==", key)).get()
            for doc in docs:
                doc.reference.update({'status': 'finalizado'})
            print(f"✅ Firestore actualizado para: {key}")
        except Exception as e:
            print(f"❌ Error Firestore: {str(e)}")

        # 2. OBTENER DATOS PARA DESTRUCCIÓN Y ACTUALIZAR MARIADB
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Buscamos el nombre de la VM antes de marcar como finalizado
            cursor.execute("SELECT vm_name FROM eventos WHERE stream_key = %s", (key,))
            row = cursor.fetchone()
            
            if row and row['vm_name']:
                vm_name = row['vm_name']
                # El service_id de Cloud Run sigue el patrón del orquestador
                service_id = f"portal-{key.lower().replace('_', '-')}"
                
                # EJECUTAR DESTRUCCIÓN DE RECURSOS EN GCP
                self._eliminar_recursos_gcp(vm_name, service_id)

            # ACTUALIZAR STATUS Y MARCAR COMO BORRADO EN DB
            query = "UPDATE eventos SET status = %s, vm_deleted = 1 WHERE stream_key = %s"
            cursor.execute(query, ('finalizado', key))
            conn.commit()
            
            print(f"✅ MariaDB actualizado y recursos marcados como borrados.")
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ Error MariaDB/Destrucción: {str(e)}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _eliminar_recursos_gcp(self, vm_name, service_id):
        """Lógica para eliminar la VM y el servicio Cloud Run"""
        # Borrar Instancia de Compute Engine
        try:
            compute = discovery.build('compute', 'v1')
            print(f"Iniciando borrado de VM: {vm_name}...")
            compute.instances().delete(
                project=self.project_id, 
                zone=self.zone, 
                instance=vm_name
            ).execute()
            print(f"✅ Petición de borrado de VM enviada.")
        except Exception as e:
            print(f"⚠️ Error al borrar VM (puede que ya no exista): {e}")

        # Borrar Servicio de Cloud Run
        try:
            client = run_v2.ServicesClient()
            resource_name = f"projects/{self.project_id}/locations/{self.region}/services/{service_id}"
            print(f"Iniciando borrado de Cloud Run: {service_id}...")
            client.delete_service(name=resource_name)
            print(f"✅ Petición de borrado de Cloud Run enviada.")
        except Exception as e:
            print(f"⚠️ Error al borrar Cloud Run: {e}")