# -*- coding: utf-8 -*-
"""黑洞引力透镜 —— 桌面实时特效（MVP）

流程：
  1. 创建全屏、置顶、鼠标穿透、捕获排除的无边框 OpenGL 窗口；
  2. 每帧用 mss 捕获真实桌面（不含本窗口）上传为纹理；
  3. GLSL 点质量引力透镜着色器对背景做扭曲采样；
  4. 叠加事件视界（纯黑）与吸积盘（旋转 + 多普勒 + 软发光）；
  5. 黑洞以「弹簧 + 阻尼」平滑跟随鼠标，模拟物理惯性。

控制：见 config.py 的全局热键（默认 Ctrl+Alt+Q/Space/↑/↓）。
"""
import os
import sys
import time
import math

import numpy as np
import mss
import pygame
from OpenGL.GL import *

import config as C
import winutil as W
import tray
from swallow import SwallowManager

try:
    from web_panel import ControlPanel
    HAS_PANEL = True
except ImportError:
    HAS_PANEL = False

import sys

# 程序根目录：打包成 exe 后用 sys.executable，开发时用 __file__
#   BASE        → exe 所在目录（用于用户数据，如被吞噬文件的存放路径）
#   _BUNDLE_DIR → 打包资源解压目录（用于只读资源，如着色器、BGM）
if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE
SHADER_DIR = os.path.join(_BUNDLE_DIR, "shaders")

STYLE_MAP = {"gold": 0.0, "fire": 1.0, "classic": 2.0, "ghost": 3.0, "purple": 4.0}


# ---------------------------------------------------------------- 着色器
def _compile(path, shader_type):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    sh = glCreateShader(shader_type)
    glShaderSource(sh, src)
    glCompileShader(sh)
    if glGetShaderiv(sh, GL_COMPILE_STATUS) != GL_TRUE:
        log = glGetShaderInfoLog(sh)
        log = log.decode("utf-8", "ignore") if isinstance(log, bytes) else str(log)
        raise RuntimeError("着色器编译失败 %s:\n%s" % (path, log))
    return sh


def build_program():
    vs = _compile(os.path.join(SHADER_DIR, "lens.vert"), GL_VERTEX_SHADER)
    fs = _compile(os.path.join(SHADER_DIR, "lens.frag"), GL_FRAGMENT_SHADER)
    prog = glCreateProgram()
    glAttachShader(prog, vs)
    glAttachShader(prog, fs)
    glLinkProgram(prog)
    if glGetProgramiv(prog, GL_LINK_STATUS) != GL_TRUE:
        log = glGetProgramInfoLog(prog)
        log = log.decode("utf-8", "ignore") if isinstance(log, bytes) else str(log)
        raise RuntimeError("着色器链接失败:\n%s" % log)
    glDeleteShader(vs)
    glDeleteShader(fs)
    return prog


# ---------------------------------------------------------------- 主循环
def main():
    W.set_dpi_aware()

    # 主显示器物理分辨率
    with mss.MSS() as s:
        mon = dict(s.monitors[1])  # 主显示器 {left,top,width,height}
    mw, mh = mon["width"], mon["height"]
    mleft, mtop = mon["left"], mon["top"]

    # 窗口初始定位（SDL 在 set_mode 时读取）
    os.environ["SDL_VIDEO_WINDOW_POS"] = "%d,%d" % (mleft, mtop)
    os.environ.setdefault("SDL_VIDEO_CENTERED", "0")

    pygame.init()
    flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME
    try:
        screen = pygame.display.set_mode((mw, mh), flags, vsync=int(C.VSYNC))
    except TypeError:
        screen = pygame.display.set_mode((mw, mh), flags)
    pygame.display.set_caption("Desktop Blackhole Plus")

    prog = build_program()

    # 全屏四边形
    quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype=np.float32)
    vbo = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
    a_pos = glGetAttribLocation(prog, "aPos")
    glEnableVertexAttribArray(a_pos)
    glVertexAttribPointer(a_pos, 2, GL_FLOAT, GL_FALSE, 0, None)

    # 背景纹理（BGRA，与 mss 输出一致）
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, mw, mh, 0, GL_BGRA, GL_UNSIGNED_BYTE, None)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    def U(name):
        return glGetUniformLocation(prog, name)

    u_res = U("uResolution")
    u_bh = U("uBlackHole")
    u_mouse = U("uMouse")
    u_ein = U("uEinsteinR")
    u_eh = U("uEventHorizon")
    u_time = U("uTime")
    u_disk = U("uDiskBright")
    u_warp = U("uWarpBoost")
    u_mouse_pull = U("uMousePull")
    u_style = U("uStyle")
    u_vis = U("uVisible")
    u_bg = U("uBg")
    # 吞噬图标渲染 uniform
    u_swallow_count = U("uSwallowCount")
    u_swallow_pos = [U("uSwallowPos[%d]" % i) for i in range(8)]
    u_swallow_orig = [U("uSwallowOrig[%d]" % i) for i in range(8)]
    u_swallow_prog = [U("uSwallowProg[%d]" % i) for i in range(8)]
    u_swallow_ang = [U("uSwallowAng[%d]" % i) for i in range(8)]
    u_icon_size = U("uIconSize")
    u_shake = U("uShake")

    # 窗口样式 / 捕获排除
    no_activate = C.NO_ACTIVATE if C.CLICK_THROUGH else False
    W.style_window(C.CLICK_THROUGH, C.TOPMOST, no_activate, mleft, mtop, mw, mh)
    excl = W.set_capture_exclusion(C.EXCLUDE_FROM_CAPTURE)
    if C.EXCLUDE_FROM_CAPTURE and not excl:
        print("[警告] 捕获排除失败（需 Windows 10 2004+），可能出现反馈拖影。", file=sys.stderr)

    # 全局热键
    hk = W.Hotkeys()
    bindings = {
        W.vk(C.HOTKEY_QUIT): "quit",
        W.vk(C.HOTKEY_TOGGLE): "toggle",
        W.vk(C.HOTKEY_BIGGER): "bigger",
        W.vk(C.HOTKEY_SMALLER): "smaller",
    }
    for vk in bindings:
        hk.register(vk)
    # F9 单键切换（无修饰键，注册为 mod=0）
    f9_vk = W.vk(C.HOTKEY_TOGGLE_F9)
    if hk.register(f9_vk, mod=0):
        bindings[f9_vk] = "toggle"
    else:
        print("[警告] F9 热键注册失败（可能被占用）", file=sys.stderr)
    # F2 单键打开控制面板（如果有 tkinter）
    if HAS_PANEL:
        f2_vk = W.vk(C.HOTKEY_PANEL)
        if hk.register(f2_vk, mod=0):
            bindings[f2_vk] = "panel"
        else:
            print("[警告] F2 热键注册失败（可能被占用）", file=sys.stderr)
    for fv in hk.failed:
        print("[警告] 热键注册失败（可能被占用）: Ctrl+Alt+%s" % fv, file=sys.stderr)

    # 系统托盘（后台线程）
    tray_state = tray.TrayState()
    tray_icon = tray.start(tray_state)

    print("=" * 52)
    print(" Desktop Blackhole Plus 已启动  %dx%d" % (mw, mh))
    print(" 捕获排除: %s | 鼠标穿透: %s" % ("成功" if excl else "失败", C.CLICK_THROUGH))
    print(" 控制：F9 显隐 | F2 面板 | Ctrl+Alt+Q 退出 | ↑↓ 大小 | 托盘右键菜单")
    print("=" * 52)

    sct = mss.MSS()

    # 状态
    bh = [mw / 2.0, mh / 2.0]
    vel = [0.0, 0.0]
    visible = 1.0 if C.VISIBLE_AT_START else 0.0
    target_vis = visible
    eh = float(C.EVENT_HORIZON)
    ein = float(C.EINSTEIN_RADIUS)
    disk = float(C.DISK_BRIGHTNESS)
    warp = float(C.WARP_BOOST)
    mouse_pull = float(C.MOUSE_PULL)
    style_val = STYLE_MAP.get(C.STYLE, 0.0)
    eh0, ein0 = eh, ein  # 重置基准

    # 最大体积限制：直径 = min(屏宽, 屏高) / 2，所以半径 = min / 4
    max_eh = min(mw, mh) / 4.0
    max_ein = max_eh * 3.0  # 爱因斯坦半径按比例限制

    # ---- 彩蛋：最大体积抖动 + BGM ----
    bgm_path = os.path.join(_BUNDLE_DIR, "资源", "bgm_easter.wav")
    bgm_loaded = False
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(bgm_path)
        bgm_loaded = True
        print("[彩蛋] BGM 已加载: %s" % bgm_path)
    except Exception as e:
        print("[彩蛋] BGM 加载失败: %s" % e, file=sys.stderr)

    easter_triggered = False   # 是否已触发过彩蛋
    easter_shake_timer = 0.0   # 抖动剩余时间
    shake_intensity = 0.0      # 当前抖动强度

    # 吞噬管理器
    swallow_mgr = None
    if C.SWALLOW_ENABLED:
        try:
            swallow_mgr = SwallowManager(
                swallow_path=C.SWALLOW_PATH,
                swallow_radius=C.SWALLOW_RADIUS,
                swallow_speed=C.SWALLOW_SPEED,
                cooldown=C.SWALLOW_COOLDOWN,
            )
            print("[吞噬] 已启用，路径: %s" % C.SWALLOW_PATH)
        except Exception as e:
            print("[吞噬] 初始化失败: %s" % e, file=sys.stderr)
            swallow_mgr = None

    # 控制面板回调
    def _on_panel_change(attr, val):
        nonlocal pending, swallow_mgr, style_val, eh, ein
        if attr == "TOGGLE":
            pending.append("toggle")
        elif attr == "QUIT":
            pending.append("quit")
        elif attr == "RESTORE":
            if swallow_mgr:
                n = swallow_mgr.restore_all()
                print("[吞噬] 已恢复 %d 个文件" % n)
        elif attr == "SWALLOW_ENABLED":
            if val and not swallow_mgr:
                try:
                    swallow_mgr = SwallowManager(
                        swallow_path=C.SWALLOW_PATH,
                        swallow_radius=C.SWALLOW_RADIUS,
                        swallow_speed=C.SWALLOW_SPEED,
                        cooldown=C.SWALLOW_COOLDOWN,
                    )
                except Exception as e:
                    print("[吞噬] 启用失败: %s" % e, file=sys.stderr)
            elif not val and swallow_mgr:
                swallow_mgr = None
        elif attr == "SWALLOW_PATH":
            if swallow_mgr:
                swallow_mgr.swallow_path = val
                os.makedirs(val, exist_ok=True)
        elif attr == "STYLE":
            style_val = STYLE_MAP.get(val, 0.0)
        elif attr == "EVENT_HORIZON":
            eh = float(val)
        elif attr == "EINSTEIN_RADIUS":
            ein = float(val)
        else:
            # 其他数值参数（DISK_BRIGHTNESS, WARP_BOOST, MOUSE_PULL, FOLLOW_*, SWALLOW_*）
            # 直接从 config 读取，无需特殊处理
            pass

    panel = None
    if HAS_PANEL:
        panel = ControlPanel(C, on_change=_on_panel_change)
        panel.show()
        print("[面板] 控制台已启动（按 F2 显隐）")
    else:
        print("[面板] 未加载（缺少 tkinter 模块）", file=sys.stderr)

    clock = pygame.time.Clock()
    t0 = time.time()
    fps_t = t0
    fps_n = 0
    running = True
    pending = []   # 待执行的命令队列（热键 + 托盘）

    while running:
        dt = clock.tick(C.TARGET_FPS) / 1000.0

        # ---- 输入 ----
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_SPACE:
                    target_vis = 0.0 if target_vis > 0.5 else 1.0
                elif e.key == pygame.K_UP:
                    eh *= 1.1; ein *= 1.1
                elif e.key == pygame.K_DOWN:
                    eh *= 0.9; ein *= 0.9
        # 全局热键命令
        for vk in hk.poll():
            action = bindings.get(vk)
            if action:
                pending.append(action)
        # 托盘命令
        pending.extend(tray_state.poll())
        for action in pending:
            if action == "quit":
                running = False
            elif action == "toggle":
                target_vis = 0.0 if target_vis > 0.5 else 1.0
            elif action == "bigger":
                eh *= 1.1; ein *= 1.1
            elif action == "smaller":
                eh *= 0.9; ein *= 0.9
            elif action == "reset":
                eh, ein = eh0, ein0
            elif action == "panel":
                if panel:
                    if panel.is_visible():
                        panel.hide()
                    else:
                        panel.show()
        pending.clear()

        # ---- 鼠标跟随（弹簧 + 阻尼）----
        mx, my = W.get_cursor_pos()
        if C.CLAMP_TO_SCREEN:
            mx = max(mleft, min(mleft + mw, mx))
            my = max(mtop, min(mtop + mh, my))
        mx -= mleft
        my -= mtop
        vel[0] = (vel[0] + (mx - bh[0]) * C.FOLLOW_STIFFNESS) * C.FOLLOW_DAMPING
        vel[1] = (vel[1] + (my - bh[1]) * C.FOLLOW_STIFFNESS) * C.FOLLOW_DAMPING
        bh[0] += vel[0]
        bh[1] += vel[1]
        # 可见度缓动
        visible += (target_vis - visible) * min(1.0, dt * 8.0)

        # ---- 吞噬更新 ----
        if swallow_mgr and target_vis > 0.5:
            swallowed = swallow_mgr.update(bh[0], bh[1], eh, dt)
            for name in swallowed:
                print("[吞噬] %s" % name)
                eh = min(eh * (1.0 + C.SWALLOW_GROWTH_RATE), max_eh)
                ein = min(ein * (1.0 + C.SWALLOW_GROWTH_RATE), max_ein)

        # ---- 彩蛋触发：达到最大体积 ----
        if eh >= max_eh * 0.98 and not easter_triggered and target_vis > 0.5:
            easter_triggered = True
            easter_shake_timer = 3.0  # 抖动3秒
            if bgm_loaded:
                try:
                    pygame.mixer.music.play()
                except Exception:
                    pass
            print("[彩蛋] 最大体积达成！")

        # 缩小后重置彩蛋，允许再次触发
        if eh < max_eh * 0.9:
            easter_triggered = False

        # 抖动强度衰减
        if easter_shake_timer > 0:
            easter_shake_timer -= dt
            if easter_shake_timer > 2.5:
                shake_intensity = 1.0
            else:
                shake_intensity = max(0.0, easter_shake_timer / 2.5)
        else:
            shake_intensity = 0.0

        # ---- 捕获桌面并上传纹理 ----
        shot = sct.grab(mon)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, mw, mh, GL_BGRA, GL_UNSIGNED_BYTE, shot.raw)

        # ---- 渲染 ----
        glViewport(0, 0, mw, mh)
        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(prog)
        glUniform2f(u_res, mw, mh)
        glUniform2f(u_bh, bh[0], bh[1])
        glUniform2f(u_mouse, mx, my)
        glUniform1f(u_ein, ein)
        glUniform1f(u_eh, eh)
        glUniform1f(u_time, time.time() - t0)
        glUniform1f(u_disk, C.DISK_BRIGHTNESS)
        glUniform1f(u_warp, C.WARP_BOOST)
        glUniform1f(u_mouse_pull, C.MOUSE_PULL)
        glUniform1f(u_style, style_val)
        glUniform1f(u_vis, visible)
        glUniform1i(u_bg, 0)
        glUniform1f(u_shake, shake_intensity)

        # ---- 传入吞噬图标渲染数据 ----
        render_items = []
        if swallow_mgr:
            render_items = swallow_mgr.get_items_for_render()
        sc = min(len(render_items), 8)
        glUniform1i(u_swallow_count, sc)
        glUniform1f(u_icon_size, float(C.ICON_RENDER_SIZE))
        for i in range(sc):
            item = render_items[i]
            glUniform2f(u_swallow_pos[i], float(item["pos"][0]), float(item["pos"][1]))
            glUniform2f(u_swallow_orig[i], float(item["original_pos"][0]), float(item["original_pos"][1]))
            glUniform1f(u_swallow_prog[i], float(item["progress"]))
            glUniform1f(u_swallow_ang[i], float(item["angle"]))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        pygame.display.flip()

        # ---- 偶发 FPS 日志 ----
        fps_n += 1
        now = time.time()
        if now - fps_t >= 3.0:
            print("[性能] %.1f fps" % (fps_n / (now - fps_t)))
            fps_t = now
            fps_n = 0

    hk.unregister_all()
    try:
        tray_icon.stop()
    except Exception:
        pass
    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            pygame.quit()
        except Exception:
            pass
        # 无控制台模式（console=False）下没有 stdin，不能调用 input()
        if sys.stdin and sys.stdin.isatty():
            input("发生错误，按回车退出...")
        else:
            import time
            time.sleep(5)  # 等待 5 秒让用户看到错误信息（如果有控制台窗口）
        sys.exit(1)
