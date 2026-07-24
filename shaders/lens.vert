#version 120
// 全屏四边形顶点着色器：直接输出裁剪空间坐标
attribute vec2 aPos;

void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
}
