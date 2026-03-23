import os
import time
from typing import Iterable, Optional

import win32api
import win32gui
import win32process
import wmi


HOST_PROCESS_NAMES = {
    "java",
    "javaw",
    "python",
    "pythonw",
    "node",
    "dotnet",
}

GENERIC_DISPLAY_NAMES = {
    "java(tm) platform se binary",
    "openjdk platform binary",
    "python",
    "pythonw",
    "node.js javascript runtime",
    "microsoft(r) .net host",
}

TITLE_SEPARATORS = (" - ", " | ", " — ", " – ", ":")


def get_app_path(hwnd) -> Optional[str]:
    """Get application path given hwnd."""
    path = None

    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = win32api.OpenProcess(
        0x0400, False, pid
    )  # PROCESS_QUERY_INFORMATION = 0x0400

    try:
        path = win32process.GetModuleFileNameEx(process, 0)
    finally:
        win32api.CloseHandle(process)

    return path


def _iter_version_info_candidates(path: str) -> Iterable[str]:
    try:
        translations = win32api.GetFileVersionInfo(path, r"\\VarFileInfo\\Translation")
    except Exception:
        translations = ()

    for language, codepage in translations:
        prefix = f"\\StringFileInfo\\{language:04X}{codepage:04X}\\"
        yield prefix + "FileDescription"
        yield prefix + "ProductName"

    yield r"\StringFileInfo\040904B0\FileDescription"
    yield r"\StringFileInfo\040904B0\ProductName"



def _is_preferred_display_name(candidate: Optional[str], process_name: str) -> bool:
    if candidate is None:
        return False

    normalized = candidate.strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if lowered == process_name.lower():
        return False

    if lowered == "unknown":
        return False

    return lowered not in GENERIC_DISPLAY_NAMES



def _extract_meaningful_title(window_title: str) -> str:
    normalized = window_title.strip()
    if not normalized:
        return ""

    cut_index = -1
    for separator in TITLE_SEPARATORS:
        index = normalized.find(separator)
        if index <= 0:
            continue
        if cut_index == -1 or index < cut_index:
            cut_index = index

    segment = normalized[:cut_index].strip() if cut_index > 0 else normalized

    if len(segment) < 2 or len(segment) > 64:
        return ""

    if ".exe" in segment.lower() or "\\" in segment or "/" in segment:
        return ""

    return segment



def _get_file_display_name(path: Optional[str], process_name: str) -> str:
    if not path:
        return process_name

    try:
        for candidate in _iter_version_info_candidates(path):
            value = win32api.GetFileVersionInfo(path, candidate)
            if _is_preferred_display_name(value, process_name):
                return value.strip()
    except Exception:
        pass

    return process_name



def _resolve_display_name(process_name: str, file_display_name: str, window_title: str) -> str:
    normalized_process_name = process_name.strip() if process_name else "unknown"
    if not normalized_process_name:
        normalized_process_name = "unknown"

    lowered_process_name = normalized_process_name.lower()
    if lowered_process_name == "unknown":
        return "unknown"

    if "minecraft" in window_title.lower():
        return "Minecraft"

    if lowered_process_name in HOST_PROCESS_NAMES:
        title_name = _extract_meaningful_title(window_title)
        if title_name:
            return title_name

    if _is_preferred_display_name(file_display_name, normalized_process_name):
        return file_display_name.strip()

    return normalized_process_name



def get_process_name(hwnd) -> Optional[str]:
    path = get_app_path(hwnd)
    if path is None:
        return None

    process_name = os.path.splitext(os.path.basename(path))[0].strip()
    return process_name or None


def get_app_name(hwnd) -> Optional[str]:
    """Get application display name given hwnd."""
    path = get_app_path(hwnd)

    if path is None:
        return None

    process_name = os.path.splitext(os.path.basename(path))[0].strip()
    if not process_name:
        return None

    title = get_window_title(hwnd) or ""
    file_display_name = _get_file_display_name(path, process_name)
    return _resolve_display_name(process_name, file_display_name, title)


def get_window_title(hwnd):
    return win32gui.GetWindowText(hwnd)


def get_active_window_handle():
    hwnd = win32gui.GetForegroundWindow()
    return hwnd


# WMI-version, used as fallback if win32gui/win32process/win32api fails (such as for "run as admin" processes)

c = wmi.WMI()

"""
Much of this derived from: http://stackoverflow.com/a/14973422/965332
"""


def get_process_name_wmi(hwnd) -> Optional[str]:
    process_name = None
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    for p in c.query("SELECT Name FROM Win32_Process WHERE ProcessId = %s" % str(pid)):
        process_name = p.Name
        break

    if process_name is None:
        return None

    process_name = os.path.splitext(process_name)[0].strip()
    return process_name or None


def get_app_name_wmi(hwnd) -> Optional[str]:
    """Get application display name given hwnd using WMI."""
    path = get_app_path_wmi(hwnd)
    process_name = None
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    for p in c.query("SELECT Name FROM Win32_Process WHERE ProcessId = %s" % str(pid)):
        process_name = p.Name
        break

    if process_name is None:
        return None

    process_name = os.path.splitext(process_name)[0].strip()
    if not process_name:
        return None

    title = get_window_title(hwnd) or ""
    file_display_name = _get_file_display_name(path, process_name)
    return _resolve_display_name(process_name, file_display_name, title)


def get_app_path_wmi(hwnd) -> Optional[str]:
    """Get application path given hwnd."""
    path = None

    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    for p in c.query(
        "SELECT ExecutablePath FROM Win32_Process WHERE ProcessId = %s" % str(pid)
    ):
        path = p.ExecutablePath
        break

    return path


if __name__ == "__main__":
    while True:
        hwnd = get_active_window_handle()
        print("Title:", get_window_title(hwnd))
        print("App:        ", get_app_name(hwnd))
        print("App (wmi):  ", get_app_name_wmi(hwnd))
        print("Path:       ", get_app_path(hwnd))
        print("Path (wmi): ", get_app_path_wmi(hwnd))

        time.sleep(1.0)
