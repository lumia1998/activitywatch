import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "aw-watcher-window" / "aw_watcher_window" / "windows.py"

sys.modules.setdefault("win32api", types.SimpleNamespace())
sys.modules.setdefault("win32gui", types.SimpleNamespace())
sys.modules.setdefault("win32process", types.SimpleNamespace())
sys.modules.setdefault("wmi", types.SimpleNamespace(WMI=lambda: types.SimpleNamespace(query=lambda _q: [])))

SPEC = spec_from_file_location("aw_watcher_window.windows", MODULE_PATH)
windows_module = module_from_spec(SPEC)
sys.modules["aw_watcher_window.windows"] = windows_module
assert SPEC.loader is not None
SPEC.loader.exec_module(windows_module)


_extract_meaningful_title = windows_module._extract_meaningful_title
_get_file_display_name = windows_module._get_file_display_name
_iter_version_info_candidates = windows_module._iter_version_info_candidates
_resolve_display_name = windows_module._resolve_display_name


class FakeWin32Api:
    def __init__(self, responses=None, translations=None, fail=False):
        self.responses = responses or {}
        self.translations = translations or ()
        self.fail = fail
        self.calls = []

    def GetFileVersionInfo(self, path, query):
        self.calls.append((path, query))
        if self.fail:
            raise RuntimeError("boom")
        if query == r"\\VarFileInfo\\Translation":
            return self.translations
        return self.responses.get(query)



def test_extract_meaningful_title_returns_first_segment():
    assert _extract_meaningful_title("Visual Studio Code - activitywatch") == "Visual Studio Code"
    assert _extract_meaningful_title("python.exe") == ""
    assert _extract_meaningful_title(r"C:/Python/python.exe") == ""



def test_is_excluded_process_name_handles_default_blacklist():
    assert windows_module._is_excluded_process_name("desktopMgr64") is True
    assert windows_module._is_excluded_process_name("python") is False



def test_get_file_display_name_prefers_localized_file_description(monkeypatch):
    fake_api = FakeWin32Api(
        responses={r"\StringFileInfo\080404B0\FileDescription": "Visual Studio Code"},
        translations=((0x0804, 0x04B0),),
    )
    monkeypatch.setattr(windows_module, "win32api", fake_api)

    assert _get_file_display_name("C:/Program Files/Microsoft VS Code/Code.exe", "Code") == "Visual Studio Code"
    assert fake_api.calls[0][1] == r"\\VarFileInfo\\Translation"
    assert ("C:/Program Files/Microsoft VS Code/Code.exe", r"\StringFileInfo\080404B0\FileDescription") in fake_api.calls



def test_get_file_display_name_falls_back_to_process_name_on_error(monkeypatch):
    monkeypatch.setattr(windows_module, "win32api", FakeWin32Api(fail=True))

    assert _get_file_display_name("C:/Windows/System32/notepad.exe", "notepad") == "notepad"



def test_resolve_display_name_prefers_title_for_host_processes():
    assert _resolve_display_name("python", "Python", "Visual Studio Code - activitywatch") == "Visual Studio Code"



def test_resolve_display_name_prefers_file_metadata_for_normal_processes():
    assert _resolve_display_name("Code", "Visual Studio Code", "activitywatch - repo") == "Visual Studio Code"


def test_resolve_display_name_handles_special_cases():
    assert _resolve_display_name("javaw", "OpenJDK Platform Binary", "Minecraft 1.21.4") == "Minecraft"
    assert _resolve_display_name("360FileBrowser64", "360FileBrowser64", "") == "360文件夹"
    assert _resolve_display_name("explorer", "Windows Explorer", "") == "360文件夹"
    assert _resolve_display_name("wezterm-gui", "wezterm-gui", "") == "wezterm"
    assert _resolve_display_name("WINWORD", "Microsoft Word", "") == "Word"
    assert _resolve_display_name("notepad", "Notepad", "") == "记事本"
    assert _resolve_display_name("Unknown", "Unknown", "") == "unknown"


def test_is_real_window_rejects_non_root_minimized_and_cloaked_windows(monkeypatch):
    monkeypatch.setattr(
        windows_module,
        "win32gui",
        types.SimpleNamespace(
            IsWindow=lambda _hwnd: True,
            IsWindowVisible=lambda _hwnd: True,
            GetWindowText=lambda _hwnd: "Visible window",
            GetAncestor=lambda _hwnd, _flag: 99,
            IsIconic=lambda _hwnd: False,
            GetWindowPlacement=lambda _hwnd: (0, 1, 0, 0, 0),
        ),
    )
    monkeypatch.setattr(windows_module, "_is_cloaked_window", lambda _hwnd: False)
    assert windows_module._is_real_window(1) is False

    monkeypatch.setattr(
        windows_module,
        "win32gui",
        types.SimpleNamespace(
            IsWindow=lambda _hwnd: True,
            IsWindowVisible=lambda _hwnd: True,
            GetWindowText=lambda _hwnd: "Visible window",
            GetAncestor=lambda _hwnd, _flag: 1,
            IsIconic=lambda _hwnd: True,
            GetWindowPlacement=lambda _hwnd: (0, 2, 0, 0, 0),
        ),
    )
    assert windows_module._is_real_window(1) is False

    monkeypatch.setattr(
        windows_module,
        "win32gui",
        types.SimpleNamespace(
            IsWindow=lambda _hwnd: True,
            IsWindowVisible=lambda _hwnd: True,
            GetWindowText=lambda _hwnd: "Visible window",
            GetAncestor=lambda _hwnd, _flag: 1,
            IsIconic=lambda _hwnd: False,
            GetWindowPlacement=lambda _hwnd: (0, 1, 0, 0, 0),
        ),
    )
    monkeypatch.setattr(windows_module, "_is_cloaked_window", lambda _hwnd: True)
    assert windows_module._is_real_window(1) is False
