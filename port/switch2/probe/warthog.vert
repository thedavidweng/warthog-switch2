#version 460
#if DEKO3D != 200
#error Expected the Ampere UAM2 compiler
#endif
layout(location = 0) in vec4 v0;
layout(std140, binding = 0) uniform vertex_constants { vec4 c[192]; };
layout(location = 0) out vec4 xD0;
layout(location = 4) out vec4 xT0;
invariant gl_Position;
void main() {
    gl_Position = vec4(dot(v0, c[0]), dot(v0, c[1]), dot(v0, c[2]), dot(v0, c[3]));
    xD0 = c[4];
    xT0 = v0;
}
