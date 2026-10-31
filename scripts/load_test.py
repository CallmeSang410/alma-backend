"""
Script de benchmarking de rendimiento (HF-002)
Ejecuta 50 solicitudes con concurrencia 10 hacia GET /health.
Verifica métricas: min, max, media, p50, p95 (< 200ms) y p99.
"""
import sys
import time
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

TARGET_URL = "http://127.0.0.1:8000/health"
TOTAL_REQUESTS = 50
CONCURRENCY = 10


def realizar_peticion(req_id: int) -> float:
    inicio = time.perf_counter()
    req = Request(TARGET_URL, headers={"X-Request-ID": f"bench-{req_id}"})
    with urlopen(req, timeout=10) as resp:
        assert resp.status == 200
    return (time.perf_counter() - inicio) * 1000


def run_benchmark(target_url: str = TARGET_URL, total: int = TOTAL_REQUESTS, concurrency: int = CONCURRENCY):
    print(f"=== INICIANDO BENCHMARK DE RENDIMIENTO (HF-002) ===")
    print(f"Objetivo: {target_url}")
    print(f"Peticiones: {total} | Concurrencia: {concurrency}")
    print(f"Fecha/Hora: {datetime.utcnow().isoformat()}Z")

    latencias = []
    errores = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futuros = [executor.submit(realizar_peticion, i) for i in range(total)]
        for f in futuros:
            try:
                latencias.append(f.result())
            except Exception as e:
                errores += 1
                print(f"Error en peticion: {e}")

    if not latencias:
        print("❌ No se pudieron completar las peticiones.")
        return False

    latencias.sort()
    min_lat = min(latencias)
    max_lat = max(latencias)
    media = statistics.mean(latencias)
    p50 = statistics.median(latencias)
    p90 = latencias[int(len(latencias) * 0.90)]
    p95 = latencias[int(len(latencias) * 0.95)]
    p99 = latencias[int(len(latencias) * 0.99)]

    print("\n--- RESULTADOS ---")
    print(f"Completadas: {len(latencias)}/{total} | Errores: {errores}")
    print(f"Min:   {min_lat:8.2f} ms")
    print(f"Max:   {max_lat:8.2f} ms")
    print(f"Media: {media:8.2f} ms")
    print(f"p50:   {p50:8.2f} ms")
    print(f"p90:   {p90:8.2f} ms")
    print(f"p95:   {p95:8.2f} ms")
    print(f"p99:   {p99:8.2f} ms")

    if p95 < 200.0:
        print("\n✅ SLA CUMPLIDO: p95 inferior a 200 ms (Nivel Excelente UNI)")
        return True
    elif p95 < 500.0:
        print("\n⚠️ SLA PARCIAL: p95 inferior a 500 ms (Nivel Bueno UNI)")
        return True
    else:
        print(f"\n❌ SLA NO CUMPLIDO: p95 ({p95:.2f} ms) superior a 500 ms")
        return False


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else TARGET_URL
    run_benchmark(target_url=url)
