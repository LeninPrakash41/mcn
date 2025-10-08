"""
MCN Integrated Development Server
Runs both MCN backend and React frontend in a single process
"""

import os
import subprocess
import threading
import time
import signal
import sys
from pathlib import Path


class MCNDevServer:
    """Integrated development server for MCN full-stack apps"""
    
    def __init__(self):
        self.backend_process = None
        self.frontend_process = None
        self.running = False
    
    def start(self, mcn_file: str, frontend_dir: str = None):
        """Start both backend and frontend servers"""
        
        print("🚀 Starting MCN Development Server...")
        
        # Start MCN backend
        self._start_backend(mcn_file)
        
        # Start React frontend if directory exists
        if frontend_dir and os.path.exists(frontend_dir):
            self._start_frontend(frontend_dir)
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("\n✅ MCN Development Server Started!")
        print("📊 Backend:  http://localhost:8000")
        if frontend_dir:
            print("🎨 Frontend: http://localhost:3000")
        print("\n💡 Press Ctrl+C to stop both servers")
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def _start_backend(self, mcn_file: str):
        """Start MCN backend server"""
        print("🔧 Starting MCN backend...")
        
        cmd = [sys.executable, "run_mcn.py", "serve", "--file", mcn_file, "--port", "8000"]
        
        self.backend_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Monitor backend in separate thread
        threading.Thread(target=self._monitor_backend, daemon=True).start()
    
    def _start_frontend(self, frontend_dir: str):
        """Start React frontend server"""
        print("🎨 Starting React frontend...")
        
        # Check if node_modules exists
        node_modules = os.path.join(frontend_dir, "node_modules")
        if not os.path.exists(node_modules):
            print("📦 Installing dependencies...")
            install_process = subprocess.run(
                ["npm", "install"],
                cwd=frontend_dir,
                capture_output=True,
                text=True
            )
            if install_process.returncode != 0:
                print(f"❌ Failed to install dependencies: {install_process.stderr}")
                return
        
        # Start React dev server
        self.frontend_process = subprocess.Popen(
            ["npm", "start"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "BROWSER": "none"}  # Don't auto-open browser
        )
        
        # Monitor frontend in separate thread
        threading.Thread(target=self._monitor_frontend, daemon=True).start()
    
    def _monitor_backend(self):
        """Monitor backend process output"""
        if not self.backend_process:
            return
        
        for line in iter(self.backend_process.stdout.readline, ''):
            if line.strip():
                print(f"🔧 Backend: {line.strip()}")
        
        if self.backend_process.stderr:
            for line in iter(self.backend_process.stderr.readline, ''):
                if line.strip():
                    print(f"❌ Backend Error: {line.strip()}")
    
    def _monitor_frontend(self):
        """Monitor frontend process output"""
        if not self.frontend_process:
            return
        
        for line in iter(self.frontend_process.stdout.readline, ''):
            if line.strip() and "webpack compiled" in line.lower():
                print(f"🎨 Frontend: Ready")
            elif line.strip() and "error" in line.lower():
                print(f"❌ Frontend Error: {line.strip()}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\n🛑 Shutting down MCN Development Server...")
        self.stop()
    
    def stop(self):
        """Stop both servers"""
        self.running = False
        
        if self.backend_process:
            print("🔧 Stopping backend...")
            self.backend_process.terminate()
            self.backend_process.wait()
        
        if self.frontend_process:
            print("🎨 Stopping frontend...")
            self.frontend_process.terminate()
            self.frontend_process.wait()
        
        print("✅ MCN Development Server stopped")
        sys.exit(0)


def start_dev_server(mcn_file: str, frontend_dir: str = None):
    """Start integrated development server"""
    server = MCNDevServer()
    server.start(mcn_file, frontend_dir)