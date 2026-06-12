import os
import sys
import time
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# --- Paleta de Colores Neón ---
C = "\033[1;36m"  # Cyan Neón
R = "\033[1;31m"  # Rojo Neón
B = "\033[1;34m"  # Azul Eléctrico
G = "\033[1;32m"  # Verde Éxito
W = "\033[1;37m"  # Blanco Brillante
Y = "\033[1;33m"  # Amarillo
RESET = "\033[0m"

# Configuración por defecto
CONFIG = {"workers": 50, "timeout": 5}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def draw_header():
    clear_screen()
    print(f"{C}╔{'═'*45}╗{RESET}")
    print(f"{C}║{W}   ██▀███   ▄▄▄       ██▓ ███▄ ▄███▓ ██▓ ███▄ ║{RESET}")
    print(f"{C}║{W}  ▓██ ▒ ██▒▒████▄    ▓██▒▓██▒▀█▀ ██▒▓██▒▒██▀  ║{RESET}")
    print(f"{C}║{W}  ▓██ ░▄█ ▒▒██  ▀█▄  ▒██▒▓██    ▓██░▒██▒░██   ║{RESET}")
    print(f"{C}║{C}   RAIMIN GEN • {R}PREMIUM IPTV CHECKER v3.0{C}    ║{RESET}")
    print(f"{C}╚{'═'*45}╝{RESET}")

def get_menu_option(prompt, options):
    while True:
        choice = input(f"{C} {prompt} {W}").strip()
        if not choice and "" in options:
            return options[""]
        if choice in options:
            return options[choice]
        print(f"{R} [!] Opción no válida. Intente de nuevo.{RESET}")

def pick_local_file():
    """Solicita la ruta de un archivo local y verifica que exista."""
    while True:
        path = input(f"{C} > Ruta completa del archivo .m3u: {W}").strip()
        if not path:
            return None
        if os.path.isfile(path) and path.lower().endswith('.m3u'):
            return path
        else:
            print(f"{R} [!] Archivo no encontrado o no es un .m3u válido.{RESET}")

def download_m3u(url):
    """Descarga el contenido de una URL. Retorna el texto o None en caso de error."""
    try:
        print(f"{Y} [i] Descargando lista...{RESET}")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"{R} [!] Error al descargar: {e}{RESET}")
        return None

def parse_m3u(content):
    """Parsea el contenido de un M3U y devuelve una lista de diccionarios {name, url, group}."""
    entries = []
    # Expresión regular para encontrar #EXTINF y la URL siguiente
    pattern = re.compile(r'#EXTINF:-?\d+.*?,(.*?)\n(http[^\s]+)', re.IGNORECASE)
    # Buscar también atributos de grupo: group-title="..."
    group_pattern = re.compile(r'group-title="(.*?)"', re.IGNORECASE)
    
    # Método línea por línea para ser más robusto
    lines = content.split('\n')
    current_name = None
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            # Extraer nombre y grupo
            name_match = re.search(r',\s*(.*)', line)
            if name_match:
                current_name = name_match.group(1).strip()
            else:
                current_name = "Unknown"
            # Buscar grupo
            group_match = group_pattern.search(line)
            group = group_match.group(1) if group_match else "General"
        elif line and not line.startswith('#') and current_name is not None:
            url = line
            entries.append({
                'name': current_name,
                'url': url,
                'group': group
            })
            current_name = None
    return entries

def check_stream(url, timeout=5):
    """Verifica si un stream responde. Retorna True y latencia en ms, o False y 0."""
    try:
        start = time.time()
        # Petición HEAD o GET parcial con timeout pequeño
        resp = requests.get(url, stream=True, timeout=timeout, headers={
            'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18'
        })
        # Leer un poco para forzar la respuesta del stream
        chunk = resp.raw.read(1024, decode_content=False)
        latency = (time.time() - start) * 1000
        resp.close()
        if resp.status_code == 200:
            return True, round(latency)
        else:
            return False, 0
    except:
        return False, 0

def print_progress_bar(iteration, total, prefix='', suffix='', length=30):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled = int(length * iteration // total)
    bar = '█' * filled + '░' * (length - filled)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if iteration == total:
        print()

def run_checker(entries, workers, timeout):
    """Ejecuta el verificador multihilo y muestra resultados."""
    total = len(entries)
    alive = 0
    dead = 0
    results = []
    print(f"\n{Y}[i] Iniciando verificación de {total} canales con {workers} hilos...{RESET}\n")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_entry = {executor.submit(check_stream, e['url'], timeout): e for e in entries}
        completed = 0
        for future in as_completed(future_to_entry):
            entry = future_to_entry[future]
            completed += 1
            is_alive, latency = future.result()
            status = f"{G}✓ VIVO{RESET}" if is_alive else f"{R}✗ MUERTO{RESET}"
            if is_alive:
                alive += 1
            else:
                dead += 1
            results.append((entry['name'], entry['url'], entry['group'], is_alive, latency))
            # Mostrar progreso
            print_progress_bar(completed, total, prefix=f"{C}Progreso{RESET}", suffix=f"{G}{alive} vivos{RESET} {R}{dead} muertos{RESET}")
    
    return results, alive, dead

def filter_by_category(entries, selection):
    """Filtra las entradas según la categoría seleccionada."""
    # Mapeo de números a palabras clave comunes en group-title
    mapping = {
        '1': ['live tv', 'tv', 'canais', 'entertainment', 'news', 'sports', 'documentary', 'kids'],
        '2': ['movie', 'cinema', 'pelicula', 'film'],
        '3': ['series', 'serie', 'tv show', 'shows']
    }
    if selection == '':
        return entries
    
    keywords = mapping.get(selection, [])
    filtered = []
    for e in entries:
        group_lower = e['group'].lower()
        if any(kw in group_lower for kw in keywords):
            filtered.append(e)
    return filtered

def main():
    while True:
        draw_header()
        
        # --- FASE 1: CONFIGURACIÓN DE RENDIMIENTO ---
        print(f"\n{B}[ STEP 1: RENDIMIENTO ]{RESET}")
        try:
            threads = input(f"{C} > Hilos (Recomendado 50): {W}").strip()
            CONFIG["workers"] = int(threads) if threads else 50
        except:
            CONFIG["workers"] = 50
        
        # --- FASE 2: CARGA DE FUENTE ---
        draw_header()
        print(f"\n{B}[ STEP 2: FUENTE DE DATOS ]{RESET}")
        print(f"{C} [1]{W} URL Remota (http/s)")
        print(f"{C} [2]{W} Archivo Local (.m3u)")
        
        op = get_menu_option("Seleccione origen:", {"1": "url", "2": "local"})
        
        source = None
        if op == "url":
            url = input(f"{C} > Ingrese URL: {W}").strip()
            if url:
                content = download_m3u(url)
                if content:
                    source = url  # Para mostrar nombre simbólico
        else:
            path = pick_local_file()
            if path:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    source = path
                except Exception as e:
                    print(f"{R} [!] Error al leer archivo: {e}{RESET}")
                    content = None
        
        if not source or not content:
            input(f"\n{R}[!] No se pudo obtener la lista. Presione Enter para reintentar...{RESET}")
            continue
        
        # Parsear entradas
        all_entries = parse_m3u(content)
        if not all_entries:
            print(f"{R}[!] No se encontraron canales en la lista.{RESET}")
            input(f"\n{R} Presione Enter para continuar...{RESET}")
            continue
        
        # --- FASE 3: FILTRADO INTELIGENTE ---
        draw_header()
        print(f"\n{B}[ STEP 3: FILTRADO DE CONTENIDO ]{RESET}")
        
        # Contar categorías detectadas
        cats = {}
        for e in all_entries:
            cats[e['group']] = cats.get(e['group'], 0) + 1
        
        print(f"{C} Categorías detectadas en la lista:{RESET}")
        for cat, count in cats.items():
            print(f" {W}• {cat}: {G}{count}{RESET}")
        
        print(f"\n{C} ¿Qué desea verificar?{RESET}")
        print(f" {W}[1] Solo TV  [2] Solo Cine  [3] Solo Series  [Enter] TODO{RESET}")
        
        sel = input(f"\n{C} > Selección: {W}").strip()
        filtered_entries = filter_by_category(all_entries, sel)
        
        if not filtered_entries:
            print(f"{R}[!] No hay canales que coincidan con el filtro.{RESET}")
            input(f"\n{R} Presione Enter para continuar...{RESET}")
            continue
        
        # --- FASE 4: RESUMEN Y ESCANEO ---
        draw_header()
        print(f"\n{G}╔{'═'*30}╗{RESET}")
        print(f"{G}║ READY TO SCAN: {W}Turbo Mode{G}    ║{RESET}")
        print(f"{G}╚{'═'*30}╝{RESET}")
        print(f"{C} Hilos: {W}{CONFIG['workers']}{RESET}")
        print(f"{C} Canales a verificar: {W}{len(filtered_entries)}{RESET}")
        print(f"{C} Destino: {W}{os.path.basename(source) if source else '...'}{RESET}")
        
        input(f"\n{R} [ PRESIONE ENTER PARA INICIAR EL ATAQUE ] {RESET}")
        
        # ESCANEO REAL
        results, alive, dead = run_checker(filtered_entries, CONFIG["workers"], CONFIG["timeout"])
        
        # Mostrar resumen final
        print(f"\n\n{G}╔{'═'*40}╗{RESET}")
        print(f"{G}║ {W}ESCANEO COMPLETADO{G}              ║{RESET}")
        print(f"{G}║ {W}VIVOS: {G}{alive}{W} / MUERTOS: {R}{dead}{W}        ║{RESET}")
        print(f"{G}╚{'═'*40}╝{RESET}")
        
        # Opción para ver detalle de vivos
        if alive > 0:
            show = input(f"\n{C} ¿Mostrar canales vivos? (s/N): {W}").strip().lower()
            if show == 's':
                print(f"\n{G}--- CANALES VIVOS ---{RESET}")
                for name, url, group, is_alive, latency in results:
                    if is_alive:
                        print(f"{G}✓ {name:<40} {Y}{latency}ms{RESET}")
        
        input(f"\n{R} [ Presione Enter para volver al menú ] {RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Operación cancelada por el usuario.{RESET}")
    except Exception as e:
        print(f"{R}[!] Error inesperado: {e}{RESET}")
    finally:
        print(f"{C}Gracias por usar RAIMIN GEN. ¡Hasta luego!{RESET}")