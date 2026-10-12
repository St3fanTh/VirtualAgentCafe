shader_type canvas_item;
render_mode unshaded;
uniform float strength : hint_range(0.0, 1.0) = 1.0;

float pool(vec2 p, vec2 center, vec2 radius) {
    vec2 q = (p - center) / radius;
    return exp(-dot(q, q) * 2.0);
}

void fragment() {
    vec2 p = UV;
    float light = pool(p, vec2(0.19, 0.28), vec2(0.18, 0.32));
    light += pool(p, vec2(0.35, 0.28), vec2(0.18, 0.32));
    light += pool(p, vec2(0.61, 0.72), vec2(0.25, 0.25));
    light += pool(p, vec2(0.89, 0.67), vec2(0.20, 0.32));
    float ray = exp(-pow((p.x - p.y * 0.28 - 0.42) * 14.0, 2.0));
    ray *= 1.0 - smoothstep(0.10, 0.82, p.y);
    float edge = smoothstep(0.22, 0.77, length((p - 0.5) * vec2(1.0, 0.85)));
    float warmth = clamp(light * 0.10 + ray * 0.15, 0.0, 0.30);
    vec3 color = mix(vec3(0.035, 0.045, 0.075), vec3(1.0, 0.73, 0.38), clamp(warmth * 8.0, 0.0, 1.0));
    COLOR = vec4(color, strength * clamp(edge * 0.27 + warmth, 0.0, 0.32));
}
