from flask import Flask, request, jsonify, Response, stream_with_context
import subprocess
import os
import re
import json
import time
import uuid
import threading
from datetime import datetime
import platform

app = Flask(__name__, static_folder='.', template_folder='.')

# Almacenamiento de descargas activas
downloads = {}
downloads_lock = threading.Lock()

class DownloadManager:
    def __init__(self):
        self.downloads = {}
        self.lock = threading.Lock()
    
    def add_download(self, url):
        download_id = str(uuid.uuid4())[:8]
        with self.lock:
            self.downloads[download_id] = {
                'id': download_id,
                'url': url,
                'status': 'iniciando',
                'file_name': 'Desconocido',
                'total_size': '0 MB',
                'downloaded': '0 MB',
                'percent': 0,
                'speed': '0 KB/s',
                'start_time': datetime.now().isoformat(),
                'completed': False,
                'error': None,
                'output': [],
                'paused': False,
                'connection_error': False,
                'pid': None,
                'retry_count': 0,
                'max_retries': 10,
                'last_update': datetime.now().isoformat()
            }
        return download_id
    
    def update_download(self, download_id, data):
        with self.lock:
            if download_id in self.downloads:
                self.downloads[download_id].update(data)
                self.downloads[download_id]['last_update'] = datetime.now().isoformat()
    
    def get_download(self, download_id):
        with self.lock:
            return self.downloads.get(download_id)
    
    def get_all_downloads(self):
        with self.lock:
            result = []
            for d in self.downloads.values():
                clean_d = {k: v for k, v in d.items() if k != 'process'}
                result.append(clean_d)
            return result
    
    def remove_download(self, download_id):
        with self.lock:
            if download_id in self.downloads:
                del self.downloads[download_id]
                return True
        return False
    
    def increment_retry(self, download_id):
        with self.lock:
            if download_id in self.downloads:
                self.downloads[download_id]['retry_count'] = self.downloads[download_id].get('retry_count', 0) + 1
                return self.downloads[download_id]['retry_count']
        return 0

manager = DownloadManager()
download_threads = {}

def get_bitzero_path():
    """Usar el binario compilado bitzero.so"""
    import os
    
    # Ruta EXACTA donde está el binario
    bin_path = "/data/data/com.termux/files/home/Downloader_Web/bitzero.so"
    
    if os.path.exists(bin_path):
        print(f"🔍 Usando binario: {bin_path}", flush=True)
        return ["python", "-c", "import sys; sys.path.insert(0, '/data/data/com.termux/files/home/Downloader_Web'); import bitzero"]
    
    # Si no está, buscar en otra ubicación
    bin_path2 = "/data/data/com.termux/files/home/Downloader_Web/bitzero.so"
    if os.path.exists(bin_path2):
        print(f"🔍 Usando binario: {bin_path2}", flush=True)
        return ["python", "-c", "import sys; sys.path.insert(0, '/data/data/com.termux/files/home/Downloader_Web'); import bitzero"]
    
    print("❌ Binario no encontrado", flush=True)
    return ["python", "-c", 'print("ERROR: binario no encontrado"); exit(1)']

@app.route('/')
def index():
    return open('index.html', 'r', encoding='utf-8').read()

@app.route('/descargas')
def descargas():
    return open('descargas.html', 'r', encoding='utf-8').read()

@app.route('/api/descargas', methods=['GET'])
def get_descargas():
    return jsonify(manager.get_all_downloads())

@app.route('/api/descargas/<download_id>', methods=['GET'])
def get_descarga(download_id):
    download = manager.get_download(download_id)
    if download:
        clean_d = {k: v for k, v in download.items() if k != 'process'}
        return jsonify(clean_d)
    return jsonify({"error": "Descarga no encontrada"}), 404

@app.route('/api/descargas/<download_id>', methods=['DELETE'])
def delete_descarga(download_id):
    download = manager.get_download(download_id)
    if download and download.get('pid'):
        try:
            os.kill(download['pid'], 9)
        except:
            pass
    if manager.remove_download(download_id):
        return jsonify({"success": True})
    return jsonify({"error": "Descarga no encontrada"}), 404

@app.route('/descargar', methods=['POST'])
def iniciar_descarga():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "No URL"}), 400
    
    if url.startswith('bitzero '):
        url = url.replace('bitzero ', '', 1)
    
    state_file = "/storage/emulated/0/Download/BitZero/.bitzero_state.json"
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
            print("🧹 Estado anterior eliminado para descarga nueva", flush=True)
        except Exception as e:
            print(f"⚠️ No se pudo eliminar estado: {e}", flush=True)
    
    download_id = manager.add_download(url)
    
    thread = threading.Thread(target=ejecutar_descarga_con_reintentos, args=(download_id, url))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "download_id": download_id,
        "message": "Descarga iniciada"
    })

def ejecutar_descarga_con_reintentos(download_id, url):
    max_retries = 10
    retry_count = 0
    wait_time = 5
    
    while retry_count < max_retries:
        download = manager.get_download(download_id)
        if not download:
            break
        
        if download.get('completed', False):
            break
        
        if download.get('status') == 'error' and not download.get('connection_error', False):
            break
        
        exit_code, was_paused = ejecutar_descarga(download_id, url)
        
        if exit_code == 0 and not was_paused:
            break
        
        if was_paused:
            retry_count += 1
            manager.update_download(download_id, {
                'status': 'reconectando',
                'error': f'Reintentando ({retry_count}/{max_retries})...',
                'retry_count': retry_count
            })
            
            wait = min(wait_time * (1.5 ** retry_count), 60)
            print(f"🔄 Reintento {retry_count}/{max_retries} en {wait:.1f}s", flush=True)
            time.sleep(wait)
            
            state_file = "/storage/emulated/0/Download/BitZero/.bitzero_state.json"
            if os.path.exists(state_file):
                print("📂 Estado encontrado, reanudando...", flush=True)
            else:
                print("⚠️ No se encontró estado, iniciando desde cero...", flush=True)
        else:
            if exit_code != 0:
                manager.update_download(download_id, {
                    'status': 'error',
                    'error': f'Error en la descarga (código {exit_code})'
                })
            break
    
    download = manager.get_download(download_id)
    if download and not download.get('completed', False):
        manager.update_download(download_id, {
            'status': 'error',
            'error': f'No se pudo completar después de {max_retries} reintentos'
        })

def ejecutar_descarga(download_id, url):
    was_paused = False
    
    try:
        manager.update_download(download_id, {'status': 'conectando'})
        
        state_file = "/storage/emulated/0/Download/BitZero/.bitzero_state.json"
        
        cmd = get_bitzero_path()
        cmd.append(url)
        print(f"🚀 Ejecutando: {cmd}", flush=True)
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0,
            universal_newlines=True,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        manager.update_download(download_id, {'pid': process.pid})
        
        file_name = "Desconocido"
        total_size = "0 MB"
        downloaded = "0 MB"
        percent = 0
        speed = "0 KB/s"
        completed = False
        last_downloaded = "0 MB"
        paused = False
        connection_error = False
        
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
            
            with manager.lock:
                if download_id in manager.downloads:
                    manager.downloads[download_id]['output'].append(line)
                    if len(manager.downloads[download_id]['output']) > 100:
                        manager.downloads[download_id]['output'] = manager.downloads[download_id]['output'][-100:]
            
            if "pausada por" in line.lower() or "sin datos por" in line.lower() or "pausada por pérdida" in line.lower():
                paused = True
                was_paused = True
                connection_error = True
                manager.update_download(download_id, {
                    'status': 'pausado',
                    'paused': True,
                    'connection_error': True,
                    'error': 'Pérdida de conexión - Reintentando...'
                })
                continue
            
            if "reanudando" in line.lower() or "descarga incompleta detectada" in line.lower():
                paused = False
                connection_error = False
                manager.update_download(download_id, {
                    'status': 'descargando',
                    'paused': False,
                    'connection_error': False,
                    'error': None
                })
                continue
            
            if "error de conexión" in line.lower() or "timeout" in line.lower():
                connection_error = True
                was_paused = True
                manager.update_download(download_id, {
                    'status': 'error_conexion',
                    'error': 'Error de conexión - Reintentando...',
                    'connection_error': True
                })
                continue
            
            if "Descargando:" in line:
                match = re.search(r'Descargando: (.+?) \| Tamaño:', line)
                if match:
                    file_name = match.group(1)
                    manager.update_download(download_id, {'file_name': file_name})
            
            if "Tamaño:" in line:
                match = re.search(r'Tamaño: (.+)', line)
                if match:
                    total_size = match.group(1).strip()
                    manager.update_download(download_id, {'total_size': total_size})
            
            if "Descargando..." in line:
                match = re.search(r'Descargando\.\.\. (\d+\.?\d*)% \| (.+)', line)
                if match:
                    percent = float(match.group(1))
                    percent = min(percent, 100.0)
                    downloaded = match.group(2).strip()
                    last_downloaded = downloaded
                    if not connection_error:
                        status = 'pausado' if paused else 'descargando'
                        manager.update_download(download_id, {
                            'percent': percent,
                            'downloaded': downloaded,
                            'status': status,
                            'paused': paused,
                            'connection_error': connection_error
                        })
            
            if "SPEED:" in line:
                try:
                    speed_bytes = float(line.replace("SPEED:", "").strip())
                    if speed_bytes > 1024*1024:
                        speed = f"{speed_bytes/(1024*1024):.1f} MB/s"
                    elif speed_bytes > 1024:
                        speed = f"{speed_bytes/1024:.1f} KB/s"
                    else:
                        speed = f"{speed_bytes:.0f} B/s"
                    if not paused and not connection_error:
                        manager.update_download(download_id, {
                            'speed': speed,
                            'downloaded': last_downloaded,
                            'percent': percent
                        })
                except:
                    pass
            
            if "GUARDADO:" in line:
                completed = True
                percent = 100
                match = re.search(r'GUARDADO: .+/(.+)', line)
                if match:
                    file_name = match.group(1)
                
                file_path = os.path.join("/storage/emulated/0/Download/BitZero", file_name)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    manager.update_download(download_id, {
                        'completed': True,
                        'percent': 100,
                        'file_name': file_name,
                        'status': 'completado',
                        'downloaded': sizeof_fmt(file_size),
                        'paused': False,
                        'connection_error': False,
                        'error': None
                    })
                else:
                    completed = False
                    was_paused = True
                    manager.update_download(download_id, {
                        'status': 'pausado',
                        'error': 'Archivo no encontrado después de guardar',
                        'paused': True
                    })
                    continue
        
        process.wait()
        
        if not completed and not paused:
            if connection_error:
                was_paused = True
                manager.update_download(download_id, {
                    'status': 'pausado',
                    'error': 'Error de conexión - Reintentando...',
                    'paused': True,
                    'connection_error': True
                })
            elif os.path.exists(state_file):
                was_paused = True
                manager.update_download(download_id, {
                    'status': 'pausado',
                    'error': 'Descarga pausada - Reanudando...',
                    'paused': True
                })
            else:
                manager.update_download(download_id, {
                    'completed': True,
                    'percent': 100,
                    'status': 'completado'
                })
        
        if os.path.exists(state_file):
            was_paused = True
            
        return process.returncode, was_paused
            
    except Exception as e:
        manager.update_download(download_id, {
            'status': 'error',
            'error': str(e)
        })
        return 1, False

def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.2f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.2f%s%s" % (num, 'Yi', suffix)

@app.route('/stream/<download_id>')
def stream_descarga(download_id):
    def generate():
        last_status = {}
        while True:
            download = manager.get_download(download_id)
            if not download:
                yield f"data: {json.dumps({'error': 'Descarga no encontrada'})}\n\n"
                break
            
            clean_data = {k: v for k, v in download.items() if k != 'process'}
            current_data = {
                'id': clean_data['id'],
                'file_name': clean_data['file_name'],
                'total_size': clean_data['total_size'],
                'downloaded': clean_data['downloaded'],
                'percent': clean_data['percent'],
                'speed': clean_data['speed'],
                'status': clean_data['status'],
                'completed': clean_data['completed'],
                'error': clean_data.get('error'),
                'paused': clean_data.get('paused', False),
                'connection_error': clean_data.get('connection_error', False),
                'retry_count': clean_data.get('retry_count', 0)
            }
            
            if current_data != last_status:
                yield f"data: {json.dumps(current_data)}\n\n"
                last_status = current_data.copy()
            
            if clean_data['completed'] or clean_data['status'] == 'error':
                break
            
            time.sleep(0.5)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    print("🚀 Servidor corriendo en http://127.0.0.1:5000")
    print("📊 Panel de descargas: http://127.0.0.1:5000/descargas")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
