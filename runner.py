import sys
import os
import time

if len(sys.argv) < 2:
    print("❌ No se proporcionó URL", flush=True)
    sys.exit(1)

url = sys.argv[1]

# Buscar el módulo en PREFIX/lib primero
prefix_lib = os.path.expandvars("$PREFIX/lib")
if prefix_lib not in sys.path:
    sys.path.insert(0, prefix_lib)

print(f"📂 Buscando módulo bitzero en: {prefix_lib}", flush=True)

try:
    import bitzero as bz
    print(f"✅ Módulo bitzero importado correctamente", flush=True)
except ImportError as e:
    print(f"❌ Error al importar bitzero: {e}", flush=True)
    sys.exit(1)

bz.stop_flag = False
bz.download_retries = 0
bz.retry_backoff = 0
bz.last_successful_chunk = time.time()

state = bz.load_state()

if state:
    print("🔄 Descarga incompleta detectada. Reanudando...", flush=True)
    bz.process_url(state["meta"], resume_state=state)
else:
    if url.startswith("BZ#"):
        try:
            meta = bz.parse_bz_link(url)
            print(f"🔓 Enlace BZ# decodificado: {meta['named']}", flush=True)
        except Exception as e:
            print(f"❌ Error al descifrar enlace BZ#: {e}", flush=True)
            sys.exit(1)
    else:
        meta = bz.parse_bitzero_url(url)
        if not meta:
            print("❌ No se pudo procesar el enlace", flush=True)
            sys.exit(1)

    bz.process_url(meta)