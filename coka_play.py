"""COKA gameplay: player, bots, targets, grenades, campaign stages and AI-training matches."""
import math, random
from panda3d.core import Vec3, Point3, CardMaker, NodePath, TransparencyAttrib, PNMImage, Texture, SamplerState
from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode
import coka_data as D
from coka_gfx import build_soldier, build_gun, blob_shadow, set_camo, set_light
from coka_world import EDGE, build_truck
from fs_geom import MB
from coka_gfx import node as mbnode

TEAMCOL = {0: (0.25, 0.5, 0.95, 1), 1: (0.85, 0.16, 0.12, 1), 2: (0.95, 0.55, 0.1, 1)}
ENEMY_CAMO = [(0.52, 0.47, 0.40), (0.36, 0.33, 0.27), (0.62, 0.58, 0.50), (0.25, 0.23, 0.2)]
FRIEND_CAMO = D.CAMO["desert"][3]


def fwd(h, p=0.0):
    hr, pr = math.radians(h), math.radians(p)
    return Vec3(-math.sin(hr) * math.cos(pr), math.cos(hr) * math.cos(pr), math.sin(pr))


def ang_to(dx, dy):
    return math.degrees(math.atan2(-dx, dy))


def adiff(a, b):
    return (a - b + 180) % 360 - 180


def ray_actor(o, d, a, maxd):
    """ray vs actor: head sphere then body cylinder. returns (t, headshot) or None"""
    hz = a.z + (1.2 if a.crouch else 1.62)
    best = None
    cx, cy = a.x - o[0], a.y - o[1]; cz = hz - o[2]
    b = cx * d[0] + cy * d[1] + cz * d[2]
    if b > 0:
        c2 = cx * cx + cy * cy + cz * cz - b * b
        if c2 < 0.16 * 0.16:
            t = b - math.sqrt(0.16 * 0.16 - c2)
            if t < maxd: best = (t, True)
    dx, dy = d[0], d[1]; A = dx * dx + dy * dy
    if A > 1e-8:
        fx, fy = o[0] - a.x, o[1] - a.y; B = 2 * (fx * dx + fy * dy); C = fx * fx + fy * fy - 0.3 * 0.3
        disc = B * B - 4 * A * C
        if disc >= 0:
            t = (-B - math.sqrt(disc)) / (2 * A)
            if t > 0:
                z = o[2] + d[2] * t
                if a.z < z < hz - 0.12 and (best is None or t < best[0]) and t < maxd: best = (t, False)
    return best


class Weapon:
    def __init__(self, wid, att, perks):
        self.d = D.W[wid]; self.id = wid; self.att = list(att)
        self.mag_size = int(self.d["mag"] * (1.5 if "extmag" in att else 1)); self.mag = self.mag_size; self.res = self.d["res"]
        self.reload = 1.6 if wid in ("p11", "km9") else (2.6 if wid in ("sg12", "sr50") else 2.1)
        if "quickhands" in perks: self.reload *= 0.7
        self.cd = 60.0 / self.d["rpm"]; self.t = 0.0


class Actor:
    """a soldier in the world (bots; the player is an Actor too, for hit tests)"""
    def __init__(self, s, name, team, x, y, h=0, wid="km9", bot=True, model=True, camo=None, female=False):
        self.s = s; self.name = name; self.team = team; self.x, self.y, self.z = x, y, 0.0; self.h = h; self.p = 0.0
        self.hp = 100.0; self.maxhp = 100.0; self.dead = False; self.dt = 0; self.crouch = False; self.bot = bot
        self.kills = 0; self.deaths = 0; self.score = 0; self.vx = self.vy = 0.0; self.last_fire = -9; self.last_hit_by = None
        self.np = None
        if model:
            r = random.Random(hash(name) & 0xffff)
            self.np = s.root.attach_new_node("actor")
            self.model, self.legs, self.up, self.head, gun = build_soldier(self.np, r, band=TEAMCOL[team] if team != 0 or s.mode in ("tdm",) else None,
                                                                           female=female, flag_tex=s.app.tex["flag"] if team == 0 else None)
            set_camo(self.model, camo or (FRIEND_CAMO if team == 0 else ENEMY_CAMO))
            self.gun = build_gun(gun, wid, camo=False); self.shadow = blob_shadow(self.np, s.app.tex["smoke"])
            self.np.set_pos(x, y, 0); self.np.set_h(h)
        self.w = Weapon(wid, (), ()); self.anim = random.random() * 6
        # brain
        self.target = None; self.react = 0; self.burst = 0; self.path = None; self.goal = None; self.repath = 0; self.behav = "hunt"
        self.home = (x, y); self.patrol = None; self.pi = 0; self.strafe = 1; self.st = 0; self.think = random.random() * 0.3; self.heard = None
        self.goal_used = None; self.stuck = 0; self.lx, self.ly = x, y; self.respawn = 0; self.sink = 0; self.speed = 3.9

    def eye(self):
        return (self.x, self.y, self.z + (1.15 if self.crouch else 1.55))

    def remove(self):
        if self.np is not None: self.np.remove_node(); self.np = None

    def sync(self, dt):
        if self.np is None: return
        self.np.set_pos(self.x, self.y, self.z - self.sink); self.np.set_h(self.h)
        if self.dead:
            k = min(1.0, self.dt / 0.55); self.model.set_p(-88 * k * k); self.model.set_y(-0.2 * k)
            return
        sp = math.hypot(self.vx, self.vy); self.anim += dt * sp * 2.2
        sw = math.sin(self.anim) * min(1.0, sp / 3.0) * 32
        self.legs[0].set_p(sw); self.legs[1].set_p(-sw)
        self.up.set_z(0.92 - (0.32 if self.crouch else 0) + abs(math.sin(self.anim)) * 0.03 * min(1, sp / 3))
        for l in self.legs: l.set_z(0.93 - (0.32 if self.crouch else 0))
        if self.crouch: self.legs[0].set_p(70); self.legs[1].set_p(20)
        self.up.set_p(self.p * 0.6)


class Target:
    """range pop-up target: silhouette on a hinge facing -X (towards the firing line)"""
    def __init__(self, s, x, y, face=-90):
        self.s = s; self.x, self.y = x, y; self.up = False; self.k = 0.0; self.t = 0; self.timer = 0
        self.np = s.root.attach_new_node("target"); self.np.set_pos(x, y, 0); self.np.set_h(face)
        cm = CardMaker("t"); cm.set_frame(-0.45, 0.45, 0.15, 1.95); c = self.np.attach_new_node(cm.generate()); c.set_two_sided(True)
        c.set_texture(s.app.tex["target"], 1); c.set_shader_input("use_tex", 1.0); c.set_transparency(TransparencyAttrib.M_binary)
        self.card = c
        mb = MB("base"); mb.box(-0.6, -0.25, 0, 0.6, 0.25, 0.22, (0.3, 0.32, 0.25, 1)); mbnode(mb, self.np)
        self.box = [x - 0.25, y - 0.45, 0.25, x + 0.25, y + 0.45, 1.9, "target", self, False]; s.world.dyn.append(self.box)
        self.card.set_p(-90)

    def pop(self, dur=3.0):
        self.up = True; self.timer = dur

    def update(self, dt):
        if self.up:
            self.k = min(1, self.k + dt * 6); self.timer -= dt
            if self.timer <= 0: self.up = False
        else: self.k = max(0, self.k - dt * 5)
        self.card.set_p(-90 * (1 - self.k)); self.box[8] = self.k > 0.9

    def remove(self):
        self.np.remove_node()
        if self.box in self.s.world.dyn: self.s.world.dyn.remove(self.box)


class Grenade:
    def __init__(self, s, o, v, owner):
        self.s = s; self.p = Vec3(*o); self.v = Vec3(*v); self.t = 2.2; self.owner = owner
        mb = MB("g"); from coka_gfx import ellipsoid; ellipsoid(mb, 0, 0, 0, 0.05, 0.05, 0.065, (0.22, 0.26, 0.18, 1), seg=8, ring=5)
        self.np = mbnode(mb, s.root); self.np.set_pos(self.p)

    def update(self, dt):
        self.t -= dt; self.v[2] -= 16 * dt; np_ = self.p + self.v * dt
        g = self.s.world.ground(np_[0], np_[1], self.p[2], 0.05)
        t, kind, _ = self.s.world.ray(self.p, (self.v / max(self.v.length(), 0.001)), self.v.length() * dt + 0.05) if self.v.length() > 0.1 else (9, None, None)
        if kind is not None and t < self.v.length() * dt + 0.05:
            self.v[0] *= -0.35; self.v[1] *= -0.35; np_ = self.p
        if np_[2] < g + 0.05:
            np_[2] = g + 0.05; self.v[2] = abs(self.v[2]) * 0.3; self.v[0] *= 0.6; self.v[1] *= 0.6
        self.p = np_; self.np.set_pos(self.p)
        if self.t <= 0:
            self.s.explode(self.p, self.owner); self.np.remove_node(); return False
        return True


class Truck:
    """convoy truck that follows the road; it waits for the player and can be destroyed"""
    def __init__(self, s, path):
        self.s = s; self.path = path; self.i = 1; self.x, self.y = path[0]; self.h = ang_to(path[1][0] - self.x, path[1][1] - self.y)
        self.hp = 1000.0; self.maxhp = 1000.0; self.np = s.root.attach_new_node("truck")
        m = {k: MB(k) for k in ("plain", "canvas", "camo")}
        build_truck(m["plain"], m["canvas"], m["camo"], 0, 0, 0)
        mbnode(m["plain"], self.np, gloss=0.3); mbnode(m["canvas"], self.np, tex=s.app.tex["canvas"], gloss=0.05); mbnode(m["camo"], self.np, camo=True).set_shader_input("camoscale", 2.2)
        set_camo(self.np, D.CAMO["woodland"][3]); self.box = [0, 0, 0, 0, 0, 2.8, "metal", self, True]; s.world.dyn.append(self.box); self.done = False
        self.sync()

    def sync(self):
        self.np.set_pos(self.x, self.y, 0); self.np.set_h(self.h)
        self.box[0], self.box[1], self.box[3], self.box[4] = self.x - 2.6, self.y - 2.6, self.x + 2.6, self.y + 2.6

    def update(self, dt, go):
        if self.done or self.i >= len(self.path): self.done = True; return
        tx, ty = self.path[self.i]; dx, dy = tx - self.x, ty - self.y; L = math.hypot(dx, dy)
        if L < 1.0: self.i += 1; return
        th = ang_to(dx, dy); self.h += max(-40 * dt, min(40 * dt, adiff(th, self.h)))
        if go:
            sp = 3.6 * dt; f = fwd(self.h); self.x += f[0] * sp; self.y += f[1] * sp
            if random.random() < 0.3: self.s.fx.dust(self.x - f[0] * 4, self.y - f[1] * 4, 0.3)
        self.sync()


# ====================================================================================================================
class Session:
    """one play session: range, campaign mission or AI-training match"""
    def __init__(self, app, mode, mission=None, diff=1):
        self.app = app; self.mode = mode; self.mission = mission; self.diff = D.DIFF[diff][1]; self.diff_i = diff
        self.world = app.world; self.root = app.render.attach_new_node("session"); self.fx = app.fx
        self.actors = []; self.targets = []; self.grenades = []; self.feed = []; self.time = 0.0; self.over = None; self.paused = False
        self.xp_gain = 0; self.objective = ""; self.marker = None; self.stage = 0; self.stages = []; self.trucks = []
        self.hold = 0.0; self.hits = 0; self.shots = 0; self.range_score = 0; self.msg = None; self.msg_t = 0
        self.tod = "golden"
        if mode == "mission": self.tod = [m for m in D.MISSIONS if m[0] == mission][0][3]
        app.apply_tod(self.tod)
        app.render.set_shader_input("flon", 0.0); app.vmroot.set_shader_input("flon", 0.0)
        pr = app.profile; perks = pr["perks"]
        self.player = Actor(self, "ANA", 0, 0, 0, 0, bot=False, model=False)
        self.player.maxhp = self.player.hp = 120.0 if "tough" in perks else 100.0
        prim = pr["primary"]; att = pr["attach"].get(prim, [])
        self.weapons = [Weapon(prim, att, perks), Weapon("p11", pr["attach"].get("p11", []), perks)]
        self.cur = 0; self.switch_t = 0; self.reload_t = 0; self.nades = 2; self.melee_t = 0
        self.vz = 0.0; self.on_ground = True; self.sprint = False; self.slide_t = 0; self.slide_v = Vec3(0); self.recoil = 0.0; self.bloom = 0.0
        self.last_dmg = -9; self.ads = 0.0; self.flash = 0; self.dmg_dir = None; self.hitm = 0; self.hit_head = False; self.shake = 0
        self.light = False; self.sprint_stam = 5.0
        app.build_viewmodel(self.weapons[self.cur])
        self.setup()

    # -------------------------------------------------------------------------------------------------- setup per mode
    def spawn_player(self, x, y, h):
        p = self.player; p.x, p.y, p.z, p.h, p.p = x, y, 0.0, h, 0.0; p.hp = p.maxhp; p.dead = False; p.crouch = False
        self.vz = 0; self.reload_t = 0; self.nades = 2
        for w in self.weapons: w.mag = w.mag_size; w.res = w.d["res"]

    def add_bot(self, team, x, y, h=0, behav="hunt", wid=None, name=None):
        if wid is None: wid = random.choice(["km9", "kr4", "kr4", "km9", "sg12"] + (["sr50"] if self.mode != "mission" else []))
        if name is None:
            pool = D.FRIENDS if team == 0 else D.BOTS; used = {a.name for a in self.actors}
            free = [n for n in pool if n not in used] or pool; name = random.choice(free)
        a = Actor(self, name, team, x, y, h, wid, female=random.random() < 0.3); a.behav = behav
        a.react = self.diff["react"]; self.actors.append(a); return a

    def setup(self):
        m = self.mode
        if m == "range":
            self.spawn_player(*self.world.spots["range"], -90)
            self.make_range(); self.objective = "FREE FIRE: shoot the pop-up targets. Esc for menu."
        elif m in ("tdm", "ffa"):
            self.score = [0, 0]; self.limit = 40 if m == "tdm" else 20; self.tlimit = 480.0
            if m == "tdm":
                self.spawns = {0: [(-60 + random.uniform(-8, 8), -30 + random.uniform(-6, 6)) for _ in range(8)],
                               1: [(60 + random.uniform(-8, 8), 30 + random.uniform(-6, 6)) for _ in range(8)]}
                self.spawn_player(*self.spawns[0][0], -90)
                for k in range(5): self.add_bot(0, *self.spawns[0][k + 1], -90)
                for k in range(6): self.add_bot(1, *self.spawns[1][k], 90)
                self.objective = "TEAM DEATHMATCH  6v6  -  first to %d" % self.limit
            else:
                self.spawn_player(-40, -10, -90)
                for k in range(7):
                    a = self.add_bot(2, *self.ffa_spawn(), random.uniform(0, 360)); a.team = 2 + k + 1
                self.objective = "FREE-FOR-ALL  8 players  -  first to %d" % self.limit
        else:
            self.stages = MISSION_STAGES[self.mission](self); self.start_stage(0)

    def ffa_spawn(self):
        best, bd = None, -1
        for _ in range(12):
            x, y = random.uniform(-95, 95), random.uniform(-95, 95)
            c = self.world.cell(x, y)
            if self.world.block[c]: continue
            d = min([math.hypot(a.x - x, a.y - y) for a in self.actors if not a.dead] + [math.hypot(self.player.x - x, self.player.y - y), 999])
            if d > bd: best, bd = (x, y), d
        return best or (0, -30)

    def make_range(self):
        for x in self.world.range_x:
            for y in self.world.lanes: self.targets.append(Target(self, x, y))
        self.range_next = 1.0

    def clear_stage_entities(self, keep_friends=True):
        for a in list(self.actors):
            if a.team != 0 or not keep_friends or a.dead:
                a.remove(); self.actors.remove(a)
        for t in self.targets: t.remove()
        self.targets = []
        for g in self.grenades: g.np.remove_node()
        self.grenades = []

    def start_stage(self, i, restart=False):
        self.stage = i; st = self.stages[i]; self.hold = 0.0
        if restart:
            self.clear_stage_entities()
        if "spawn" in st and (restart or i == 0 or st.get("respawn")):
            self.spawn_player(*st["spawn"])
        st["setup"](self); self.objective = st["text"]
        if i > 0 and not restart: self.app.play_voice("checkpoint"); self.banner("CHECKPOINT")
        self.ckpt = (self.player.x, self.player.y, self.player.h)
        st["spawn"] = self.ckpt

    # -------------------------------------------------------------------------------------------------- events
    def banner(self, t, sub="", dur=2.4):
        self.app.hud.banner(t, sub, dur)

    def kill_feed(self, killer, victim, how=""):
        self.app.hud.feed("%s  [%s]  %s" % (killer, how, victim))

    def give_xp(self, k, n=None, label=None):
        v = D.XP[k] if n is None else n; self.xp_gain += v
        old = D.rank_of(self.app.profile["xp"]); self.app.profile["xp"] += v; new = D.rank_of(self.app.profile["xp"])
        self.app.hud.xp_pop("+%d %s" % (v, label or k.upper()))
        if new > old:
            self.app.hud.rank_up(D.RANKS[new][0]); self.app.play_voice("rankup"); self.app.sfx("win", 0.7)
            self.app.save_profile()

    def damage(self, a, dmg, src, how="", head=False):
        if a.dead: return
        if a is self.player:
            if self.app.god: dmg = 0
            a.hp -= dmg; self.last_dmg = self.time; self.flash = 1.0
            if src is not None: self.dmg_dir = ang_to(src.x - a.x, src.y - a.y)
            if a.hp <= 0: self.on_death(a, src, how)
            return
        a.hp -= dmg; a.last_hit_by = src
        if a.target is None and src is not None and src.team != a.team: a.target = src; a.react = self.diff["react"] * 0.6
        if src is self.player: self.hitm = 0.25; self.hit_head = head; self.app.sfx("hit", 0.6)
        if a.hp <= 0: self.on_death(a, src, how or ("HEADSHOT" if head else "")); a.headshot = head

    def on_death(self, a, src, how):
        a.dead = True; a.dt = 0; a.deaths += 1; a.hp = 0
        kn = src.name if src is not None else "EXPLOSION"
        self.kill_feed(kn, a.name, how or (src.w.d["name"] if src is not None and src is not self.player else (self.weapons[self.cur].d["name"] if src is self.player else "")))
        if src is not None and src is not a:
            src.kills += 1; src.score += 100
            if src is self.player:
                self.give_xp("kill", label="KILL")
                if how == "HEADSHOT": self.give_xp("headshot", label="HEADSHOT")
                if how == "MELEE": self.give_xp("melee", label="MELEE")
                if "scavenger" in self.app.profile["perks"]:
                    w = self.weapons[self.cur]; w.res += w.mag_size
            if self.mode == "tdm" and src.team in (0, 1) and src.team != a.team: self.score[src.team] += 1
        if a is self.player:
            self.app.sfx("crash", 0.4, 0.6)
            if self.mode == "tdm": self.score[1] += 0 if src is None else 0
            self.respawn_t = 3.0 if self.mode in ("tdm", "ffa") else 2.5
        elif self.mode in ("tdm", "ffa"):
            a.respawn = 4.0

    def explode(self, p, owner):
        self.fx.explosion(p[0], p[1], max(p[2], 0)); self.app.sfx("crash", 1.0, 0.55, pos=p); self.shake = max(self.shake, 1.0 - min(1, (Vec3(self.player.x, self.player.y, 1.5) - p).length() / 30))
        for a in self.actors + [self.player]:
            if a.dead: continue
            d = math.sqrt((a.x - p[0]) ** 2 + (a.y - p[1]) ** 2 + (a.z + 1 - p[2]) ** 2)
            if d < 7.5 and self.world.los((p[0], p[1], p[2] + 0.4), (a.x, a.y, a.z + 1.0)):
                if owner is not None and a is not owner and a.team == owner.team and self.mode != "ffa": continue
                dmg = 150 * (1 - d / 7.5) ** 1.2
                if a is self.player and "flak" in self.app.profile["perks"]: dmg *= 0.55
                self.damage(a, dmg, owner, "GRENADE")
        for t in self.targets:
            if t.up and math.hypot(t.x - p[0], t.y - p[1]) < 4: self.target_hit(t)
        self.on_explode(p)

    def on_explode(self, p):
        st = self.stages[self.stage] if self.stages else None
        if st and "explode" in st: st["explode"](self, p)

    def target_hit(self, t):
        t.up = False; self.hits += 1; self.range_score += 1; self.give_xp("target", label="TARGET"); self.app.sfx("beep", 0.5)

    # -------------------------------------------------------------------------------------------------- shooting
    def hitscan(self, shooter, o, d, rng, dmg, pellets=1):
        """one bullet: nearest of world boxes and actors (not the shooter, no friendly fire)"""
        t, kind, own = self.world.ray(o, d, rng * 3)
        hit, head = None, False
        for a in self.actors + [self.player]:
            if a is shooter or a.dead: continue
            if self.mode != "ffa" and a.team == shooter.team: continue
            r = ray_actor(o, d, a, t)
            if r and r[0] < t: t, hit, head = r[0], a, r[1]
        p = Vec3(o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t)
        if hit is not None:
            k = 1.0 if t < rng else max(0.45, 1 - (t - rng) / (rng * 2))
            self.damage(hit, dmg * k * (2.0 if head else 1.0), shooter, "HEADSHOT" if head else "", head)
            if self.app.fx_on: self.fx.emit("smoke", p[0], p[1], p[2], 2, 0.05, (0, 0, 0.3), 0.25, 0.4, (0.45, 0.08, 0.06, 0.8), 1.8)
            return p, "flesh"
        if kind is not None:
            if kind == "target" and own is not None and own.up and shooter is self.player: self.target_hit(own)
            elif own is not None and isinstance(own, Truck) and shooter.team != 0: own.hp -= dmg * 0.6
            elif shooter is self.player and own is None: self.shot_world(p)
            if self.app.fx_on and t < 90:
                col = {"sand": (0.62, 0.55, 0.42, 0.75), "dirt": (0.6, 0.52, 0.4, 0.75), "wood": (0.55, 0.45, 0.32, 0.7), "metal": (0.4, 0.4, 0.38, 0.6)}.get(kind, (0.55, 0.5, 0.42, 0.7))
                self.fx.dust(p[0] - d[0] * 0.05, p[1] - d[1] * 0.05, p[2], col)
            return p, kind
        if d[2] < -0.001:
            tg = -o[2] / d[2]
            if tg < rng * 3 and self.app.fx_on: self.fx.dust(o[0] + d[0] * tg, o[1] + d[1] * tg, 0.05)
        return None, None

    def shot_world(self, p):
        st = self.stages[self.stage] if self.stages else None
        if st and "shot" in st: st["shot"](self, p)

    def player_fire(self):
        w = self.weapons[self.cur]; p = self.player
        if self.reload_t > 0 or self.switch_t > 0 or self.melee_t > 0: return
        if w.t > 0: return
        if w.mag <= 0:
            self.app.sfx("empty", 0.5); w.t = 0.25; self.start_reload(); return
        w.t = w.cd; w.mag -= 1; self.shots += 1; p.last_fire = self.time
        sup = "suppressor" in w.att
        self.app.sfx(w.d["snd"], 0.35 if sup else 0.8, w.d["rate"] * (1.15 if sup else 1.0))
        ads = self.ads > 0.7
        spread = (w.d["ads"] * (0.9 if "reddot" in w.att else 1.0) * (0.75 if "ironlungs" in self.app.profile["perks"] else 1.0)) if ads else w.d["hip"]
        mv = math.hypot(p.vx, p.vy); spread += mv * (0.12 if ads else 0.35) + self.bloom + (0 if self.on_ground else 3)
        if p.crouch: spread *= 0.8
        e = p.eye(); o = (e[0], e[1], e[2])
        for _ in range(w.d.get("pellets", 1)):
            sh = p.h + random.gauss(0, spread * 0.5); sp = p.p + random.gauss(0, spread * 0.5)
            self.hitscan(p, o, fwd(sh, sp), w.d["rng"], w.d["dmg"] * (0.92 if sup else 1.0))
        rec = w.d["rec"] * (0.75 if "grip" in w.att else 1.0) * (0.7 if ads else 1.0)
        kick = rec * random.uniform(0.75, 1.0); p.p = min(85, p.p + kick); self.recoil += kick; p.h += random.uniform(-0.35, 0.35) * rec
        self.bloom = min(4.0, self.bloom + (0.35 if w.d["auto"] else 0.8))
        self.app.vm_kick(rec)
        if not sup: self.alert_bots(p, 45)
        if w.mag == 0 and w.res > 0: self.start_reload()

    def alert_bots(self, src, r):
        for a in self.actors:
            if not a.dead and a.team != src.team and a.target is None and math.hypot(a.x - src.x, a.y - src.y) < r: a.heard = (src.x, src.y)

    def start_reload(self):
        w = self.weapons[self.cur]
        if self.reload_t > 0 or w.mag >= w.mag_size or w.res <= 0: return
        self.reload_t = w.reload; self.app.sfx("click", 0.6); self.app.vm_anim("reload", w.reload)

    def throw_nade(self):
        if self.nades <= 0 or self.player.dead: return
        self.nades -= 1; p = self.player; e = p.eye(); f = fwd(p.h, p.p + 12)
        self.grenades.append(Grenade(self, (e[0] + f[0] * 0.5, e[1] + f[1] * 0.5, e[2] - 0.1), f * 17 + Vec3(p.vx, p.vy, 0), p))
        self.app.sfx("swing", 0.6, 0.8); self.app.vm_anim("throw", 0.5)

    def melee(self):
        if self.melee_t > 0 or self.player.dead: return
        self.melee_t = 0.55; self.app.sfx("swing", 0.8); self.app.vm_anim("melee", 0.55); p = self.player
        for a in self.actors:
            if a.dead or (a.team == 0 and self.mode != "ffa"): continue
            dx, dy = a.x - p.x, a.y - p.y; d = math.hypot(dx, dy)
            if d < 2.2 and abs(adiff(ang_to(dx, dy), p.h)) < 50:
                self.damage(a, 200, p, "MELEE"); self.app.sfx("hit", 1.0, 0.7); break

    # -------------------------------------------------------------------------------------------------- player update
    def update_player(self, dt, inp):
        p = self.player; app = self.app
        if p.dead:
            self.respawn_t -= dt
            if self.respawn_t <= 0:
                if self.mode == "tdm": self.spawn_player(*random.choice(self.spawns[0]), -90)
                elif self.mode == "ffa": self.spawn_player(*self.ffa_spawn(), random.uniform(0, 360))
                elif self.mode == "range": self.spawn_player(*self.world.spots["range"], -90)
                else:
                    app.play_voice("fail"); self.banner("DRILL FAILED", "Back to the last checkpoint"); self.start_stage(self.stage, restart=True)
            return
        w = self.weapons[self.cur]; w.t = max(0, w.t - dt)
        # look
        p.h -= inp["mx"]; p.p = max(-85, min(85, p.p - inp["my"]))
        rr = min(self.recoil, self.recoil * 6 * dt); self.recoil -= rr; p.p -= rr * 0.55
        self.bloom = max(0, self.bloom - dt * 4)
        # stance
        if inp["crouch_pressed"]:
            if self.sprint and self.on_ground and self.slide_t <= 0:
                self.slide_t = 0.75 * (1.35 if "marathon" in app.profile["perks"] else 1); self.slide_v = fwd(p.h) * 9.5; app.sfx("swing", 0.4, 0.5)
                p.crouch = True
            else: p.crouch = not p.crouch
        want_ads = inp["ads"] and self.reload_t <= 0 and self.switch_t <= 0 and self.melee_t <= 0 and self.slide_t <= 0
        self.ads = min(1, self.ads + dt * 7) if want_ads else max(0, self.ads - dt * 7)
        mvx = (1 if inp["d"] else 0) - (1 if inp["a"] else 0); mvy = (1 if inp["w"] else 0) - (1 if inp["s"] else 0)
        self.sprint = inp["sprint"] and mvy > 0 and self.ads < 0.3 and not p.crouch and self.sprint_stam > 0
        if self.sprint: self.sprint_stam -= dt * (0.6 if "marathon" in app.profile["perks"] else 1)
        else: self.sprint_stam = min(5.0, self.sprint_stam + dt * 0.8)
        if self.sprint and p.crouch: p.crouch = False
        spd = 7.0 if self.sprint else (2.3 if p.crouch else (2.9 if self.ads > 0.5 else 4.6))
        f = fwd(p.h); rgt = Vec3(f[1], -f[0], 0)          # D = right, A = left
        v = (f * mvy + rgt * mvx); vl = v.length()
        if vl > 0: v = v / vl * spd
        if self.slide_t > 0:
            self.slide_t -= dt; v = self.slide_v * (0.35 + 0.65 * max(0, self.slide_t) / 0.75)
            if random.random() < 0.5 and app.fx_on: self.fx.dust(p.x, p.y, 0.1)
        if not self.on_ground: v = Vec3(p.vx, p.vy, 0) * 0.98 + v * 0.02
        p.vx, p.vy = v[0], v[1]
        hgt = 0.9 if self.slide_t > 0 else (1.15 if p.crouch else 1.8)
        nx, ny = p.x + v[0] * dt, p.y + v[1] * dt
        if p.crouch and not self.slide_t > 0:
            pass
        nx, ny = self.world.push(nx, ny, p.z, hgt)
        for a in self.actors:      # don't walk through soldiers or the truck
            if a.dead: continue
            dx, dy = nx - a.x, ny - a.y; dd = math.hypot(dx, dy)
            if 0.001 < dd < 0.65: nx, ny = a.x + dx / dd * 0.65, a.y + dy / dd * 0.65
        p.x, p.y = nx, ny
        if not p.crouch and self.slide_t <= 0:
            pass
        # can't stand up under the crawl wire
        if p.crouch and inp.get("stand_try"):
            pass
        g = self.world.ground(p.x, p.y, p.z)
        if inp["jump"] and self.on_ground:
            if p.crouch: p.crouch = False
            else: self.vz = 5.8; self.on_ground = False; app.sfx("swing", 0.25, 0.6)
        self.vz -= 18 * dt; p.z += self.vz * dt
        if p.z <= g:
            if not self.on_ground and self.vz < -6: app.sfx("click", 0.4, 0.5)
            p.z = g; self.vz = 0; self.on_ground = True
        else: self.on_ground = p.z - g < 0.05
        if p.z < g + 0.5 and p.z > g: p.z = g if self.vz <= 0 else p.z
        if self.slide_t <= 0 and p.crouch is True and self.slide_v.length() > 0 and not inp["crouch_held"]: self.slide_v = Vec3(0)
        # wire overhead: force crouch while under it
        if self.overhead(p.x, p.y, p.z + 1.75):
            if not p.crouch: p.crouch = True
        # weapon actions
        if inp["fire"] and not self.sprint:
            if w.d["auto"] or inp["fire_pressed"]: self.player_fire()
        if inp["reload"]: self.start_reload()
        if self.reload_t > 0:
            self.reload_t -= dt
            if self.reload_t <= 0:
                n = min(w.mag_size - w.mag, w.res); w.mag += n; w.res -= n; app.sfx("switch", 0.5)
        if inp["swap"] is not None and inp["swap"] != self.cur and self.switch_t <= 0:
            self.cur = inp["swap"]; self.switch_t = 0.45; self.reload_t = 0; app.build_viewmodel(self.weapons[self.cur]); app.sfx("switch", 0.5)
        self.switch_t = max(0, self.switch_t - dt); self.melee_t = max(0, self.melee_t - dt)
        if inp["nade"]: self.throw_nade()
        if inp["melee"]: self.melee()
        if inp["light"] and self.tod == "night": self.light = not self.light; app.sfx("click", 0.5)
        # health regen
        if self.time - self.last_dmg > 4.5: p.hp = min(p.maxhp, p.hp + 22 * dt)
        self.flash = max(0, self.flash - dt * 1.6); self.hitm = max(0, self.hitm - dt); self.shake = max(0, self.shake - dt * 1.8)

    def overhead(self, x, y, ztop):
        for b in self.world.boxes:
            if b[6] == "wire" and b[0] - 0.3 < x < b[3] + 0.3 and b[1] - 0.3 < y < b[4] + 0.3 and ztop > b[2]: return True
        return False

    # -------------------------------------------------------------------------------------------------- bots
    def enemies_of(self, a):
        res = [o for o in self.actors if not o.dead and o.team != a.team and (self.mode == "ffa" or o.team != a.team)]
        if not self.player.dead and self.player.team != a.team: res.append(self.player)
        return res

    def update_bot(self, a, dt):
        if a.dead:
            a.dt += dt
            if a.respawn > 0:
                a.respawn -= dt
                if a.respawn <= 0:
                    if self.mode == "tdm": x, y = random.choice(self.spawns[a.team])
                    else: x, y = self.ffa_spawn()
                    a.x, a.y, a.z = x, y, 0; a.hp = 100; a.dead = False; a.target = None; a.path = None; a.model.set_p(0); a.model.set_y(0)
                    a.w.mag = a.w.mag_size; a.sink = 0
            elif a.dt > 7: a.sink = min(1.0, (a.dt - 7) * 0.4)
            a.sync(dt); return
        a.think -= dt
        if a.think <= 0:
            a.think = 0.25
            best, bd = None, 75.0
            for e in self.enemies_of(a):
                dx, dy = e.x - a.x, e.y - a.y; d = math.hypot(dx, dy)
                if d > bd: continue
                if d > 6 and abs(adiff(ang_to(dx, dy), a.h)) > 80 and e is not a.target and (self.time - e.last_fire > 1.0 or d > 40): continue
                if self.tod == "night" and d > (28 if (e is self.player and self.light) else 16) and self.time - e.last_fire > 1.0: continue
                ee = e.eye()
                if self.world.los(a.eye(), (ee[0], ee[1], ee[2] - 0.3)): best, bd = e, d
            if best is not a.target:
                if best is not None and a.target is None: a.react = self.diff["react"] * random.uniform(0.8, 1.3)
                a.target = best
            if a.target is not None: a.heard = (a.target.x, a.target.y)
        a.w.t = max(0, a.w.t - dt); mv = Vec3(0)
        t = a.target
        if t is not None and not t.dead:
            dx, dy = t.x - a.x, t.y - a.y; d = math.hypot(dx, dy)
            th = ang_to(dx, dy); a.h += max(-300 * dt, min(300 * dt, adiff(th, a.h)))
            a.p = math.degrees(math.atan2((t.z + 1.2) - (a.z + 1.5), max(d, 0.1)))
            a.react -= dt
            # move: strafe, close in with shotguns/SMGs, keep range with rifles
            a.st -= dt
            if a.st <= 0: a.st = random.uniform(0.7, 1.8); a.strafe = random.choice((-1, 1, 0)); a.crouch = a.behav == "hold" and random.random() < 0.4
            f = fwd(a.h); r = Vec3(f[1], -f[0], 0); want = 8 if a.w.id in ("sg12", "km9") else (30 if a.w.id == "sr50" else 18)
            if a.behav != "hold": mv = r * a.strafe * 2.2 + f * (2.5 if d > want else (-1.5 if d < want * 0.5 else 0))
            else: mv = r * a.strafe * 1.0
            if a.crouch: mv *= 0.4
            if a.react <= 0 and a.w.t <= 0 and abs(adiff(th, a.h)) < 12:
                if a.w.mag <= 0:
                    a.w.mag = a.w.mag_size; a.w.t = a.w.reload
                else:
                    a.w.mag -= 1; a.w.t = a.w.cd * (1 if a.w.d["auto"] else 1.6); a.burst += 1; a.last_fire = self.time
                    if a.burst >= self.diff["burst"] + random.randint(0, 3): a.burst = 0; a.w.t += random.uniform(0.35, 0.8)
                    err = self.diff["aim"] * (1 + d / 45) * (1.5 if math.hypot(t.vx, t.vy) > 5 else 1) * (0.8 if a.crouch else 1)
                    e = a.eye(); te = (t.x, t.y, t.z + (0.9 if t.crouch else 1.2))
                    aim = Vec3(te[0] - e[0], te[1] - e[1], te[2] - e[2]); aim.normalize()
                    ah = ang_to(aim[0], aim[1]); ap = math.degrees(math.asin(max(-1, min(1, aim[2]))))
                    for _ in range(a.w.d.get("pellets", 1)):
                        self.hitscan(a, e, fwd(ah + random.gauss(0, err), ap + random.gauss(0, err * 0.7)), a.w.d["rng"], a.w.d["dmg"] * self.diff["dmg"])
                    dist = math.hypot(a.x - self.player.x, a.y - self.player.y)
                    self.app.sfx(a.w.d["snd"], 0.9 / (1 + dist / 14), a.w.d["rate"] * random.uniform(0.95, 1.05))
                    if self.app.fx_on and dist < 60:
                        g = a.gun.get_pos(self.root); m = g + fwd(a.h, a.p) * 0.5
                        self.fx.emit("flash", m[0], m[1], m[2], 1, 0.0, (0, 0, 0), 0.35, 0.05, (1, 0.9, 0.7, 0.9), 1.2)
                    # bots throw the odd grenade at campers (veteran/regular)
                    if self.diff_i > 0 and random.random() < 0.006 * self.diff_i and 8 < d < 22:
                        f2 = fwd(a.h, 25); self.grenades.append(Grenade(self, (a.x, a.y, a.z + 1.6), f2 * (d * 0.75 + 3), a))
        else:
            a.target = None; a.p = 0
            goal = None
            if a.behav == "hold":
                goal = a.heard if a.heard and math.hypot(a.heard[0] - a.x, a.heard[1] - a.y) < 14 else None
                a.h += math.sin(self.time * 0.5 + a.anim) * 20 * dt
            elif a.behav == "patrol" and a.patrol:
                goal = a.patrol[a.pi % len(a.patrol)]
                if math.hypot(goal[0] - a.x, goal[1] - a.y) < 2: a.pi += 1
            elif a.behav == "assault": goal = a.heard or a.goal
            elif a.behav == "follow":
                p = self.player; goal = (p.x + a.home[0], p.y + a.home[1]) if math.hypot(p.x - a.x, p.y - a.y) > 6 else None
            else:   # hunt (matches)
                if a.heard: goal = a.heard
                elif a.goal is None or math.hypot(a.goal[0] - a.x, a.goal[1] - a.y) < 3:
                    es = self.enemies_of(a); e = random.choice(es) if es and random.random() < 0.6 else None
                    a.goal = (e.x + random.uniform(-10, 10), e.y + random.uniform(-10, 10)) if e else (random.uniform(-90, 90), random.uniform(-90, 90))
                goal = goal or a.goal
            if goal is not None:
                if a.path is None or a.repath <= 0 or a.goal_used != goal:
                    if self.path_budget > 0:
                        self.path_budget -= 1; a.path = self.world.path((a.x, a.y), goal) or []; a.repath = 3.0; a.goal_used = goal
                a.repath -= dt
                if a.path:
                    wx, wy = a.path[0]; dx, dy = wx - a.x, wy - a.y; d = math.hypot(dx, dy)
                    if d < 1.0:
                        a.path.pop(0)
                        if not a.path and a.heard and math.hypot(a.heard[0] - a.x, a.heard[1] - a.y) < 3: a.heard = None
                    else:
                        th = ang_to(dx, dy); a.h += max(-240 * dt, min(240 * dt, adiff(th, a.h)))
                        mv = fwd(a.h) * (a.speed if abs(adiff(th, a.h)) < 40 else 1.2)
                elif a.heard and a.path is not None and not a.path: a.heard = None
            a.crouch = False
        mv[2] = 0; nx, ny = a.x + mv[0] * dt, a.y + mv[1] * dt
        nx, ny = self.world.push(nx, ny, a.z, 1.15 if a.crouch else 1.8, 0.32)
        p = self.player
        if not p.dead:
            dx, dy = nx - p.x, ny - p.y; dd = math.hypot(dx, dy)
            if 0.001 < dd < 0.65: nx, ny = p.x + dx / dd * 0.65, p.y + dy / dd * 0.65
        a.vx, a.vy = (nx - a.x) / max(dt, 1e-4), (ny - a.y) / max(dt, 1e-4); a.x, a.y = nx, ny
        g = self.world.ground(a.x, a.y, a.z); a.z = g if a.z - g < 0.6 else max(g, a.z - 9 * dt)
        if self.overhead(a.x, a.y, a.z + 1.75): a.crouch = True
        a.sync(dt)

    # -------------------------------------------------------------------------------------------------- frame
    def update(self, dt, inp):
        if self.over: return
        self.time += dt; self.path_budget = 3
        self.update_player(dt, inp)
        for a in self.actors: self.update_bot(a, dt)
        self.grenades = [g for g in self.grenades if g.update(dt)]
        for t in self.targets: t.update(dt)
        for tr in self.trucks: tr.update(dt, self.truck_go(tr))
        if self.mode == "range":
            self.range_next -= dt
            if self.range_next <= 0:
                self.range_next = random.uniform(0.6, 1.4); down = [t for t in self.targets if not t.up and t.k == 0]
                if down: random.choice(down).pop(random.uniform(2.5, 4.0))
        elif self.mode in ("tdm", "ffa"): self.match_logic()
        else: self.mission_logic(dt, inp)
        if self.tod == "night":
            p = self.player; e = p.eye(); self.app.render.set_shader_input("flon", 1.0 if self.light else 0.0)
            self.app.render.set_shader_input("flpos", Vec3(*e)); self.app.render.set_shader_input("fldir", fwd(p.h, p.p))

    def truck_go(self, tr):
        p = self.player
        near = [a for a in self.actors if not a.dead and a.team == 1 and math.hypot(a.x - tr.x, a.y - tr.y) < 30]
        return math.hypot(p.x - tr.x, p.y - tr.y) < 28 and not near

    def match_logic(self):
        if self.mode == "tdm":
            won = 0 if self.score[0] >= self.limit else (1 if self.score[1] >= self.limit else None)
            if won is None and self.time >= self.tlimit: won = 0 if self.score[0] > self.score[1] else 1
            if won is not None: self.finish(won == 0, "VICTORY" if won == 0 else "DEFEAT")
        else:
            allp = self.actors + [self.player]; top = max(allp, key=lambda a: a.kills)
            if top.kills >= self.limit or self.time >= self.tlimit: self.finish(top is self.player, "YOU WIN" if top is self.player else "%s WINS" % top.name)

    def finish(self, win, title):
        self.over = (win, title)
        if self.mode in ("tdm", "ffa"):
            self.give_xp("match", label="MATCH")
            if win: self.give_xp("win", label="WIN")
        self.app.on_session_over(self)

    def mission_logic(self, dt, inp):
        st = self.stages[self.stage]
        if st.get("fail") and st["fail"](self):
            self.app.play_voice("fail"); self.banner("DRILL FAILED", st.get("failtext", "Back to the last checkpoint")); self.start_stage(self.stage, restart=True); return
        m = st.get("marker"); self.marker = m(self) if callable(m) else m
        if "hold" in st and not self.player.dead:
            hx, hy, hr, ht = st["hold"](self)
            if math.hypot(self.player.x - hx, self.player.y - hy) < hr and inp["use"]:
                self.hold += dt
                if self.hold >= ht: st["held"](self); self.hold = 0
            else: self.hold = max(0, self.hold - dt * 2)
        if st["done"](self):
            self.give_xp("objective", label="OBJECTIVE")
            if self.stage + 1 < len(self.stages): self.start_stage(self.stage + 1)
            else:
                first = self.mission not in self.app.profile["done"]
                self.give_xp("mission", D.XP["mission"] if first else D.XP["mission"] // 2, "MISSION")
                if first: self.app.profile["done"].append(self.mission)
                self.app.play_voice("done"); self.over = (True, "MISSION COMPLETE"); self.app.on_session_over(self)

    def scoreboard(self):
        rows = [(a.name, a.team, a.kills, a.deaths, a.score) for a in self.actors] + [("ANA (YOU)", 0, self.player.kills, self.player.deaths, self.player.score)]
        return sorted(rows, key=lambda r: (r[1] if self.mode == "tdm" else 0, -r[2]))

    def destroy(self):
        for a in self.actors: a.remove()
        for t in self.targets: t.remove()
        for g in self.grenades: g.np.remove_node()
        for tr in self.trucks: tr.np.remove_node()
        self.world.dyn = []; self.root.remove_node(); self.fx.clear()


# ====================================================================================================================
# campaign stages: each stage = dict(text, spawn, setup, done, [fail], [marker], [hold/held], [explode])
def alive(s, team): return [a for a in s.actors if a.team == team and not a.dead]


def _m1(s):
    W = s.world
    def range_setup(s):
        s.hits = 0
        for x in W.range_x[:3]:
            for y in W.lanes: s.targets.append(Target(s, x, y))
        s.range_next = 1.0; s.mode_range = True
    def range_done(s):
        s.range_next -= s.app.dt
        if s.range_next <= 0:
            s.range_next = 1.1; down = [t for t in s.targets if not t.up and t.k == 0]
            if down and sum(1 for t in s.targets if t.up) < 2: random.choice(down).pop(3.5)
        s.objective = "RANGE QUALIFICATION: hit pop-up targets  %d / 12" % s.hits
        return s.hits >= 12
    def course_setup(s):
        for t in s.targets: t.remove()
        s.targets = []; s.gate = 0; s.course_t = 0
    def course_done(s):
        g = W.gates; s.course_t += s.app.dt
        if s.gate < len(g) and math.hypot(s.player.x - g[s.gate][0], s.player.y - g[s.gate][1]) < 2.6: s.gate += 1; s.app.sfx("checkpoint", 0.6)
        s.objective = "OBSTACLE COURSE: run through gate %d / %d  (jump the walls, crouch under the wire)  %.0fs" % (min(s.gate + 1, len(g)), len(g), s.course_t)
        return s.gate >= len(g)
    return [dict(text="RANGE QUALIFICATION", spawn=(42, -9, -90), setup=range_setup, done=range_done),
            dict(text="OBSTACLE COURSE", spawn=(-66, -72, -90), respawn=True, setup=course_setup, done=course_done,
                 marker=lambda s: W.gates[min(s.gate, len(W.gates) - 1)])]


def _m2(s):
    W = s.world; kx, ky = W.spots["killhouse"]
    def a_setup(s): pass
    def b_setup(s):
        for (x, y) in W.kill_rooms[3:]: s.add_bot(1, x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5), random.uniform(0, 360), "hold", "km9")
        for (x, y) in W.kill_rooms[3:5]: s.add_bot(1, x + 1.5, y - 1.2, random.uniform(0, 360), "hold", "km9")
    def c_setup(s):
        for (x, y) in W.kill_rooms[:3]: s.add_bot(1, x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5), random.uniform(0, 360), "hold", "km9")
        s.add_bot(1, W.kill_rooms[0][0] + 1.5, W.kill_rooms[0][1] + 1.5, 0, "hold", "sg12")
    def nearest(s):
        al = alive(s, 1)
        if not al: return None
        e = min(al, key=lambda a: math.hypot(a.x - s.player.x, a.y - s.player.y)); return (e.x, e.y)
    return [dict(text="Move to the kill house entrance", spawn=(-60, -12, 90), setup=a_setup, marker=W.spots["killhouse_door"],
                 done=lambda s: math.hypot(s.player.x - W.spots["killhouse_door"][0], s.player.y - W.spots["killhouse_door"][1]) < 3),
            dict(text="Clear the east rooms", setup=b_setup, marker=nearest, done=lambda s: not alive(s, 1)),
            dict(text="Clear the west rooms", setup=c_setup, marker=nearest, done=lambda s: not alive(s, 1))]


def _m3(s):
    W = s.world; tx, ty = W.spots["depot_truck"]
    def a_setup(s):
        for k in range(5):
            a = s.add_bot(1, -60 + k * 12, 61, 90, "patrol", "kr4"); a.patrol = [(-70 + k * 12, 61), (-62 + k * 12, 44 + 40 * (k % 2))]; a.speed = 2.0
        s.banner("PRESS L FOR YOUR HELMET LIGHT", "Lights make you easier to spot", 3.5)
    def b_setup(s):
        for (x, y) in ((tx - 6, ty - 6), (tx + 8, ty + 2), (tx - 10, ty + 8)): s.add_bot(1, x, y, random.uniform(0, 360), "hold", "kr4")
        s.planted = False
    def b_held(s):
        s.planted = True; s.app.sfx("beep", 0.8); s.banner("CHARGE PLANTED", "Get clear!"); s.boom_t = 4.0
    def b_done(s):
        if getattr(s, "planted", False):
            s.boom_t -= s.app.dt; s.objective = "Charge planted: get clear!  %.0f" % max(0, s.boom_t)
            if s.boom_t <= 0:
                s.explode(Vec3(tx, ty, 1.0), None); s.fx.explosion(tx, ty, 1.5, 1.8); s.planted = False; s.blown = True
        return getattr(s, "blown", False)
    def c_setup(s):
        for k in range(3): s.add_bot(1, 20 + k * 6, 85, 180, "assault", "km9").goal = (-30, 102)
    return [dict(text="Eliminate the north tents patrol (5)", spawn=(-100, 30, -150), setup=a_setup, done=lambda s: not alive(s, 1), marker=W.spots["north_tents"]),
            dict(text="Plant a charge on the depot truck (hold F)", setup=b_setup, marker=(tx, ty), hold=lambda s: (tx, ty, 3.6, 3.0), held=b_held, done=b_done),
            dict(text="Reach the extraction point", setup=c_setup, marker=(-30, 102),
                 done=lambda s: math.hypot(s.player.x + 30, s.player.y - 102) < 4)]


def _m4(s):
    W = s.world
    def squad(s):
        if not alive(s, 0):
            for k, (x, y) in enumerate(((-12, 0), (12, 0), (0, -12), (0, 12))): s.add_bot(0, x, y, k * 90, "hold", "kr4")
    def wave(n, gates):
        def setup(s):
            squad(s); s.app.play_voice("wave"); s.banner("WAVE %d" % n, "%d attackers" % (3 + 3 * n))
            for k in range(3 + 3 * n):
                gx, gy = gates[k % len(gates)]
                a = s.add_bot(1, gx + random.uniform(-4, 4), gy + random.uniform(-4, 4), 0, "assault"); a.goal = (random.uniform(-4, 4), random.uniform(-4, 4))
            s.hq_t = 0
        return setup
    def fail(s):
        if any(math.hypot(a.x, a.y) < 6 for a in alive(s, 1)): s.hq_t = getattr(s, "hq_t", 0) + s.app.dt
        s.objective = "Hold the HQ tent  -  attackers left: %d   HQ %d%%" % (len(alive(s, 1)), max(0, 100 - s.hq_t * 10))
        return s.hq_t >= 10
    G = [(-100, -40), (100, 20), (0, 100)]
    return [dict(text="WAVE 1", spawn=(0, -10, 0), setup=wave(1, G[:1]), done=lambda s: not alive(s, 1), fail=fail, failtext="The HQ was taken", marker=(0, 0)),
            dict(text="WAVE 2", setup=wave(2, G[1:]), done=lambda s: not alive(s, 1), fail=fail, failtext="The HQ was taken", marker=(0, 0)),
            dict(text="WAVE 3", setup=wave(3, G), done=lambda s: not alive(s, 1), fail=fail, failtext="The HQ was taken", marker=(0, 0))]


def _m5(s):
    W = s.world; road = [(-100, -40)] + W.road[1:-1] + [(104, 20)]
    def start(s):
        if not s.trucks: s.trucks.append(Truck(s, road))
        tr = s.trucks[0]
        if getattr(s, "truck_ck", None): tr.x, tr.y, tr.i, tr.h = s.truck_ck; tr.sync()
        tr.hp = tr.maxhp
        for k, (x, y) in enumerate(((-96, -46), (-96, -34))): s.add_bot(0, x, y, -90, "follow", "kr4").home = ((-3, -3), (3, -3))[k]
    def amb(points):
        def setup(s):
            if not s.trucks: start(s)
            tr = s.trucks[0]; s.truck_ck = (tr.x, tr.y, tr.i, tr.h); s.trucks[0].hp = max(tr.hp, 600)
            if not alive(s, 0):
                for k in range(2): s.add_bot(0, tr.x - 3 + k * 6, tr.y - 4, 0, "follow", "kr4").home = ((-3, -3), (3, -3))[k]
            for (x, y) in points:
                for k in range(3): s.add_bot(1, x + random.uniform(-3, 3), y + random.uniform(-3, 3), 0, "assault").goal = (tr.x, tr.y)
        return setup
    def tfail(s):
        tr = s.trucks[0] if s.trucks else None
        if tr is None: return False
        for a in alive(s, 1):     # attackers near the truck damage it
            if math.hypot(a.x - tr.x, a.y - tr.y) < 30 and a.target is None: a.goal = (tr.x, tr.y)
        s.objective = "Escort the supply truck  -  TRUCK %d%%   (it waits for you and stops under fire)" % max(0, tr.hp / 10)
        return tr.hp <= 0
    def reach(i):
        return lambda s: bool(s.trucks) and s.trucks[0].i >= i and not alive(s, 1)
    def setup0(s):
        start(s); s.truck_ck = None
    mk = lambda s: (s.trucks[0].x, s.trucks[0].y) if s.trucks else None
    return [dict(text="Escort the truck", spawn=(-96, -44, -90), setup=setup0, done=reach(2), fail=tfail, failtext="The truck was destroyed", marker=mk),
            dict(text="Ambush!", setup=amb([(-30, -6), (-10, -44)]), done=reach(4), fail=tfail, failtext="The truck was destroyed", marker=mk),
            dict(text="Ambush at the east road", setup=amb([(50, 40), (70, 0), (82, 34)]), fail=tfail, failtext="The truck was destroyed", marker=mk,
                 done=lambda s: bool(s.trucks) and s.trucks[0].done and not alive(s, 1))]


def _m6(s):
    W = s.world; sx, sy, sz = W.spots["sniper"]
    def squad(s):
        if len(alive(s, 0)) < 3:
            for k in range(4 - len(alive(s, 0))): s.add_bot(0, 56 + k * 2, 50, -90, "follow", "kr4").home = ((-3, -3), (3, -3), (-3, 3), (3, 3))[k]
    def a_setup(s):
        squad(s)
        sn = s.add_bot(1, sx, sy, 160, "hold", "sr50", "WATCHTOWER"); sn.z = sz; s.sniper = sn
        for (x, y) in ((80, 58), (90, 66), (78, 76), (96, 70), (88, 48)): s.add_bot(1, x, y, 200, "hold", "kr4")
    def b_setup(s):
        squad(s); s.masts = {"mast1": False, "mast2": False}
        for (x, y) in ((84, 78), (96, 58)): s.add_bot(1, x, y, 0, "hold", "km9")
    def b_held(s):
        p = s.player
        for k in ("mast1", "mast2"):
            mx, my = W.spots[k]
            if not s.masts[k] and math.hypot(p.x - mx, p.y - my) < 3.5:
                s.masts[k] = True; s.app.sfx("beep", 0.8); s.banner("CHARGE PLANTED", "Mast %s" % k[-1]); s.boom = (mx, my, 3.5)
    def b_done(s):
        if getattr(s, "boom", None):
            mx, my, t = s.boom; t -= s.app.dt; s.boom = (mx, my, t)
            if t <= 0: s.explode(Vec3(mx, my, 1.0), None); s.fx.explosion(mx, my, 3, 1.5); s.boom = None
        n = sum(s.masts.values()); s.objective = "Destroy the radio masts (hold F at each)  %d / 2" % n
        return n == 2 and not getattr(s, "boom", None)
    def mast_marker(s):
        for k in ("mast1", "mast2"):
            if not s.masts.get(k): return W.spots[k]
        return None
    def b_hold(s):
        p = s.player
        for k in ("mast1", "mast2"):
            mx, my = W.spots[k]
            if not s.masts[k] and math.hypot(p.x - mx, p.y - my) < 3.5: return (mx, my, 3.5, 2.0)
        return (0, 0, 0, 1)
    def c_setup(s):
        squad(s); s.flag_up = 0
        for k in range(4): s.add_bot(1, 74 + k * 8, 96 - 8, 180, "assault", "km9").goal = W.spots["flag_east"][:2]
    def c_held(s):
        s.flag_up = 1; s.app.sfx("win", 0.8)
    fx, fy, fz = W.spots["flag_east"]
    return [dict(text="Take out the tower sniper and the outer defenders", spawn=(58, 46, -60), setup=a_setup, done=lambda s: not alive(s, 1), marker=(sx, sy)),
            dict(text="Destroy both radio masts", setup=b_setup, marker=mast_marker, hold=b_hold, held=b_held, done=b_done),
            dict(text="Raise our flag at the compound (hold F at the pole)", setup=c_setup, marker=(fx, fy), hold=lambda s: (fx, fy, 3.0, 3.0), held=c_held,
                 done=lambda s: getattr(s, "flag_up", 0) and not alive(s, 1))]


MISSION_STAGES = {"m1": _m1, "m2": _m2, "m3": _m3, "m4": _m4, "m5": _m5, "m6": _m6}
