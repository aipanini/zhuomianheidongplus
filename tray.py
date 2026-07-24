# -*- coding: utf-8 -*-
"""系统托盘控制。

主循环与托盘运行在不同线程，通过 TrayState 共享变量通信：
  - 主循环每帧轮询 state.poll() 获取待执行命令
  - 托盘菜单回调将命令追加到队列
  - state.quit_event 用于通知主循环退出
"""
import threading
import queue

from PIL import Image, ImageDraw
import pystray


class TrayState:
    """托盘与主循环的共享状态。"""

    def __init__(self):
        self.cmds = queue.Queue()      # 待执行命令：toggle / bigger / smaller / reset / quit
        self.quit_event = threading.Event()

    def push(self, cmd):
        self.cmds.put(cmd)

    def poll(self):
        """取出并返回所有待执行命令（列表）。"""
        out = []
        while not self.cmds.empty():
            try:
                out.append(self.cmds.get_nowait())
            except queue.Empty:
                break
        return out


def _make_icon():
    """程序生成托盘图标：黑圆心 + 橙色吸积盘环 + 透明背景。"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    # 外发光
    for i, a in enumerate([20, 40, 70]):
        r = 30 - i * 4
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 140, 30, a))
    # 橙色吸积盘环
    d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(255, 150, 40, 230))
    # 黑色事件视界
    d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(0, 0, 0, 255))
    return img


def _menu(state):
    return pystray.Menu(
        pystray.MenuItem("显示 / 关闭黑洞", lambda: state.push("toggle"), default=True),
        pystray.MenuItem("显示 / 关闭控制台", lambda: state.push("panel")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda: (state.push("quit"), state.quit_event.set())),
    )


def start(state):
    """启动托盘图标（后台线程）。返回 pystray.Icon。"""
    icon = pystray.Icon("blackhole", _make_icon(), "黑洞引力透镜", _menu(state))
    t = threading.Thread(target=icon.run, daemon=True)
    t.start()
    return icon
