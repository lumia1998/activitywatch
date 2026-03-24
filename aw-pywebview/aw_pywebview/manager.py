import logging
import os
import platform
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

_module_dir = os.path.dirname(os.path.realpath(__file__))
_parent_dir = os.path.abspath(os.path.join(_module_dir, os.pardir))
# Root dir (2 levels up from aw_pywebview package: aw_pywebview -> aw-pywebview -> root)
_root_dir = os.path.abspath(os.path.join(_module_dir, "..", ".."))

_IGNORED_FILENAMES = [
    "aw-cli",
    "aw-client",
    "aw-qt",
    "aw-qt.desktop",
    "aw-qt.spec",
    "aw-pywebview",
]

_SOURCE_MODULES = [
    "aw-server",
    "aw-watcher-afk",
    "aw-watcher-window",
    "aw-watcher-input",
]


def _is_executable(path: str, filename: str) -> bool:
    if not os.path.isfile(path):
        return False
    if platform.system() == "Windows":
        return filename.endswith(".exe")
    if not os.access(path, os.X_OK):
        return False
    if filename.endswith(".desktop"):
        return False
    return True


def _filename_to_name(filename: str) -> str:
    return filename.replace(".exe", "")


def _discover_modules_in_directory(path: str) -> List["Module"]:
    modules = []
    matches = glob(os.path.join(path, "aw-*"))
    for p in matches:
        basename = os.path.basename(p)
        if _is_executable(p, basename) and basename.startswith("aw-"):
            name = _filename_to_name(basename)
            modules.append(Module(name, Path(p), "bundled"))
        elif os.path.isdir(p) and os.access(p, os.X_OK):
            modules.extend(_discover_modules_in_directory(p))
    return modules


def _filter_modules(modules: Iterable["Module"]) -> Set["Module"]:
    return {m for m in modules if m.name not in _IGNORED_FILENAMES}


def _discover_modules_bundled() -> List["Module"]:
    search_paths = [_module_dir, _parent_dir]
    if platform.system() == "Darwin":
        macos_dir = os.path.abspath(os.path.join(_parent_dir, os.pardir, "MacOS"))
        search_paths.append(macos_dir)

    modules: List[Module] = []
    for path in search_paths:
        modules += _discover_modules_in_directory(path)

    modules = list(_filter_modules(modules))
    logger.info("Found %d bundled modules", len(modules))
    return modules


def _discover_modules_system() -> List["Module"]:
    search_paths = os.get_exec_path()
    if _parent_dir in search_paths:
        search_paths.remove(_parent_dir)

    modules: List[Module] = []
    paths = [p for p in search_paths if os.path.isdir(p)]
    for path in paths:
        try:
            ls = os.listdir(path)
        except PermissionError:
            logger.warning("PermissionError while listing %s, skipping", path)
            continue

        for basename in ls:
            if not basename.startswith("aw-"):
                continue
            if not _is_executable(os.path.join(path, basename), basename):
                continue
            name = _filename_to_name(basename)
            if name not in [m.name for m in modules]:
                modules.append(Module(name, Path(path) / basename, "system"))

    modules = list(_filter_modules(modules))
    logger.info("Found %d system modules", len(modules))
    return modules


def _discover_modules_source() -> List["Module"]:
    modules: List[Module] = []
    for name in _SOURCE_MODULES:
        # We assume they are in the root directory
        # name is aw-server, but module is aw_server
        module_path = os.path.join(_root_dir, name)
        if os.path.isdir(module_path):
            modules.append(Module(name, Path(module_path), "source"))
    logger.info("Found %d source modules", len(modules))
    return modules


class Module:
    def __init__(self, name: str, path: Path, type: str) -> None:
        self.name = name
        self.path = path
        assert type in ["system", "bundled", "source"]
        self.type = type
        self.started = False
        self._process: Optional[subprocess.Popen[str]] = None

    def __hash__(self) -> int:
        return hash((self.name, self.path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Module):
            return False
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f"<Module {self.name} at {self.path} ({self.type})>"

    def start(self, testing: bool) -> None:
        logger.info("Starting module %s (%s)", self.name, self.type)

        env = os.environ.copy()
        if self.type == "source":
            # Add all source modules to PYTHONPATH
            pythonpath_parts = [
                os.path.join(_root_dir, "aw-core"),
                os.path.join(_root_dir, "aw-client"),
                os.path.join(_root_dir, "aw-server"),
                os.path.join(_root_dir, "aw-watcher-afk"),
                os.path.join(_root_dir, "aw-watcher-window"),
                os.path.join(_root_dir, "aw-watcher-input"),
            ]
            existing_path = env.get("PYTHONPATH", "")
            if existing_path:
                pythonpath_parts.append(existing_path)
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

            # Run as python -m module_name
            py_exec = sys.executable
            # We need to use the package name, not the directory name with dash
            package_name = self.name.replace("-", "_")
            exec_cmd = [py_exec, "-m", package_name]
        else:
            exec_cmd = [str(self.path)]

        if testing:
            exec_cmd.append("--testing")

        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self._process = subprocess.Popen(
            exec_cmd, universal_newlines=True, startupinfo=startupinfo, env=env
        )
        self.started = True

    def stop(self) -> None:
        if not self.started:
            return
        if self._process and self.is_alive():
            logger.debug("Stopping module %s", self.name)
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self.started = False

    def is_alive(self) -> bool:
        if self._process is None:
            return False
        self._process.poll()
        return self._process.returncode is None


def _existing_module_names(modules: Iterable["Module"]) -> Set[str]:
    return {module.name for module in modules}


def _filter_existing_autostart_modules(
    modules: Iterable["Module"], autostart_modules: List[str]
) -> List[str]:
    existing_names = _existing_module_names(modules)
    for name in autostart_modules:
        if name not in existing_names:
            logger.error("Module %s not found in any discoverable location", name)
    return list({name for name in autostart_modules if name in existing_names})


def _preferred_server_module(module_names: Iterable[str]) -> Optional[str]:
    names = set(module_names)
    if "aw-server-rust" in names:
        return "aw-server-rust"
    if "aw-server" in names:
        return "aw-server"
    return None


def _start_priority(module: "Module") -> int:
    order = {"bundled": 0, "system": 1, "source": 2}
    return order[module.type]


class Manager:
    def __init__(self, testing: bool = False) -> None:
        self.testing = testing
        self.modules: List[Module] = []
        self.discover_modules()

    @property
    def modules_system(self) -> List[Module]:
        return [m for m in self.modules if m.type == "system"]

    @property
    def modules_bundled(self) -> List[Module]:
        return [m for m in self.modules if m.type == "bundled"]

    @property
    def modules_source(self) -> List[Module]:
        return [m for m in self.modules if m.type == "source"]

    def discover_modules(self) -> None:
        modules = set(_discover_modules_bundled())
        modules |= set(_discover_modules_system())
        modules |= set(_discover_modules_source())
        modules = _filter_modules(modules)
        for m in modules:
            if m not in self.modules:
                self.modules.append(m)

    def autostart(self, autostart_modules: List[str]) -> None:
        autostart_modules = _filter_existing_autostart_modules(self.modules, autostart_modules)

        server_module = _preferred_server_module(autostart_modules)
        if server_module:
            self.start(server_module)

        others = list(set(autostart_modules) - {"aw-server", "aw-server-rust"})
        for name in others:
            self.start(name)

    def start(self, module_name: str) -> None:
        # Priority: bundled > system > source
        candidates = [m for m in self.modules if m.name == module_name]
        if not candidates:
            logger.error("Manager tried to start nonexistent module %s", module_name)
            return

        candidates.sort(key=_start_priority)
        candidates[0].start(self.testing)

    def stop_all(self) -> None:
        for module in [m for m in self.modules if m.is_alive()]:
            module.stop()
