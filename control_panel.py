# -*- coding: utf-8 -*-
"""黑洞参数控制面板（tkinter）。

轻量级、功能全的独立调节窗口。
"""

import tkinter as tk
from tkinter import ttk, filedialog
import os
import threading


class ControlPanel:
    """参数控制面板。"""

    def __init__(self, config, on_change=None):
        self.config = config
        self.on_change = on_change
        self._window = None
        self._running = False
        self._thread = None

    def _build_ui(self):
        """构建界面。"""
        self._window = tk.Tk()
        self._window.title("黑洞控制台")
        self._window.geometry("380x680")
        self._window.resizable(False, False)
        self._window.attributes("-topmost", True)

        canvas = tk.Canvas(self._window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._window, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        pad = {"padx": 10, "pady": 4}

        # ---- 黑洞参数 ----
        ttk.Label(frame, text="● 黑洞参数", font=("", 11, "bold")).pack(anchor="w", **pad)
        self._add_slider(frame, "事件视界", "EVENT_HORIZON", 20, 200, 1.0)
        self._add_slider(frame, "爱因斯坦半径", "EINSTEIN_RADIUS", 60, 400, 1.0)
        self._add_slider(frame, "扭曲增强", "WARP_BOOST", 0.0, 2.0, 0.05)
        self._add_slider(frame, "吸积盘亮度", "DISK_BRIGHTNESS", 0.0, 3.0, 0.05)

        # ---- 风格选择 ----
        ttk.Label(frame, text="● 风格", font=("", 11, "bold")).pack(anchor="w", **pad)
        style_frame = ttk.Frame(frame)
        style_frame.pack(fill="x", **pad)
        self._style_var = tk.StringVar(value=self.config.STYLE)
        styles = [("金色", "gold"), ("炽焰", "fire"), ("经典橙红", "classic"),
                  ("幽冥青", "ghost"), ("紫电", "purple")]
        for text, val in styles:
            ttk.Radiobutton(style_frame, text=text, value=val,
                            variable=self._style_var,
                            command=self._on_style_change).pack(side="left", padx=2)

        # ---- 鼠标吸入 ----
        ttk.Label(frame, text="● 鼠标吸入", font=("", 11, "bold")).pack(anchor="w", **pad)
        self._add_slider(frame, "吸入强度", "MOUSE_PULL", 0.0, 1.0, 0.02)

        # ---- 跟随参数 ----
        ttk.Label(frame, text="● 鼠标跟随", font=("", 11, "bold")).pack(anchor="w", **pad)
        self._add_slider(frame, "弹簧刚度", "FOLLOW_STIFFNESS", 0.002, 0.05, 0.001)
        self._add_slider(frame, "阻尼系数", "FOLLOW_DAMPING", 0.7, 0.99, 0.005)

        # ---- 吞噬功能 ----
        ttk.Label(frame, text="● 吞噬功能", font=("", 11, "bold")).pack(anchor="w", **pad)
        self._swallow_var = tk.BooleanVar(value=self.config.SWALLOW_ENABLED)
        ttk.Checkbutton(frame, text="启用吞噬", variable=self._swallow_var,
                        command=self._on_swallow_toggle).pack(anchor="w", **pad)
        self._add_slider(frame, "吞噬半径", "SWALLOW_RADIUS", 1.0, 4.0, 0.1)
        self._add_slider(frame, "吸引速度", "SWALLOW_SPEED", 0.02, 0.5, 0.01)

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill="x", **pad)
        ttk.Label(path_frame, text="吞噬路径:").pack(side="left")
        self._path_var = tk.StringVar(value=self.config.SWALLOW_PATH)
        path_entry = ttk.Entry(path_frame, textvariable=self._path_var, width=22)
        path_entry.pack(side="left", padx=4)
        ttk.Button(path_frame, text="...", width=3,
                   command=self._choose_path).pack(side="left")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", **pad)
        ttk.Button(btn_frame, text="恢复所有文件",
                   command=self._on_restore).pack(side="left")

        # ---- 快捷操作 ----
        ttk.Label(frame, text="● 快捷操作", font=("", 11, "bold")).pack(anchor="w", **pad)
        btn_frame2 = ttk.Frame(frame)
        btn_frame2.pack(fill="x", **pad)
        ttk.Button(btn_frame2, text="显示 / 隐藏 (F9)",
                   command=self._on_toggle).pack(side="left", padx=2)
        ttk.Button(btn_frame2, text="退出程序",
                   command=self._on_quit).pack(side="left", padx=2)

        # ---- 预设 ----
        ttk.Label(frame, text="● 预设", font=("", 11, "bold")).pack(anchor="w", **pad)
        preset_frame = ttk.Frame(frame)
        preset_frame.pack(fill="x", **pad)
        presets = [("微型", "tiny"), ("标准", "normal"), ("巨型", "huge"), ("狂暴", "chaos")]
        for text, val in presets:
            ttk.Button(preset_frame, text=text, width=6,
                       command=lambda v=val: self._apply_preset(v)).pack(side="left", padx=2)

        # ---- 热键说明 ----
        ttk.Separator(frame).pack(fill="x", pady=6)
        ttk.Label(frame, text="热键:", font=("", 9, "bold")).pack(anchor="w", padx=10)
        hotkeys = [
            "F9 - 显示/隐藏黑洞",
            "F2 - 打开此面板",
            "Ctrl+Alt+Space - 切换显示",
            "Ctrl+Alt+↑/↓ - 增大/缩小",
            "Ctrl+Alt+Q - 退出程序",
        ]
        for hk in hotkeys:
            ttk.Label(frame, text="  " + hk, font=("", 9)).pack(anchor="w", padx=10)

    def _add_slider(self, parent, label, attr, min_val, max_val, step):
        """添加滑块。"""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=10, pady=2)
        ttk.Label(frame, text=label, width=12, anchor="w").pack(side="left")

        current = getattr(self.config, attr)
        var = tk.DoubleVar(value=current)
        val_label = ttk.Label(frame, text=f"{current:.3g}", width=8, anchor="e")
        val_label.pack(side="right")

        def on_change(v):
            val = float(v)
            setattr(self.config, attr, val)
            val_label.config(text=f"{val:.3g}")
            if self.on_change:
                self.on_change(attr, val)

        scale = ttk.Scale(frame, from_=min_val, to=max_val, orient="horizontal",
                          variable=var, command=on_change)
        scale.pack(side="left", fill="x", expand=True, padx=6)

    def _on_style_change(self):
        self.config.STYLE = self._style_var.get()
        if self.on_change:
            self.on_change("STYLE", self.config.STYLE)

    def _on_swallow_toggle(self):
        self.config.SWALLOW_ENABLED = self._swallow_var.get()
        if self.on_change:
            self.on_change("SWALLOW_ENABLED", self.config.SWALLOW_ENABLED)

    def _choose_path(self):
        path = filedialog.askdirectory(initialdir=self.config.SWALLOW_PATH,
                                       title="选择吞噬文件存放路径")
        if path:
            self.config.SWALLOW_PATH = path
            self._path_var.set(path)
            if self.on_change:
                self.on_change("SWALLOW_PATH", path)

    def _on_restore(self):
        if self.on_change:
            self.on_change("RESTORE", None)

    def _on_toggle(self):
        if self.on_change:
            self.on_change("TOGGLE", None)

    def _on_quit(self):
        if self.on_change:
            self.on_change("QUIT", None)
        self.hide()

    def _apply_preset(self, name: str):
        presets = {
            "tiny":   {"EVENT_HORIZON": 25,  "EINSTEIN_RADIUS": 80,  "DISK_BRIGHTNESS": 0.8, "WARP_BOOST": 0.5},
            "normal": {"EVENT_HORIZON": 60,  "EINSTEIN_RADIUS": 180, "DISK_BRIGHTNESS": 1.2, "WARP_BOOST": 1.0},
            "huge":   {"EVENT_HORIZON": 120, "EINSTEIN_RADIUS": 300, "DISK_BRIGHTNESS": 1.5, "WARP_BOOST": 1.5},
            "chaos":  {"EVENT_HORIZON": 180, "EINSTEIN_RADIUS": 400, "DISK_BRIGHTNESS": 2.5, "WARP_BOOST": 2.0},
        }
        p = presets.get(name)
        if not p:
            return
        for attr, val in p.items():
            setattr(self.config, attr, val)
        if self.on_change:
            for attr, val in p.items():
                self.on_change(attr, val)
        self._refresh_sliders()

    def _refresh_sliders(self):
        """刷新滑块显示。"""
        if not self._window:
            return
        self._window.update_idletasks()

    def show(self):
        """显示面板。"""
        if self._running and self._window:
            try:
                self._window.deiconify()
                self._window.lift()
                return
            except Exception:
                self._running = False

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def hide(self):
        """隐藏面板。"""
        if self._window:
            try:
                self._window.withdraw()
            except Exception:
                pass

    def _run(self):
        self._running = True
        self._build_ui()
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)
        self._window.mainloop()
        self._running = False

    def _on_close(self):
        self._window.withdraw()

    def is_visible(self) -> bool:
        if not self._window or not self._running:
            return False
        try:
            return self._window.state() == "normal"
        except Exception:
            return False
