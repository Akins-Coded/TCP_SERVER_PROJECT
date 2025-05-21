import socket
import time
import matplotlib.pyplot as plt
import os  # Added import for directory creation

# Server configuration
SERVER_HOST = "135.181.96.160"
SERVER_PORT = 44445

# Benchmark queries
TEST_QUERIES = ["test_line_1", "test_line_2", "test_line_3", "not_existing_line"] * 5

def measure_query_latency(query: str) -> float:
    """
    Measure the response time for a given query.

    Args:
        query (str): The query string.

    Returns:
        float: Latency in milliseconds, or -1 if the request fails.
    """
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=5) as sock:
            start = time.perf_counter()
            sock.sendall(f"{query}\n".encode())
            response = sock.recv(1024).decode('utf-8').strip()
            end = time.perf_counter()
            print(f"Query '{query}' response: {response}")
            return (end - start) * 1000
    except Exception as e:
        print(f"Query failed: {e}")
        return -1

def run_benchmark():
    """
    Executes all test queries, collects latencies, and plots the results.
    """
    # Ensure report directory exists
    os.makedirs("report", exist_ok=True)

    latencies = []
    for query in TEST_QUERIES:
        latency = measure_query_latency(query)
        latencies.append(latency)
        print(f"Query '{query}' took {latency:.2f} ms")

    plt.figure(figsize=(12, 6))
    plt.plot(range(len(latencies)), latencies, marker="o", label="Query Latency (ms)")
    plt.axhline(y=40, color='r', linestyle='--', label='40ms Threshold')
    plt.xlabel("Query Number")
    plt.ylabel("Latency (ms)")
    plt.title("TCP Server Benchmark - Query Response Time")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("report/benchmark_plot.png")
    print("\nBenchmark graph saved to: report/benchmark_plot.png")

if __name__ == "__main__":
    run_benchmark()
