import ctypes
import logging
import math
import threading
from ctypes import POINTER, WINFUNCTYPE, byref, sizeof
from ctypes.wintypes import BOOL, DWORD, HHOOK, HINSTANCE, HWND, LPARAM, MSG, POINT, WPARAM
from typing import Dict, Optional, Tuple

from aw_watcher_window.lib import get_current_window_windows

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0

WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_XBUTTONDOWN = 0x020B
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E

XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
WHEEL_DELTA = 120
MAX_SEGMENT_DISTANCE = 250.0

ULONG_PTR = ctypes.c_ulonglong if sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
LRESULT = LPARAM

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, HINSTANCE, DWORD]
user32.SetWindowsHookExW.restype = HHOOK
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostThreadMessageW.argtypes = [DWORD, ctypes.c_uint, WPARAM, LPARAM]
user32.PostThreadMessageW.restype = BOOL
kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.GetModuleHandleW.restype = HINSTANCE
kernel32.GetCurrentThreadId.restype = DWORD


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", DWORD),
        ("scanCode", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


LowLevelKeyboardProc = WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
LowLevelMouseProc = WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)


class WindowsHookInputSource:
    def __init__(self) -> None:
        self.new_event = threading.Event()
        self._lock = threading.Lock()
        self._event_data = self._empty_data()
        self._pressed_keys = set()
        self._last_mouse_position: Optional[Tuple[int, int]] = None
        self._keyboard_hook: Optional[int] = None
        self._mouse_hook: Optional[int] = None
        self._keyboard_proc = None
        self._mouse_proc = None
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._started = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._running = False

    def _empty_data(self) -> Dict[str, int]:
        return {
            "presses": 0,
            "clicks": 0,
            "scrollX": 0,
            "scrollY": 0,
            "deltaX": 0,
            "deltaY": 0,
        }

    def start(self) -> None:
        if self._running:
            return
        self._started.clear()
        self._startup_error = None
        self._thread = threading.Thread(target=self._message_loop, name="aw-input-hook", daemon=True)
        self._thread.start()
        self._started.wait(timeout=5)
        if self._startup_error is not None:
            raise self._startup_error
        if not self._running:
            raise RuntimeError("Failed to start Windows input hooks")

    def stop(self) -> None:
        if not self._running:
            return
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        self._thread_id = None
        self._running = False

    def has_new_event(self) -> bool:
        return self.new_event.is_set()

    def next_event(self) -> Dict[str, int]:
        with self._lock:
            self.new_event.clear()
            data = dict(self._event_data)
            self._event_data = self._empty_data()
            return data

    def handle_key_message(self, message: int, vk_code: int) -> None:
        with self._lock:
            if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if vk_code not in self._pressed_keys:
                    self._pressed_keys.add(vk_code)
                    self._event_data["presses"] += 1
                    self.new_event.set()
            elif message in (WM_KEYUP, WM_SYSKEYUP):
                self._pressed_keys.discard(vk_code)

    def handle_mouse_click(self) -> None:
        with self._lock:
            self._event_data["clicks"] += 1
            self.new_event.set()

    def handle_mouse_scroll(self, delta: int, horizontal: bool = False) -> None:
        ticks = abs(int(delta)) // WHEEL_DELTA
        if ticks <= 0:
            return
        with self._lock:
            if horizontal:
                self._event_data["scrollX"] += ticks
            else:
                self._event_data["scrollY"] += ticks
            self.new_event.set()

    def handle_mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            if self._last_mouse_position is None:
                self._last_mouse_position = (x, y)
                return

            last_x, last_y = self._last_mouse_position
            dx = x - last_x
            dy = y - last_y
            segment_distance = math.sqrt(dx * dx + dy * dy)
            self._last_mouse_position = (x, y)

            if segment_distance > MAX_SEGMENT_DISTANCE:
                return

            self._event_data["deltaX"] += abs(dx)
            self._event_data["deltaY"] += abs(dy)
            if dx or dy:
                self.new_event.set()

    def _keyboard_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            hook = ctypes.cast(l_param, POINTER(KBDLLHOOKSTRUCT)).contents
            self.handle_key_message(int(w_param), int(hook.vkCode))
        return user32.CallNextHookEx(self._keyboard_hook or 0, n_code, w_param, l_param)

    def _mouse_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            hook = ctypes.cast(l_param, POINTER(MSLLHOOKSTRUCT)).contents
            message = int(w_param)
            if message in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN):
                self.handle_mouse_click()
            elif message == WM_MOUSEMOVE:
                self.handle_mouse_move(int(hook.pt.x), int(hook.pt.y))
            elif message == WM_MOUSEWHEEL:
                self.handle_mouse_scroll(_signed_high_word(hook.mouseData), horizontal=False)
            elif message == WM_MOUSEHWHEEL:
                self.handle_mouse_scroll(_signed_high_word(hook.mouseData), horizontal=True)
        return user32.CallNextHookEx(self._mouse_hook or 0, n_code, w_param, l_param)

    def _message_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        self._keyboard_proc = LowLevelKeyboardProc(self._keyboard_callback)
        self._mouse_proc = LowLevelMouseProc(self._mouse_callback)
        module_handle = kernel32.GetModuleHandleW(None)

        try:
            self._keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                ctypes.cast(self._keyboard_proc, ctypes.c_void_p),
                HINSTANCE(module_handle),
                0,
            )
            if not self._keyboard_hook:
                raise ctypes.WinError(ctypes.get_last_error())

            self._mouse_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL,
                ctypes.cast(self._mouse_proc, ctypes.c_void_p),
                HINSTANCE(module_handle),
                0,
            )
            if not self._mouse_hook:
                raise ctypes.WinError(ctypes.get_last_error())

            self._running = True
            self._started.set()

            msg = MSG()
            while user32.GetMessageW(byref(msg), HWND(0), 0, 0) != 0:
                user32.TranslateMessage(byref(msg))
                user32.DispatchMessageW(byref(msg))
        except BaseException as exc:
            self._startup_error = exc
            logger.exception("Failed to start Windows low-level input hooks")
            self._started.set()
        finally:
            if self._keyboard_hook:
                user32.UnhookWindowsHookEx(HHOOK(self._keyboard_hook))
                self._keyboard_hook = None
            if self._mouse_hook:
                user32.UnhookWindowsHookEx(HHOOK(self._mouse_hook))
                self._mouse_hook = None
            self._running = False


def _signed_high_word(value: int) -> int:
    high = (int(value) >> 16) & 0xFFFF
    return ctypes.c_short(high).value


def get_active_window_context() -> Dict[str, str]:
    try:
        current_window = get_current_window_windows()
    except Exception:
        return {}

    if not current_window:
        return {}

    data: Dict[str, str] = {}
    app = current_window.get("app")
    title = current_window.get("title")
    display_name = current_window.get("display_name")
    if isinstance(app, str) and app:
        data["app"] = app
    if isinstance(title, str) and title:
        data["title"] = title
    if isinstance(display_name, str) and display_name:
        data["display_name"] = display_name
    return data
