# -*- coding: utf-8 -*-
"""桌面黑洞 —— 集中参数配置。

所有可调参数集中于此，便于调试与开源协作。
单位除特别说明外均为「像素」，基于主显示器物理分辨率。
"""

import os
import sys

# 程序根目录：打包成 exe 后，__file__ 指向临时解压目录，需要用 sys.executable
if getattr(sys, 'frozen', False) or "__compiled__" in dir(sys.modules.get('__main__', {})):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ===================== 窗口与捕获 =====================
FULLSCREEN = True             # 全屏无边框覆盖主显示器
CLICK_THROUGH = True          # 鼠标穿透：点击作用于真实桌面，形成"真黑洞"错觉
TOPMOST = True                # 窗口置顶
EXCLUDE_FROM_CAPTURE = True   # 将本窗口排除出屏幕捕获，避免反馈拖影（需 Win10 2004+）
NO_ACTIVATE = True            # 不抢占焦点（配合鼠标穿透，用全局热键控制）

# ===================== 黑洞物理与视觉 =====================
EVENT_HORIZON = 60.0          # 事件视界半径（纯黑核心，光无法逃逸）
EINSTEIN_RADIUS = 180.0       # 爱因斯坦半径：决定透镜扭曲强度与爱因斯坦环大小
WARP_BOOST = 1.0              # 广域扭曲增强（0=纯物理透镜，1=广域可见扭曲）
DISK_BRIGHTNESS = 1.2         # 吸积盘亮度倍数
STYLE = "gold"                # 风格：gold(金色) / fire(炽焰) / classic(经典橙红) / ghost(幽冥青) / purple(紫电)

# ===================== 鼠标吸入效果 =====================
MOUSE_PULL = 0.5              # 鼠标吸入强度（0=关闭，1=最强）

# ===================== 鼠标跟随（弹簧 + 阻尼，模拟物理惯性）=====================
FOLLOW_STIFFNESS = 0.012      # 弹簧刚度：越大跟随越紧
FOLLOW_DAMPING = 0.86         # 阻尼系数：越小惯性越大、越顺滑

# ===================== 渲染 =====================
TARGET_FPS = 60               # 目标帧率
VSYNC = True                  # 垂直同步
CLAMP_TO_SCREEN = True        # 限制黑洞中心不移出主屏可视区域

# ===================== 启动状态 =====================
VISIBLE_AT_START = False      # 启动时是否显示黑洞效果（默认不显示，通过F9或托盘开启）

# ===================== 全局热键 =====================
HOTKEY_QUIT = "Q"             # Ctrl+Alt+Q 退出程序
HOTKEY_TOGGLE = "SPACE"       # Ctrl+Alt+Space 显示/隐藏黑洞
HOTKEY_BIGGER = "UP"          # Ctrl+Alt+↑ 增大黑洞
HOTKEY_SMALLER = "DOWN"       # Ctrl+Alt+↓ 缩小黑洞
HOTKEY_TOGGLE_F9 = "F9"       # 单按 F9 显示/隐藏黑洞（推荐）
HOTKEY_PANEL = "F2"           # F2 打开参数面板

# ===================== 吞噬功能 =====================
SWALLOW_ENABLED = True        # 是否启用吞噬桌面图标
SWALLOW_RADIUS = 1.8          # 吞噬触发半径（事件视界的倍数）
SWALLOW_PATH = os.path.join(_APP_DIR, "资源", "被吞噬")
SWALLOW_SPEED = 0.15          # 图标被吸引的速度系数
SWALLOW_COOLDOWN = 0.0        # 吞噬冷却时间（秒），0=经过即吞噬，无需停顿
SWALLOW_GROWTH_RATE = 0.05    # 每吞噬一个图标，黑洞增大5%
ICON_RENDER_SIZE = 80         # 吸入动画中图标的渲染大小（像素）
