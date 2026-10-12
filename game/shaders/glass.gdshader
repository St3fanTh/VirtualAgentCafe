shader_type canvas_item;
render_mode unshaded;
uniform float strength : hint_range(0.0, 1.0) = 1.0;

void fragment() {
    vec2 p = UV;
    vec3 sky = mix(vec3(0.12, 0.20, 0.32), vec3(0.44, 0.32, 0.38), p.y);
    float skyline = step(0.64 + 0.15 * sin(floor(p.x * 10.0) * 3.0), p.y);
    sky = mix(sky, vec3(0.09, 0.14, 0.22), skyline);
    vec2 cell = fract(p * vec2(26.0, 10.0));
    float windows = step(0.35, cell.x) * step(cell.x, 0.58) * step(0.35, cell.y) * step(cell.y, 0.50);
    sky += vec3(0.32, 0.19, 0.055) * windows * skyline;
    float reflection = pow(max(0.0, 1.0 - abs(p.x + p.y * 0.38 - 0.62) * 7.0), 2.0);
    float drops = pow(max(0.0, sin(p.x * 180.0)), 24.0);
    drops *= pow(max(0.0, sin(p.y * 26.0 + TIME * 0.7 + floor(p.x * 28.0))), 10.0);
    sky += strength * (vec3(0.14, 0.15, 0.17) * reflection + vec3(0.10, 0.14, 0.17) * drops);
    COLOR = vec4(sky, 1.0);
}
