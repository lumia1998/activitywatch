import os
import subprocess
import sys
from pathlib import Path


base_dir = Path(__file__).resolve().parent

for rel in [
    "aw-pywebview",
    "aw-core",
    "aw-client",
    "aw-server",
    "aw-watcher-afk",
    "aw-watcher-window",
    "aw-watcher-input",
]:
    sys.path.insert(0, str(base_dir / rel))


def _run(command):
    subprocess.check_call(command, cwd=str(base_dir))


def _ensure_pip() -> None:
    try:
        import pip  # noqa: F401
    except ImportError:
        _run([sys.executable, "-m", "ensurepip", "--upgrade"])


def _ensure_python_packages() -> None:
    _ensure_pip()
    packages = [
        "pytest",
        "pytest-cov",
        "requests>=2.32.3",
        "pywebview>=5.1",
        "pystray>=0.19.5",
        "Pillow>=10.4.0",
        "flask>=2.2",
        "flask-restx>=1.0.3",
        "flask-cors",
        "werkzeug>=2.3.3",
        "jsonschema>=4.3",
        "peewee>=3,<4",
        "platformdirs==3.10",
        "iso8601",
        "rfc3339-validator>=0.1.4",
        "strict-rfc3339>=0.7",
        "tomlkit",
        "deprecation",
        "timeslot",
        "click",
    ]

    if sys.platform in ["win32", "cygwin"]:
        packages.extend([
            "pywin32==306",
            "wmi",
        ])

    _run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    _run([sys.executable, "-m", "pip", "install", *packages])


def main() -> None:
    _ensure_python_packages()
    from aw_pywebview import main as aw_main

    aw_main()


if __name__ == "__main__":
    main()
