"""COKA: shaders (dusty daylight / dusk / night, procedural digital camo), procedural meshes for soldiers, weapons and FX.
No bloom, no glow: smoke and fire are plain alpha-blended particles.  ©2026 EX Inc./HYPERION DIGITAL ©2026"""
import math, random
from panda3d.core import (Shader, NodePath, CardMaker, TransparencyAttrib, Vec3, Vec4, PTA_LVecBase3f, BillboardEffect,
                          TextureStage, SamplerState, ColorBlendAttrib)
from fs_geom import MB

VERT = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix; uniform mat4 p3d_ModelMatrix; uniform mat4 p3d_ModelViewMatrix;
uniform struct p3d_LightSourceParameters { vec4 position; vec4 color; sampler2DShadow shadowMap; mat4 shadowViewMatrix; } p3d_LightSource[1];
attribute vec4 p3d_Vertex; attribute vec3 p3d_Normal; attribute vec2 p3d_MultiTexCoord0; attribute vec4 p3d_Color;
varying vec3 wpos; varying vec3 wnrm; varying vec3 opos; varying vec2 uv; varying vec4 vcol; varying float vdist; varying vec4 sc;
void main() {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  wpos = (p3d_ModelMatrix * p3d_Vertex).xyz; wnrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
  opos = p3d_Vertex.xyz; uv = p3d_MultiTexCoord0; vcol = p3d_Color;
  vec4 mv = p3d_ModelViewMatrix * p3d_Vertex; vdist = length(mv.xyz);
  sc = p3d_LightSource[0].shadowViewMatrix * mv;
}"""
# FIREOUT SHINE material model (fs_shaders): wrap-lit diffuse with sky/ground hemisphere, environment reflection with fresnel,
# gloss-weighted specular, soft highlight roll-off, height haze. COKA adds: sun shadows (PCF), digital camo, sun in-scattering in the
# haze ("sun shafts" from fog, no bloom), ground variation and the night-ops helmet light.
FRAG = """#version 120
uniform sampler2D p3d_Texture0; uniform sampler2D envmap; uniform vec4 p3d_ColorScale;
uniform struct p3d_LightSourceParameters { vec4 position; vec4 color; sampler2DShadow shadowMap; mat4 shadowViewMatrix; } p3d_LightSource[1];
uniform float use_tex; uniform float camo; uniform vec3 camo0; uniform vec3 camo1; uniform vec3 camo2; uniform vec3 camo3; uniform float camoscale;
uniform vec3 sundir; uniform vec3 suncol; uniform vec3 skytop; uniform vec3 skybot; uniform vec3 fogcol; uniform float fogden; uniform vec3 envtint;
uniform vec3 campos; uniform float gvar; uniform float gloss; uniform float sheen; uniform vec4 tint; uniform float flon; uniform vec3 flpos; uniform vec3 fldir;
uniform float use_shadow; uniform float shadow_px; uniform float pcf;
varying vec3 wpos; varying vec3 wnrm; varying vec3 opos; varying vec2 uv; varying vec4 vcol; varying float vdist; varying vec4 sc;
float h3(vec3 c) { return fract(sin(dot(c, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
float vnoise(vec2 p, float s) { vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h3(vec3(i, s)), h3(vec3(i + vec2(1, 0), s)), f.x), mix(h3(vec3(i + vec2(0, 1), s)), h3(vec3(i + vec2(1, 1), s)), f.x), f.y); }
void main() {
  vec4 base = vcol * tint;
  if (use_tex > 0.5) base *= texture2D(p3d_Texture0, uv);
  if (camo > 0.5) {      // digital camo from object-space cells: no UVs, so no stretched or broken textures
    vec3 q = opos * camoscale + vec3(0.013, 0.029, 0.017);
    float v = h3(floor(q * 0.33)) * 0.55 + h3(floor(q)) * 0.45;
    vec3 c = v < 0.32 ? camo3 : (v < 0.52 ? camo1 : (v < 0.74 ? camo0 : camo2));
    base.rgb = c * base.rgb;
  }
  if (gvar > 0.0) base.rgb *= mix(vec3(0.78, 0.74, 0.70), vec3(1.12, 1.06, 0.98), vnoise(wpos.xy * 0.045, 1.0) * 0.7 + vnoise(wpos.xy * 0.19, 2.0) * 0.3);
  vec3 N = normalize(wnrm); vec3 V = normalize(campos - wpos);
  if (dot(N, V) < 0.0) N = -N;
  vec3 L = normalize(sundir);
  float sh = 1.0;
  if (use_shadow > 0.5 && sc.w > 0.0) {
    vec4 s = sc; s.z -= 0.0015 * s.w;
    if (pcf > 0.5) {
      float o = shadow_px * s.w; sh = 0.0;
      sh += shadow2DProj(p3d_LightSource[0].shadowMap, s + vec4(-o, -o, 0, 0)).r; sh += shadow2DProj(p3d_LightSource[0].shadowMap, s + vec4(o, -o, 0, 0)).r;
      sh += shadow2DProj(p3d_LightSource[0].shadowMap, s + vec4(-o, o, 0, 0)).r; sh += shadow2DProj(p3d_LightSource[0].shadowMap, s + vec4(o, o, 0, 0)).r;
      sh *= 0.25;
    } else sh = shadow2DProj(p3d_LightSource[0].shadowMap, s).r;
    vec3 pc = s.xyz / s.w; if (pc.x < 0.01 || pc.x > 0.99 || pc.y < 0.01 || pc.y > 0.99) sh = 1.0;
  }
  float ndl = max(dot(N, L), 0.0); float wrap = max((dot(N, L) + 0.45) / 1.45, 0.0);
  vec3 hemi = mix(skybot, skytop, N.z * 0.5 + 0.5);
  vec3 c = base.rgb;
  vec3 diff = c * (hemi + suncol * mix(ndl, wrap, sheen) * sh);
  vec3 R = reflect(-V, N);
  vec2 euv = vec2(atan(R.y, R.x) / 6.2831 + 0.5, clamp(0.5 + asin(clamp(R.z, -1.0, 1.0)) / 3.1416, 0.01, 0.99));
  vec3 env = texture2D(envmap, euv).rgb * envtint;
  float fres = 0.04 + 0.96 * pow(1.0 - max(dot(N, V), 0.0), 5.0);
  float fk = fres * gloss * (1.0 - 0.85 * clamp(sheen, 0.0, 1.0));
  vec3 col = diff * (1.0 - gloss * 0.12) + env * (fk + gloss * 0.08) * mix(1.0, 0.6, 1.0 - sh);
  vec3 H = normalize(L + V);
  col += suncol * pow(max(dot(N, H), 0.0), mix(8.0, 90.0, gloss)) * gloss * 0.5 * sh;
  if (flon > 0.5) {      // night ops: helmet torch cone
    vec3 d = wpos - flpos; float dl = length(d); vec3 dn = d / max(dl, 0.001);
    float cone = smoothstep(0.86, 0.95, dot(dn, normalize(fldir)));
    col += c * vec3(1.0, 0.92, 0.78) * cone * max(dot(N, -dn), 0.0) * 2.6 / (1.0 + dl * dl * 0.012);
  }
  col *= p3d_ColorScale.rgb;
  col = min(col, vec3(0.82) + 0.18 * (1.0 - exp(-(max(col - vec3(0.82), vec3(0.0))) * 4.0)));   // soft highlight roll-off
  float vd = length(campos - wpos);           // per-pixel distance (a per-vertex distance breaks on the big ground quad)
  float f = 1.0 - exp(-fogden * fogden * vd * vd);
  f *= mix(1.0, 0.45, clamp(wpos.z / 40.0, 0.0, 1.0));                    // height haze: dust hangs low
  float sunk = pow(max(dot(-V, L), 0.0), 6.0);                            // sun in-scattering in the dust (sun shafts via fog)
  vec3 fc = fogcol + suncol * (sunk * 0.42 + pow(max(dot(-V, L), 0.0), 40.0) * 0.25);
  col = mix(col, fc, clamp(f, 0.0, 1.0));
  gl_FragColor = vec4(col, base.a * p3d_ColorScale.a);
}"""
_sh = {}


def shader():
    if "s" not in _sh: _sh["s"] = Shader.make(Shader.SL_GLSL, VERT, FRAG)
    return _sh["s"]


def setup_render(root, campos):
    root.set_shader(shader())
    for k, v in (("use_tex", 0.0), ("gvar", 0.0), ("sheen", 0.0), ("use_shadow", 0.0), ("shadow_px", 0.0005), ("pcf", 1.0), ("envtint", Vec3(1)), ("camo", 0.0), ("camoscale", 13.0), ("gloss", 0.2), ("tint", Vec4(1, 1, 1, 1)), ("flon", 0.0),
                 ("flpos", Vec3(0)), ("fldir", Vec3(0, 1, 0)), ("campos", campos)):
        root.set_shader_input(k, v)
    set_camo(root, [(0.58, 0.52, 0.42), (0.45, 0.40, 0.32), (0.70, 0.66, 0.58), (0.33, 0.30, 0.25)])


LIGHTS = {  # sundir, sun colour, sky top (hemi), ground bounce, fog colour, fog density, env tint, sky colour scale
    "golden": ((0.62, -0.55, 0.30), (1.38, 1.02, 0.70), (0.44, 0.48, 0.58), (0.44, 0.36, 0.28), (0.78, 0.64, 0.50), 0.0055, (1.0, 0.8, 0.62), (1.0, 0.78, 0.58)),
    "day": ((0.45, -0.35, 0.72), (1.2, 1.04, 0.84), (0.56, 0.60, 0.68), (0.50, 0.42, 0.32), (0.76, 0.70, 0.60), 0.0048, (1, 1, 1), (1, 1, 1)),
    "dusk": ((-0.62, 0.45, 0.16), (1.35, 0.62, 0.32), (0.36, 0.36, 0.48), (0.40, 0.27, 0.20), (0.66, 0.44, 0.33), 0.0072, (0.95, 0.62, 0.5), (1.0, 0.62, 0.46)),
    "night": ((0.3, 0.5, 0.75), (0.30, 0.36, 0.52), (0.13, 0.15, 0.22), (0.07, 0.07, 0.09), (0.06, 0.07, 0.1), 0.0125, (0.16, 0.18, 0.26), (0.12, 0.14, 0.2)),
}


def set_light(root, tod, base):
    s, sc, st, sb, fc, fd, et, _ = LIGHTS[tod]; root.set_shader_input("envtint", Vec3(*et))
    root.set_shader_input("sundir", Vec3(*s)); root.set_shader_input("suncol", Vec3(*sc)); root.set_shader_input("skytop", Vec3(*st))
    root.set_shader_input("skybot", Vec3(*sb)); root.set_shader_input("fogcol", Vec3(*fc)); root.set_shader_input("fogden", fd)
    base.set_background_color(*fc, 1)


def set_camo(np_, pal, on=None):
    for i, c in enumerate(pal): np_.set_shader_input("camo%d" % i, Vec3(*c))
    if on is not None: np_.set_shader_input("camo", 1.0 if on else 0.0)


# ---------------------------------------------------------------------------------------------------------- mesh helpers
def _sv(mb, p, n, c, t=(0, 0)):
    mb.v.append((p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0, t[0], t[1]))
    return len(mb.v) - 1


def ellipsoid(mb, cx, cy, cz, rx, ry, rz, col, seg=14, ring=9, zmin=-1.0, zmax=1.0):
    """smooth-shaded (cut) ellipsoid; zmin/zmax in -1..1 cut the bottom/top (helmet shells, caps)"""
    rows = []
    for i in range(ring + 1):
        t = zmin + (zmax - zmin) * i / ring; ph = math.asin(max(-1, min(1, t)))
        r = []
        for j in range(seg + 1):
            a = 2 * math.pi * j / seg
            nx, ny, nz = math.cos(ph) * math.cos(a), math.cos(ph) * math.sin(a), math.sin(ph)
            n = (nx / rx, ny / ry, nz / rz); l = math.sqrt(sum(k * k for k in n)) or 1
            r.append(_sv(mb, (cx + rx * nx, cy + ry * ny, cz + rz * nz), (n[0] / l, n[1] / l, n[2] / l), col, (j / seg, i / ring)))
        rows.append(r)
    for i in range(ring):
        for j in range(seg):
            a, b, c, d = rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]
            mb.t.append((a, b, c)); mb.t.append((a, c, d))


def cyl(mb, x, y, z, r, l, col, axis="y", seg=12, caps=True, r2=None):
    """cylinder from (x,y,z) along +axis for length l"""
    r2 = r if r2 is None else r2
    def P(a, t, rr):
        u, v = rr * math.cos(a), rr * math.sin(a)
        return {"y": (x + u, y + t, z + v), "x": (x + t, y + u, z + v), "z": (x + u, y + v, z + t)}[axis]
    def Nn(a):
        u, v = math.cos(a), math.sin(a)
        return {"y": (u, 0, v), "x": (0, u, v), "z": (u, v, 0)}[axis]
    for j in range(seg):
        a0, a1 = 2 * math.pi * j / seg, 2 * math.pi * (j + 1) / seg
        i0 = _sv(mb, P(a0, 0, r), Nn(a0), col); i1 = _sv(mb, P(a1, 0, r), Nn(a1), col)
        i2 = _sv(mb, P(a1, l, r2), Nn(a1), col); i3 = _sv(mb, P(a0, l, r2), Nn(a0), col)
        mb.t.append((i0, i1, i2)); mb.t.append((i0, i2, i3))
        if caps:
            ax = {"y": (0, 1, 0), "x": (1, 0, 0), "z": (0, 0, 1)}[axis]
            c0 = _sv(mb, P(0, l, 0), ax, col); e0 = _sv(mb, P(a0, l, r2), ax, col); e1 = _sv(mb, P(a1, l, r2), ax, col); mb.t.append((c0, e0, e1))
            na = tuple(-k for k in ax)
            c1 = _sv(mb, P(0, 0, 0), na, col); f0 = _sv(mb, P(a0, 0, r), na, col); f1 = _sv(mb, P(a1, 0, r), na, col); mb.t.append((c1, f1, f0))


def node(mb, parent, name=None, camo=False, gloss=0.2, tex=None):
    n = mb.node(); n.reparent_to(parent); n.set_name(name or mb.name)
    if camo: n.set_shader_input("camo", 1.0)
    n.set_shader_input("gloss", gloss)
    if tex is not None: n.set_texture(tex, 1); n.set_shader_input("use_tex", 1.0)
    return n


# ---------------------------------------------------------------------------------------------------------- soldiers
SKIN = [(0.80, 0.60, 0.47, 1), (0.66, 0.47, 0.34, 1), (0.47, 0.33, 0.24, 1), (0.88, 0.70, 0.58, 1), (0.36, 0.25, 0.18, 1)]
WHITE = (1, 1, 1, 1); BOOT = (0.16, 0.13, 0.10, 1); VEST = (0.42, 0.40, 0.31, 1); DARK = (0.08, 0.08, 0.09, 1)


def build_soldier(parent, rnd, band=None, female=False, cap=False, hair=None, flag_tex=None):
    """digital-camo soldier with helmet (or Ana's cap + black bob), plate carrier, boots, team armband. Faces +Y. 1.8 m."""
    root = parent.attach_new_node("soldier"); sk = rnd.choice(SKIN); w = 0.92 if female else 1.0
    legs = []
    for sd in (-1, 1):
        hip = root.attach_new_node("hip"); hip.set_pos(0.11 * sd * w, 0, 0.92)
        mb = MB("leg"); mb.box(-0.085, -0.09, -0.86, 0.085, 0.10, 0.0, WHITE); node(mb, hip, camo=True)
        mb = MB("boot"); mb.box(-0.075, -0.07, -0.93, 0.075, 0.19, -0.80, BOOT); node(mb, hip, gloss=0.4)
        hip.set_z(0.93); legs.append(hip)
    up = root.attach_new_node("upper"); up.set_z(0.92)
    mb = MB("torso"); mb.box(-0.21 * w, -0.13, 0.0, 0.21 * w, 0.13, 0.56, WHITE); node(mb, up, camo=True)
    mb = MB("vest"); mb.box(-0.205 * w, -0.155, 0.12, 0.205 * w, 0.155, 0.52, VEST)
    for x in (-0.12, 0.0, 0.12): mb.box(x - 0.045, 0.155, 0.14, x + 0.045, 0.2, 0.27, (0.36, 0.34, 0.26, 1))
    mb.box(-0.19 * w, -0.2, 0.2, 0.19 * w, -0.155, 0.48, (0.38, 0.36, 0.28, 1))          # back panel
    node(mb, up, gloss=0.1)
    mb = MB("belt"); mb.box(-0.215 * w, -0.14, -0.02, 0.215 * w, 0.14, 0.07, (0.2, 0.18, 0.14, 1)); node(mb, up)
    head = up.attach_new_node("head"); head.set_z(0.70)
    mb = MB("neck"); cyl(mb, 0, 0, -0.16, 0.055, 0.1, sk, axis="z", caps=False); ellipsoid(mb, 0, 0.005, 0.0, 0.098 * w, 0.112, 0.125, sk)
    mb.box(-0.02, 0.1, -0.02, 0.02, 0.125, 0.025, sk)                                      # nose
    node(mb, head, gloss=0.25)
    mb = MB("eyes")
    for sd in (-1, 1): ellipsoid(mb, 0.037 * sd, 0.096, 0.028, 0.017, 0.008, 0.009, (0.07, 0.05, 0.04, 1), seg=8, ring=4)
    mb.box(-0.032, 0.103, -0.062, 0.032, 0.108, -0.052, (0.45, 0.25, 0.22, 1))            # mouth line
    node(mb, head, gloss=0.6)
    if hair:        # Ana: black bob (shell around the back and sides, chin length) under the cap
        mb = MB("hair"); ellipsoid(mb, 0, -0.012, 0.0, 0.118, 0.128, 0.142, hair, zmin=-0.55, zmax=0.95)
        mb.box(-0.12, -0.03, -0.075, -0.085, 0.07, 0.05, hair); mb.box(0.085, -0.03, -0.075, 0.12, 0.07, 0.05, hair)
        h = node(mb, head, gloss=0.35); h.set_two_sided(True)
    if cap:
        mb = MB("cap"); ellipsoid(mb, 0, -0.005, 0.045, 0.118, 0.13, 0.11, WHITE, zmin=0.0, zmax=1.0)
        mb.box(-0.09, 0.08, 0.04, 0.09, 0.22, 0.055, WHITE); c = node(mb, head, camo=True); c.set_two_sided(True)
    else:
        mb = MB("helmet"); ellipsoid(mb, 0, -0.01, 0.03, 0.145, 0.16, 0.15, WHITE, zmin=-0.05, zmax=1.0)
        hm = node(mb, head, camo=True); hm.set_two_sided(True)
        mb = MB("strap"); mb.box(-0.105, -0.02, -0.11, -0.095, 0.02, 0.03, DARK); mb.box(0.095, -0.02, -0.11, 0.105, 0.02, 0.03, DARK)
        mb.box(-0.06, 0.135, 0.08, 0.06, 0.16, 0.12, (0.12, 0.12, 0.12, 1)); node(mb, head, gloss=0.6)   # goggles on the helmet
    # arms in a rifle-ready pose (forward)
    arms = up.attach_new_node("arms")
    for sd in (-1, 1):
        sh = arms.attach_new_node("sh"); sh.set_pos(0.25 * sd * w, 0.0, 0.5)
        mb = MB("arm"); mb.box(-0.06, -0.06, -0.3, 0.06, 0.06, 0.02, WHITE); node(mb, sh, camo=True)
        sh.set_p(68); sh.set_r(16 * sd)
        fo = sh.attach_new_node("fo"); fo.set_pos(0, 0, -0.28); fo.set_p(20); fo.set_r(34 * sd)
        mb = MB("fore"); mb.box(-0.052, -0.052, -0.28, 0.052, 0.052, 0.0, WHITE); node(mb, fo, camo=True)
        mb = MB("glove"); mb.box(-0.045, -0.05, -0.37, 0.045, 0.05, -0.27, (0.12, 0.11, 0.1, 1)); node(mb, fo, gloss=0.3)
    if band is not None:     # team armband on both upper arms
        for sd in (-1, 1):
            mb = MB("band"); mb.box(0.25 * sd * w - 0.068, -0.068, 0.40, 0.25 * sd * w + 0.068, 0.068, 0.46, band); node(mb, up, gloss=0.1)
    if flag_tex is not None:
        cm = CardMaker("patch"); cm.set_frame(-0.05, 0.05, -0.033, 0.033); p = up.attach_new_node(cm.generate())
        p.set_pos(-0.312 * w, 0.02, 0.38); p.set_h(-90); p.set_texture(flag_tex, 1); p.set_shader_input("use_tex", 1.0)
    gun = up.attach_new_node("gun"); gun.set_pos(0.06, 0.32, 0.36)
    return root, legs, up, head, gun


def blob_shadow(parent, tex=None):
    cm = CardMaker("shadow"); cm.set_frame(-0.45, 0.45, -0.45, 0.45); s = parent.attach_new_node(cm.generate())
    s.set_p(-90); s.set_z(0.03); s.set_color(0, 0, 0, 0.32); s.set_transparency(TransparencyAttrib.M_alpha); s.set_shader_off(1)
    if tex: s.set_texture(tex, 1)
    s.set_depth_write(False); s.set_bin("transparent", 0)
    from panda3d.core import BitMask32; s.hide(BitMask32.bit(3))
    return s


# ---------------------------------------------------------------------------------------------------------- weapons
METAL = (0.13, 0.13, 0.14, 1); POLY = (0.2, 0.2, 0.19, 1)


def build_gun(parent, wid, att=(), camo=True):
    """weapon models (bore axis along +Y at z=0, sight line at z=+0.05). camo on the furniture, metal parts dark."""
    g = parent.attach_new_node("w_" + wid); m = MB("metal"); f = MB("furn"); muzzle = 0.4
    if wid == "km9":     # compact SMG like the poster: boxy receiver, vertical mag in the grip, folding wire stock
        f.box(-0.022, -0.12, -0.035, 0.022, 0.22, 0.03, WHITE); f.box(-0.02, 0.0, -0.17, 0.02, 0.05, -0.035, WHITE); m.box(-0.012, -0.11, 0.03, 0.012, 0.2, 0.036, METAL)
        m.box(-0.02, 0.005, -0.33 if "extmag" in att else -0.27, 0.02, 0.045, -0.17, METAL)
        cyl(m, 0, 0.22, 0.0, 0.011, 0.07, METAL); m.box(-0.006, -0.12, -0.02, 0.006, -0.32, 0.0, METAL)
        m.box(-0.025, -0.33, -0.06, 0.025, -0.31, 0.01, METAL); m.box(-0.02, 0.14, -0.1, 0.02, 0.17, -0.035, POLY); muzzle = 0.29
    elif wid == "kr4":   # assault rifle
        f.box(-0.03, -0.18, -0.04, 0.03, 0.2, 0.04, WHITE); f.box(-0.032, 0.2, -0.035, 0.032, 0.42, 0.035, WHITE)
        f.box(-0.03, -0.46, -0.07, 0.03, -0.18, 0.025, WHITE); f.box(-0.022, -0.1, -0.16, 0.022, -0.04, -0.04, WHITE)
        m.box(-0.018, 0.03, -0.26 if "extmag" in att else -0.21, 0.018, 0.1, -0.04, METAL); cyl(m, 0, 0.42, 0.0, 0.011, 0.2, METAL); muzzle = 0.62
    elif wid == "p11":   # pistol
        m.box(-0.017, -0.06, -0.01, 0.017, 0.13, 0.035, METAL); f.box(-0.016, -0.06, -0.13, 0.016, -0.0, -0.01, WHITE)
        m.box(-0.012, -0.05, -0.17 if "extmag" in att else -0.13, 0.012, -0.01, -0.12, METAL); muzzle = 0.14
    elif wid == "sg12":  # pump shotgun
        cyl(m, 0, -0.1, 0.0, 0.017, 0.72, METAL); cyl(m, 0, -0.1, -0.035, 0.014, 0.6, METAL)
        f.box(-0.03, 0.2, -0.065, 0.03, 0.4, -0.015, WHITE); f.box(-0.032, -0.16, -0.05, 0.032, 0.0, 0.03, WHITE)
        f.box(-0.03, -0.5, -0.09, 0.03, -0.16, 0.02, WHITE); muzzle = 0.62
    elif wid == "sr50":  # bolt sniper with scope + bipod
        f.box(-0.032, -0.2, -0.05, 0.032, 0.35, 0.03, WHITE); f.box(-0.03, -0.55, -0.09, 0.03, -0.2, 0.03, WHITE)
        cyl(m, 0, 0.35, 0.0, 0.012, 0.45, METAL); m.box(-0.02, -0.02, -0.15, 0.02, 0.06, -0.05, METAL)
        cyl(m, 0, -0.14, 0.075, 0.026, 0.3, METAL); m.box(-0.008, -0.04, 0.03, 0.008, 0.06, 0.06, METAL)
        m.box(-0.06, 0.62, -0.18, -0.05, 0.64, -0.01, METAL); m.box(0.05, 0.62, -0.18, 0.06, 0.64, -0.01, METAL); muzzle = 0.8
    if "reddot" in att and wid != "sr50":
        m.box(-0.018, -0.05, 0.035, 0.018, 0.03, 0.05, METAL); m.box(-0.018, -0.01, 0.05, 0.018, 0.0, 0.085, METAL)
    if "scope4" in att and wid in ("kr4",):
        cyl(m, 0, -0.12, 0.072, 0.022, 0.24, METAL); m.box(-0.01, -0.05, 0.035, 0.01, 0.05, 0.055, METAL)
    if "grip" in att and wid not in ("p11",):
        m.box(-0.015, 0.25 if wid != "km9" else 0.15, -0.14, 0.015, 0.28 if wid != "km9" else 0.18, -0.03, POLY)
    if "suppressor" in att:
        cyl(m, 0, muzzle, 0.0, 0.022, 0.16, METAL); muzzle += 0.16
    if not ("reddot" in att or "scope4" in att or wid == "sr50"):     # iron sights: rear notch + front post
        ry, fy = {"km9": (-0.08, 0.2), "kr4": (-0.12, 0.4), "p11": (-0.05, 0.12), "sg12": (-0.1, 0.55)}[wid]
        top = 0.035 if wid != "sg12" else 0.017
        m.box(-0.011, ry, top, -0.004, ry + 0.01, 0.045, METAL); m.box(0.004, ry, top, 0.011, ry + 0.01, 0.045, METAL)
        m.box(-0.0025, fy, top - 0.005, 0.0025, fy + 0.008, 0.045, METAL)
    node(m, g, gloss=0.55); fn = node(f, g, camo=camo, gloss=0.25); fn.set_shader_input("camoscale", 40.0)
    if not camo: fn.set_shader_input("tint", Vec4(0.24, 0.23, 0.21, 1))
    g.set_python_tag("muzzle", muzzle)
    return g


# ---------------------------------------------------------------------------------------------------------- particles
class FX:
    """smoke, fire, dust and debris cards (alpha-blended, depth-sorted, no additive glow)"""
    def __init__(self, base, root, tex, scale=1.0):
        self.base = base; self.root = root.attach_new_node("fx"); self.tex = tex; self.p = []; self.scale = scale
        self.root.set_shader_off(1); self.root.set_light_off(1); self.root.set_transparency(TransparencyAttrib.M_alpha)
        self.root.set_depth_write(False); self.root.set_bin("fixed", 10); self.root.set_two_sided(True)
        cm = CardMaker("p"); cm.set_frame(-0.5, 0.5, -0.5, 0.5); self.card = NodePath(cm.generate())

    def emit(self, kind, x, y, z, n=1, spread=0.5, vel=(0, 0, 1), size=1.0, life=2.0, col=(1, 1, 1, 1), grow=1.0, rnd=random):
        n = max(1, int(n * self.scale))
        for _ in range(n):
            c = self.card.copy_to(self.root); c.set_texture(self.tex[kind], 1)
            c.set_billboard_point_eye(); c.set_pos(x + rnd.uniform(-spread, spread), y + rnd.uniform(-spread, spread), z + rnd.uniform(-spread, spread) * 0.5)
            v = Vec3(vel[0] + rnd.uniform(-1, 1) * spread, vel[1] + rnd.uniform(-1, 1) * spread, vel[2] * rnd.uniform(0.6, 1.3))
            s = size * rnd.uniform(0.7, 1.3); c.set_scale(s); c.set_r(rnd.uniform(0, 360)); c.set_color(*col)
            self.p.append([c, v, 0.0, life * rnd.uniform(0.7, 1.2), s, grow, col, kind])
            if len(self.p) > 420: o = self.p.pop(0); o[0].remove_node()

    def explosion(self, x, y, z, big=1.0):
        self.emit("fire", x, y, z + 0.6, 14 * big, 0.8 * big, (0, 0, 3.2), 1.6 * big, 0.55, (1, 1, 1, 0.95), 2.2)
        self.emit("smoke", x, y, z + 0.8, 18 * big, 1.0 * big, (0, 0, 2.6), 2.2 * big, 3.6, (0.24, 0.22, 0.2, 0.85), 2.6)
        self.emit("smoke", x, y, z + 0.3, 10 * big, 2.0 * big, (0, 0, 0.6), 1.8 * big, 2.6, (0.62, 0.54, 0.42, 0.6), 2.0)   # dust ring
        self.emit("debris", x, y, z + 0.5, 12 * big, 0.3, (0, 0, 7.5), 0.12, 1.4, (0.25, 0.22, 0.18, 1), 1.0)

    def dust(self, x, y, z, col=(0.62, 0.55, 0.44, 0.7)):
        self.emit("smoke", x, y, z, 2, 0.08, (0, 0, 0.5), 0.35, 0.8, col, 2.2)

    def update(self, dt):
        keep = []
        for q in self.p:
            c, v, t, life, s, grow, col, kind = q; t += dt; q[2] = t
            if t >= life: c.remove_node(); continue
            if kind == "debris": v[2] -= 18 * dt
            else: v *= (1 - 0.9 * dt); v[2] += 0.15 * dt
            c.set_pos(c.get_pos() + v * dt); k = t / life
            c.set_scale(s * (1 + (grow - 1) * k))
            a = col[3] * (1 - k) ** (1.4 if kind != "fire" else 0.8)
            if kind == "fire": c.set_color(col[0], col[1] * (1 - 0.4 * k), col[2] * (1 - 0.6 * k), a)
            else: c.set_color(col[0], col[1], col[2], a)
            keep.append(q)
        self.p = keep

    def clear(self):
        for q in self.p: q[0].remove_node()
        self.p = []
