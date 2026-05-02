from flask import Flask, render_template, request, redirect, url_for, session
from models import EventoModel
import requests
import xml.etree.ElementTree as ET
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'tfg_secret_key_pro'
model = EventoModel()
CORS(app)



@app.route('/')
def login():
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    username = request.form['username']
    password = request.form['password']
    user = model.validar_usuario(username, password)
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        return redirect(url_for('dashboard'))
    return "Usuario o contraseña incorrectos", 401

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    eventos = model.get_eventos_por_usuario(session['user_id'])
    return render_template('dashboard.html', eventos=eventos)

@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        model.crear_reserva(
            session['user_id'],
            request.form.get('nombre_evento'),
            request.form.get('cliente_email'),
            request.form.get('fecha_inicio'),
            request.form.get('hora_arranque')
        )
        return redirect(url_for('dashboard'))
    return render_template('reservar.html')

@app.route('/streaming/<key>')
def ver_streaming(key):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    evento = model.obtener_evento_por_key(key)
    if not evento: return "Evento no encontrado", 404
    
    # Si la VM está apagada o no tiene IP todavía
    if not evento.get('vm_ip'):
        return render_template('monitor.html', evento=evento, stats={'status': 'Iniciando servidor...'})

    url_stats = f"http://{evento['vm_ip']}/stat"
    telemetria = {'status': 'Offline', 'bitrate': '0 kbps', 'fps': '0'}

    try:
        respuesta = requests.get(url_stats, timeout=2)
        if respuesta.status_code == 200:
            root = ET.fromstring(respuesta.content)
            # Buscamos la stream key en el XML de Nginx-RTMP
            stream_node = root.find(f".//stream[name='{key}']")
            if stream_node is not None:
                telemetria['status'] = 'En Directo'
                bw_in = int(stream_node.find("bw_in").text)
                telemetria['bitrate'] = f"{round(bw_in / 1024)} kbps"
                # Nginx RTMP no siempre da FPS en el stat básico, pero el bitrate confirma señal
    except Exception:
        telemetria['status'] = 'Servidor en espera de señal'

    return render_template('monitor.html', evento=evento, stats=telemetria)


@app.route('/api/stats/<key>')
def proxy_stats(key):
    if 'user_id' not in session: 
        return {"error": "No autorizado"}, 401
    
    # 1. Buscamos el evento para tener la IP real de la base de datos
    evento = model.obtener_evento_por_key(key)
    if not evento or not evento.get('vm_ip'):
        return {"error": "Servidor sin IP"}, 404

    # 2. Consultamos a la VM (desde el servidor, sin problemas de Mixed Content)
    url_stats = f"http://{evento['vm_ip']}/stat"
    try:
        respuesta = requests.get(url_stats, timeout=3)
        # Devolvemos el XML tal cual a nuestro Dashboard
        return (respuesta.content, 200, {'Content-Type': 'text/xml'})
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/cerrar_stream/<key>', methods=['POST'])
def cerrar_stream(key):
    if 'user_id' not in session: 
        return {"error": "No autorizado"}, 401
    
    print(f"Interrupción solicitada para: {key}")
    
    # Llamamos al método que acabamos de crear/modificar en models.py
    exito = model.finalizar_evento(key)
    
    if exito:
        return {"status": "success"}, 200
    else:
        # Si llega aquí, es el Error 500 que viste antes
        return {"status": "error", "message": "No se pudo actualizar Firestore"}, 500

@app.route('/monitor/<key>')
def monitor(key):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # Usamos 'model' (que es el nombre que definiste arriba)
    evento = model.obtener_evento_por_key(key) 
    
    if not evento: return "Evento no encontrado", 404
    ip_servidor = evento.get('vm_ip') or evento.get('ip_servidor') or "0.0.0.0"
    # Pasamos el objeto evento y extraemos la ip para la variable vm_ip
    return render_template('monitor.html', evento=evento, vm_ip=ip_servidor)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)