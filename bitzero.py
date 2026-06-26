import requests
from bs4 import BeautifulSoup
import sys
import os
import random
import time
import urllib3
import base64
import json
import signal
import hashlib
import hmac
import zlib
import struct
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuración ──────────────────────────────────────────────
CONNECTION_TIMEOUT = 300
MAX_RETRIES = 5
CHECK_INTERVAL = 2.0
BACKOFF_BASE = 5
BACKOFF_MAX = 60

# ── Contraseñas para BZ# ──────────────────────────────────────
LINK_PASSWORD = "IcIx++r&7q8a7XjhJz^btzw^z"
LINK_SECRET   = "Xk9#mP2@qL5!vR7$nT4^wJ8&cF6*eB3"

_B62_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

# ── Globales ───────────────────────────────────────────────────
named = "INDEFINIDO"
STATE_FILE = "/storage/emulated/0/Download/BitZero/.bitzero_state.json"
DIRECTORY = "/storage/emulated/0/Download/BitZero"
stop_flag = False
connection_error = False
last_successful_chunk = 0
download_retries = 0
retry_backoff = 0

speed_tracker = {"bytes": 0, "time": time.time()}

# ── Utilidades ─────────────────────────────────────────────────

def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.2f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.2f%s%s" % (num, 'Yi', suffix)

def _b62_decode(text: str) -> bytes:
    n = 0
    for c in text:
        n = n * 62 + _B62_CHARS.index(c)
    result = []
    while n:
        result.append(n & 255)
        n >>= 8
    for c in text:
        if c == _B62_CHARS[0]:
            result.append(0)
        else:
            break
    return bytes(reversed(result))

def _derive_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])

def _zx_decrypt(data: bytes) -> bytes:
    master  = hashlib.sha256(LINK_PASSWORD.encode()).digest()
    enc_key = master[:16]
    mac_key = master[16:]
    body, mac_recv = data[:-32], data[-32:]
    mac_calc = hmac.new(mac_key, body, hashlib.sha256).digest()
    if not hmac.compare_digest(mac_recv, mac_calc):
        raise ValueError("MAC inválido")
    nonce      = body[:16]
    length     = int.from_bytes(body[16:20], "big")
    ciphertext = body[20:20 + length]
    ks         = _derive_keystream(enc_key, nonce, length)
    compressed = bytes(a ^ b for a, b in zip(ciphertext, ks))
    return zlib.decompress(compressed)

def parse_bz_link(enlace: str) -> dict:
    partes = enlace.split("#", 2)
    if len(partes) != 3 or partes[0] != "BZ":
        raise ValueError("Formato inválido")
    alias, token_str = partes[1], partes[2]
    encrypted = _b62_decode(token_str)
    payload   = _zx_decrypt(encrypted).decode("utf-8")
    campos = payload.split("\x1f")
    if len(campos) != 11:
        raise ValueError(f"Payload corrupto ({len(campos)} campos)")
    link_pass, secret, secret_check, host, user, password, repo, bz_flag, total_size, ids_joined, filename = campos
    if link_pass != LINK_PASSWORD:
        raise ValueError("LINK_PASSWORD no coincide")
    expected_check = hashlib.sha256(secret.encode()).hexdigest()[:16]
    if not hmac.compare_digest(secret_check, expected_check):
        raise ValueError("Verificación de contraseña fallida")
    host_clean = host.rstrip("/")
    ids = [i.strip() for i in ids_joined.split("-") if i.strip()]
    download_urls = [
        f"{host_clean}/$$$call$$$/api/file/file-api/download-file"
        f"?submissionFileId={fid}&submissionId={repo}&stageId=1"
        for fid in ids
    ]
    return {
        "named":         filename,
        "host":          host_clean,
        "username":      user,
        "password":      password,
        "repo":          repo,
        "bitzero":       bz_flag,
        "size":          total_size,
        "download_urls": download_urls,
        "url_original":  enlace,
    }

# ── Estado ─────────────────────────────────────────────────────

def save_state(state: dict):
    os.makedirs(DIRECTORY, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_state() -> dict | None:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

# ── Monitoreo ──────────────────────────────────────────────────

def check_connection_timeout():
    global connection_error, stop_flag, last_successful_chunk, download_retries, retry_backoff
    current_time = time.time()
    time_since_last_chunk = current_time - last_successful_chunk
    if time_since_last_chunk < CONNECTION_TIMEOUT:
        if connection_error:
            connection_error = False
            download_retries = 0
            retry_backoff = 0
            print("✅ Conexión recuperada", flush=True)
        return False
    if not connection_error:
        connection_error = True
        download_retries += 1
        retry_backoff = min(BACKOFF_BASE * (1.5 ** download_retries), BACKOFF_MAX)
        print(f"⚠️ Sin datos por {time_since_last_chunk:.0f}s. (Intento {download_retries}/{MAX_RETRIES})", flush=True)
        print(f"⏳ Esperando {retry_backoff:.0f}s", flush=True)
        if download_retries >= MAX_RETRIES:
            print("❌ Demasiados reintentos", flush=True)
            return True
        return False
    if time_since_last_chunk > CONNECTION_TIMEOUT + retry_backoff:
        print(f"🔄 Reintentando después de {time_since_last_chunk:.0f}s", flush=True)
        connection_error = False
        return True
    return False

def update_speed(bytes_added):
    global speed_tracker, last_successful_chunk
    current_time = time.time()
    speed_tracker["bytes"] += bytes_added
    last_successful_chunk = current_time
    if current_time - speed_tracker["time"] >= 1.0:
        bytes_per_sec = speed_tracker["bytes"] / (current_time - speed_tracker["time"])
        if bytes_per_sec > 0:
            print(f"SPEED:{bytes_per_sec}", flush=True)
        speed_tracker["bytes"] = 0
        speed_tracker["time"] = current_time

# ── Login ──────────────────────────────────────────────────────

def do_login(host, username, password):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    up = requests.Session()
    try:
        getToken = up.get(host + "/login", headers=headers, verify=False, timeout=30)
        token_input = BeautifulSoup(getToken.text, "html.parser").find('input', {'name': 'csrfToken'})
        if token_input is None:
            print("Error: No se encontró token CSRF", flush=True)
            sys.exit(1)
        login_data = {
            "password": password, "remember": 1, "source": "",
            "username": username, "csrfToken": token_input.get('value', '')
        }
        resp = up.post(f"{host}/login/signIn", data=login_data, headers=headers, verify=False, timeout=30)
        if resp.status_code != 200:
            print("Error en el login", flush=True)
            sys.exit(1)
        print("✅ Login exitoso", flush=True)
        return up
    except Exception as e:
        print(f"Error en login: {e}", flush=True)
        sys.exit(1)

# ── Descarga de fragmento con acumulación global ─────────────────

def download_chunk(url, name, up, total_size, resume_bytes=0, retry_count=0, meta=None, i=0, files=None, random_id=0, totaldown_ref=None):
    """
    Descarga un fragmento y actualiza el progreso global acumulado.
    totaldown_ref es una lista [totaldown_actual] para modificarlo dentro de la función.
    """
    global stop_flag, connection_error, last_successful_chunk, download_retries, retry_backoff

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }

    # Si existe el archivo, obtener su tamaño actual
    if os.path.exists(name):
        current_size = os.path.getsize(name)
        if resume_bytes == 0:
            resume_bytes = current_size
        elif current_size != resume_bytes:
            resume_bytes = current_size
    else:
        current_size = 0

    if resume_bytes > 0:
        headers["Range"] = f"bytes={resume_bytes}-"

    try:
        print(f"📡 Conectando... (reintento {retry_count+1})", flush=True)

        with up.get(url, headers=headers, stream=True, verify=False, timeout=(30, 120)) as r:
            if r.status_code not in (200, 206):
                print(f"⚠️ Código de estado: {r.status_code}", flush=True)
                r.raise_for_status()

            connection_error = False
            download_retries = 0
            retry_backoff = 0
            last_successful_chunk = time.time()

            content_length = r.headers.get('Content-Length')
            if content_length:
                chunk_expected = int(content_length)  # Tamaño de este fragmento
                print(f"📦 Tamaño del fragmento: {sizeof_fmt(chunk_expected)}", flush=True)
            else:
                chunk_expected = None

            with open(name, mode="ab" if resume_bytes > 0 else "wb") as f:
                bytes_recibidos = resume_bytes
                last_progress_report = time.time()
                bytes_since_last_report = 0
                chunk_count = 0

                for chunk in r.iter_content(chunk_size=32768):
                    chunk_count += 1

                    if chunk_count % 10 == 0:
                        if check_connection_timeout():
                            if meta and i is not None and files is not None:
                                save_state({
                                    "url_original": meta.get("url_original", ""),
                                    "meta": meta,
                                    "current_index": i,
                                    "files_done": files,
                                    "resume_bytes": os.path.getsize(name) if os.path.exists(name) else 0,
                                    "random_id": random_id,
                                    "totaldown": bytes_recibidos,
                                    "retry_count": download_retries + 1
                                })
                            print("⏳ Procesando parte...", flush=True)
                            sys.exit(0)

                    if stop_flag:
                        return None

                    if chunk:
                        connection_error = False
                        download_retries = 0
                        retry_backoff = 0
                        last_successful_chunk = time.time()

                        chunk_size_bytes = len(chunk)
                        bytes_recibidos += chunk_size_bytes
                        f.write(chunk)
                        bytes_since_last_report += chunk_size_bytes

                        # Actualizar totaldown_ref sumando los bytes nuevos al acumulado global
                        if totaldown_ref is not None:
                            totaldown_ref[0] += chunk_size_bytes

                        # Calcular porcentaje global
                        total_int = int(total_size)
                        if total_int > 0:
                            # Usamos el acumulado global para el porcentaje
                            porcentaje = min((totaldown_ref[0] / total_int) * 100, 100)
                        else:
                            porcentaje = 0

                        current_time = time.time()
                        if current_time - last_progress_report >= 1.0 or bytes_since_last_report >= 1024 * 1024:
                            # Calcular progreso total del archivo
                            total_int = int(total_size)
                            if total_int > 0:
                                porcentaje_total = min((totaldown_ref[0] / total_int) * 100, 100)
                            else:
                                porcentaje_total = 0
                            descargado = totaldown_ref[0] if totaldown_ref is not None else bytes_recibidos
                            print(f"Descargando... {porcentaje_total:.1f}% | {sizeof_fmt(descargado)} / {sizeof_fmt(total_int)}", flush=True)
                            last_progress_report = current_time
                            bytes_since_last_report = 0

                        update_speed(chunk_size_bytes)

                # Verificar integridad del fragmento
                final_size = os.path.getsize(name)
                if chunk_expected is not None:
                    # Si se reanudó, el tamaño final debe ser resume_bytes + chunk_expected
                    expected_final = resume_bytes + chunk_expected
                    margen = max(1024 * 10, chunk_expected * 0.01)
                    if abs(final_size - expected_final) > margen:
                        print(f"⚠️ Tamaño incorrecto del fragmento: {sizeof_fmt(final_size)} vs {sizeof_fmt(expected_final)}", flush=True)
                        if meta and i is not None and files is not None:
                            save_state({
                                "url_original": meta.get("url_original", ""),
                                "meta": meta,
                                "current_index": i,
                                "files_done": files,
                                "resume_bytes": final_size,
                                "random_id": random_id,
                                "totaldown": final_size,
                                "retry_count": download_retries + 1
                            })
                        print("⏳ Avanzando...", flush=True)
                        sys.exit(0)

                # Actualizar totaldown_ref con el total acumulado (ya se fue sumando)
                # Pero si no se sumó por alguna razón, lo forzamos
                if totaldown_ref is not None:
                    # totaldown_ref[0] ya contiene el acumulado global
                    pass

                return final_size

    except Exception as e:
        print(f"ERROR en descarga: {str(e)}", flush=True)
        if os.path.exists(name):
            cur_bytes = os.path.getsize(name)
            if meta and i is not None and files is not None:
                save_state({
                    "url_original": meta.get("url_original", ""),
                    "meta": meta,
                    "current_index": i,
                    "files_done": files,
                    "resume_bytes": cur_bytes,
                    "random_id": random_id,
                    "totaldown": cur_bytes,
                    "retry_count": download_retries + 1
                })
        if "Connection" in str(e) or "Timeout" in str(e) or "reset" in str(e).lower():
            print("⏸️ Descarga pausada por error de red.", flush=True)
            sys.exit(0)
        else:
            stop_flag = True
            return None

# ── Parseo de URL ─────────────────────────────────────────────

def parse_bitzero_url(url):
    try:
        parts = url.split('/')
        named = parts[-1]
        surl = parts[-4]
        key = parts[-2].split('-')
        bitzero = parts[-3]
        k = parts[-5]
        host = base64.b64decode(key[0].replace("@","==").replace("#","=")).decode()
        uname = base64.b64decode(key[1].replace("@","==").replace("#","=")).decode()
        passwd = base64.b64decode(key[2].replace("@","==").replace("#","=")).decode()
        repo = base64.b64decode(key[3].replace("@","==").replace("#","=")).decode()
        sub_urls = surl.split("-") if "-" in surl else [surl]
        download_urls = [
            f"{host}/$$$call$$$/api/file/file-api/download-file?submissionFileId={s}&submissionId={repo}&stageId=1"
            for s in sub_urls
        ]
        return {
            "named": named, "host": host, "username": uname,
            "password": passwd, "repo": repo, "bitzero": bitzero,
            "size": k.split("-")[0], "download_urls": download_urls,
            "url_original": url
        }
    except Exception as e:
        print(f"Error parseando URL: {e}", flush=True)
        return None

# ── Procesamiento principal ───────────────────────────────────

def process_url(meta: dict, resume_state=None):
    global stop_flag, connection_error, last_successful_chunk, download_retries, retry_backoff

    print(f"📥 Iniciando descarga de: {meta['named']}", flush=True)

    named = meta["named"]
    host = meta["host"]
    username = meta["username"]
    password = meta["password"]
    bitzero = meta["bitzero"]
    size = meta["size"]
    download_urls = meta["download_urls"]

    start_index = resume_state["current_index"] if resume_state else 0
    files_done = resume_state["files_done"] if resume_state else []
    resume_bytes = resume_state["resume_bytes"] if resume_state else 0
    random_id = resume_state["random_id"] if resume_state else random.randint(1000, 9999)
    totaldown_local = resume_state["totaldown"] if resume_state else 0
    download_retries = resume_state.get("retry_count", 0) if resume_state else 0
    retry_backoff = 0
    last_successful_chunk = time.time()

    print(f"📄 Archivo: {named} | Tamaño: {sizeof_fmt(int(size))}", flush=True)
    print(f"Descargando: {named} | Tamaño: {sizeof_fmt(int(size))}", flush=True)

    # Login
    up = None
    for intento in range(3):
        try:
            up = do_login(host, username, password)
            break
        except Exception as e:
            print(f"⚠️ Intento de login {intento+1} falló: {e}", flush=True)
            time.sleep(2)
    if up is None:
        print("❌ No se pudo iniciar sesión después de 3 intentos", flush=True)
        sys.exit(1)

    files = list(files_done)

    for i, dl_url in enumerate(download_urls):
        if i < start_index:
            continue

        part_name = f"index_{random_id}_{i}"
        resume_b = resume_bytes if i == start_index else 0

        # Si el archivo parcial existe y es mayor que el total, reiniciar
        if os.path.exists(part_name):
            cur_size = os.path.getsize(part_name)
            if cur_size > int(size):
                print(f"⚠️ Archivo parcial ({sizeof_fmt(cur_size)}) mayor que el total, reiniciando", flush=True)
                os.remove(part_name)
                resume_b = 0
                totaldown_local = 0
            elif resume_b == 0:
                resume_b = cur_size
                totaldown_local = cur_size

        # Guardar estado
        save_state({
            "url_original": meta.get("url_original", ""),
            "meta": meta,
            "current_index": i,
            "files_done": files,
            "resume_bytes": os.path.getsize(part_name) if os.path.exists(part_name) else 0,
            "random_id": random_id,
            "totaldown": totaldown_local,
            "retry_count": download_retries
        })

        print(f"📦 Parte {i+1}/{len(download_urls)}", flush=True)

        connection_error = False
        last_successful_chunk = time.time()

        # totaldown_ref mantiene el acumulado global
        totaldown_ref = [totaldown_local]

        # Descargar el fragmento
        result_bytes = download_chunk(
            dl_url, part_name, up, size, resume_b,
            retry_count=download_retries,
            meta=meta, i=i, files=files, random_id=random_id,
            totaldown_ref=totaldown_ref
        )

        if result_bytes is None:
            sys.exit(0)

        # Actualizar totaldown_local con el acumulado global
        totaldown_local = totaldown_ref[0]

        files.append(part_name)
        resume_bytes = 0

    # Ensamblar archivo final
    print("\n📦 Finalizando descarga...", flush=True)

    out_path = os.path.join(DIRECTORY, named)

    missing_files = [f for f in files if not os.path.exists(f)]
    if missing_files:
        print(f"❌ Faltan archivos: {missing_files}", flush=True)
        sys.exit(1)

    SPYPNG_SIZE = 69

    with open(out_path, "wb") as file:
        for f in files:
            if os.path.exists(f):
                try:
                    if bitzero == '1':
                        data = open(f, "rb").read()
                        if data[:4] == b'\x89PNG':
                            data = data[SPYPNG_SIZE:]
                        file.write(data)
                    elif bitzero == '2':
                        content = open(f, "r").read()
                        content = content.replace('<!DOCTYPE html>\n<html lang="es">\n<bytes>', '').replace('</bytes></html>', '')
                        file.write(base64.b64decode(content))
                    else:
                        file.write(open(f, "rb").read())
                    os.unlink(f)
                except Exception as e:
                    print(f"❌ Error ensamblando {f}: {e}", flush=True)
                    sys.exit(1)

    # Verificar tamaño final
    if int(size) > 0:
        final_size = os.path.getsize(out_path)
        margen = max(1024 * 100, int(size) * 0.01)
        if abs(final_size - int(size)) > margen:
            print(f"⚠️ Archivo final tamaño incorrecto: {sizeof_fmt(final_size)} vs {sizeof_fmt(int(size))}", flush=True)
            print("❌ La descarga puede estar corrupta", flush=True)
        else:
            print(f"✅ Verificación de integridad: OK ({sizeof_fmt(final_size)})", flush=True)

    clear_state()
    print(f"✅ GUARDADO: {out_path}", flush=True)
    print(f"📁 Carpeta: {DIRECTORY}", flush=True)
    print(f"📄 Archivo: {named}", flush=True)
    print(f"📊 Tamaño: {sizeof_fmt(os.path.getsize(out_path))}", flush=True)

# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DIRECTORY):
        try:
            os.makedirs(DIRECTORY, exist_ok=True)
            print(f"📁 Carpeta creada: {DIRECTORY}", flush=True)
        except Exception as e:
            print(f"⚠️ No se pudo crear la carpeta: {e}", flush=True)
            DIRECTORY = os.path.join(os.getcwd(), "downloads")
            os.makedirs(DIRECTORY, exist_ok=True)
            print(f"📁 Usando carpeta alternativa: {DIRECTORY}", flush=True)

    state = load_state()

    if state:
        print("🔄 Descarga incompleta detectada. Reanudando...", flush=True)
        print(f"📊 Progreso guardado: {state.get('totaldown', 0)} bytes", flush=True)
        process_url(state["meta"], resume_state=state)
    else:
        url = ""

        if len(sys.argv) > 1:
            url = sys.argv[1].strip()

        LINK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bz_link.txt")
        if not url and os.path.exists(LINK_FILE):
            try:
                with open(LINK_FILE, "r", encoding="utf-8") as _lf:
                    url = _lf.read().strip()
                if url:
                    print(f"📎 Enlace leído desde bz_link.txt ({len(url)} chars)", flush=True)
                    os.remove(LINK_FILE)
            except Exception as _e:
                print(f"⚠️ No se pudo leer bz_link.txt: {_e}", flush=True)

        if not url:
            print(" • Pega el enlace y presiona Enter (o guárdalo en bz_link.txt):", flush=True)
            url = sys.stdin.readline().strip()

        if url:
            stop_flag = False
            download_retries = 0
            retry_backoff = 0
            last_successful_chunk = time.time()

            if url.startswith("BZ#"):
                try:
                    meta = parse_bz_link(url)
                    print(f"🔓 Enlace BZ# decodificado: {meta['named']}", flush=True)
                except Exception as e:
                    print(f"❌ Error al descifrar enlace BZ#: {e}", flush=True)
                    sys.exit(1)
            else:
                meta = parse_bitzero_url(url)
                if meta:
                    meta["url_original"] = url
                else:
                    print("❌ No se pudo procesar el enlace", flush=True)
                    sys.exit(1)

            process_url(meta)