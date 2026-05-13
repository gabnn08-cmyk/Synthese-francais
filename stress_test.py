import urllib.request
import concurrent.futures
import time

URL = "http://127.0.0.1:8000/healthz"

def test_request(_):
    start = time.time()
    try:
        r = urllib.request.urlopen(URL, timeout=5)
        duration = time.time() - start
        return r.status, duration
    except Exception as e:
        return str(e), None

TOTAL_REQUESTS = 100

with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    results = list(executor.map(test_request, range(TOTAL_REQUESTS)))

success = sum(1 for r, _ in results if r == 200)
failures = TOTAL_REQUESTS - success

times = [t for _, t in results if t is not None]

print(f"Succès: {success}")
print(f"Erreurs: {failures}")

if times:
    print(f"Temps moyen: {sum(times)/len(times):.3f}s")
    print(f"Temps max: {max(times):.3f}s")