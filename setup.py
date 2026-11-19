    #1 create virtual environment for installing packages
    #2 install modules in requirements.txt
    #3 install frontend dependencies
    #4 start backend
    #5 start frontend

from pathlib import Path
import os
import signal
import subprocess
import sys
import time

ProjectRootDirectory = Path(__file__).resolve().parent
frontend = ProjectRootDirectory / "frontend"
backend = ProjectRootDirectory / "backend"
VirtualEnv = ProjectRootDirectory / ".venv"

IS_WINDOWS = os.name == "nt"
BIN_DIR = "Scripts" if IS_WINDOWS else "bin"
EXE = ".exe" if IS_WINDOWS else ""

uvicorn = VirtualEnv / BIN_DIR / f"uvicorn{EXE}"
pip = VirtualEnv / BIN_DIR / f"pip{EXE}"
python_exe = VirtualEnv / BIN_DIR / f"python{EXE}"

requirements = ProjectRootDirectory / "requirements.txt"

procs = []


def createVirtualEnvironment():
    if VirtualEnv.is_dir():
        print("Virtual Environment already exists.")
    else:
        print("Creating Virtual Environment...")
        subprocess.run([sys.executable, "-m", "venv", str(VirtualEnv)], check=True)


def installPythonModules():
    if requirements.is_file():
        print("# Installing Python dependencies")
        subprocess.run([str(pip), "install", "-r", str(requirements)], check=True)
        print("# Python dependencies installation complete")
    else:
        print(f"Requirements file not found at {requirements}, skipping Python deps")


def installFrontendDependencies():
    print("# Installing frontend dependencies")
    subprocess.run(["npm", "install", "--verbose"], cwd=frontend, check=True, shell=IS_WINDOWS)
    print("# Frontend dependencies installation complete")


def startBackend():
    if not uvicorn.exists():
        print(f"uvicorn not found at {uvicorn} — did installPythonModules() run?")
        sys.exit(1)
    proc = subprocess.Popen(
        [str(uvicorn), "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=backend,
        start_new_session=not IS_WINDOWS,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0,
    )
    procs.append(proc)
    return proc


def startFrontend():
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend,
        shell=IS_WINDOWS,
        start_new_session=not IS_WINDOWS,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0,
    )
    procs.append(proc)
    return proc


def stop(proc):
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if IS_WINDOWS:
            proc.terminate()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    except ProcessLookupError:
        pass


def _raise_interrupt(signum, frame):
    raise KeyboardInterrupt


def main():
    if not IS_WINDOWS:
        signal.signal(signal.SIGHUP, _raise_interrupt)
        signal.signal(signal.SIGTERM, _raise_interrupt)

    try:
        createVirtualEnvironment()
        installPythonModules()
        installFrontendDependencies()
        startBackend()
        time.sleep(2)  # brief head start before starting frontend
        startFrontend()

        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\nStopping servers...")
    finally:
        for p in procs:
            stop(p)


if __name__ == "__main__":
    main()
