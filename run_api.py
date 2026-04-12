import subprocess
import sys
import os

if __name__ == "__main__":
    print("Starting Advisor Voice Agent API server...")
    # Use the Python executable from the venv
    python_exe = r"C:\MULTILINGUAL VOICE AGENT\venv\Scripts\python.exe"
    subprocess.run([python_exe, "-m", "uvicorn", "surfaces.api:app", "--host", "127.0.0.1", "--port", "8000", "--reload"])
