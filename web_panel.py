# -*- coding: utf-8 -*-
"""黑洞控制台 —— Web 版（DPI 自适应，跨分辨率兼容）。

用 Python 标准库 http.server 启动本地 Web 服务器，
通过浏览器渲染控制面板界面，彻底解决 Tkinter 的 DPI 缩放问题。
浏览器原生支持响应式布局和 DPI 缩放，任何分辨率下都能正常显示。
"""

import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


# ========================================================================
#  HTML 页面（内嵌，无需外部文件）
# ========================================================================
HTML_PAGE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>黑洞控制台</title>
<style>
:root {
    --bg-primary: #0d1117;
    --bg-card: #161b22;
    --bg-input: #21262d;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #7d8590;
    --accent: #d4af37;
    --accent-hover: #f0c75e;
    --accent-grad: linear-gradient(135deg, #d4af37, #ff6b35);
    --danger: #f85149;
    --success: #3fb950;
    --radius: 10px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Microsoft YaHei", "PingFang SC", sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    padding: 16px;
    line-height: 1.5;
}

/* ---- 顶部标题 + 快捷键 ---- */
.header {
    text-align: center;
    margin-bottom: 20px;
}
.header h1 {
    font-size: 1.6rem;
    font-weight: 700;
    background: var(--accent-grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.shortcuts {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    margin-top: 10px;
}
.shortcut {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.78rem;
    color: var(--text-secondary);
}
.shortcut kbd {
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 5px;
    font-family: "Consolas", monospace;
    color: var(--accent);
    margin-right: 4px;
    font-size: 0.75rem;
}

/* ---- 两列网格布局 ---- */
.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    max-width: 860px;
    margin: 0 auto;
}
@media (max-width: 680px) {
    .grid { grid-template-columns: 1fr; }
}

/* ---- 卡片 ---- */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: 14px;
}
.card-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 12px;
    color: var(--accent);
    display: flex;
    align-items: center;
    gap: 6px;
}
.card-title::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
}

/* ---- 滑块组 ---- */
.slider-group { margin-bottom: 14px; }
.slider-group:last-child { margin-bottom: 0; }
.slider-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 2px;
}
.slider-label { font-size: 0.88rem; }
.slider-value {
    font-size: 0.82rem;
    color: var(--accent);
    font-family: "Consolas", monospace;
    min-width: 48px;
    text-align: right;
}
.slider-desc {
    font-size: 0.72rem;
    color: var(--text-secondary);
    margin-top: 2px;
}

input[type="range"] {
    width: 100%;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--bg-input);
    border-radius: 3px;
    outline: none;
    margin: 5px 0;
    cursor: pointer;
}
input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    background: var(--accent);
    border-radius: 50%;
    cursor: pointer;
    border: 3px solid var(--bg-card);
    box-shadow: 0 0 6px rgba(212,175,55,0.4);
    transition: transform 0.1s;
}
input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.2);
}
input[type="range"]::-moz-range-thumb {
    width: 14px;
    height: 14px;
    background: var(--accent);
    border-radius: 50%;
    cursor: pointer;
    border: 3px solid var(--bg-card);
}

/* ---- 风格选择（按钮式单选）---- */
.style-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.style-btn {
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-input);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 0.82rem;
    transition: all 0.2s;
}
.style-btn:hover {
    border-color: var(--accent);
    color: var(--text-primary);
}
.style-btn.active {
    background: var(--accent-grad);
    color: #0d1117;
    border-color: transparent;
    font-weight: 600;
}

/* ---- 预设按钮 ---- */
.preset-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.preset-btn {
    flex: 1;
    min-width: 70px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-input);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.82rem;
    text-align: center;
    transition: all 0.2s;
}
.preset-btn:hover {
    border-color: var(--accent);
    background: var(--bg-card);
    transform: translateY(-1px);
}

/* ---- 通用按钮 ---- */
.btn {
    padding: 9px 18px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-input);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.2s;
}
.btn:hover {
    border-color: var(--accent);
    background: var(--bg-card);
}
.btn-primary {
    background: var(--accent-grad);
    color: #0d1117;
    border: none;
    font-weight: 600;
}
.btn-primary:hover {
    opacity: 0.9;
    transform: translateY(-1px);
}
.btn-danger {
    border-color: var(--danger);
    color: var(--danger);
}
.btn-danger:hover {
    background: var(--danger);
    color: #fff;
}
.btn-group {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

/* ---- 路径输入 ---- */
.path-row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 8px;
}
.path-input {
    flex: 1;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 7px 10px;
    color: var(--text-primary);
    font-size: 0.8rem;
    font-family: "Consolas", monospace;
    outline: none;
    min-width: 0;
    word-break: break-all;
}
.path-input:focus { border-color: var(--accent); }

/* ---- 吞噬开关 ---- */
.toggle-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
    cursor: pointer;
}
.toggle-switch {
    position: relative;
    width: 42px;
    height: 22px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 12px;
    transition: all 0.2s;
    flex-shrink: 0;
}
.toggle-switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    background: var(--text-secondary);
    border-radius: 50%;
    transition: all 0.2s;
}
.toggle-switch.on {
    background: var(--success);
    border-color: var(--success);
}
.toggle-switch.on::after {
    left: 22px;
    background: #fff;
}
.toggle-label { font-size: 0.88rem; }

/* ---- 提示文字 ---- */
.hint {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

/* ---- 底部状态 ---- */
.footer {
    text-align: center;
    margin-top: 16px;
    font-size: 0.75rem;
    color: var(--text-secondary);
}
.footer a {
    color: var(--accent);
    text-decoration: none;
}

/* ---- Toast 提示 ---- */
.toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--bg-card);
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 10px 20px;
    color: var(--text-primary);
    font-size: 0.85rem;
    opacity: 0;
    transition: all 0.3s;
    z-index: 999;
    pointer-events: none;
}
.toast.show {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
}
</style>
</head>
<body>

<div class="header">
    <h1>黑洞控制台</h1>
    <div class="shortcuts">
        <span class="shortcut"><kbd>F9</kbd>显示/隐藏黑洞</span>
        <span class="shortcut"><kbd>F2</kbd>开/关控制台</span>
        <span class="shortcut"><kbd>Ctrl+Alt+↑</kbd>增大</span>
        <span class="shortcut"><kbd>Ctrl+Alt+↓</kbd>缩小</span>
        <span class="shortcut"><kbd>Ctrl+Alt+Q</kbd>退出</span>
    </div>
</div>

<div class="grid">
    <!-- ============ 左列 ============ -->
    <div>
        <!-- 黑洞外观 -->
        <div class="card">
            <div class="card-title">黑洞外观</div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">黑洞大小</span>
                    <span class="slider-value" id="val-EVENT_HORIZON">60</span>
                </div>
                <input type="range" data-attr="EVENT_HORIZON" min="20" max="200" step="1" value="60">
                <div class="slider-desc">黑色圆圈的大小</div>
            </div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">扭曲范围</span>
                    <span class="slider-value" id="val-EINSTEIN_RADIUS">180</span>
                </div>
                <input type="range" data-attr="EINSTEIN_RADIUS" min="60" max="400" step="1" value="180">
                <div class="slider-desc">画面被弯曲的范围</div>
            </div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">扭曲强度</span>
                    <span class="slider-value" id="val-WARP_BOOST">1</span>
                </div>
                <input type="range" data-attr="WARP_BOOST" min="0" max="2" step="0.05" value="1">
                <div class="slider-desc">远处画面的弯曲程度</div>
            </div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">光环亮度</span>
                    <span class="slider-value" id="val-DISK_BRIGHTNESS">1.2</span>
                </div>
                <input type="range" data-attr="DISK_BRIGHTNESS" min="0" max="3" step="0.05" value="1.2">
                <div class="slider-desc">发光环的亮度</div>
            </div>
        </div>

        <!-- 视觉风格 -->
        <div class="card">
            <div class="card-title">视觉风格</div>
            <div class="style-grid" id="style-grid">
                <button class="style-btn" data-style="gold">金色</button>
                <button class="style-btn" data-style="fire">炽焰</button>
                <button class="style-btn" data-style="classic">经典橙红</button>
                <button class="style-btn" data-style="ghost">幽冥青</button>
                <button class="style-btn" data-style="purple">紫电</button>
            </div>
        </div>

        <!-- 一键预设 -->
        <div class="card">
            <div class="card-title">一键预设</div>
            <div class="preset-grid">
                <button class="preset-btn" data-preset="tiny">微型</button>
                <button class="preset-btn" data-preset="normal">标准</button>
                <button class="preset-btn" data-preset="huge">巨型</button>
                <button class="preset-btn" data-preset="chaos">狂暴</button>
            </div>
        </div>
    </div>

    <!-- ============ 右列 ============ -->
    <div>
        <!-- 鼠标跟随 -->
        <div class="card">
            <div class="card-title">鼠标跟随</div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">跟随速度</span>
                    <span class="slider-value" id="val-FOLLOW_STIFFNESS">0.012</span>
                </div>
                <input type="range" data-attr="FOLLOW_STIFFNESS" min="0.002" max="0.05" step="0.001" value="0.012">
                <div class="slider-desc">追上鼠标的速度</div>
            </div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">滑动惯性</span>
                    <span class="slider-value" id="val-FOLLOW_DAMPING">0.86</span>
                </div>
                <input type="range" data-attr="FOLLOW_DAMPING" min="0.7" max="0.99" step="0.005" value="0.86">
                <div class="slider-desc">移动的顺滑程度</div>
            </div>
        </div>

        <!-- 吞噬功能 -->
        <div class="card">
            <div class="card-title">吞噬功能</div>
            <div class="hint">黑洞靠近桌面文件时会将其吸入</div>

            <div class="toggle-row" id="swallow-toggle">
                <div class="toggle-switch" id="swallow-switch"></div>
                <span class="toggle-label">启用吞噬</span>
            </div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">吞噬范围</span>
                    <span class="slider-value" id="val-SWALLOW_RADIUS">1.8</span>
                </div>
                <input type="range" data-attr="SWALLOW_RADIUS" min="1" max="4" step="0.1" value="1.8">
                <div class="slider-desc">多近会被吸入</div>
            </div>

            <div class="slider-group">
                <div class="slider-header">
                    <span class="slider-label">吞噬速度</span>
                    <span class="slider-value" id="val-SWALLOW_SPEED">0.15</span>
                </div>
                <input type="range" data-attr="SWALLOW_SPEED" min="0.02" max="0.5" step="0.01" value="0.15">
                <div class="slider-desc">拉入黑洞的速度</div>
            </div>

            <div class="path-row">
                <input type="text" class="path-input" id="swallow-path"
                       placeholder="吞噬文件存放路径" value="">
            </div>

            <div style="margin-top: 12px;">
                <button class="btn" id="btn-restore">恢复所有文件</button>
            </div>
        </div>

        <!-- 操作 -->
        <div class="card">
            <div class="card-title">操作</div>
            <div class="btn-group">
                <button class="btn btn-primary" id="btn-toggle">显示/隐藏黑洞 (F9)</button>
                <button class="btn btn-danger" id="btn-quit">退出程序</button>
            </div>
        </div>
    </div>
</div>

<div class="footer">
    桌面黑洞Plus · 控制台运行于本地浏览器
</div>

<div class="toast" id="toast"></div>

<script>
// ==================== API 通信 ====================

async function fetchState() {
    try {
        const res = await fetch('/api/state');
        return await res.json();
    } catch(e) { return null; }
}

async function updateConfig(attr, val) {
    try {
        await fetch('/api/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({attr, val})
        });
    } catch(e) {}
}

async function doAction(action) {
    try {
        await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action})
        });
    } catch(e) {}
}

async function applyPreset(name) {
    try {
        await fetch('/api/preset', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        await loadState();
        showToast('已应用预设：' + ({tiny:'微型',normal:'标准',huge:'巨型',chaos:'狂暴'}[name]||name));
    } catch(e) {}
}

// ==================== UI 更新 ====================

function formatVal(attr, val) {
    if (attr === 'EVENT_HORIZON' || attr === 'EINSTEIN_RADIUS') return Math.round(val);
    if (attr === 'WARP_BOOST' || attr === 'DISK_BRIGHTNESS') return parseFloat(val).toFixed(2);
    if (attr === 'FOLLOW_STIFFNESS') return parseFloat(val).toFixed(3);
    if (attr === 'FOLLOW_DAMPING') return parseFloat(val).toFixed(2);
    if (attr === 'SWALLOW_RADIUS') return parseFloat(val).toFixed(1);
    if (attr === 'SWALLOW_SPEED') return parseFloat(val).toFixed(2);
    return val;
}

function updateSliderDisplay(slider) {
    const attr = slider.dataset.attr;
    const valEl = document.getElementById('val-' + attr);
    if (valEl) valEl.textContent = formatVal(attr, slider.value);
}

function loadState() {
    return fetchState().then(state => {
        if (!state) return;

        // 更新滑块（跳过正在拖动的）
        document.querySelectorAll('input[type="range"]').forEach(slider => {
            if (document.activeElement === slider) return;
            const attr = slider.dataset.attr;
            if (attr && state[attr] !== undefined) {
                slider.value = state[attr];
                updateSliderDisplay(slider);
            }
        });

        // 更新风格选择
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.style === state.STYLE);
        });

        // 更新吞噬开关
        const sw = document.getElementById('swallow-switch');
        sw.classList.toggle('on', !!state.SWALLOW_ENABLED);

        // 更新路径（跳过正在编辑的）
        const pathInput = document.getElementById('swallow-path');
        if (document.activeElement !== pathInput) {
            pathInput.value = state.SWALLOW_PATH || '';
        }
    });
}

// ==================== Toast ====================

let toastTimer = null;
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2000);
}

// ==================== 事件绑定 ====================

// 滑块
document.querySelectorAll('input[type="range"]').forEach(slider => {
    slider.addEventListener('input', () => {
        updateSliderDisplay(slider);
    });
    slider.addEventListener('change', () => {
        const attr = slider.dataset.attr;
        const val = parseFloat(slider.value);
        updateConfig(attr, val);
    });
});

// 风格选择
document.querySelectorAll('.style-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        updateConfig('STYLE', btn.dataset.style);
    });
});

// 预设
document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        applyPreset(btn.dataset.preset);
    });
});

// 吞噬开关
document.getElementById('swallow-toggle').addEventListener('click', () => {
    const sw = document.getElementById('swallow-switch');
    const isOn = !sw.classList.contains('on');
    sw.classList.toggle('on', isOn);
    updateConfig('SWALLOW_ENABLED', isOn);
});

// 路径输入（失焦时保存）
document.getElementById('swallow-path').addEventListener('blur', (e) => {
    updateConfig('SWALLOW_PATH', e.target.value);
});

// 恢复文件
document.getElementById('btn-restore').addEventListener('click', () => {
    doAction('restore');
    showToast('已发送恢复指令');
});

// 显示/隐藏黑洞
document.getElementById('btn-toggle').addEventListener('click', () => {
    doAction('toggle');
});

// 退出
document.getElementById('btn-quit').addEventListener('click', () => {
    doAction('quit');
    showToast('已发送退出指令');
});

// ==================== 初始化 ====================
loadState();
// 定时同步状态（外部修改时更新 UI）
setInterval(loadState, 2000);
</script>

</body>
</html>'''


# ========================================================================
#  HTTP 请求处理器
# ========================================================================

# 允许通过 API 修改的配置项白名单
_ALLOWED_ATTRS = {
    "EVENT_HORIZON", "EINSTEIN_RADIUS", "WARP_BOOST", "DISK_BRIGHTNESS",
    "STYLE", "FOLLOW_STIFFNESS", "FOLLOW_DAMPING",
    "SWALLOW_ENABLED", "SWALLOW_RADIUS", "SWALLOW_SPEED", "SWALLOW_PATH",
    "MOUSE_PULL",
}

# 预设配置
_PRESETS = {
    "tiny":   {"EVENT_HORIZON": 25,  "EINSTEIN_RADIUS": 80,  "DISK_BRIGHTNESS": 0.8, "WARP_BOOST": 0.5},
    "normal": {"EVENT_HORIZON": 60,  "EINSTEIN_RADIUS": 180, "DISK_BRIGHTNESS": 1.2, "WARP_BOOST": 1.0},
    "huge":   {"EVENT_HORIZON": 120, "EINSTEIN_RADIUS": 300, "DISK_BRIGHTNESS": 1.5, "WARP_BOOST": 1.5},
    "chaos":  {"EVENT_HORIZON": 180, "EINSTEIN_RADIUS": 400, "DISK_BRIGHTNESS": 2.5, "WARP_BOOST": 2.0},
}


class _PanelHandler(BaseHTTPRequestHandler):
    """处理控制面板的 HTTP 请求。"""

    panel = None  # 由 ControlPanel.show() 设置

    def log_message(self, format, *args):
        """静默日志，避免控制台刷屏。"""
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send_html(HTML_PAGE)
        elif path == "/api/state":
            self._send_json(self.panel.get_state())
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()
        if path == "/api/update":
            self.panel.handle_update(body)
            self._send_json({"ok": True})
        elif path == "/api/action":
            self.panel.handle_action(body)
            self._send_json({"ok": True})
        elif path == "/api/preset":
            self.panel.handle_preset(body)
            self._send_json({"ok": True})
        else:
            self.send_error(404)

    def _read_body(self):
        """读取并解析 JSON 请求体。"""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        data = self.rfile.read(length)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {}

    def _send_html(self, content):
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


# ========================================================================
#  控制面板（与 Tkinter 版接口兼容）
# ========================================================================

class ControlPanel:
    """Web 版控制面板。

    接口与原 Tkinter 版 ControlPanel 完全一致：
      - show()       启动服务器并打开浏览器
      - hide()       标记为隐藏
      - is_visible() 返回可见状态
      - on_change    配置变更回调 (attr, val)
    """

    def __init__(self, config, on_change=None):
        self.config = config
        self.on_change = on_change
        self._server = None
        self._thread = None
        self._running = False
        self._port = 18089
        self._visible = False

    def get_state(self):
        """返回当前配置状态，供前端读取。"""
        c = self.config
        return {
            "EVENT_HORIZON": float(c.EVENT_HORIZON),
            "EINSTEIN_RADIUS": float(c.EINSTEIN_RADIUS),
            "WARP_BOOST": float(c.WARP_BOOST),
            "DISK_BRIGHTNESS": float(c.DISK_BRIGHTNESS),
            "STYLE": c.STYLE,
            "FOLLOW_STIFFNESS": float(c.FOLLOW_STIFFNESS),
            "FOLLOW_DAMPING": float(c.FOLLOW_DAMPING),
            "SWALLOW_ENABLED": bool(c.SWALLOW_ENABLED),
            "SWALLOW_RADIUS": float(c.SWALLOW_RADIUS),
            "SWALLOW_SPEED": float(c.SWALLOW_SPEED),
            "SWALLOW_PATH": c.SWALLOW_PATH,
        }

    def handle_update(self, body):
        """处理前端发来的配置更新。"""
        attr = body.get("attr")
        val = body.get("val")
        if not attr or attr not in _ALLOWED_ATTRS:
            return

        # 类型转换
        current = getattr(self.config, attr, None)
        if isinstance(current, bool):
            val = bool(val)
        elif isinstance(current, float):
            val = float(val)
        elif isinstance(current, int) and not isinstance(current, bool):
            val = int(val)
        # 字符串（如 STYLE, SWALLOW_PATH）直接使用

        setattr(self.config, attr, val)
        if self.on_change:
            self.on_change(attr, val)

    def handle_action(self, body):
        """处理前端发来的动作请求。"""
        action = body.get("action")
        if not action or not self.on_change:
            return
        mapping = {
            "toggle": "TOGGLE",
            "quit": "QUIT",
            "restore": "RESTORE",
        }
        attr = mapping.get(action)
        if attr:
            self.on_change(attr, None)

    def handle_preset(self, body):
        """应用预设配置。"""
        name = body.get("name")
        preset = _PRESETS.get(name)
        if not preset:
            return
        for attr, val in preset.items():
            setattr(self.config, attr, val)
            if self.on_change:
                self.on_change(attr, val)

    def show(self):
        """启动 Web 服务器并打开浏览器。"""
        if self._running:
            # 服务器已在运行，直接打开浏览器
            webbrowser.open(f"http://127.0.0.1:{self._port}")
            self._visible = True
            return

        _PanelHandler.panel = self

        # 尝试在 18089~18098 范围内找可用端口
        for port in range(18089, 18099):
            try:
                self._server = HTTPServer(("127.0.0.1", port), _PanelHandler)
                self._port = port
                break
            except OSError:
                continue
        else:
            print("[面板] Web 服务器启动失败：无可用端口", flush=True)
            return

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._running = True
        self._visible = True

        # 延迟打开浏览器，确保服务器已就绪
        url = f"http://127.0.0.1:{self._port}"
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        print(f"[面板] 控制台已启动：{url}", flush=True)

    def hide(self):
        """标记控制面板为隐藏状态。"""
        self._visible = False

    def is_visible(self) -> bool:
        """返回控制面板是否可见。"""
        return self._visible and self._running
