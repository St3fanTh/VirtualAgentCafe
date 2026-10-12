shader_type canvas_item;
render_mode unshaded;
uniform vec4 activity_color : source_color = vec4(0.34, 0.78, 0.66, 1.0);
uniform float strength : hint_range(0.0, 1.0) = 1.0;

void fragment() {
    vec2 p = UV;
    vec3 base = vec3(0.06, 0.13, 0.17);
    float row = floor(p.y * 7.0);
    float code = step(0.12, p.x) * step(p.x, 0.68 - mod(row, 3.0) * 0.13);
    code *= step(0.36, fract(p.y * 7.0)) * step(fract(p.y * 7.0), 0.52);
    float scan = 0.94 + 0.06 * sin(p.y * 160.0 + TIME * 1.5);
    float bloom = exp(-length((p - vec2(0.5)) * vec2(1.5, 1.0)) * 2.0);
    vec3 color = base + activity_color.rgb * (code * 0.70 + bloom * 0.10);
    COLOR = vec4(mix(color, color * scan + activity_color.rgb * bloom * 0.08, strength), 1.0);
}
