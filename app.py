import uvicorn
import os
import sys

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting IPS ERP System on http://{host}:{port} ...")
    uvicorn.run("ips_app.main:app", host=host, port=port, reload=False)
