def monitor_resources(interval=1.0):
    """
    Monitor and record CPU and RAM usage during script execution.
    
    Parameters:
    -----------
    interval : float
        Sampling interval in seconds (default: 1.0)
    
    Returns:
    --------
    dict
        Dictionary with timestamps and resource usage data
    
    Usage:
    ------
    # Start monitoring at the beginning of your script
    monitor = monitor_resources()
    monitor.start()
    
    # Your script execution here
    
    # Stop monitoring at the end
    results = monitor.stop()
    
    # Plot the results
    monitor.plot_results()
    """
    import psutil
    import time
    import threading
    import matplotlib.pyplot as plt
    from datetime import datetime
    import numpy as np
    
    class ResourceMonitor:
        def __init__(self, interval):
            self.interval = interval
            self.running = False
            self.thread = None
            self.data = {
                'timestamps': [],
                'cpu_percent': [],
                'cpu_per_core': [],
                'memory_percent': [],
                'memory_used': []
            }
            self.start_time = None
        
        def _monitor(self):
            cpu_count = psutil.cpu_count(logical=True)
            while self.running:
                # Record timestamp
                current_time = time.time() - self.start_time
                self.data['timestamps'].append(current_time)
                
                # CPU usage (overall and per core)
                cpu_percent = psutil.cpu_percent(interval=0)
                self.data['cpu_percent'].append(cpu_percent)
                
                cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)
                self.data['cpu_per_core'].append(cpu_per_core)
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.data['memory_percent'].append(memory.percent)
                self.data['memory_used'].append(memory.used / (1024 * 1024 * 1024))  # GB
                
                # Wait for next interval
                time.sleep(self.interval)
        
        def start(self):
            """Start monitoring resources"""
            if not self.running:
                self.running = True
                self.start_time = time.time()
                self.thread = threading.Thread(target=self._monitor)
                self.thread.daemon = True
                self.thread.start()
                print(f"Resource monitoring started at {datetime.now().strftime('%H:%M:%S')}")
        
        def stop(self):
            """Stop monitoring and return collected data"""
            if self.running:
                self.running = False
                if self.thread:
                    self.thread.join(timeout=self.interval*2)
                print(f"Resource monitoring stopped at {datetime.now().strftime('%H:%M:%S')}")
            return self.data
        
        def plot_results(self, filename=None):
            """Plot the monitored resource usage"""
            if len(self.data['timestamps']) == 0:
                print("No data available to plot")
                return
                
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            try:
                # Plot CPU usage
                ax1.plot(self.data['timestamps'], self.data['cpu_percent'], 'b-', label='Total CPU')
                
                # If we have per-core data and more than one sample
                if self.data['cpu_per_core'] and len(self.data['cpu_per_core'][0]) > 1:
                    cpu_cores = len(self.data['cpu_per_core'][0])
                    core_data = np.array(self.data['cpu_per_core']).T  # Transpose for per-core time series
                    
                    for i in range(cpu_cores):
                        ax1.plot(self.data['timestamps'], core_data[i], 
                                 alpha=0.3, label=f'Core {i}' if i < 5 else None)
                
                ax1.set_title('CPU Usage Over Time')
                ax1.set_xlabel('Time (seconds)')
                ax1.set_ylabel('CPU Usage (%)')
                ax1.grid(True)
                ax1.legend(loc='upper right')
                
                # Plot Memory usage
                ax2.plot(self.data['timestamps'], self.data['memory_used'], 'r-')
                ax2.set_title('Memory Usage Over Time')
                ax2.set_xlabel('Time (seconds)')
                ax2.set_ylabel('Memory Usage (GB)')
                ax2.grid(True)
                
                plt.tight_layout()
                
                if filename:
                    plt.savefig(filename)
                    print(f"Resource usage plot saved to {filename}")
                
                plt.show()
            finally:
                # Always close the figure to prevent memory leaks
                plt.close(fig)
            
    return ResourceMonitor(interval)