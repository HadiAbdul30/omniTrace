# examples/dummy_logger.py
import time
import traceback

def simulate_background_crash():
    try:
        # Intentional error: Dictionary key lookup failure
        config = {"host": "localhost", "port": 8080}
        return config["database_password"]
    except Exception:
        return traceback.format_exc()

if __name__ == "__main__":
    print("Dummy backend service started. Writing to app.log...")
    
    with open("app.log", "a") as f:
        f.write("[INFO] System starting...\n")
        time.sleep(2)
        f.write("[INFO] Connecting to local services...\n")
        time.sleep(2)
        
        # Simulate the crash occurring
        f.write("[ERROR] Unhandled exception in worker thread:\n")
        f.write(simulate_background_crash())
        
    print("Crash written to app.log!")
