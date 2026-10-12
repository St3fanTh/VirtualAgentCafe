shader_type canvas_item;
render_mode unshaded;
uniform float strength : hint_range(0.0, 1.0) = 1.0;

void fragment() {
    vec2 p = UV;
    float wave = sin(p.y * 12.0 - TIME * 1.3) * 0.06 + sin(p.y * 23.0 + TIME * 0.7) * 0.025;
    float trail = exp(-pow((p.x - 0.5 - wave) / (0.04 + (1.0 - p.y) * 0.10), 2.0));
    float fade = smoothstep(0.0, 0.24, p.y) * (1.0 - smoothstep(0.78, 1.0, p.y));
    COLOR = vec4(0.93, 0.86, 0.74, trail * fade * strength * 0.22);
}
