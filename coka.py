"""COKA - CALL OF KIMS ARMY  v1.0.0.1
An army-camp training shooter: campaign with Ana, a shooting range and COKA ONLINE AI TRAINING (bot matches).
©2026 EX Inc./HYPERION DIGITAL ©2026"""
import os, sys, json, math, random, time, threading, traceback
VERSION = "1.0.0.1"
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
def A(*p):
    from panda3d.core import Filename
    return Filename.from_os_specific(os.path.join(HERE, "assets", *p)).get_fullpath()
if os.name == "nt": PROFDIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "EX Inc", "COKA")
else: PROFDIR = os.path.join(os.path.expanduser("~"), ".coka")
os.makedirs(PROFDIR, exist_ok=True)
LOG = os.path.join(PROFDIR, "coka_log.txt")
def log(m):
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(m) + "\n")
    except Exception: pass

import coka_data as D
import ssl

def _fallback_ssl():
    """certifi's CA bundle + every Windows ROOT/CA certificate. Verifying (CERT_REQUIRED, hostname checked)."""
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        import certifi; c.load_verify_locations(cafile=certifi.where())
    except Exception: c.load_default_certs()
    for st in ("ROOT", "CA") if hasattr(ssl, "enum_certificates") else ():
        try:
            for der, enc, tr in ssl.enum_certificates(st):
                if enc == "x509_asn" and (tr is True or "1.3.6.1.5.5.7.3.1" in tr):
                    try: c.load_verify_locations(cadata=der)
                    except Exception: pass
        except Exception: pass
    return c
# 1.0.0.1: antivirus / proxy HTTPS scanning roots live only in the Windows store -> verify against it (truststore).
# The fallback context is built BEFORE truststore patches ssl.SSLContext.
try: _SSL_FB = _fallback_ssl()
except Exception: _SSL_FB = None
try:
    import truststore; truststore.inject_into_ssl(); _SSL_TS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except Exception: _SSL_TS = None
def _ssl_contexts(): return [c for c in (_SSL_TS, _SSL_FB) if c is not None] or [ssl.create_default_context()]
DEFAULT = dict(xp=0, primary="km9", attach={}, camo="desert", perks=["quickhands", "marathon"], done=[], range_best=0,
               settings=dict(gfx="", sens=1.0, fov=80, vol=0.8, voice=1.0, fullscreen=False, diff=1, mode="tdm"))
def load_profile():
    p = json.loads(json.dumps(DEFAULT))
    try:
        with open(os.path.join(PROFDIR, "profile.json"), encoding="utf-8") as f: q = json.load(f)
        s = q.pop("settings", {}); p.update(q); p["settings"].update(s)
    except Exception: pass
    return p

PROFILE = load_profile(); ST = PROFILE["settings"]; TEST = os.environ.get("COKA_TEST", "")

def _win_size():
    """1.0.0.1: per-monitor DPI aware (no blurry bitmap-stretching at 125-150 %% scaling, which made the 1280x720 window
    larger than the screen) and a 16:9 window that fits the monitor's work area (taskbar excluded)."""
    w, h = 1280, 720
    if os.name == "nt":
        try:
            import ctypes
            try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception: ctypes.windll.user32.SetProcessDPIAware()
            class RECT(ctypes.Structure): _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
            rc = RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rc), 0):
                aw, ah = rc.r - rc.l, rc.b - rc.t - 40          # minus the title bar
                k = min(0.92 * aw / 16, 0.92 * ah / 9, 100)        # at most 1600x900
                w, h = max(800, int(k * 16)) // 2 * 2, max(450, int(k * 9)) // 2 * 2
        except Exception: pass
    e = os.environ.get("COKA_WIN")
    if e: w, h = (int(v) for v in e.lower().split("x"))
    return w, h
WIN_W, WIN_H = _win_size()
from panda3d.core import loadPrcFileData
loadPrcFileData("", "window-title COKA - CALL OF KIMS ARMY\nwin-size %d %d\nsync-video %d\nframebuffer-multisample 0\ndepth-bits 24\ntextures-power-2 none\n"
                "texture-minfilter linear-mipmap-linear\ntexture-magfilter linear\ntexture-anisotropic-degree %d\naudio-library-name p3openal_audio\n"
                "icon-filename %s\ndefault-model-extension .bam\nnotify-level-display error\n" % (WIN_W, WIN_H, 0 if TEST else 1, 16 if ST.get("gfx") == "RTX" else 8, A("icon.ico")))
if os.environ.get("COKA_NOAUDIO"): loadPrcFileData("", "audio-library-name null")
loadPrcFileData("", "dpi-aware 1")
if ST.get("fullscreen") and not TEST: loadPrcFileData("", "fullscreen 1")
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (Vec3, Vec4, Point3, TextNode, Texture, SamplerState, TransparencyAttrib, CardMaker, NodePath, Camera, PerspectiveLens,
                          PNMImage, KeyboardButton, MouseButton, WindowProperties, Shader, FrameBufferProperties, PTA_float, PTA_LVecBase3f, TextureStage)
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectSlider, DirectLabel, DGG
from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
import coka_gfx as G
from coka_world import World, EDGE
import coka_play as P

GV = """#version 120
attribute vec4 p3d_Vertex; attribute vec2 p3d_MultiTexCoord0; uniform mat4 p3d_ModelViewProjectionMatrix; varying vec2 uv;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; uv = p3d_MultiTexCoord0; }"""
GF = """#version 120
uniform sampler2D scene; uniform float gtime; uniform float grain; uniform float warm; varying vec2 uv;
void main() {
  vec3 c = clamp(texture2D(scene, uv).rgb, 0.0, 1.0);
  c = mix(c, c * c * (3.0 - 2.0 * c), 0.34);                                   // filmic S-curve, no bloom
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c += vec3(-0.016, 0.004, 0.022) * (1.0 - l) * (1.0 - l) + vec3(0.036, 0.016, -0.026) * l * l * warm;   // teal shadows, dusty warm highlights
  c = mix(vec3(l), c, 0.94);
  vec2 d = (uv - 0.5) * vec2(1.0, 0.8); c *= mix(0.68, 1.0, smoothstep(0.8, 0.25, length(d)));
  float n = fract(sin(dot(floor(gl_FragCoord.xy) + vec2(gtime * 137.0, gtime * 61.0), vec2(12.9898, 78.233))) * 43758.5453);
  c += (n - 0.5) * grain * (0.6 + 0.4 * (1.0 - l));
  gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}"""

GOLD = (0.95, 0.78, 0.3, 1); WHITE = (0.95, 0.94, 0.9, 1); DIM = (0.7, 0.68, 0.62, 1); RED = (0.9, 0.22, 0.16, 1); PANEL = (0.06, 0.06, 0.05, 0.78)


class Hud:
    def __init__(self, app):
        self.app = app; f = app.font; fp = app.fontp
        self.root = app.aspect2d.attach_new_node("hud"); self.root.hide()
        class _C: pass
        a = _C(); a.aspect2d = app.aspect2d; a.render2d = app.render2d
        self.corners = []
        for k in ("a2dBottomRight", "a2dBottomLeft", "a2dTopLeft", "a2dTopRight", "a2dTopCenter"):
            n = getattr(app, k).attach_new_node("hud_" + k); setattr(a, k, n); self.corners.append(n); n.hide()
        self.ch = [DirectFrame(parent=self.root, frameColor=(1, 1, 1, 0.85), frameSize=fs) for fs in
                   ((-0.002, 0.002, 0.012, 0.035), (-0.002, 0.002, -0.035, -0.012), (0.012, 0.035, -0.002, 0.002), (-0.035, -0.012, -0.002, 0.002))]
        self.hm = []
        for r in (45, 135, 225, 315):
            h = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1), frameSize=(-0.0025, 0.0025, 0.012, 0.03)); h.set_r(r); self.hm.append(h)
        self.ammo = OnscreenText(parent=a.a2dBottomRight, pos=(-0.08, 0.14), scale=0.085, fg=WHITE, align=TextNode.A_right, font=f, shadow=(0, 0, 0, 0.7))
        self.wname = OnscreenText(parent=a.a2dBottomRight, pos=(-0.08, 0.075), scale=0.038, fg=DIM, align=TextNode.A_right, font=fp, shadow=(0, 0, 0, 0.7))
        self.hint = OnscreenText(parent=self.root, pos=(0, -0.22), scale=0.045, fg=GOLD, font=f, shadow=(0, 0, 0, 0.8))
        DirectFrame(parent=a.a2dBottomLeft, frameColor=(0, 0, 0, 0.5), frameSize=(0.07, 0.62, 0.07, 0.105))
        self.hp = DirectFrame(parent=a.a2dBottomLeft, frameColor=(0.9, 0.9, 0.85, 0.9), frameSize=(0.075, 0.615, 0.075, 0.1))
        self.hptxt = OnscreenText(parent=a.a2dBottomLeft, pos=(0.075, 0.125), scale=0.034, fg=WHITE, align=TextNode.A_left, font=fp, shadow=(0, 0, 0, 0.7))
        # minimap (north-up, 90 m across, centred on the player)
        self.mm = a.a2dTopLeft.attach_new_node("mm"); self.mm.set_pos(0.3, 0, -0.3)
        DirectFrame(parent=self.mm, frameColor=(0, 0, 0, 0.55), frameSize=(-0.235, 0.235, -0.235, 0.235))
        cm = CardMaker("map"); cm.set_frame(-0.22, 0.22, -0.22, 0.22); self.map = self.mm.attach_new_node(cm.generate())
        self.map.set_texture(app.map_tex); self.map.set_transparency(TransparencyAttrib.M_alpha); self.map.set_color(1, 1, 1, 0.85)
        self.blips = [DirectFrame(parent=self.mm, frameColor=(1, 0, 0, 1), frameSize=(-0.008, 0.008, -0.008, 0.008)) for _ in range(24)]
        self.me = OnscreenText(parent=self.mm, text="^", scale=0.06, fg=GOLD, pos=(0, -0.022), font=f)
        self.mk = OnscreenText(parent=self.mm, text="*", scale=0.07, fg=(1, 0.9, 0.2, 1), font=f)
        OnscreenText(parent=self.mm, text="N", scale=0.035, fg=WHITE, pos=(0, 0.205), font=f)
        self.feedt = [OnscreenText(parent=a.a2dTopRight, pos=(-0.06, -0.08 - i * 0.05), scale=0.036, fg=WHITE, align=TextNode.A_right, font=fp, shadow=(0, 0, 0, 0.8))
                      for i in range(5)]
        self.feeds = []
        self.obj = OnscreenText(parent=a.a2dTopCenter if hasattr(a, "a2dTopCenter") else self.root, pos=(0, -0.075), scale=0.042, fg=WHITE, font=f, shadow=(0, 0, 0, 0.85))
        self.scoret = OnscreenText(parent=a.a2dTopCenter, pos=(0, -0.14), scale=0.05, fg=GOLD, font=f, shadow=(0, 0, 0, 0.85))
        self.ban = OnscreenText(parent=self.root, pos=(0, 0.32), scale=0.1, fg=GOLD, font=f, shadow=(0, 0, 0, 0.9))
        self.bansub = OnscreenText(parent=self.root, pos=(0, 0.24), scale=0.045, fg=WHITE, font=fp, shadow=(0, 0, 0, 0.9)); self.ban_t = 0
        self.xpt = OnscreenText(parent=self.root, pos=(0, 0.1), scale=0.045, fg=GOLD, font=f, shadow=(0, 0, 0, 0.8)); self.xp_t = 0
        self.rk = DirectFrame(parent=self.root, frameColor=(0.05, 0.05, 0.04, 0.85), frameSize=(-0.55, 0.55, -0.1, 0.12), pos=(0, 0, 0.55))
        OnscreenText(parent=self.rk, text="RANK UP", scale=0.05, fg=WHITE, pos=(0, 0.045), font=f)
        self.rkn = OnscreenText(parent=self.rk, text="", scale=0.075, fg=GOLD, pos=(0, -0.05), font=f); self.rk.hide(); self.rk_t = 0
        self.red = DirectFrame(parent=a.render2d, frameColor=(0.6, 0.0, 0.0, 0), frameSize=(-1, 1, -1, 1)); self.red.hide()
        self.bar = DirectFrame(parent=self.root, frameColor=(0, 0, 0, 0.6), frameSize=(-0.25, 0.25, -0.012, 0.012), pos=(0, 0, -0.3))
        self.barf = DirectFrame(parent=self.bar, frameColor=GOLD, frameSize=(-0.25, -0.25, -0.012, 0.012)); self.bar.hide()
        self.scope = OnscreenImage(image=app.scope_tex, parent=a.render2d, scale=(1, 1, 1)); self.scope.set_transparency(TransparencyAttrib.M_alpha); self.scope.hide()
        self.sb = DirectFrame(parent=self.root, frameColor=(0.04, 0.04, 0.035, 0.88), frameSize=(-0.95, 0.95, -0.62, 0.62)); self.sb.hide(); self.sb.set_scale(0.78)
        self.sbt = [OnscreenText(parent=self.sb, scale=0.036, pos=(x, 0.53), align=al, fg=WHITE, font=fp, mayChange=True)
                    for x, al in ((-0.88, TextNode.A_left), (0.25, TextNode.A_right), (0.45, TextNode.A_right), (0.65, TextNode.A_right), (0.88, TextNode.A_right))]

    def show(self, on):
        (self.root.show if on else self.root.hide)(); self.red.hide() if not on else None
        for n in self.corners: n.show() if on else n.hide()
        for o in [self.ammo, self.wname, self.hptxt] + self.feedt + [self.obj, self.scoret]:
            o.show() if on else o.hide()
        self.mm.show() if on else self.mm.hide()
        for n in self.app.a2dBottomLeft.get_children():
            pass
        if not on: self.scope.hide()

    def banner(self, t, sub="", dur=2.4): self.ban.setText(t); self.bansub.setText(sub); self.ban_t = dur
    def feed(self, t): self.feeds.insert(0, [t, 6.0]); self.feeds = self.feeds[:5]
    def xp_pop(self, t): self.xpt.setText(t); self.xp_t = 1.4
    def rank_up(self, n): self.rkn.setText(n); self.rk.show(); self.rk_t = 3.5

    def update(self, dt, s):
        a = self.app; p = s.player; w = s.weapons[s.cur]
        self.ammo.setText("%d  /  %d" % (w.mag, w.res)); self.wname.setText("%s     GRENADES x%d" % (w.d["name"], s.nades))
        k = max(0, p.hp / p.maxhp); self.hp["frameSize"] = (0.075, 0.075 + 0.54 * k, 0.075, 0.1)
        self.hp["frameColor"] = (0.9, 0.9, 0.85, 0.9) if k > 0.35 else (0.9, 0.2, 0.15, 0.95)
        rk = D.rank_of(a.profile["xp"]); self.hptxt.setText("ANA   |   %s   |   %d XP" % (D.RANKS[rk][0], a.profile["xp"]))
        sniper = s.ads > 0.9 and (w.id == "sr50" or (w.id == "kr4" and "scope4" in w.att))
        gap = 0.012 + (w.d["hip"] + s.bloom + math.hypot(p.vx, p.vy) * 0.35) * 0.006
        for i, c in enumerate(self.ch):
            c.set_pos([(0, 0, gap - 0.012), (0, 0, -gap + 0.012), (gap - 0.012, 0, 0), (-gap + 0.012, 0, 0)][i])
            c.show() if (s.ads < 0.5 and not p.dead and not s.sprint) else c.hide()
        for h in self.hm:
            h.show() if s.hitm > 0 else h.hide(); h["frameColor"] = (1, 0.25, 0.2, 1) if s.hit_head else (1, 1, 1, 1)
        self.scope.show() if sniper else self.scope.hide()
        hint = ""
        if p.dead: hint = "YOU WERE TAKEN DOWN  -  respawning..."
        elif w.mag == 0 and w.res == 0: hint = "NO AMMO - switch weapon (1/2)"
        elif w.mag <= w.mag_size * 0.2 and s.reload_t <= 0: hint = "RELOAD  [R]"
        st = s.stages[s.stage] if s.stages else None
        if st and "hold" in st and not p.dead:
            hx, hy, hr, ht = st["hold"](s)
            if hr > 0 and math.hypot(p.x - hx, p.y - hy) < hr: hint = "HOLD  [F]"
            if s.hold > 0: self.bar.show(); self.barf["frameSize"] = (-0.25, -0.25 + 0.5 * min(1, s.hold / ht), -0.012, 0.012)
            else: self.bar.hide()
        else: self.bar.hide()
        self.hint.setText(hint)
        # minimap
        R = 45.0; self.map.set_tex_offset(TextureStage.get_default(), (p.x + EDGE - R) / (2 * EDGE), (p.y + EDGE - R) / (2 * EDGE))
        self.map.set_tex_scale(TextureStage.get_default(), 2 * R / (2 * EDGE), 2 * R / (2 * EDGE))
        self.me.set_r(-p.h); bi = 0
        for o in s.actors:
            if o.dead or bi >= len(self.blips): continue
            friend = o.team == 0 and s.mode != "ffa"
            if not friend and s.time - o.last_fire > 1.6: continue
            dx, dy = (o.x - p.x) / R, (o.y - p.y) / R
            if abs(dx) > 1 or abs(dy) > 1: continue
            b = self.blips[bi]; bi += 1; b.show(); b.set_pos(dx * 0.22, 0, dy * 0.22); b["frameColor"] = (0.3, 0.6, 1, 1) if friend else (1, 0.2, 0.15, 1)
        for b in self.blips[bi:]: b.hide()
        if s.marker is not None:
            dx, dy = (s.marker[0] - p.x) / R, (s.marker[1] - p.y) / R; m = max(abs(dx), abs(dy))
            if m > 1: dx, dy = dx / m, dy / m
            self.mk.show(); self.mk.set_pos(dx * 0.22, 0, dy * 0.22 - 0.025)
        else: self.mk.hide()
        # feeds and popups
        for f_ in self.feeds: f_[1] -= dt
        self.feeds = [f_ for f_ in self.feeds if f_[1] > 0]
        for i, t in enumerate(self.feedt): t.setText(self.feeds[i][0] if i < len(self.feeds) else "")
        self.obj.setText(s.objective)
        if s.mode == "tdm": self.scoret.setText("KIMS ARMY  %d   :   %d  RED TEAM      %d:%02d" % (s.score[0], s.score[1], max(0, s.tlimit - s.time) // 60, max(0, s.tlimit - s.time) % 60))
        elif s.mode == "ffa":
            top = max(s.actors, key=lambda o: o.kills); self.scoret.setText("YOU  %d     LEADER  %s  %d" % (p.kills, top.name, top.kills))
        elif s.mode == "range": self.scoret.setText("HITS %d   ACCURACY %d%%" % (s.hits, 100 * s.hits / max(1, s.shots)))
        else: self.scoret.setText("")
        self.ban_t -= dt; self.ban.show() if self.ban_t > 0 else self.ban.hide(); self.bansub.show() if self.ban_t > 0 else self.bansub.hide()
        self.xp_t -= dt; self.xpt.show() if self.xp_t > 0 else self.xpt.hide()
        self.rk_t -= dt
        if self.rk_t <= 0: self.rk.hide()
        if s.flash > 0 or p.dead: self.red.show(); self.red["frameColor"] = (0.55, 0.02, 0.0, 0.45 if p.dead else s.flash * 0.35)
        else: self.red.hide()
        if a.tab_down: self.sb.show(); self.fill_sb(s)
        else: self.sb.hide()

    def fill_sb(self, s):
        cols = [["NAME"], ["TEAM"], ["KILLS"], ["DEATHS"], ["SCORE"]]
        for r in s.scoreboard():
            cols[0].append(r[0]); cols[1].append("KIMS" if r[1] == 0 and s.mode == "tdm" else ("RED" if s.mode == "tdm" else "-"))
            cols[2].append(str(r[2])); cols[3].append(str(r[3])); cols[4].append(str(r[4]))
        for t, c in zip(self.sbt, cols): t.setText("\n".join(c[:16]))


class App(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.disable_mouse(); self.profile = PROFILE; self.settings = PROFILE["settings"]; self.god = bool(os.environ.get("COKA_GOD"))
        if not self.settings.get("gfx"):
            try:
                import re; r = self.win.gsg.get_driver_renderer().upper()
                self.settings["gfx"] = "RTX" if ("RTX" in r or ("RADEON" in r and re.search(r"RX\s*[6-9]\d{3}", r)) or ("INTEL" in r and " ARC" in r)) else "EXHD"
            except Exception: self.settings["gfx"] = "EXHD"
        self.font = self.loader.load_font(A("ui_font.ttf")); self.fontp = self.loader.load_font(A("ui_plain.ttf"))
        for fnt in (self.font, self.fontp): fnt.set_pixels_per_unit(64)
        self.tex = {}
        for k in ("dirt", "canvas", "sandbag", "gabion", "plywood", "olive", "target", "smoke", "fire", "flash", "sky", "flag"):
            t = self.loader.load_texture(A("tex", k + ".png")); t.set_anisotropic_degree(16 if self.settings["gfx"] == "RTX" else 8)
            if k in ("flag",): t.set_minfilter(SamplerState.FT_linear)
            self.tex[k] = t
        self.tex["debris"] = self.tex["smoke"]
        self.campos = PTA_LVecBase3f([Vec3(0)])
        G.setup_render(self.render, self.campos)
        self.camLens.set_near_far(0.05, 900)
        self.fx_on = True; self.fx = G.FX(self, self.render, self.tex, 1.0 if self.settings["gfx"] == "RTX" else 0.65)
        self.world = World(self, self.tex); self.sky()
        self.map_tex = self.make_map(); self.scope_tex = self.make_scope()
        # viewmodel scene (own camera so the gun never clips into walls)
        self.vmroot = NodePath("vm"); self.vmpos = PTA_LVecBase3f([Vec3(0)]); G.setup_render(self.vmroot, self.vmpos)
        self.vmroot.set_shader_input("envmap", self.tex["sky"]); self.render.set_shader_input("envmap", self.tex["sky"])
        self.setup_shadows(); self.apply_tod("golden")
        self.vmcam = Camera("vmcam"); self.vml = PerspectiveLens(); self.vml.set_fov(68); self.vml.set_near_far(0.01, 10); self.vmcam.set_lens(self.vml)
        self.vmcamnp = self.vmroot.attach_new_node(self.vmcam); self.vm = None; self.vm_t = {}; self.vm_k = 0
        self.gtime = PTA_float([0.0]); self.setup_grade()
        self.sounds = {}; self.load_sounds(); self.voice = None
        self.hud = Hud(self); self.session = None; self.ui = None; self.tab_down = False; self.dt = 0.016
        self.keys_pressed = set()
        for k in ("space", "c", "control", "r", "g", "v", "q", "f", "l", "1", "2", "wheel_up", "wheel_down", "mouse1", "escape", "enter", "tab", "tab-up"):
            self.accept(k, self.on_key, [k])
        self.taskMgr.add(self.loop, "loop"); self.taskMgr.add(self.fit_ui, "fit_ui", sort=45)
        self.accept("window-event", self.on_window)
        self.set_volume()
        self.upd_text = None; threading.Thread(target=self.check_update, daemon=True).start()
        self.ambient = self.sounds["wind"][0]; self.ambient.set_loop(True); self.ambient.set_volume(0.25); self.ambient.play()
        self.smoke_t = 0; self.intro = None; self.flycam = None
        self.bars = [DirectFrame(parent=self.render2d, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, 0.84, 1)),
                     DirectFrame(parent=self.render2d, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, -1, -0.84))]
        for b in self.bars: b.hide()
        self.taskMgr.add(self.flycam_task, "flycam")
        if TEST: self.taskMgr.do_method_later(0.5, self.autotest_start, "at")
        else: self.title_screen()

    # ------------------------------------------------------------------------------------------- render setup
    SKYV = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix; attribute vec4 p3d_Vertex; varying vec3 d;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; d = p3d_Vertex.xyz; }"""
    SKYF = """#version 120
uniform vec3 zen; uniform vec3 hor; uniform vec3 sunc; uniform vec3 sundir; uniform vec3 haze; varying vec3 d;
void main() {
  vec3 v = normalize(d); vec3 L = normalize(sundir); float e = clamp(v.z, -0.2, 1.0); float m = max(dot(v, L), 0.0);
  vec3 c = mix(hor, zen, pow(clamp(e, 0.0, 1.0), 0.55));
  c = mix(c, haze, smoothstep(0.12, -0.05, e));                                   // dusty horizon band
  c += sunc * (pow(m, 5.0) * 0.28 + pow(m, 60.0) * 0.35);                         // forward scattering around the sun
  c = mix(c, vec3(1.0, 0.96, 0.86), smoothstep(0.9993, 0.9997, m));               // sun disc (no halo, no bloom)
  gl_FragColor = vec4(c, 1.0);
}"""
    SKYS = {"golden": ((0.34, 0.45, 0.62), (0.95, 0.70, 0.46), (0.9, 0.55, 0.3), (0.80, 0.62, 0.44)),
            "day": ((0.36, 0.52, 0.74), (0.78, 0.76, 0.70), (0.5, 0.45, 0.35), (0.76, 0.70, 0.60)),
            "dusk": ((0.22, 0.26, 0.42), (0.92, 0.52, 0.32), (0.9, 0.4, 0.2), (0.66, 0.44, 0.33)),
            "night": ((0.02, 0.025, 0.05), (0.06, 0.07, 0.1), (0.05, 0.06, 0.09), (0.06, 0.07, 0.1))}

    def sky(self):
        m = G.MB("sky")
        for i in range(24):
            for j in range(8):
                a0, a1 = 2 * math.pi * i / 24, 2 * math.pi * (i + 1) / 24; e0, e1 = -0.3 + 1.87 * j / 8, -0.3 + 1.87 * (j + 1) / 8
                P_ = lambda a, e: (500 * math.cos(a) * math.cos(e), 500 * math.sin(a) * math.cos(e), 500 * math.sin(e))
                m.quad(P_(a0, e0), P_(a1, e0), P_(a1, e1), P_(a0, e1), (1, 1, 1, 1))
        self.skynp = m.node(); self.skynp.reparent_to(self.camera); self.skynp.set_compass(); self.skynp.set_shader(Shader.make(Shader.SL_GLSL, self.SKYV, self.SKYF), 10)
        self.skynp.set_two_sided(True); self.skynp.set_bin("background", 0); self.skynp.set_depth_write(False); self.skynp.set_light_off(1)

    def apply_tod(self, tod):
        G.set_light(self.render, tod, self); G.set_light(self.vmroot, tod, self); self.vmroot.set_shader_input("fogden", 0.0); self.tod = tod
        z, h, sc, hz = self.SKYS[tod]; L = G.LIGHTS[tod]
        for k, v in (("zen", z), ("hor", h), ("sunc", sc), ("haze", hz), ("sundir", L[0])): self.skynp.set_shader_input(k, Vec3(*v), 10)
        self.sun_dir = Vec3(*L[0]); self.sun_dir.normalize()

    def setup_shadows(self):
        from panda3d.core import DirectionalLight, BitMask32
        rtx = self.settings["gfx"] == "RTX"; size = 2048 if rtx else 1024
        self.sun = DirectionalLight("sun"); self.sun.set_shadow_caster(True, size, size); self.sun.set_camera_mask(BitMask32.bit(3))
        self.sun.get_lens().set_film_size(70 if rtx else 60, 70 if rtx else 60); self.sun.get_lens().set_near_far(5, 400)
        self.sunnp = self.render.attach_new_node(self.sun); self.render.set_light(self.sunnp)
        self.render.set_shader_input("use_shadow", 1.0); self.render.set_shader_input("shadow_px", 0.9 / size); self.render.set_shader_input("pcf", 1.0 if rtx else 0.0)
        self.vmroot.set_shader_input("use_shadow", 0.0)
        self.skynp.hide(BitMask32.bit(3)); self.fx.root.hide(BitMask32.bit(3)); self.shadow_mask = BitMask32.bit(3)

    def place_sun(self, x, y):
        d = self.sun_dir; c = Point3(round(x / 2) * 2, round(y / 2) * 2, 0)
        self.sunnp.set_pos(c + d * 180); self.sunnp.look_at(c)

    def make_map(self):
        n = 256; img = PNMImage(n, n, 4); img.fill(0.55, 0.5, 0.42); img.alpha_fill(0.75)
        for (x0, y0, z0, x1, y1, z1, k) in self.world.boxes:
            if z1 < 0.6: continue
            c = {"cloth": (0.36, 0.34, 0.26), "wood": (0.42, 0.32, 0.2), "sand": (0.3, 0.28, 0.22), "metal": (0.2, 0.22, 0.2)}.get(k, (0.3, 0.28, 0.22))
            i0, i1 = int((x0 + EDGE) / (2 * EDGE) * n), int((x1 + EDGE) / (2 * EDGE) * n); j0, j1 = int((y0 + EDGE) / (2 * EDGE) * n), int((y1 + EDGE) / (2 * EDGE) * n)
            for i in range(max(0, i0), min(n, i1 + 1)):
                for j in range(max(0, j0), min(n, j1 + 1)): img.set_xel(i, n - 1 - j, *c); img.set_alpha(i, n - 1 - j, 0.95)
        for (ax, ay), (bx, by) in zip(self.world.road, self.world.road[1:]):
            for k in range(200):
                x, y = ax + (bx - ax) * k / 200, ay + (by - ay) * k / 200; i, j = int((x + EDGE) / (2 * EDGE) * n), int((y + EDGE) / (2 * EDGE) * n)
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        if 0 <= i + di < n and 0 <= j + dj < n: img.set_xel(i + di, n - 1 - j - dj, 0.68, 0.62, 0.52)
        t = Texture("map"); t.load(img); t.set_wrap_u(SamplerState.WM_border_color); t.set_wrap_v(SamplerState.WM_border_color); t.set_border_color((0, 0, 0, 0))
        return t

    def make_scope(self):
        n = 512; img = PNMImage(n, n, 4); img.fill(0, 0, 0); img.alpha_fill(1)
        for i in range(n):
            for j in range(n):
                r = math.hypot(i - n / 2, j - n / 2) / (n / 2)
                if r < 0.86: img.set_alpha(i, j, 0.0 if r < 0.84 else (r - 0.84) / 0.02)
                if (abs(i - n / 2) < 1.2 or abs(j - n / 2) < 1.2) and r < 0.86 and r > 0.012: img.set_alpha(i, j, 0.9 if r > 0.25 else 0.85)
        t = Texture("scope"); t.load(img); return t

    def setup_grade(self):
        self.fm = None
        try:
            from direct.filter.FilterManager import FilterManager
            self.fm = FilterManager(self.win, self.cam); tex = Texture("scene"); fb = FrameBufferProperties(); fb.set_rgb_color(True); fb.set_depth_bits(24)
            ms = 4 if self.settings["gfx"] == "RTX" else 2
            if not TEST: fb.set_multisamples(ms)
            q = self.fm.renderSceneInto(colortex=tex, fbprops=fb)
            if q is None: raise RuntimeError("no buffer")
            q.set_shader(Shader.make(Shader.SL_GLSL, GV, GF)); q.set_shader_input("scene", tex); q.set_shader_input("gtime", self.gtime)
            q.set_shader_input("grain", 0.03 if self.settings["gfx"] == "RTX" else 0.024); q.set_shader_input("warm", 1.0); self.gq = q
            buf = self.fm.buffers[-1]
        except Exception as e:
            log("grade off: %r" % e); self.fm = None; buf = self.win
        dr = buf.make_display_region(); dr.set_sort(20); dr.set_clear_depth_active(True); dr.set_camera(self.vmcamnp); self.vmdr = dr

    # ------------------------------------------------------------------------------------------- sound
    def load_sounds(self):
        for k in ("pistol", "smg", "shotgun", "hit", "swing", "empty", "click", "checkpoint", "win", "wind", "beep", "go", "crash", "switch"):
            self.sounds[k] = [self.loader.load_sfx(A("sfx", k + ".wav")) for _ in range(6 if k in ("smg", "pistol", "shotgun", "hit") else 2)]
        self.sidx = {}

    def set_volume(self):
        self.sfxManagerList[0].set_volume(self.settings["vol"])

    def sfx(self, k, vol=1.0, rate=1.0, pos=None):
        if pos is not None and self.session:
            d = math.hypot(pos[0] - self.session.player.x, pos[1] - self.session.player.y); vol *= 1 / (1 + d / 25)
        pool = self.sounds[k]; i = self.sidx.get(k, 0); self.sidx[k] = (i + 1) % len(pool); s = pool[i]
        s.stop(); s.set_volume(min(1, vol)); s.set_play_rate(rate); s.play()

    def play_voice(self, k):
        try:
            if self.voice: self.voice.stop()
            self.voice = self.loader.load_sfx(A("voice", k + ".wav")); self.voice.set_volume(self.settings["voice"]); self.voice.play()
            return self.voice.length()
        except Exception as e:
            log("voice %s: %r" % (k, e)); return 2.5

    # ------------------------------------------------------------------------------------------- viewmodel
    def build_viewmodel(self, w):
        if self.vm: self.vm.remove_node()
        self.vm = self.vmroot.attach_new_node("vmrig"); g = G.build_gun(self.vm, w.id, w.att, camo=True)
        G.set_camo(g, D.CAMO[self.profile["camo"]][3]); self.vmgun = g
        skin = (0.8, 0.6, 0.47, 1); glove = (0.13, 0.12, 0.1, 1)
        def limb(p0, p1, wd, col, camo):
            n = self.vm.attach_new_node("limb"); n.set_pos(*p0); n.look_at(Point3(*p1)); L = (Vec3(*p1) - Vec3(*p0)).length()
            mb = G.MB("l"); mb.box(-wd, 0, -wd, wd, L, wd, col, bottom=True); G.node(mb, n, camo=camo); return n
        grip = {"km9": (0, 0.025, -0.11), "kr4": (0, -0.07, -0.1), "p11": (0, -0.03, -0.07), "sg12": (0, -0.08, -0.06), "sr50": (0, -0.12, -0.08)}[w.id]
        fore = {"km9": (0, 0.16, -0.07), "kr4": (0, 0.3, -0.05), "p11": (-0.005, -0.02, -0.08), "sg12": (0, 0.3, -0.06), "sr50": (0, 0.3, -0.07)}[w.id]
        limb((0.13, -0.3, -0.24), (grip[0] + 0.02, grip[1] - 0.05, grip[2] - 0.02), 0.042, (1, 1, 1, 1), True)
        limb((grip[0] + 0.02, grip[1] - 0.07, grip[2] - 0.02), (grip[0], grip[1] + 0.02, grip[2] + 0.02), 0.03, glove, False)
        limb((-0.24, -0.18, -0.26), (fore[0] - 0.035, fore[1] - 0.05, fore[2] - 0.025), 0.04, (1, 1, 1, 1), True)
        limb((fore[0] - 0.035, fore[1] - 0.06, fore[2] - 0.025), (fore[0] + 0.005, fore[1] + 0.02, fore[2] - 0.005), 0.03, glove, False)
        G.set_camo(self.vm, D.CAMO["desert"][3]); G.set_camo(g, D.CAMO[self.profile["camo"]][3])
        cm = CardMaker("mf"); cm.set_frame(-0.07, 0.07, -0.07, 0.07); self.mflash = self.vm.attach_new_node(cm.generate())
        self.mflash.set_texture(self.tex["flash"]); self.mflash.set_shader_off(1); self.mflash.set_transparency(TransparencyAttrib.M_alpha)
        self.mflash.set_depth_write(False); self.mflash.set_bin("fixed", 50); self.mflash.set_pos(0, g.get_python_tag("muzzle") + 0.06, 0); self.mflash.hide()
        self.mflash.set_billboard_point_eye()
        sight = 0.085 if ("reddot" in w.att and w.id != "sr50") else (0.072 if (w.id in ("sr50",) or "scope4" in w.att) else 0.045)
        if w.id == "p11": sight = 0.035
        if w.id == "sg12": sight = 0.03
        self.vm_hip = Vec3(0.13, 0.42, -0.125); self.vm_ads = Vec3(0, 0.44 if w.id != "p11" else 0.4, -sight)
        if "reddot" in w.att and w.id != "sr50":
            cm = CardMaker("dot"); cm.set_frame(-0.0025, 0.0025, -0.0025, 0.0025); d = g.attach_new_node(cm.generate()); d.set_pos(0, 0.0, 0.068)
            d.set_shader_off(1); d.set_color(1, 0.1, 0.05, 1); self.dot = d
        self.vm_t = {}; self.vm_k = 0

    def vm_kick(self, rec):
        self.vm_k = min(1.0, self.vm_k + 0.25 + rec * 0.05); self.mflash.show(); self.mflash.set_r(random.uniform(0, 360)); self.mf_t = 0.045

    def vm_anim(self, k, dur): self.vm_t[k] = [0.0, dur]

    def update_vm(self, dt, s):
        if not self.vm: return
        p = s.player; a = s.ads; self.vm_k = max(0, self.vm_k - dt * 9)
        bob = math.hypot(p.vx, p.vy) * (0.0 if not s.on_ground else 1) ; self.bob = getattr(self, "bob", 0) + dt * bob * 1.7
        pos = self.vm_hip * (1 - a) + self.vm_ads * a
        pos += Vec3(math.sin(self.bob) * 0.006 * (1 - a * 0.8), 0, -abs(math.cos(self.bob)) * 0.007 * (1 - a * 0.8))
        pos += Vec3(0, -0.04 * self.vm_k, 0.005 * self.vm_k)
        hpr = Vec3(0, self.vm_k * 3, 0)
        if s.sprint: pos += Vec3(0.02, -0.04, -0.06); hpr += Vec3(35, -18, 10)
        if s.switch_t > 0: pos += Vec3(0, 0, -0.25 * s.switch_t / 0.45)
        for k, v in list(self.vm_t.items()):
            v[0] += dt; t = v[0] / v[1]
            if t >= 1: del self.vm_t[k]; continue
            e = math.sin(math.pi * t)
            if k == "reload": pos += Vec3(-0.03 * e, 0, -0.1 * e); hpr += Vec3(-10 * e, -25 * e, 30 * e)
            elif k == "throw": pos += Vec3(0.05 * e, 0, -0.2 * e)
            elif k == "melee": pos += Vec3(-0.12 * e, 0.18 * e, 0.04 * e); hpr += Vec3(40 * e, 0, -20 * e)
        self.vm.set_pos(pos); self.vm.set_hpr(hpr)
        if getattr(self, "mf_t", 0) > 0:
            self.mf_t -= dt
            if self.mf_t <= 0: self.mflash.hide()
        hide = s.ads > 0.9 and (s.weapons[s.cur].id == "sr50" or "scope4" in s.weapons[s.cur].att) or p.dead
        self.vm.hide() if hide else self.vm.show()
        sd = G.LIGHTS[s.tod][0]
        self.vmroot.set_shader_input("sundir", self.camera.get_relative_vector(self.render, Vec3(sd[0], sd[1], sd[2])))
        self.vml.set_aspect_ratio(self.getAspectRatio())

    # ------------------------------------------------------------------------------------------- input / loop
    def on_key(self, k):
        if k in ("wheel_up", "wheel_down") and self.ui is not None: self.menu_wheel(-1 if k == "wheel_up" else 1); return
        if k == "tab": self.tab_down = True; return
        if k == "tab-up": self.tab_down = False; return
        if k == "escape":
            if self.session and not self.session.over: self.pause(not self.session.paused)
            elif self.ui_back: self.ui_back()
            return
        if k == "enter" and self.ui_enter: self.ui_enter(); return
        self.keys_pressed.add(k)

    def held(self, k):
        mw = self.mouseWatcherNode
        if k == "shift": return mw.is_button_down(KeyboardButton.shift()) or mw.is_button_down(KeyboardButton.lshift())
        if k == "control": return mw.is_button_down(KeyboardButton.control())
        if k == "mouse1": return mw.is_button_down(MouseButton.one())
        if k == "mouse3": return mw.is_button_down(MouseButton.three())
        return mw.is_button_down(KeyboardButton.ascii_key(k))

    def grab_mouse(self, on):
        wp = WindowProperties(); wp.set_cursor_hidden(on); self.win.request_properties(wp); self.mgrab = on
        if on: self.win.move_pointer(0, self.win.get_x_size() // 2, self.win.get_y_size() // 2)

    def read_input(self):
        kp = self.keys_pressed; self.keys_pressed = set(); s = self.session
        inp = dict(mx=0.0, my=0.0, w=False, a=False, s=False, d=False, sprint=False, fire=False, fire_pressed="mouse1" in kp, ads=False,
                   jump="space" in kp, crouch_pressed=("c" in kp or "control" in kp), crouch_held=self.held("c") or self.held("control"),
                   reload="r" in kp, nade="g" in kp, melee=("v" in kp or "q" in kp), use=self.held("f"), light="l" in kp, swap=None)
        if "1" in kp: inp["swap"] = 0
        if "2" in kp: inp["swap"] = 1
        if "wheel_up" in kp or "wheel_down" in kp: inp["swap"] = 1 - s.cur
        if getattr(self, "mgrab", False) and self.win.get_properties().get_foreground():
            md = self.win.get_pointer(0); cx, cy = self.win.get_x_size() // 2, self.win.get_y_size() // 2
            sens = 0.1 * self.settings["sens"] * (0.45 if s.ads > 0.5 else 1) * (0.4 if (s.ads > 0.5 and s.weapons[s.cur].id == "sr50") else 1)
            inp["mx"] = (md.get_x() - cx) * sens; inp["my"] = (md.get_y() - cy) * sens
            self.win.move_pointer(0, cx, cy)
        for k in "wasd": inp[k] = self.held(k)
        inp["sprint"] = self.held("shift"); inp["fire"] = self.held("mouse1"); inp["ads"] = self.held("mouse3")
        return inp

    def loop(self, task):
        dt = min(0.05, globalClock.get_dt()); self.dt = dt; self.gtime[0] = (self.gtime[0] + dt) % 100
        s = self.session
        if s and self.intro is not None:
            self.intro_tick(dt, s); self.fx.update(dt); self.distant_smoke(dt); return task.cont
        if s and not s.paused and not s.over:
            inp = self.autopilot(s) if TEST else self.read_input()
            s.update(dt, inp)
            if self.session is s and not s.over: self.update_cam(dt, s); self.hud.update(dt, s); self.update_vm(dt, s)
            self.distant_smoke(dt)
        elif s and TEST and s.over: pass
        self.fx.update(dt)
        return task.cont

    def distant_smoke(self, dt):
        self.smoke_t -= dt
        if self.smoke_t > 0: return
        self.smoke_t = 0.45 if self.settings["gfx"] == "RTX" else 0.7
        dark = self.session.tod == "night"
        for (x, y) in ((150, 70), (-160, 120), (40, -170)):
            self.fx.emit("smoke", x, y, 3, 1, 3.0, (1.2, 0.4, 3.0), 9.0, 14.0, (0.2, 0.19, 0.18, 0.55) if not dark else (0.05, 0.05, 0.06, 0.5), 3.2)
            if random.random() < 0.5: self.fx.emit("fire", x, y, 2.0, 1, 2.0, (0, 0, 1.2), 4.0, 1.2, (1, 0.8, 0.6, 0.85), 1.3)

    def update_cam(self, dt, s):
        p = s.player
        eye = 0.85 if s.slide_t > 0 else (1.12 if p.crouch else 1.62)
        self.cam_eye = getattr(self, "cam_eye", eye) + (eye - getattr(self, "cam_eye", eye)) * min(1, dt * 12)
        z = p.z + (self.cam_eye if not p.dead else 0.35)
        sh = s.shake * 0.6
        self.camera.set_pos(p.x, p.y, z); self.camera.set_hpr(p.h + random.uniform(-sh, sh), p.p + random.uniform(-sh, sh), (8 if p.dead else 0) + (-4 if s.slide_t > 0 else 0))
        self.campos[0] = self.camera.get_pos(self.render); self.place_sun(p.x, p.y)
        w = s.weapons[s.cur]; base = self.settings["fov"]
        tf = base if s.ads < 0.01 else base + (base * (w.d["fov"] / 70.0) * (0.62 if (w.id == "kr4" and "scope4" in w.att) else 1) - base) * s.ads
        if s.sprint: tf += 6
        self.camLens.set_fov(tf)

    # ------------------------------------------------------------------------------------------- session control
    def start(self, mode, mission=None):
        self.clear_ui(); pass
        self.session = P.Session(self, mode, mission, self.settings.get("diff", 1))
        self.flycam = None; self.grab_mouse(not TEST); self.ui_back = None; self.ui_enter = None
        if mode == "mission": self.hud.banner([m for m in D.MISSIONS if m[0] == mission][0][1], self.session.objective, 3.0)
        if not TEST or os.environ.get("COKA_INTRO"):
            self.intro = dict(t=0.0, dur=4.2); self.hud.show(False); [b.show() for b in self.bars]; self.keys_pressed = set()
            m = [q for q in D.MISSIONS if q[0] == mission][0] if mode == "mission" else None
            self.intro_txt = OnscreenText(parent=self.render2d, text=(m[1] if m else {"tdm": "TEAM DEATHMATCH", "ffa": "FREE-FOR-ALL", "range": "SHOOTING RANGE"}[mode]),
                                          pos=(0, -0.93), scale=(0.05 / self.getAspectRatio(), 0.05), fg=GOLD, font=self.font)
        else: self.hud.show(True)

    def intro_tick(self, dt, s):
        """short cinematic camera move: high crane shot over the camp that swoops down into Ana's eyes, then first person"""
        it = self.intro; it["t"] += dt; k = min(1.0, it["t"] / it["dur"]); e = k * k * (3 - 2 * k)
        p = s.player; f = P.fwd(p.h); eye = Vec3(p.x, p.y, p.z + 1.62)
        a = math.radians(p.h + 150); A0 = eye + Vec3(math.cos(a) * 26, math.sin(a) * 26, 15); A1 = eye + Vec3(-f[0] * 9 + f[1] * 6, -f[1] * 9 - f[0] * 6, 5)
        A2 = eye - f * 2.2 + Vec3(0, 0, 0.5); A3 = eye
        u = 1 - e; pos = A0 * u ** 3 + A1 * 3 * u * u * e + A2 * 3 * u * e * e + A3 * e ** 3
        look = (Vec3(p.x, p.y, p.z + 1.0)) * (1 - e) + (eye + f * 30) * e
        self.camera.set_pos(pos); self.camera.look_at(Point3(look)); self.campos[0] = pos; self.place_sun(p.x, p.y); self.camLens.set_fov(self.settings["fov"] - 12 * (1 - e))
        if self.vm: self.vm.hide()
        skip = self.keys_pressed & {"mouse1", "space", "enter"}; self.keys_pressed = set()
        if k >= 1 or skip:
            self.intro = None; [b.hide() for b in self.bars]; self.intro_txt.remove_node(); self.hud.show(True)
            if self.vm: self.vm.show()
            if getattr(self, "mgrab", False): self.win.move_pointer(0, self.win.get_x_size() // 2, self.win.get_y_size() // 2)

    def flycam_task(self, task):
        """slow cinematic dolly over the camp behind the briefing screen"""
        fc = self.flycam
        if fc is None or self.session is not None: return task.cont
        fc["t"] += globalClock.get_dt(); t = fc["t"]; x, y = fc["c"]
        a = fc["a"] + t * 0.035; r = 34 - t * 0.25
        pos = Vec3(x + math.cos(a) * r, y + math.sin(a) * r, 9 + 2.5 * math.sin(t * 0.15))
        self.camera.set_pos(pos); self.camera.look_at(Point3(x, y, 2.0)); self.campos[0] = pos; self.place_sun(x, y); self.camLens.set_fov(62)
        if int(t * 10) % 7 == 0: self.distant_smoke_static()
        self.fx.update(globalClock.get_dt())
        return task.cont

    def distant_smoke_static(self):
        self.smoke_t -= 0.1
        if self.smoke_t > 0: return
        self.smoke_t = 0.5
        for (x, y) in ((150, 70), (-160, 120), (40, -170)):
            self.fx.emit("smoke", x, y, 3, 1, 3.0, (1.2, 0.4, 3.0), 9.0, 14.0, (0.2, 0.19, 0.18, 0.55), 3.2)

    def pause(self, on):
        s = self.session; s.paused = on; self.grab_mouse(not on)
        if on: self.pause_menu()
        else: self.clear_ui()

    def end_session(self):
        if self.session: self.session.destroy(); self.session = None
        if self.vm: self.vm.remove_node(); self.vm = None
        self.hud.show(False); self.hud.red.hide(); self.grab_mouse(False); self.save_profile()

    def on_session_over(self, s):
        self.save_profile(); self.grab_mouse(False)
        if TEST: return
        self.taskMgr.do_method_later(1.6, lambda t: self.results(s), "res")

    def save_profile(self):
        try:
            with open(os.path.join(PROFDIR, "profile.json"), "w", encoding="utf-8") as f: json.dump(self.profile, f, indent=1)
        except Exception as e: log("save: %r" % e)

    def check_update(self):
        try:
            import urllib.request
            u = "https://raw.githubusercontent.com/Teobokki/coka/main/latest.json"
            j = None
            for c in _ssl_contexts():      # Windows store first, then certifi + Windows ROOT/CA; verification always on
                try:
                    with urllib.request.urlopen(u, timeout=6, context=c) as r: j = json.loads(r.read().decode()); break
                except Exception as e:
                    if "CERTIFICATE_VERIFY_FAILED" not in str(e) and "chain policy" not in str(e).lower(): raise
                    log("update check: certificate not trusted (%s)" % e)
            if j is None: return
            if tuple(int(x) for x in j["version"].split(".")) > tuple(int(x) for x in VERSION.split(".")): self.upd_text = "UPDATE AVAILABLE: v%s  -  get it in HYPERION DIGITAL EX" % j["version"]
        except Exception: pass

    # ------------------------------------------------------------------------------------------- menus
    def clear_ui(self):
        if self.ui: self.ui.remove_node()
        self.ui = None; self.ui_back = None; self.ui_enter = None

    # 1.0.0.1 menu layout. aspect2d is "window height = 2 units", so the UI follows the window height. Menu content goes
    # into its own node (self.cn, the old design units) right of the poster, scaled by UI_K (~0.7x of 1.0.0). fit_ui()
    # measures the real bounds every time a menu is built and shrinks it further / turns on mouse-wheel scrolling, so
    # nothing is cut off at any resolution or aspect (4:3 ... 32:9), windowed or DPI-scaled. Menus rebuild on resize.
    UI_K = 0.7

    def panel_left(self):
        ar = self.getAspectRatio(); return -ar + max(0.55, min(1.9, 2 * ar - 1.7))

    def content(self, x0, center=False):
        self.cn = self.ui.attach_new_node("content"); self.cn.set_pos(x0, 0, 0); self.cn.set_scale(self.UI_K)
        self.cn_center = center; self.cn_scroll = 0.0; self.cn_range = (0, 0); self.fit_pending = True
        return self.cn

    def fit_ui(self, task):
        cn = getattr(self, "cn", None)
        if getattr(self, "fit_pending", False) and self.ui is not None and cn is not None and not cn.is_empty():
            self.fit_pending = False; ar = self.getAspectRatio(); k = self.UI_K; cn.set_scale(k); cn.set_z(0)
            b = cn.get_tight_bounds(self.aspect2d)
            if b:
                lo, hi = b; x0 = cn.get_x(); f = 1.0
                if hi[0] > ar - 0.04: f = min(f, (ar - 0.04 - x0) / max(0.01, hi[0] - x0))
                if self.cn_center and lo[0] < -ar + 0.04: f = min(f, (ar - 0.04 + x0) / max(0.01, x0 - lo[0]))
                cn.set_scale(k * max(f, 0.55))
                lo, hi = cn.get_tight_bounds(self.aspect2d); top, bot = 0.92, -0.9
                if hi[2] - lo[2] <= top - bot:
                    cn.set_z(max(0.0, bot - lo[2]) - max(0.0, hi[2] - top))
                else:                                                   # taller than the window: scroll with the wheel
                    cn.set_z(top - hi[2]); self.cn_range = (cn.get_z(), cn.get_z() + (bot - lo[2]) - (top - hi[2]))
        return task.cont

    def menu_wheel(self, d):
        cn = getattr(self, "cn", None)
        if self.ui is not None and cn is not None and not cn.is_empty() and self.cn_range[1] > self.cn_range[0]:
            cn.set_z(max(self.cn_range[0], min(self.cn_range[1], cn.get_z() + d * 0.12)))

    def on_window(self, win=None):
        self.windowEvent(win)                     # keep ShowBase's own handler (aspect ratio, close)
        ar = round(self.getAspectRatio(), 3)
        if ar != getattr(self, "_menu_ar", ar) and self.ui is not None and getattr(self, "_menu_fn", None):
            self._menu_fn()
        self._menu_ar = ar

    def new_ui(self, poster="left", dim=0.55):
        self.clear_ui(); self.ui = self.aspect2d.attach_new_node("ui"); ar = self.getAspectRatio(); pl = self.panel_left()
        self._menu_ar = round(ar, 3)
        if poster == "world":      # live camp behind a translucent panel (briefings)
            DirectFrame(parent=self.ui, frameColor=(0.03, 0.028, 0.024, 0.8), frameSize=(pl, ar + 0.1, -1.1, 1.1))
            for i in range(24): DirectFrame(parent=self.ui, frameColor=(0.03, 0.028, 0.024, 0.033), frameSize=(pl - 0.9 + i * 0.0375, pl, -1.1, 1.1))
            OnscreenText(parent=self.ui, text=D.COPYRIGHT, pos=(ar - 0.05, -0.96), scale=0.03, fg=DIM, align=TextNode.A_right, font=self.fontp)
            return self.content(pl + 0.12)
        self.flycam = None
        DirectFrame(parent=self.ui, frameColor=(0.05, 0.045, 0.04, 1), frameSize=(-ar - 0.1, ar + 0.1, -1.1, 1.1))
        x = 0 if poster == "center" else pl - 0.9
        im = OnscreenImage(image=A("menu_bg.jpg"), parent=self.ui, scale=(1, 1, 1), pos=(x, 0, 0))
        if poster != "center":
            DirectFrame(parent=self.ui, frameColor=(0.04, 0.035, 0.03, 0.9), frameSize=(pl, ar + 0.1, -1.1, 1.1))
            for i in range(10): DirectFrame(parent=self.ui, frameColor=(0.04, 0.035, 0.03, 0.09 * i), frameSize=(pl - 0.9 + i * 0.09, pl - 0.81 + i * 0.09, -1.1, 1.1))
        OnscreenText(parent=self.ui, text=D.COPYRIGHT, pos=(ar - 0.05, -0.96), scale=0.03, fg=DIM, align=TextNode.A_right, font=self.fontp)
        return self.ui if poster == "center" else self.content(pl + 0.12)

    def btn(self, parent, text, cmd, pos, w=0.62, scale=0.055, active=True, sel=False):
        b = DirectButton(parent=parent, text=text, command=(lambda: (self.sfx("click", 0.5), cmd())) if active else None, pos=pos, scale=scale, text_font=self.font,
                         text_fg=(GOLD if sel else WHITE) if active else (0.45, 0.43, 0.4, 1), frameColor=((0.16, 0.14, 0.1, 0.9), (0.42, 0.33, 0.14, 0.95), (0.3, 0.25, 0.12, 0.95), (0.1, 0.1, 0.1, 0.6)),
                         frameSize=(-w / scale / 2, w / scale / 2, -0.45, 0.95), text_align=TextNode.A_center, relief=DGG.FLAT, pressEffect=1)
        if not active: b["state"] = DGG.DISABLED
        return b

    def title_screen(self):
        self._menu_fn = self.title_screen
        ui = self.new_ui("center"); ar = self.getAspectRatio()
        t = OnscreenText(parent=ui, text="PRESS ENTER OR CLICK TO START", pos=(0, -0.86), scale=0.055, fg=WHITE, font=self.font, shadow=(0, 0, 0, 1))
        DirectButton(parent=ui, frameColor=(0, 0, 0, 0), frameSize=(-ar, ar, -1, 1), command=self.main_menu, relief=DGG.FLAT)
        OnscreenText(parent=ui, text="v" + VERSION, pos=(-ar + 0.05, -0.96), scale=0.03, fg=DIM, align=TextNode.A_left, font=self.fontp)
        def blink(task):
            if not t.is_empty(): t.setFg((1, 1, 1, 0.45 + 0.55 * abs(math.sin(task.time * 2.2)))); return task.cont
            return task.done
        self.taskMgr.add(blink, "blink"); self.ui_enter = self.main_menu

    def header(self, ui, title, sub=""):
        ar = self.getAspectRatio(); x = 0; root = self.ui
        OnscreenText(parent=ui, text=title, pos=(x, 0.78), scale=0.085, fg=GOLD, align=TextNode.A_left, font=self.font)
        if sub: OnscreenText(parent=ui, text=sub, pos=(x, 0.71), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.fontp)
        xp = self.profile["xp"]; r = D.rank_of(xp); nxt = D.RANKS[r + 1][1] if r + 1 < len(D.RANKS) else xp
        OnscreenText(parent=root, text="%s   %d XP" % (D.RANKS[r][0], xp), pos=(ar - 0.06, 0.9), scale=0.035, fg=WHITE, align=TextNode.A_right, font=self.font)
        k = 1 if nxt == xp else (xp - D.RANKS[r][1]) / max(1, nxt - D.RANKS[r][1])
        DirectFrame(parent=root, frameColor=(0.2, 0.2, 0.18, 1), frameSize=(ar - 0.5, ar - 0.06, 0.865, 0.875))
        DirectFrame(parent=root, frameColor=GOLD, frameSize=(ar - 0.5, ar - 0.5 + 0.44 * k, 0.865, 0.875))
        return x

    def main_menu(self):
        self._menu_fn = lambda: self.main_menu()
        ui = self.new_ui(); x = self.header(ui, "MAIN MENU", "Camp Kim  -  Kims Army training command"); cx = x + 0.4
        items = [("CAMPAIGN", self.campaign_menu), ("COKA ONLINE AI TRAINING", self.ai_menu), ("SHOOTING RANGE", lambda: self.start("range")),
                 ("LOADOUT", self.loadout_menu), ("SETTINGS", self.settings_menu), ("QUIT", self.quit_game)]
        for i, (t, c) in enumerate(items): self.btn(ui, t, c, (cx + 0.12, 0, 0.42 - i * 0.14), w=0.95)
        done = len(self.profile["done"])
        OnscreenText(parent=ui, text="Campaign %d / 6   |   Range best %d" % (done, self.profile.get("range_best", 0)), pos=(x, -0.5), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.fontp)
        OnscreenText(parent=ui, text="WASD move  |  Mouse aim  |  LMB fire  |  RMB aim down sights  |  Shift sprint  |  C crouch (slide while sprinting)\n"
                     "Space jump  |  R reload  |  G grenade  |  V knife  |  F use  |  1/2 weapons  |  Tab scoreboard  |  Esc pause",
                     pos=(x, -0.62), scale=0.034, fg=DIM, align=TextNode.A_left, font=self.fontp)
        if self.upd_text: OnscreenText(parent=ui, text=self.upd_text, pos=(x, -0.8), scale=0.034, fg=GOLD, align=TextNode.A_left, font=self.font)
        self.ui_back = self.title_screen; self.ui_enter = None

    def campaign_menu(self):
        self._menu_fn = lambda: self.campaign_menu()
        ui = self.new_ui(); x = self.header(ui, "CAMPAIGN", "Ana's training at Camp Kim  -  six missions")
        for i, (mid, t, sub, tod, br) in enumerate(D.MISSIONS):
            ok = i == 0 or D.MISSIONS[i - 1][0] in self.profile["done"] or os.environ.get("COKA_UNLOCK")
            done = mid in self.profile["done"]
            self.btn(ui, "%d.  %s%s" % (i + 1, t, "   [DONE]" if done else ("" if ok else "   [LOCKED]")), (lambda m=mid: self.briefing(m)), (x + 0.52, 0, 0.5 - i * 0.135), w=1.04, active=bool(ok))
            OnscreenText(parent=ui, text=sub + ("   (night)" if tod == "night" else ("   (dusk)" if tod == "dusk" else "")), pos=(x + 1.1, 0.48 - i * 0.135), scale=0.035, fg=DIM, align=TextNode.A_left, font=self.fontp)
        self.btn(ui, "BACK", self.main_menu, (x + 0.2, 0, -0.42), w=0.4); self.ui_back = self.main_menu

    def briefing(self, mid):
        self._menu_fn = lambda: self.briefing(mid)
        m = [q for q in D.MISSIONS if q[0] == mid][0]; ui = self.new_ui("world"); x = self.header(ui, m[1], "BRIEFING  -  " + m[2])
        self.apply_tod(m[3]); self.render.set_shader_input("flon", 0.0)
        focus = {"m1": (60, -9), "m2": (-89, -8), "m3": (-40, 61), "m4": (0, 0), "m5": (-40, -34), "m6": (88, 66)}[mid]
        self.flycam = dict(t=0.0, c=focus, a=random.uniform(0, 6.28))
        im = OnscreenImage(image=A("ana_portrait.jpg"), parent=ui, scale=0.22, pos=(x + 0.22, 0, 0.38))
        OnscreenText(parent=ui, text="ANA\nRecruit, Kims Army", pos=(x + 0.5, 0.5), scale=0.04, fg=WHITE, align=TextNode.A_left, font=self.font)
        lines = OnscreenText(parent=ui, text="", pos=(x, 0.05), scale=0.04, fg=WHITE, align=TextNode.A_left, font=self.fontp, wordwrap=34, mayChange=True)
        st = {"i": 0, "t": 0.0, "txt": ""}
        def step(task):
            if self.ui is not ui or lines.is_empty(): return task.done
            if task.time >= st["t"] and st["i"] < len(m[4]):
                who, line = m[4][st["i"]]; d = self.play_voice("%s_%d" % (mid, st["i"]))
                st["txt"] += ("COL. KIM:  " if who == "KIM" else "ANA:  ") + line + "\n\n"; lines.setText(st["txt"]); st["i"] += 1; st["t"] = task.time + d + 0.35
            return task.cont
        self.taskMgr.add(step, "brief")
        go = lambda: (self.voice.stop() if self.voice else None, self.start("mission", mid))
        self.btn(ui, "DEPLOY", go, (x + 0.35, 0, -0.62), w=0.6, sel=True); self.btn(ui, "BACK", self.campaign_menu, (x + 1.05, 0, -0.62), w=0.5)
        self.ui_back = self.campaign_menu; self.ui_enter = go

    def ai_menu(self):
        self._menu_fn = lambda: self.ai_menu()
        ui = self.new_ui(); x = self.header(ui, "COKA ONLINE AI TRAINING", "Bot matches on the camp map with match XP"); S = self.settings
        def setm(m): S["mode"] = m; self.ai_menu()
        def setd(d): S["diff"] = d; self.ai_menu()
        OnscreenText(parent=ui, text="MODE", pos=(x, 0.5), scale=0.04, fg=DIM, align=TextNode.A_left, font=self.font)
        self.btn(ui, "TEAM DEATHMATCH 6v6", lambda: setm("tdm"), (x + 0.75, 0, 0.5), w=0.75, sel=S["mode"] == "tdm")
        self.btn(ui, "FREE-FOR-ALL 8", lambda: setm("ffa"), (x + 1.55, 0, 0.5), w=0.75, sel=S["mode"] == "ffa")
        OnscreenText(parent=ui, text="BOTS", pos=(x, 0.33), scale=0.04, fg=DIM, align=TextNode.A_left, font=self.font)
        for i, (n, _) in enumerate(D.DIFF): self.btn(ui, n, (lambda i=i: setd(i)), (x + 0.6 + i * 0.52, 0, 0.33), w=0.48, sel=S.get("diff", 1) == i)
        OnscreenText(parent=ui, text=("Two teams of six: you and five Kims Army bots against six Red Team bots.\nFirst team to 40 kills, or the higher score after 8 minutes."
                                      if S["mode"] == "tdm" else "Eight soldiers, everyone for themselves.\nFirst to 20 kills, or the leader after 8 minutes.") +
                     "\n\nXP: kill 100, headshot +50, knife +60, match +250, win +500.\nThese are AI bots on your PC, so no internet is needed.",
                     pos=(x, 0.15), scale=0.034, fg=WHITE, align=TextNode.A_left, font=self.fontp)
        g = lambda: (self.save_profile(), self.start(S["mode"]))
        self.btn(ui, "START MATCH", g, (x + 0.4, 0, -0.4), w=0.7, sel=True); self.btn(ui, "BACK", self.main_menu, (x + 1.15, 0, -0.4), w=0.5)
        self.ui_back = self.main_menu; self.ui_enter = g

    def loadout_menu(self, back=None):
        self._menu_fn = lambda: self.loadout_menu(back)
        back = back or self.main_menu
        ui = self.new_ui(); x = self.header(ui, "LOADOUT", "Unlock weapons, attachments, camos and perks by ranking up"); pr = self.profile; rk = D.rank_of(pr["xp"])
        OnscreenText(parent=ui, text="PRIMARY", pos=(x, 0.6), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.font)
        prim = [w for w in D.WEAPONS if w["slot"] == 0]
        for i, w in enumerate(prim):
            ok = rk >= w["rank"]
            self.btn(ui, w["name"] if ok else "%s  (%s)" % (w["name"], D.RANKS[w["rank"]][0]), (lambda w=w: (pr.__setitem__("primary", w["id"]), self.loadout_menu(back))),
                     (x + 0.42, 0, 0.5 - i * 0.1), w=0.84, scale=0.04, active=ok, sel=pr["primary"] == w["id"])
        w = D.W[pr["primary"]]
        OnscreenText(parent=ui, text="%s  -  %s\nDamage %d   Rate %d rpm   Mag %d   Range %d m" % (w["name"], w["cls"], w["dmg"], w["rpm"], w["mag"], w["rng"]),
                     pos=(x, -0.03), scale=0.036, fg=WHITE, align=TextNode.A_left, font=self.fontp)
        OnscreenText(parent=ui, text="SECONDARY: P-11 WASP", pos=(x, -0.16), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.fontp)
        ax = x + 1.0
        OnscreenText(parent=ui, text="ATTACHMENTS (%s)" % w["name"], pos=(ax, 0.6), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.font)
        cur = pr["attach"].setdefault(pr["primary"], [])
        def tog(a):
            if a in cur: cur.remove(a)
            else:
                if a in ("reddot", "scope4"):
                    for o in ("reddot", "scope4"):
                        if o in cur: cur.remove(o)
                cur.append(a)
            self.loadout_menu(back)
        for i, (aid, an, ar_, desc) in enumerate(D.ATTACH):
            ok = rk >= ar_ and not (aid == "scope4" and pr["primary"] != "kr4") and not (aid == "reddot" and pr["primary"] == "sr50")
            self.btn(ui, ("[x] " if aid in cur else "[  ] ") + an + ("" if rk >= ar_ else "  (%s)" % D.RANKS[ar_][0]), (lambda a=aid: tog(a)), (ax + 0.45, 0, 0.5 - i * 0.1), w=0.9, scale=0.036, active=ok)
        OnscreenText(parent=ui, text="CAMO", pos=(ax, -0.03), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.font)
        for i, (cid, cn, cr, pal) in enumerate(D.CAMOS):
            ok = rk >= cr
            self.btn(ui, cn if ok else "%s (%s)" % (cn, D.RANKS[cr][0]), (lambda c=cid: (pr.__setitem__("camo", c), self.loadout_menu(back))),
                     (ax + 0.24 + (i % 2) * 0.5, 0, -0.12 - (i // 2) * 0.09), w=0.48, scale=0.034, active=ok, sel=pr["camo"] == cid)
        OnscreenText(parent=ui, text="PERKS (pick 2)", pos=(x, -0.3), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.font)
        def perk(p_):
            if p_ in pr["perks"]: pr["perks"].remove(p_)
            else:
                pr["perks"].append(p_); pr["perks"][:] = pr["perks"][-2:]
            self.loadout_menu(back)
        for i, (pid, pn, prk, desc) in enumerate(D.PERKS):
            ok = rk >= prk
            self.btn(ui, ("[x] " if pid in pr["perks"] else "") + pn + ("" if ok else " (%s)" % D.RANKS[prk][0]), (lambda p_=pid: perk(p_)), (x + 0.24 + (i % 3) * 0.5, 0, -0.39 - (i // 3) * 0.09), w=0.48, scale=0.034, active=ok)
        sel = [p for p in D.PERKS if p[0] in pr["perks"]]
        OnscreenText(parent=ui, text="   ".join("%s: %s" % (p[1], p[3]) for p in sel), pos=(x, -0.6), scale=0.034, fg=WHITE, align=TextNode.A_left, font=self.fontp)
        def done(): self.save_profile(); back()
        self.btn(ui, "DONE", done, (x + 0.25, 0, -0.75), w=0.45, sel=True); self.ui_back = done

    def settings_menu(self, back=None):
        self._menu_fn = lambda: self.settings_menu(back)
        back = back or self.main_menu
        ui = self.new_ui(); x = self.header(ui, "SETTINGS", "Graphics, controls and sound"); S = self.settings
        def gfx(m): S["gfx"] = m; self.save_profile(); self.settings_menu(back)
        OnscreenText(parent=ui, text="GRAPHICS", pos=(x, 0.55), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.font)
        self.btn(ui, "RTX", lambda: gfx("RTX"), (x + 0.75, 0, 0.55), w=0.45, sel=S["gfx"] == "RTX"); self.btn(ui, "EX HD", lambda: gfx("EXHD"), (x + 1.25, 0, 0.55), w=0.45, sel=S["gfx"] == "EXHD")
        OnscreenText(parent=ui, text="RTX: 4x MSAA, 16x anisotropic filtering, denser smoke and fire.  EX HD: 2x MSAA, 8x AF, lighter particles.  (Same cinematic grade, no bloom.)\nAnti-aliasing changes apply the next time you start the game.",
                     pos=(x, 0.46), scale=0.033, fg=DIM, align=TextNode.A_left, font=self.fontp)
        def slider(lbl, key, lo, hi, y, fmt):
            OnscreenText(parent=ui, text=lbl, pos=(x, y - 0.015), scale=0.036, fg=DIM, align=TextNode.A_left, font=self.font)
            val = OnscreenText(parent=ui, text=fmt % S[key], pos=(x + 1.7, y - 0.015), scale=0.036, fg=WHITE, align=TextNode.A_left, font=self.font, mayChange=True)
            def ch():
                S[key] = round(sl["value"], 2); val.setText(fmt % S[key])
                if key == "vol": self.set_volume()
            sl = DirectSlider(parent=ui, range=(lo, hi), value=S[key], pos=(x + 1.05, 0, y), scale=0.5, command=ch, frameColor=(0.2, 0.2, 0.18, 1), thumb_frameColor=GOLD, thumb_relief=DGG.FLAT)
        slider("MOUSE SENSITIVITY", "sens", 0.2, 3.0, 0.3, "%.2f"); slider("FIELD OF VIEW", "fov", 65, 105, 0.18, "%d")
        slider("MASTER VOLUME", "vol", 0.0, 1.0, 0.06, "%.2f"); slider("VOICE VOLUME", "voice", 0.0, 1.0, -0.06, "%.2f")
        def fs():
            S["fullscreen"] = not S["fullscreen"]; wp = WindowProperties(); wp.set_fullscreen(S["fullscreen"])
            if S["fullscreen"]: wp.set_size(self.pipe.get_display_width(), self.pipe.get_display_height())
            self.win.request_properties(wp); self.settings_menu(back)
        self.btn(ui, "FULLSCREEN: %s" % ("ON" if S["fullscreen"] else "OFF"), fs, (x + 0.4, 0, -0.22), w=0.75)
        def upd():
            self.upd_text = None; self.check_update(); self.settings_menu(back)
        self.btn(ui, "CHECK FOR UPDATES", upd, (x + 1.25, 0, -0.22), w=0.75)
        OnscreenText(parent=ui, text=self.upd_text or ("COKA v%s  -  you have the latest version (or no connection)." % VERSION), pos=(x, -0.34), scale=0.035, fg=WHITE, align=TextNode.A_left, font=self.fontp)
        OnscreenText(parent=ui, text=D.FICTION + "\nVoices: Piper TTS, VCTK voices (CC BY 4.0). Engine: Panda3D. Font: Exo 2 (OFL).", pos=(x, -0.45), scale=0.033, fg=DIM, align=TextNode.A_left, font=self.fontp)
        def done(): self.save_profile(); back()
        self.btn(ui, "DONE", done, (x + 0.25, 0, -0.7), w=0.45, sel=True); self.ui_back = done

    def pause_menu(self):
        self._menu_fn = self.pause_menu
        self.clear_ui(); ui = self.ui = self.aspect2d.attach_new_node("pause"); s = self.session
        DirectFrame(parent=ui, frameColor=(0, 0, 0, 0.6), frameSize=(-3, 3, -1.2, 1.2)); ui = self.content(0, center=True)
        OnscreenText(parent=ui, text="PAUSED", pos=(0, 0.45), scale=0.1, fg=GOLD, font=self.font)
        back_here = lambda: (self.clear_ui(), self.pause_menu())
        items = [("RESUME", lambda: self.pause(False))]
        if s.mode == "range": items.append(("LOADOUT", lambda: self.loadout_menu(self.reload_range)))
        if s.mode == "mission": items.append(("RESTART CHECKPOINT", lambda: (self.pause(False), s.start_stage(s.stage, restart=True))))
        items += [("SETTINGS", lambda: self.settings_menu(back_here)), ("QUIT TO MENU", lambda: (self.end_session(), self.main_menu()))]
        for i, (t, c) in enumerate(items): self.btn(ui, t, c, (0, 0, 0.25 - i * 0.13), w=0.8)
        self.ui_back = lambda: self.pause(False)

    def quit_game(self):
        self.save_profile(); self.userExit()

    def reload_range(self):
        self.end_session(); self.start("range")

    def results(self, s):
        self._menu_fn = lambda: self.results(s)
        if self.session is not s: return
        win, title = s.over; self.hud.show(False); self.hud.red.hide()
        ui = self.new_ui(); x = self.header(ui, title, {"mission": "Campaign", "tdm": "Team Deathmatch", "ffa": "Free-for-all", "range": "Range"}[s.mode])
        txt = "XP EARNED   +%d\nKILLS   %d     DEATHS   %d\n" % (s.xp_gain, s.player.kills, s.player.deaths)
        if s.mode == "tdm": txt += "FINAL SCORE   KIMS ARMY %d  :  %d RED TEAM\n" % tuple(s.score)
        OnscreenText(parent=ui, text=txt, pos=(x, 0.5), scale=0.045, fg=WHITE, align=TextNode.A_left, font=self.font)
        if s.mode in ("tdm", "ffa"):
            rows = s.scoreboard()[:12]
            OnscreenText(parent=ui, text="\n".join("%-22s %4d %4d" % (r[0][:22], r[2], r[3]) for r in rows), pos=(x, 0.2), scale=0.03, fg=DIM, align=TextNode.A_left, font=self.fontp)
        def cont():
            mid = s.mission; mode = s.mode; self.end_session()
            if mode == "mission":
                i = [m[0] for m in D.MISSIONS].index(mid)
                if win and i + 1 < len(D.MISSIONS): self.briefing(D.MISSIONS[i + 1][0]); return
                self.campaign_menu(); return
            self.main_menu()
        self.btn(ui, "CONTINUE", cont, (x + 0.35, 0, -0.6), w=0.6, sel=True); self.ui_back = cont; self.ui_enter = cont

    # ------------------------------------------------------------------------------------------- automated test (COKA_TEST)
    def autotest_start(self, task):
        spec = TEST.split(":"); self.shots_dir = os.environ.get("COKA_SHOTS", os.path.join(PROFDIR, "shots")); os.makedirs(self.shots_dir, exist_ok=True)
        self.at = dict(name=spec[0], t=0.0, shots=[float(v) for v in os.environ.get("COKA_AT", "3,8,14").split(",")], end=float(os.environ.get("COKA_END", "20")))
        n = spec[0]
        if n in ("title", "main", "loadout", "brief", "ai", "settings", "campaign"):
            {"title": self.title_screen, "main": self.main_menu, "loadout": self.loadout_menu, "brief": lambda: self.briefing("m1"), "ai": self.ai_menu,
             "settings": self.settings_menu, "campaign": self.campaign_menu}[n]()
        elif n in ("range", "tdm", "ffa"): self.start(n)
        elif n == "pause": self.start("range"); self.taskMgr.doMethodLater(2.0, lambda t: self.pause(True), "atp")
        elif n == "sb": self.start("tdm"); self.tab_down = True
        else: self.start("mission", n)
        if len(spec) > 1 and self.session: self.session.start_stage(int(spec[1]), restart=True)
        self.taskMgr.add(self.autotest_tick, "att"); return task.done

    def autotest_tick(self, task):
        at = self.at; at["t"] = task.time
        if at["shots"] and task.time >= at["shots"][0]:
            at["shots"].pop(0); fn = os.path.join(self.shots_dir, "%s_%02d.png" % (at["name"], int(task.time)))
            from panda3d.core import Filename as _F; self.win.save_screenshot(_F.from_os_specific(fn)); log("shot %s" % fn)
            s = self.session

            if s: log("state t=%.1f hp=%.0f kills=%d deaths=%d stage=%d obj=%s xp=%d fps=%.1f" % (s.time, s.player.hp, s.player.kills, s.player.deaths, s.stage, s.objective, s.xp_gain, globalClock.get_average_frame_rate()))
        if task.time >= at["end"]:
            s = self.session
            if s: log("END %s stage=%d over=%s kills=%d deaths=%d xp=%d score=%s" % (at["name"], s.stage, s.over, s.player.kills, s.player.deaths, s.xp_gain, getattr(s, "score", "")))
            self.save_profile(); self.userExit()
        return task.cont

    def autopilot(self, s):
        """test driver: walk to the objective marker, aim at the nearest visible enemy / raised target, shoot"""
        p = s.player; inp = dict(mx=0, my=0, w=False, a=False, s=False, d=False, sprint=False, fire=False, fire_pressed=False, ads=False, jump=False,
                                 crouch_pressed=False, crouch_held=False, reload=False, nade=False, melee=False, use=True, light=False, swap=None)
        best, bd = None, 80
        for t in s.targets:
            if t.up and t.k > 0.9:
                d = math.hypot(t.x - p.x, t.y - p.y)
                if d < bd: best, bd = (t.x, t.y, 1.2), d
        for a in s.actors:
            if a.dead or (a.team == 0 and s.mode != "ffa"): continue
            d = math.hypot(a.x - p.x, a.y - p.y)
            if d < bd and s.world.los(p.eye(), a.eye()): best, bd = (a.x, a.y, a.z + 1.3), d
        goal = s.marker
        if s.mode in ("tdm", "ffa") and best is None:
            es = [a for a in s.actors if not a.dead and (a.team != 0 or s.mode == "ffa")]
            if es: e = min(es, key=lambda a: math.hypot(a.x - p.x, a.y - p.y)); goal = (e.x, e.y)
        if best is not None:
            th = P.ang_to(best[0] - p.x, best[1] - p.y); tp = math.degrees(math.atan2(best[2] - p.z - 1.62, max(bd, 0.1)))
            inp["mx"] = -P.adiff(th, p.h) * 0.35; inp["my"] = -(tp - p.p) * 0.35
            if abs(P.adiff(th, p.h)) < 3: inp["fire"] = True; inp["fire_pressed"] = random.random() < 0.3; inp["ads"] = bd > 30
        elif goal is not None:
            if not hasattr(self, "at_path") or self.at_goal != goal or not self.at_path or random.random() < 0.01:
                self.at_path = s.world.path((p.x, p.y), goal) or [goal]; self.at_goal = goal
            wx, wy = self.at_path[0]
            if math.hypot(wx - p.x, wy - p.y) < 1.2 and len(self.at_path) > 1: self.at_path.pop(0)
            th = P.ang_to(wx - p.x, wy - p.y); inp["mx"] = -P.adiff(th, p.h) * 0.3; inp["my"] = p.p * 0.2
            inp["w"] = math.hypot(wx - p.x, wy - p.y) > 1.0; inp["sprint"] = True
            if s.overhead(p.x + math.sin(math.radians(-p.h)) * 1.5, p.y + math.cos(math.radians(p.h)) * 1.5, 1.75) and not p.crouch: inp["crouch_pressed"] = True
            if any(b[6] == "wood" and b[5] < 1.0 and b[0] - 1.2 < p.x < b[3] + 1.2 and b[1] - 1.2 < p.y < b[4] + 1.2 for b in s.world.boxes): inp["jump"] = True
        w = s.weapons[s.cur]
        if w.mag == 0 and w.res == 0: inp["swap"] = 1 - s.cur
        if os.environ.get("COKA_AT_STRAFE") and int(s.time) % 4 < 2: inp["d"] = True
        return inp


def main():
    try:
        App().run()
    except SystemExit: pass
    except Exception:
        log(traceback.format_exc())
        if getattr(sys, "frozen", False): os._exit(1)
        raise


if __name__ == "__main__":
    main()
