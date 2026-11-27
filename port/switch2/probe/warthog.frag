#version 460
#if DEKO3D != 200
#error Expected the Ampere UAM2 compiler
#endif
layout(location = 0) in vec4 xD0;
layout(location = 4) in vec4 xT0;
layout(binding = 0) uniform sampler2D tex0;
layout(std140, binding = 0) uniform pixel_parameters {
    vec4 ps_c0[8];
    vec4 alpha_reference;
};
layout(location = 0) out vec4 fragment_color;
void main() {
    vec4 color = texture(tex0, xT0.xy) * xD0 + ps_c0[0];
    if (color.a < alpha_reference.x) discard;
    fragment_color = color;
}
