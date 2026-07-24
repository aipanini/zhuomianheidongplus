#version 120
// 黑洞引力透镜片段着色器（高级版）
// 点质量引力透镜方程（薄透镜近似）：β = θ (1 - θ_E^2 / |θ|^2)
// 视觉特性：
//   - 扁盘吸积盘（类似土星环，水平宽/垂直薄）
//   - 金色风格分层质感（内白热/中金黄/外暗金）
//   - 光子环 + 外晕 + 径向喷流
//   - 多普勒光束 + 色差 + 软调色
//   - 鼠标吸入效果（鼠标位置附近的额外扭曲）

uniform vec2 uResolution;     // 屏幕物理分辨率
uniform vec2 uBlackHole;      // 黑洞中心（左上原点，像素坐标）
uniform vec2 uMouse;          // 鼠标位置（左上原点，像素坐标）
uniform float uEinsteinR;     // 爱因斯坦半径（像素）
uniform float uEventHorizon;  // 事件视界半径（像素）
uniform float uTime;          // 时间（秒）
uniform float uDiskBright;    // 吸积盘亮度倍数
uniform float uWarpBoost;     // 广域扭曲增强
uniform float uMousePull;     // 鼠标吸入强度
uniform float uVisible;       // 效果可见度 0..1
uniform float uStyle;         // 风格：0=gold, 1=fire, 2=classic, 3=ghost, 4=purple
uniform sampler2D uBg;        // 桌面背景纹理

// ---- 吞噬图标渲染 ----
#define MAX_SWALLOW 8
uniform int uSwallowCount;               // 正在吞噬的图标数量
uniform vec2 uSwallowPos[MAX_SWALLOW];   // 图标当前位置（像素）
uniform vec2 uSwallowOrig[MAX_SWALLOW];  // 图标原始位置（像素）
uniform float uSwallowProg[MAX_SWALLOW]; // 吞噬进度 0..1
uniform float uSwallowAng[MAX_SWALLOW];  // 旋转角度
uniform float uIconSize;                 // 图标渲染大小（像素）
uniform float uShake;                    // 屏幕抖动强度 0..1

// 渲染单个被吞噬的图标，返回 rgba（a=0 表示无图标）
vec4 renderSwallowedIcon(vec2 pos) {
    vec4 result = vec4(0.0);
    for (int i = 0; i < MAX_SWALLOW; i++) {
        if (i >= uSwallowCount) break;
        vec2 center = uSwallowPos[i];
        vec2 offset = pos - center;
        float iconR = uIconSize * 0.5 * (1.0 - uSwallowProg[i] * 0.6);  // 随进度缩小
        float dist = length(offset);
        if (dist > iconR) continue;

        // 旋转（反向，因为我们要从原始位置采样）
        float ca = cos(-uSwallowAng[i]);
        float sa = sin(-uSwallowAng[i]);
        vec2 rotated = vec2(offset.x * ca - offset.y * sa,
                            offset.x * sa + offset.y * ca);
        // 缩放回原始大小
        float scale = iconR / (uIconSize * 0.5);
        vec2 origOffset = rotated / max(scale, 0.01);
        vec2 samplePos = uSwallowOrig[i] + origOffset;

        // 边界检查
        if (samplePos.x < 0.0 || samplePos.x > uResolution.x ||
            samplePos.y < 0.0 || samplePos.y > uResolution.y) continue;

        vec3 iconColor = texture2D(uBg, samplePos / uResolution).rgb;
        // 透明度：中心不透明，边缘渐隐；随进度整体渐隐
        float alpha = smoothstep(iconR, iconR * 0.3, dist);
        alpha *= (1.0 - uSwallowProg[i] * 0.8);  // 接近黑洞时渐隐
        result = vec4(mix(result.rgb, iconColor, alpha), max(result.a, alpha));
    }
    return result;
}

void main() {
    vec2 pos = vec2(gl_FragCoord.x, uResolution.y - gl_FragCoord.y);

    // ---- 屏幕抖动（彩蛋）----
    if (uShake > 0.001) {
        float sx = sin(uTime * 47.0) * uShake * 15.0;
        float sy = cos(uTime * 53.0) * uShake * 15.0;
        pos += vec2(sx, sy);
    }

    vec2 d = pos - uBlackHole;
    float r = length(d);
    float r2 = dot(d, d);

    vec3 effect;
    if (r < uEventHorizon) {
        effect = vec3(0.0);
    } else {
        // ---- 鼠标吸入扭曲 ----
        vec2 mouseOffset = pos - uMouse;
        float mouseDist = length(mouseOffset);
        float pullRadius = uEventHorizon * 2.5;
        float pullStrength = 0.0;
        if (mouseDist < pullRadius && uMousePull > 0.001) {
            float t = 1.0 - mouseDist / pullRadius;
            pullStrength = t * t * uMousePull * 30.0;
            vec2 pullDir = normalize(uMouse - pos + vec2(0.001));
            d += pullDir * pullStrength;
            r = length(d);
            r2 = dot(d, d);
        }

        // ---- 引力透镜背景采样 ----
        float k = 1.0 - (uEinsteinR * uEinsteinR) / r2;
        float wide = (uEinsteinR / max(r, 1.0)) * uWarpBoost;
        k += wide * 0.35;
        vec2 samplePos = uBlackHole + d * k;

        // 透镜区色差
        float lensDev = (uEinsteinR * uEinsteinR) / r2;
        vec2 caOff = (d / max(r, 1.0)) * lensDev * 6.0;
        vec2 uvC = samplePos / uResolution;
        float bgR = texture2D(uBg, (samplePos + caOff) / uResolution).r;
        float bgG = texture2D(uBg, uvC).g;
        float bgB = texture2D(uBg, (samplePos - caOff) / uResolution).b;
        vec3 bg = vec3(bgR, bgG, bgB);

        float ang = atan(d.y, d.x);

        // ---- 扁盘吸积盘 ----
        // 将半径映射到扁盘坐标：垂直方向压缩，形成薄盘效果
        float diskAngle = 0.0;  // 盘的旋转角度（0=水平）
        float diskTilt = 0.85;  // 扁度：1=正圆，0=完全扁
        vec2 diskDir = vec2(cos(diskAngle), sin(diskAngle));
        float proj = dot(d, diskDir) / r;
        float rDisk = r * sqrt(1.0 - proj * proj * (1.0 - diskTilt * diskTilt));
        // 简化：直接用垂直分量压缩
        float vertical = abs(d.y) / max(r, 1.0);
        float rFlat = r * (0.25 + 0.75 * (1.0 - vertical * vertical));
        // 更扁的盘：垂直方向厚度薄
        float diskThickness = 0.35;  // 盘的厚度比例
        float yComp = abs(d.y) / (uEventHorizon * 4.0 * diskThickness);
        float diskMaskY = smoothstep(1.0, 0.2, yComp);

        // 径向结构
        float dInner = uEventHorizon * 1.3;
        float dOuter = uEventHorizon * 4.5;
        float t = clamp((rFlat - dInner) / (dOuter - dInner), 0.0, 1.0);

        // 多层径向遮罩
        float innerRing = smoothstep(0.0, 0.04, t) * (1.0 - smoothstep(0.15, 0.35, t));
        float midRing = smoothstep(0.1, 0.25, t) * (1.0 - smoothstep(0.5, 0.8, t));
        float outerRing = smoothstep(0.4, 0.6, t) * (1.0 - smoothstep(0.85, 1.0, t));
        float mask = (innerRing * 1.2 + midRing * 0.9 + outerRing * 0.6) * diskMaskY;

        // 开普勒差分旋转
        float speed = 4.0 / (0.3 + t * 1.8);
        float arms = ang * 4.0 + uTime * speed - t * 18.0;

        // 多频密度纹理
        float dens = 0.5 + 0.5 * sin(arms);
        dens *= 0.55 + 0.45 * sin(arms * 2.7 + 2.1);
        dens *= 0.7 + 0.3 * sin(arms * 5.3 + 1.3);
        dens = pow(dens, 1.4);

        // 内边缘高亮（白热）
        float hotEdge = pow(1.0 - t, 4.0);

        // 多普勒光束
        float dop = sin(ang);
        float beam = mix(0.2, 2.5, dop * 0.5 + 0.5);

        // 风格颜色梯度
        vec3 cCore, cInner, cMid, cOuter, cDopHi, cDopLo, cPhoton, cJet;

        if (uStyle < 0.5) {
            // 0: 金色 (gold)
            cCore   = vec3(1.0, 0.98, 0.90);
            cInner  = vec3(1.0, 0.85, 0.35);
            cMid    = vec3(1.0, 0.60, 0.10);
            cOuter  = vec3(0.45, 0.20, 0.05);
            cDopHi  = vec3(1.0, 0.95, 0.80);
            cDopLo  = vec3(0.55, 0.35, 0.10);
            cPhoton = vec3(1.0, 0.95, 0.80);
            cJet    = vec3(0.7, 0.85, 1.0);
        } else if (uStyle < 1.5) {
            // 1: 炽焰 (fire)
            cCore   = vec3(1.0, 1.0, 0.95);
            cInner  = vec3(1.0, 0.70, 0.15);
            cMid    = vec3(1.0, 0.25, 0.05);
            cOuter  = vec3(0.40, 0.05, 0.02);
            cDopHi  = vec3(1.0, 0.90, 0.70);
            cDopLo  = vec3(0.60, 0.10, 0.05);
            cPhoton = vec3(1.0, 0.85, 0.60);
            cJet    = vec3(1.0, 0.50, 0.20);
        } else if (uStyle < 2.5) {
            // 2: 经典橙红 (classic)
            cCore   = vec3(1.0, 0.95, 0.85);
            cInner  = vec3(1.0, 0.55, 0.15);
            cMid    = vec3(0.90, 0.30, 0.08);
            cOuter  = vec3(0.35, 0.10, 0.03);
            cDopHi  = vec3(1.0, 0.85, 0.65);
            cDopLo  = vec3(0.50, 0.15, 0.05);
            cPhoton = vec3(1.0, 0.80, 0.55);
            cJet    = vec3(0.85, 0.45, 0.15);
        } else if (uStyle < 3.5) {
            // 3: 幽冥青 (ghost)
            cCore   = vec3(0.90, 1.0, 1.0);
            cInner  = vec3(0.35, 0.85, 0.80);
            cMid    = vec3(0.15, 0.55, 0.60);
            cOuter  = vec3(0.05, 0.20, 0.30);
            cDopHi  = vec3(0.75, 0.95, 1.0);
            cDopLo  = vec3(0.10, 0.30, 0.40);
            cPhoton = vec3(0.60, 0.95, 0.95);
            cJet    = vec3(0.40, 0.70, 0.90);
        } else {
            // 4: 紫电 (purple)
            cCore   = vec3(0.95, 0.90, 1.0);
            cInner  = vec3(0.75, 0.45, 1.0);
            cMid    = vec3(0.50, 0.20, 0.75);
            cOuter  = vec3(0.20, 0.05, 0.35);
            cDopHi  = vec3(0.90, 0.80, 1.0);
            cDopLo  = vec3(0.35, 0.10, 0.55);
            cPhoton = vec3(0.80, 0.60, 1.0);
            cJet    = vec3(0.65, 0.40, 0.95);
        }

        vec3 dcol = mix(cMid, cCore, hotEdge * 0.7);
        dcol = mix(dcol, cInner, smoothstep(0.1, 0.3, t) * (1.0 - hotEdge));
        dcol = mix(dcol, cOuter, smoothstep(0.5, 0.95, t));
        // 多普勒色调偏移
        dcol = mix(dcol, cDopHi, max(dop, 0.0) * 0.35);
        dcol = mix(dcol, cDopLo, max(-dop, 0.0) * 0.2);

        float diskInten = mask * (dens * beam + hotEdge * 1.0) * uDiskBright;

        // ---- 光子环 ----
        float pr = uEventHorizon * 1.18;
        float photonRing = exp(-pow((r - pr) / (uEventHorizon * 0.045), 2.0)) * 2.5 * uDiskBright;
        photonRing *= diskMaskY;

        // ---- 外晕 ----
        float glow = exp(-r / (uEventHorizon * 2.2)) * 0.3 * uDiskBright;
        // 垂直方向更扁的外晕
        float glowFlat = exp(-rFlat / (uEventHorizon * 2.5)) * 0.2 * uDiskBright;
        glow += glowFlat;

        // ---- 喷流（上下两极）----
        float jetY = abs(d.y) / max(r, 1.0);
        float jetCore = smoothstep(0.85, 0.98, jetY) * exp(-r / (uEventHorizon * 3.0));
        float jet = jetCore * 0.4 * uDiskBright;
        vec3 jetCol = vec3(0.7, 0.85, 1.0);

        // ---- 组合 ----
        vec3 add = dcol * (diskInten + glow) + cPhoton * photonRing + cJet * jet;
        vec3 addTM = add / (1.0 + add * 0.3);
        effect = bg + addTM;
    }

    vec2 idUV = pos / uResolution;
    vec3 plain = texture2D(uBg, idUV).rgb;

    // 叠加被吞噬的图标
    vec4 iconLayer = renderSwallowedIcon(pos);
    vec3 finalColor = mix(plain, effect, uVisible);
    finalColor = mix(finalColor, iconLayer.rgb, iconLayer.a * uVisible);

    gl_FragColor = vec4(finalColor, 1.0);
}
