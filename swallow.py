# -*- coding: utf-8 -*-
"""桌面图标吞噬模块。

检测桌面文件/文件夹，当黑洞靠近时将其吸引并"吞噬"（移动到预设路径）。
通过 Windows API 获取桌面图标的真实屏幕位置。
"""

import os
import shutil
import time
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    SIZE_T = ctypes.c_size_t

    LVM_GETITEMCOUNT = 0x1004
    LVM_GETITEMTEXT = 0x102D
    LVM_GETITEMPOSITION = 0x1010

    LVIF_TEXT = 0x0001

    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    MEM_RELEASE = 0x8000
    PAGE_READWRITE = 0x04

    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    PROCESS_QUERY_INFORMATION = 0x0400


@dataclass
class DesktopItem:
    """桌面项目"""
    path: str
    name: str
    is_dir: bool
    pos: Tuple[float, float] = (0.0, 0.0)
    original_pos: Tuple[int, int] = (0, 0)
    being_swallowed: bool = False
    swallow_progress: float = 0.0
    angle: float = 0.0
    swirled: bool = False


class SwallowManager:
    """吞噬管理器。"""

    def __init__(self, swallow_path: str, swallow_radius: float = 1.8,
                 swallow_speed: float = 0.15, cooldown: float = 2.0):
        self.swallow_path = swallow_path
        self.swallow_radius_mult = swallow_radius
        self.swallow_speed = swallow_speed
        self.cooldown = cooldown

        os.makedirs(swallow_path, exist_ok=True)

        self.items: List[DesktopItem] = []
        self.last_swallow_time = 0.0
        self._desktop_path = self._get_desktop_path()
        self._last_refresh = 0.0
        self.refresh_items()

    def _get_desktop_path(self) -> str:
        """获取桌面路径。"""
        try:
            CSIDL_DESKTOPDIRECTORY = 0x0010
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(
                0, CSIDL_DESKTOPDIRECTORY, 0, SHGFP_TYPE_CURRENT, buf
            )
            return buf.value
        except Exception:
            return os.path.join(os.path.expanduser("~"), "Desktop")

    def _find_desktop_listview(self) -> Optional[int]:
        """找到桌面 ListView 控件句柄。"""
        if not IS_WINDOWS:
            return None
        try:
            hwnd = user32.FindWindowW("Progman", "Program Manager")
            if hwnd:
                hwnd = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
            if hwnd:
                hwnd = user32.FindWindowExW(hwnd, 0, "SysListView32", None)
            if hwnd:
                return hwnd
            # Win10/11 可能在 WorkerW 中
            workerw = 0
            while True:
                workerw = user32.FindWindowExW(0, workerw, "WorkerW", None)
                if not workerw:
                    break
                defview = user32.FindWindowExW(workerw, 0, "SHELLDLL_DefView", None)
                if defview:
                    lv = user32.FindWindowExW(defview, 0, "SysListView32", None)
                    if lv:
                        return lv
            return None
        except Exception:
            return None

    def _get_desktop_icon_positions(self) -> Dict[str, Tuple[int, int]]:
        """获取桌面图标名称->屏幕位置的映射。"""
        if not IS_WINDOWS:
            return {}
        hwnd = self._find_desktop_listview()
        if not hwnd:
            return {}

        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return {}

            h_proc = kernel32.OpenProcess(
                PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
                False, pid.value
            )
            if not h_proc:
                return {}

            try:
                count = user32.SendMessageW(hwnd, LVM_GETITEMCOUNT, 0, 0)
                if count <= 0 or count > 500:
                    return {}

                point_size = ctypes.sizeof(wintypes.POINT)
                mem_size = 2048
                mem = kernel32.VirtualAllocEx(
                    h_proc, None, mem_size,
                    MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
                )
                if not mem:
                    return {}

                try:
                    result = {}
                    # 获取桌面 ListView 客户区原点的屏幕坐标
                    pt0 = wintypes.POINT()
                    pt0.x = 0
                    pt0.y = 0
                    user32.ClientToScreen(hwnd, ctypes.byref(pt0))
                    offset_x = pt0.x
                    offset_y = pt0.y

                    # ANSI 版本的 LVITEM
                    class LVITEMA(ctypes.Structure):
                        _fields_ = [
                            ("mask", wintypes.UINT),
                            ("iItem", ctypes.c_int),
                            ("iSubItem", ctypes.c_int),
                            ("state", wintypes.UINT),
                            ("stateMask", wintypes.UINT),
                            ("pszText", wintypes.LPVOID),
                            ("cchTextMax", ctypes.c_int),
                            ("iImage", ctypes.c_int),
                            ("lParam", wintypes.LPARAM),
                        ]

                    lvitem_size = ctypes.sizeof(LVITEMA)
                    pos_addr = mem
                    lvitem_addr = mem + point_size + 32
                    text_addr = lvitem_addr + lvitem_size + 32

                    for i in range(count):
                        # 位置
                        if user32.SendMessageW(hwnd, LVM_GETITEMPOSITION, i, pos_addr) == 0:
                            continue
                        pt = wintypes.POINT()
                        bytes_read = SIZE_T()
                        if not kernel32.ReadProcessMemory(
                            h_proc, pos_addr, ctypes.byref(pt), point_size, ctypes.byref(bytes_read)
                        ):
                            continue

                        # 文本（用 ANSI 版本）
                        lvitem = LVITEMA()
                        lvitem.mask = LVIF_TEXT
                        lvitem.iItem = i
                        lvitem.iSubItem = 0
                        lvitem.pszText = text_addr
                        lvitem.cchTextMax = 260

                        if not kernel32.WriteProcessMemory(
                            h_proc, lvitem_addr, ctypes.byref(lvitem),
                            lvitem_size, None
                        ):
                            continue

                        res = user32.SendMessageA(hwnd, LVM_GETITEMTEXT, i, lvitem_addr)
                        if res <= 0:
                            continue

                        raw_buf = (ctypes.c_ubyte * 260)()
                        if not kernel32.ReadProcessMemory(
                            h_proc, text_addr, raw_buf, 260, ctypes.byref(bytes_read)
                        ):
                            continue

                        raw_bytes = bytes(raw_buf[:res])
                        try:
                            name = raw_bytes.decode("gbk")
                        except UnicodeDecodeError:
                            try:
                                name = raw_bytes.decode("utf-8")
                            except UnicodeDecodeError:
                                name = raw_bytes.decode("gbk", errors="replace")

                        if name:
                            result[name] = (pt.x + offset_x, pt.y + offset_y)

                    return result
                finally:
                    kernel32.VirtualFreeEx(h_proc, mem, 0, MEM_RELEASE)
            finally:
                kernel32.CloseHandle(h_proc)
        except Exception as e:
            print(f"[吞噬] 获取图标位置失败: {e}")
            return {}

    def _match_name(self, display_name: str, file_name: str) -> bool:
        """判断 ListView 显示名是否匹配文件名。

        ListView 通常隐藏已知扩展名（如 .lnk），所以需要模糊匹配。
        """
        if display_name == file_name:
            return True
        # 去掉扩展名后比较
        base = os.path.splitext(file_name)[0]
        if display_name == base:
            return True
        # 大小写不敏感比较
        if display_name.lower() == file_name.lower():
            return True
        if display_name.lower() == base.lower():
            return True
        return False

    def refresh_items(self):
        """刷新桌面项目列表，并获取真实位置。"""
        if not os.path.isdir(self._desktop_path):
            return

        positions = self._get_desktop_icon_positions() if IS_WINDOWS else {}

        items = []
        # 构建文件系统中的文件列表
        fs_files = []
        for name in os.listdir(self._desktop_path):
            full_path = os.path.join(self._desktop_path, name)
            if name.startswith(".") or name == "被吞噬":
                continue
            if name.lower() == "desktop.ini":
                continue
            is_dir = os.path.isdir(full_path)
            fs_files.append((name, full_path, is_dir))

        # 匹配 ListView 中的位置和文件系统中的文件
        matched = set()
        for disp_name, pos in positions.items():
            for fs_name, fs_path, fs_is_dir in fs_files:
                if fs_name in matched:
                    continue
                if self._match_name(disp_name, fs_name):
                    items.append(DesktopItem(
                        path=fs_path,
                        name=fs_name,
                        is_dir=fs_is_dir,
                        original_pos=pos,
                    ))
                    matched.add(fs_name)
                    break

        # 没有匹配到位置的文件也加入（位置为 0,0，吞噬时跳过）
        for fs_name, fs_path, fs_is_dir in fs_files:
            if fs_name not in matched:
                items.append(DesktopItem(
                    path=fs_path,
                    name=fs_name,
                    is_dir=fs_is_dir,
                    original_pos=(0, 0),
                ))

        self.items = items
        self._last_refresh = time.time()

    def _maybe_refresh(self):
        """定期刷新（每5秒），应对桌面图标变化。"""
        now = time.time()
        if now - self._last_refresh > 5.0:
            self.refresh_items()

    def get_nearby_items(self, bh_x: float, bh_y: float,
                         event_horizon: float) -> List[DesktopItem]:
        """获取黑洞附近的桌面项目。"""
        radius = event_horizon * self.swallow_radius_mult
        nearby = []
        for item in self.items:
            ix, iy = item.original_pos
            if ix == 0 and iy == 0:
                continue
            dx = ix - bh_x
            dy = iy - bh_y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < radius:
                nearby.append(item)
        return nearby

    def update(self, bh_x: float, bh_y: float, event_horizon: float,
               dt: float) -> List[str]:
        """更新吞噬状态。

        返回被吞噬的文件名列表。
        """
        self._maybe_refresh()

        swallowed = []
        now = time.time()
        radius = event_horizon * self.swallow_radius_mult
        horizon = event_horizon * 0.5

        for item in list(self.items):
            ix, iy = item.pos if item.being_swallowed else item.original_pos
            if ix == 0 and iy == 0:
                continue
            dx = bh_x - ix
            dy = bh_y - iy
            dist = (dx * dx + dy * dy) ** 0.5

            if not item.being_swallowed and dist < radius and dist > 1:
                if now - self.last_swallow_time > self.cooldown:
                    item.being_swallowed = True
                    item.pos = (float(ix), float(iy))
                    item.angle = 0.0
                    item.swirled = False

            if item.being_swallowed:
                item.angle += dt * 3.0
                speed = self.swallow_speed * (1.0 + item.swallow_progress * 3.0)
                item.swallow_progress += dt * speed

                if dist > 1:
                    pull = speed * dt * 200.0
                    nx = item.pos[0] + dx / dist * pull
                    ny = item.pos[1] + dy / dist * pull
                    swirl = 15.0 * (1.0 - item.swallow_progress)
                    perp_x = -dy / dist * swirl
                    perp_y = dx / dist * swirl
                    item.pos = (nx + perp_x * dt, ny + perp_y * dt)

                if item.swallow_progress >= 1.0 or dist < horizon:
                    self._do_swallow(item)
                    swallowed.append(item.name)
                    self.items.remove(item)
                    self.last_swallow_time = now

        return swallowed

    def _do_swallow(self, item: DesktopItem):
        """执行吞噬：移动文件到预设路径。"""
        try:
            base_name = item.name
            dest = os.path.join(self.swallow_path, base_name)
            counter = 1
            name, ext = os.path.splitext(base_name)
            while os.path.exists(dest):
                dest = os.path.join(self.swallow_path, f"{name}_{counter}{ext}")
                counter += 1
            shutil.move(item.path, dest)
        except Exception as e:
            print(f"吞噬失败: {item.name}: {e}")

    def get_items_for_render(self) -> List[dict]:
        """获取需要渲染的项目（正在被吞噬的）。"""
        result = []
        for item in self.items:
            if item.being_swallowed:
                result.append({
                    "name": item.name,
                    "pos": item.pos,
                    "original_pos": item.original_pos,
                    "progress": item.swallow_progress,
                    "angle": item.angle,
                    "is_dir": item.is_dir,
                })
        return result

    def restore_all(self):
        """恢复所有被吞噬的文件到桌面。"""
        if not os.path.isdir(self.swallow_path):
            return 0
        count = 0
        for name in os.listdir(self.swallow_path):
            src = os.path.join(self.swallow_path, name)
            dst = os.path.join(self._desktop_path, name)
            try:
                shutil.move(src, dst)
                count += 1
            except Exception as e:
                print(f"恢复失败: {name}: {e}")
        self.refresh_items()
        return count
