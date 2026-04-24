import os
import sys
import json
import signal
import socket
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

import psutil


class Process:
    """Process works, find port and run it and make it detachable"""

    @staticmethod
    def find_port(start=8080, end=8090):
        """Find available port in range"""
        for port in range(start, end + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
                sock.close()
                return port
            except OSError:
                continue
        return None

    @staticmethod
    def spawn(api_key, port, verbose=False):
        """Spawn detached proxy process"""
        exe = sys.executable

        # Check if running as PyInstaller binary or Python script
        if getattr(sys, "frozen", False):
            # PyInstaller binary: exe is the binary itself
            cmd = [exe, "--detach", f"--api-key={api_key}", f"--port={port}"]
        else:
            # Python script: need to run the script with Python
            script = str(Path(__file__).parent.parent / "proxy.main.py")
            cmd = [exe, script, "--detach", f"--api-key={api_key}", f"--port={port}"]

        if verbose:
            cmd.append("--verbose")

        env = os.environ.copy()
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)

        kw = {
            "env": env,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }

        if sys.platform == "win32":
            kw["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
            proc = subprocess.Popen(cmd, **kw)
        else:
            proc = subprocess.Popen(cmd, start_new_session=True, **kw)

        return proc.pid

    @staticmethod
    def alive(pid):
        """Check if process alive"""
        try:
            p = psutil.Process(pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    @staticmethod
    def kill(pid, timeout=5):
        """Kill process gracefully"""
        try:
            p = psutil.Process(pid)
            if sys.platform == "win32":
                p.terminate()
            else:
                p.send_signal(signal.SIGTERM)
            try:
                p.wait(timeout=timeout)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait(timeout=2)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False


class Session:
    """Maintaining sessions here, creation, listing, killing"""

    def __init__(self):
        self.dir = Path.home() / ".zgrc" / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_key(api_key):
        """Hash API key for session ID"""
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]

    def path(self, api_key):
        """Get session file path"""
        return self.dir / f"{self.hash_key(api_key)}.json"

    def save(self, api_key, port, pid):
        """Save session"""
        data = {
            "port": port,
            "pid": pid,
            "host": "127.0.0.1",
            "key_hash": self.hash_key(api_key),
            "started": datetime.utcnow().isoformat(),
        }
        self.path(api_key).write_text(json.dumps(data, indent=2))

    def load(self, api_key):
        """Load session"""
        p = self.path(api_key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, IOError):
            p.unlink(missing_ok=True)
            return None

    def get(self, api_key):
        """Get active session"""
        s = self.load(api_key)
        if s and Process.alive(s["pid"]):
            return s
        if s:
            self.path(api_key).unlink(missing_ok=True)
        return None

    def all(self):
        """List all active sessions"""
        active = []
        for f in self.dir.glob("*.json"):
            try:
                s = json.loads(f.read_text())
                if Process.alive(s["pid"]):
                    active.append(s)
                else:
                    f.unlink(missing_ok=True)
            except (json.JSONDecodeError, IOError, KeyError):
                f.unlink(missing_ok=True)
        return active

    def kill(self, api_key):
        """Kill session"""
        s = self.load(api_key)
        if not s:
            return False
        ok = Process.kill(s["pid"])
        if ok:
            self.path(api_key).unlink(missing_ok=True)
        return ok

    def kill_all(self):
        """Kill all sessions"""
        count = 0
        for s in self.all():
            if Process.kill(s["pid"]):
                count += 1
        for f in self.dir.glob("*.json"):
            f.unlink(missing_ok=True)
        return count


class Manager:
    """Orchestrating all works that's all"""

    def __init__(self):
        self.session = Session()

    def start(self, api_key, port=None, verbose=False):
        """Start or reuse proxy server"""
        # Check existing
        s = self.session.get(api_key)
        if s:
            return s["port"], s["pid"], False

        # Find port
        if port is None:
            port = Process.find_port()
            if not port:
                raise RuntimeError("No available port in range 8080-8090")

        pid = Process.spawn(api_key, port, verbose)
        self.session.save(api_key, port, pid)

        return port, pid, True

    def env(self, port):
        """Get env vars for port"""
        cert = str(Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem")
        return {
            "HTTPS_PROXY": f"http://127.0.0.1:{port}",
            "HTTP_PROXY": f"http://127.0.0.1:{port}",
            "NODE_EXTRA_CA_CERTS": cert,
        }

    def status(self):
        """Get all active sessions"""
        return self.session.all()

    def kill_all(self):
        """Kill all servers"""
        return self.session.kill_all()
