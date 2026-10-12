shader_type canvas_item;

varying vec2 local_position;
uniform float strength : hint_range(0.0, 1.0) = 1.0;

void vertex() {
    local_position = VERTEX;
}

void fragment() {
    vec4 base = COLOR;
    float row = floor(local_position.y / 12.0);
    float tone = fract(sin(row * 17.13) * 437.5);
    vec3 wood = mix(vec3(0.36, 0.27, 0.23), vec3(0.43, 0.33, 0.27), tone);
    float grain = sin(local_position.x * 2.0 + sin(local_position.y * 0.7) * 2.0);
    wood += grain * 0.009;
    float horizontal_distance = min(fract(local_position.y / 12.0), 1.0 - fract(local_position.y / 12.0)) * 12.0;
    float vertical_distance = abs(fract(local_position.x / 48.0 + mod(row, 2.0) * 0.5) - 0.5) * 48.0;
    float seams = (1.0 - smoothstep(0.02, 0.28, horizontal_distance));
    seams += (1.0 - smoothstep(0.02, 0.25, vertical_distance));
    wood -= seams * 0.055;
    float light_band = exp(-pow((local_position.y - 52.0) / 65.0, 2.0));
    wood += vec3(0.035, 0.018, 0.008) * light_band;
    base.rgb = mix(base.rgb, wood, strength);
    COLOR = base;
}
