// Linear EXR plate and actual camera-space depth. AgX is applied once by WorldEnvironment.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_always, shadows_disabled, fog_disabled;
uniform sampler2D base_tex : filter_linear;
uniform sampler2D depth_tex : filter_nearest;
uniform bool use_depth = true;
uniform bool key_mode = false;
void vertex() { POSITION = vec4(VERTEX.xy, 0.5, 1.0); }
void fragment() {
    ALBEDO = key_mode ? vec3(1.0, 0.0, 1.0) : texture(base_tex, SCREEN_UV).rgb;
    ivec2 size = textureSize(depth_tex, 0);
    ivec2 px = clamp(ivec2(SCREEN_UV * vec2(size)), ivec2(0), size - 1);
    vec3 e = round(texelFetch(depth_tex, px, 0).rgb * 255.0);
    float d = use_depth ? (e.r * 65536.0 + e.g * 256.0 + e.b) / 16777215.0 * 1000.0 : 1000.0;
    vec4 r = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, 0.5, 1.0);
    vec3 p = r.xyz / r.w;
    p *= d / -p.z;
    vec4 clip = PROJECTION_MATRIX * vec4(p, 1.0);
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
    DEPTH = clip.z / clip.w * 0.5 + 0.5;
#else
    DEPTH = clip.z / clip.w;
#endif
}
