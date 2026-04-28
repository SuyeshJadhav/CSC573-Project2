import subprocess
import time
import re
import statistics
import matplotlib.pyplot as plt
import os
import csv

# Configurable constants
HOST = "127.0.0.1"
RUNS_PER_PARAM = 5

SERVER_EXE = "./Simple_ftp_server.exe" if os.name == 'nt' else "./Simple_ftp_server"
CLIENT_EXE = "./Simple_ftp_client.exe" if os.name == 'nt' else "./Simple_ftp_client"

PORT = "7735"
TEST_FILE = "test_1mb.dat"
RECV_FILE = "test_1mb_received.dat"

def run_transfer(N, MSS, p):
    # Delete the server's output file between runs so it doesn't accumulate data
    if os.path.exists(RECV_FILE):
        try:
            os.remove(RECV_FILE)
        except OSError:
            pass
            
    try:
        # Launch the server as a subprocess first
        server_proc = subprocess.Popen([SERVER_EXE, PORT, RECV_FILE, str(p)], 
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Give it 500ms to bind
        time.sleep(0.5) 
        
        # Launch the client as a subprocess
        client_cmd = [CLIENT_EXE, HOST, PORT, TEST_FILE, str(N), str(MSS)]
        client_proc = subprocess.run(client_cmd, capture_output=True, text=True, timeout=60)
        
        # Kill and clean up the server process after each run
        try:
            server_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server_proc.terminate()
            server_proc.wait(timeout=1)
            
        output = client_proc.stdout
        
        # Parse the exact format outputted by client.c
        match = re.search(r"Total transfer delay:\s*(\d+)\s*ms", output)
        if match:
            delay = int(match.group(1))
            return delay
        else:
            print(f" [Parse Error] ", end="")
            return -1
            
    except Exception as e:
        # Wrap each subprocess call in a try/except so one failed run doesn't crash the script
        print(f" [Exception: {e}] ", end="")
        try:
            server_proc.kill()
            server_proc.wait(timeout=2)
        except:
            pass
        return -1

def save_plot(task_name, vary_name, vary_values, averages, std_devs, filename):
    plt.figure()
    
    # Error bars showing standard deviation across the 5 runs
    plt.errorbar(vary_values, averages, yerr=std_devs, marker='o', linestyle='-', color='b', capsize=5)
    
    if vary_name == "N":
        plt.xscale('log', base=2)
        
    plt.xlabel(f"{vary_name}")
    plt.ylabel("Average Delay (ms)")
    plt.title(f"{task_name}: Delay vs {vary_name}")
    plt.grid(True)
    plt.savefig(filename)
    plt.close()
    print(f"Saved plot to {filename}")

def main():
    if not os.path.exists(TEST_FILE):
        print(f"Error: {TEST_FILE} not found. Please create a 1MB file first.")
        return

    # Save all raw results and averages to results.csv
    csv_file = open("results.csv", "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["task", "parameter", "run", "delay_ms"])

    tasks = [
        ("Task 1", "N", [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024], None, 500, 0.05, "task1_N_vs_delay.png"),
        ("Task 2", "MSS", [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], 64, None, 0.05, "task2_MSS_vs_delay.png"),
        ("Task 3", "p", [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10], 64, 500, None, "task3_p_vs_delay.png")
    ]

    for task_name, vary_name, vary_values, fixed_N, fixed_MSS, fixed_p, filename in tasks:
        print(f"\n=== {task_name} ===")
        averages = []
        std_devs = []
        
        for val in vary_values:
            N = val if vary_name == 'N' else fixed_N
            MSS = val if vary_name == 'MSS' else fixed_MSS
            p = val if vary_name == 'p' else fixed_p
            
            print(f"Testing {vary_name} = {val}: ", end="", flush=True)
            delays = []
            
            for run_idx in range(RUNS_PER_PARAM):
                d = run_transfer(N, MSS, p)
                if d != -1:
                    delays.append(d)
                    csv_writer.writerow([task_name, val, run_idx + 1, d])
                    csv_file.flush()
                else:
                    print("X ", end="", flush=True)
                    
            if delays:
                avg_delay = statistics.mean(delays)
                std_dev = statistics.stdev(delays) if len(delays) > 1 else 0.0
                averages.append(avg_delay)
                std_devs.append(std_dev)
                print(f" => Avg: {avg_delay:.2f} ms (StdDev: {std_dev:.2f})")
            else:
                # If parsing fails for a run, it's skipped from the average
                averages.append(0)
                std_devs.append(0)
                print(" => No successful runs.")
                
        save_plot(task_name, vary_name, vary_values, averages, std_devs, filename)

    csv_file.close()
    print("\nAll local experiments completed. Results saved to results.csv.")

if __name__ == "__main__":
    main()