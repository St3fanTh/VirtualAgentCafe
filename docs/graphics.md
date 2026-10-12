# Café rendering

The game uses a 1920×1280 reference canvas (same 3:2 aspect as the original).
Its initial desktop window is 1440×960; resizing/maximizing scales the layout.
HUD text, station labels and speech bubbles render with larger native font glyphs.
Characters retain their pixel-art silhouettes and event-driven animation states.

Four CanvasItem shaders run with Godot 4.4.1's Compatibility renderer:

- **wood.gdshader:** staggered planks, subtle wood grain and a soft light band.
- **glass.gdshader:** dusk skyline, interior reflection and decorative rain highlights.
- **monitor.gdshader:** scanlines and soft illumination; agent monitor colors come
  from the latest backend state (coding green, tests amber, errors red, thinking violet).
- **atmosphere.gdshader:** warm pools of light, a window light beam and edge shading.

The **Atmosphere** button toggles shader embellishments. It never modifies agent
state. Ambient weather/scanlines are decorative; agent actions still only follow
observed events. UI is in a separate canvas layer so effects do not reduce readability.
No third-party art or Vulkan-specific effects are required.

Furniture gains contact shadows, grain, edge highlights, keycaps, cushions, rugs,
pendant lamps and shelving. Shader panels ignore mouse input so agent selection works.

## Rendered preview / shader validation

Headless import does not exercise the graphics driver. With a graphical display:

```bash
mkdir -p .runtime/previews
VAC_PREVIEW_DIR="$PWD/.runtime/previews" godot --path game \
  --resolution 1920x1280 --audio-driver Dummy --rendering-method gl_compatibility \
  --script res://tests/render_preview.gd
```

To include live demo state, set VAC_BACKEND_URL to the running demo backend.
The preview freezes each observed agent at its station to compare effects fairly.
It saves effects-on, effects-off and task-panel PNGs. CI runs the same render under
Xvfb, fails on shader/runtime errors, and uploads screenshots as artifacts.

The committed [demo screenshot](images/cafe-preview.png) was rendered with actual
Godot Compatibility/OpenGL using Mesa llvmpipe and a live demo backend. It is a
visual preview of simulated states, not evidence of live LLM execution. Windows
GPU performance still depends on the device; Atmosphere can be disabled if desired.
