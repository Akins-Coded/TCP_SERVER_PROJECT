# benchmark_test.py
import time
from client.client import send_query

QUERIES = ["example_string_1", "nonexistent_string", "example_string_2"]
REPEATS = 50

def benchmark(ssl_enabled=True):
    results = []
    for query in QUERIES:
        durations = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            send_query(query, ssl_enabled=ssl_enabled)
            end = time.perf_counter()
            durations.append(end - start)
        results.append((query, sum(durations)/REPEATS))
    return results

def print_report(results, label):
    print(f"\nBenchmark Results ({label}):")
    for query, avg_time in results:
        print(f"  Query: '{query}' -> Avg Time: {avg_time:.5f} seconds")

if __name__ == "__main__":
    print("Make sure server is running with correct REREAD_ON_QUERY setting...")

    print("🔁 Testing REREAD_ON_QUERY=True ...")
    results_reread = benchmark()
    print_report(results_reread, "REREAD_ON_QUERY=True")

    input("\nNow toggle config to REREAD_ON_QUERY=False and restart the server. Press Enter when ready...")

    print("🔁 Testing REREAD_ON_QUERY=False ...")
    results_cache = benchmark()
    print_report(results_cache, "REREAD_ON_QUERY=False")
