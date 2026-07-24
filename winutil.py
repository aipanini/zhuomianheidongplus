# -*- coding: utf-8 -*-
"""Windows 平台工具：DPI 感知、窗口样式（穿透/置顶/不抢焦点）、
捕获排除（WDA_EXCLUDEFROMCAPTURE）、系统级全局热键、光标位置。

仅在 Windows 可用；其它平台退化为普通窗口 + pygame 鼠标。
所有 Win32 调用均显式声明 argtypes/restype，确保 64 位句柄不截断。
"""
import ctypes
import sys
from ctypes import wintypes

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    user32 = ctypes.windll.user32

    # ---- 常量 ----
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020   # 鼠标点击穿透
    WS_EX_TOPMOST = 0x00000008
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080    # 不出现在任务栏/Alt+Tab

    LWA_ALPHA = 0x00000002
    WDA_NONE = 0x0
    WDA_EXCLUDEFROMCAPTURE = 0x11

    MOD_CONTROL = 0x0002
    MOD_ALT = 0x0001
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    # 虚拟键码（用于 GetAsyncKeyState 修饰键检测）
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12      # Alt
    VK_LWIN = 0x5B
    WM_HOTKEY = 0x0312
    PM_REMOVE = 0x0001

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    HWND_TOPMOST = -1

    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD), ("pt", wintypes.POINT)]

    # ---- 函数原型（64 位安全）----
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF,
                                                  ctypes.c_byte, wintypes.DWORD]
    user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.MoveWindow.restype = wintypes.BOOL
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT,
                                    wintypes.UINT, wintypes.UINT]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    # GetAsyncKeyState：轮询物理按键状态，不依赖消息队列，pygame 无法干扰
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

    def _hwnd():
        import pygame
        info = pygame.display.get_wm_info()
        h = info.get("window") or info.get("hwnd")
        return ctypes.c_void_p(h) if h else None

    def set_dpi_aware():
        """按显示器 DPI 感知，使窗口像素与 mss 捕获的物理像素一致。"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
            return
        except Exception:
            pass
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    def style_window(click_through, topmost, no_activate, x, y, w, h):
        """应用扩展样式并定位窗口。返回是否成功。"""
        hwnd = _hwnd()
        if not hwnd:
            return False
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if topmost:
            ex |= WS_EX_TOPMOST
        if no_activate:
            ex |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        if click_through:
            ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            ex &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        if click_through:
            # alpha=255 完全不透明，但鼠标穿透
            user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
        # 定位并置顶
        flags = SWP_NOACTIVATE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, ctypes.c_void_p(HWND_TOPMOST if topmost else 0),
                            x, y, w, h, flags)
        return True

    def set_capture_exclusion(exclude):
        hwnd = _hwnd()
        if not hwnd:
            return False
        aff = WDA_EXCLUDEFROMCAPTURE if exclude else WDA_NONE
        return bool(user32.SetWindowDisplayAffinity(hwnd, aff))

    def get_cursor_pos():
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    class Hotkeys:
        """全局按键监听（基于 GetAsyncKeyState 轮询）。

        不依赖 Windows 消息队列，因此不会被 pygame/SDL2 的消息泵拦截，
        在鼠标穿透（窗口无焦点）模式下仍能稳定工作。
        每帧 poll() 检测按键「上升沿」（从松开到按下的瞬间），
        返回本帧触发的 vk 列表。带修饰键的组合需修饰键同时按下。
        """

        def __init__(self):
            self._entries = []   # [(vk, mod)]
            self._prev = {}      # vk -> bool（上一帧是否按下）

        def register(self, vk, mod=MOD_CONTROL | MOD_ALT):
            self._entries.append((vk, mod))
            # 初始化为当前状态，避免启动时按键已按下导致误触发
            self._prev[vk] = self._down(vk)
            return True  # GetAsyncKeyState 无需注册，始终可用

        @staticmethod
        def _down(vk):
            return (user32.GetAsyncKeyState(vk) & 0x8000) != 0

        def _mods_pressed(self, mod):
            if (mod & MOD_CONTROL) and not self._down(VK_CONTROL):
                return False
            if (mod & MOD_ALT) and not self._down(VK_MENU):
                return False
            if (mod & MOD_SHIFT) and not self._down(VK_SHIFT):
                return False
            if (mod & MOD_WIN) and not self._down(VK_LWIN):
                return False
            return True

        def poll(self):
            """返回本帧触发的 vk 列表（上升沿 + 修饰键满足）。"""
            out = []
            for vk, mod in self._entries:
                now = self._down(vk)
                prev = self._prev.get(vk, False)
                self._prev[vk] = now
                if now and not prev:
                    if mod == 0 or self._mods_pressed(mod):
                        out.append(vk)
            return out

        @property
        def failed(self):
            return []  # 轮询方案无注册失败

        def unregister_all(self):
            pass  # 无需注销

    _SPECIAL_VK = {"SPACE": 0x20, "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
                   "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
                   "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
                   "F11": 0x7A, "F12": 0x7B}

    def vk(name):
        name = name.upper()
        return _SPECIAL_VK.get(name, ord(name[0]))

else:
    # ---------- 非 Windows 退化实现 ----------
    def set_dpi_aware():
        pass

    def style_window(click_through, topmost, no_activate, x, y, w, h):
        return False

    def set_capture_exclusion(exclude):
        return False

    def get_cursor_pos():
        import pygame
        return pygame.mouse.get_pos()

    class Hotkeys:
        def register(self, vk, mod=0):
            return False

        def poll(self):
            return []

        @property
        def failed(self):
            return []

        def unregister_all(self):
            pass

    def vk(name):
        return 0
