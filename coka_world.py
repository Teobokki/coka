"""COKA: the procedural army camp (static geometry batched per texture, collision boxes, nav grid, ray casts)."""
import math, random, heapq
import numpy as np
from panda3d.core import CardMaker, TransparencyAttrib, SamplerState, Vec4
from fs_geom import MB
from coka_gfx import cyl, node, ellipsoid

W = (1, 1, 1, 1)
EDGE = 112.0


def tbox(mb, x0, y0, z0, x1, y1, z1, col=W, s=1.0, top=True):
    sx, sy, sz = (x1 - x0) / s, (y1 - y0) / s, (z1 - z0) / s
    mb.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), col, ((0, 0), (sx, 0), (sx, sz), (0, sz)))
    mb.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), col, ((0, 0), (sy, 0), (sy, sz), (0, sz)))
    mb.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), col, ((0, 0), (sx, 0), (sx, sz), (0, sz)))
    mb.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), col, ((0, 0), (sy, 0), (sy, sz), (0, sz)))
    if top: mb.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), col, ((0, 0), (sx, 0), (sx, sy), (0, sy)))


def build_truck(mb_plain, mb_canvas, mb_camo, x, y, h, cover=True):
    """army truck (cab + bed + canvas cover + wheels) at x,y heading h (deg, nose along local +Y). returns collision obox list"""
    c, s = math.cos(math.radians(h)), math.sin(math.radians(h))
    def P(a, b, z): return (x + a * c - b * s, y + a * s + b * c, z)
    def ob(mb, a0, b0, z0, a1, b1, z1, col, uv=1.0):
        pts = [P(a0, b0, 0), P(a1, b0, 0), P(a1, b1, 0), P(a0, b1, 0)]
        for i in range(4):
            p, q = pts[i], pts[(i + 1) % 4]
            ln = math.hypot(q[0] - p[0], q[1] - p[1]) / uv; hz = (z1 - z0) / uv
            mb.quad((p[0], p[1], z0), (q[0], q[1], z0), (q[0], q[1], z1), (p[0], p[1], z1), col, ((0, 0), (ln, 0), (ln, hz), (0, hz)))
        mb.quad((pts[0][0], pts[0][1], z1), (pts[1][0], pts[1][1], z1), (pts[2][0], pts[2][1], z1), (pts[3][0], pts[3][1], z1), col,
                ((0, 0), ((a1 - a0) / uv, 0), ((a1 - a0) / uv, (b1 - b0) / uv), (0, (b1 - b0) / uv)))
    ob(mb_camo, -1.15, 1.6, 0.9, 1.15, 3.6, 1.4, W)                     # engine/bonnet
    ob(mb_camo, -1.2, 1.4, 1.4, 1.2, 2.7, 2.75, W)                      # cab
    ob(mb_plain, -1.0, 2.68, 1.85, 1.0, 2.72, 2.55, (0.16, 0.2, 0.24, 1))   # windscreen
    ob(mb_plain, -1.05, 3.6, 0.55, 1.05, 3.75, 1.2, (0.1, 0.1, 0.1, 1))     # grille/bumper
    ob(mb_plain, -1.2, -4.0, 0.7, 1.2, 1.4, 0.95, (0.2, 0.2, 0.18, 1))      # chassis
    ob(mb_camo, -1.25, -4.0, 0.95, 1.25, 1.3, 1.55, W)                  # bed sides
    if cover:
        for i in range(8):     # canvas hoop cover
            a0, a1 = math.pi * i / 8, math.pi * (i + 1) / 8
            p0 = (-1.25 * math.cos(a0), 1.55 + 1.15 * math.sin(a0)); p1 = (-1.25 * math.cos(a1), 1.55 + 1.15 * math.sin(a1))
            A, B, C, D = P(p0[0], -4.0, p0[1]), P(p1[0], -4.0, p1[1]), P(p1[0], 1.3, p1[1]), P(p0[0], 1.3, p0[1])
            mb_canvas.quad(A, B, C, D, W, ((0, i / 4), (0, (i + 1) / 4), (3, (i + 1) / 4), (3, i / 4)))
        e = [P(-1.25 * math.cos(math.pi * i / 8), -4.0, 1.55 + 1.15 * math.sin(math.pi * i / 8)) for i in range(9)]
        for i in range(8): mb_canvas.quad(P(0, -4.0, 1.55), P(0, -4.0, 1.55), e[i + 1], e[i], (0.42, 0.42, 0.4, 1), ((0.5, 0), (0.5, 0), (0.1 * i, 0.4), (0.1 * i + 0.1, 0.4)))
    for a in (-1.15, 1.15):
        for b in (-2.9, -1.7, 2.5):
            px, py, _ = P(a, b, 0)
            for k in range(10):   # wheel as a 10-sided prism along the local axle
                t0, t1 = 2 * math.pi * k / 10, 2 * math.pi * (k + 1) / 10
                q = lambda t, side: P(a + side, b + 0.55 * math.cos(t), 0.55 + 0.55 * math.sin(t))
                mb_plain.quad(q(t0, -0.2), q(t1, -0.2), q(t1, 0.2), q(t0, 0.2), (0.07, 0.07, 0.07, 1))
                hub = (0.12, 0.12, 0.11, 1); sd = 0.2 if a > 0 else -0.2
                mb_plain.quad(P(a + sd, b, 0.55), P(a + sd, b, 0.55), q(t1, sd), q(t0, sd), hub)
    return (x, y, h, 1.3, 3.8, 2.75)


class World:
    def __init__(self, base, tex, seed=7):
        self.base = base; self.tex = tex; self.rnd = random.Random(seed)
        self.root = base.render.attach_new_node("world")
        self.mbs = {k: MB(k) for k in ("dirt", "canvas", "sandbag", "gabion", "plywood", "olive", "plain", "camo", "road")}
        self.boxes = []; self.spots = {}
        self.build()
        self.finish()

    # -- primitives ---------------------------------------------------------------------------------------------------
    def col(self, x0, y0, z0, x1, y1, z1, kind="dirt"):
        self.boxes.append((min(x0, x1), min(y0, y1), z0, max(x0, x1), max(y0, y1), z1, kind))

    def sandbags(self, x0, y0, x1, y1, h=1.0, th=0.8):
        """sandbag wall from (x0,y0) to (x1,y1) (axis aligned)"""
        if abs(x1 - x0) > abs(y1 - y0): a, b, c, d = min(x0, x1), y0 - th / 2, max(x0, x1), y0 + th / 2
        else: a, b, c, d = x0 - th / 2, min(y0, y1), x0 + th / 2, max(y0, y1)
        tbox(self.mbs["sandbag"], a, b, 0, c, d, h, W, 1.25); self.col(a, b, 0, c, d, h, "sand")

    def gabions(self, x0, y0, x1, y1, h=2.0, th=1.0):
        if abs(x1 - x0) > abs(y1 - y0): a, b, c, d = min(x0, x1), y0 - th / 2, max(x0, x1), y0 + th / 2
        else: a, b, c, d = x0 - th / 2, min(y0, y1), x0 + th / 2, max(y0, y1)
        tbox(self.mbs["gabion"], a, b, 0, c, d, h, W, 1.0); self.col(a, b, 0, c, d, h, "sand")

    def crate(self, x, y, s=1.0, z=0.0):
        tbox(self.mbs["olive"], x - s / 2, y - s / 2, z, x + s / 2, y + s / 2, z + s, W, s); self.col(x - s / 2, y - s / 2, z, x + s / 2, y + s / 2, z + s, "metal")

    def drum(self, x, y):
        cyl(self.mbs["plain"], x, y, 0, 0.3, 0.9, (0.25, 0.3, 0.2, 1), axis="z", seg=10); self.col(x - 0.3, y - 0.3, 0, x + 0.3, y + 0.3, 0.9, "metal")

    def tent(self, cx, cy, w, l, rot=False, h=2.6):
        """military ridge tent: low walls + gable roof (canvas). rot: ridge along X"""
        mb = self.mbs["canvas"]; wall = 1.2
        if rot: w, l = l, w
        x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - l / 2, cy + l / 2
        if not rot:   # ridge along Y
            tbox(mb, x0, y0, 0, x1, y1, wall, W, 2.0, top=False)
            mb.quad((x0 - 0.15, y0, wall - 0.1), (x0 - 0.15, y1, wall - 0.1), (cx, y1, h), (cx, y0, h), W, ((0, 0), (l / 2, 0), (l / 2, 1.5), (0, 1.5)))
            mb.quad((x1 + 0.15, y1, wall - 0.1), (x1 + 0.15, y0, wall - 0.1), (cx, y0, h), (cx, y1, h), W, ((0, 0), (l / 2, 0), (l / 2, 1.5), (0, 1.5)))
            for yy, sg in ((y0, -1), (y1, 1)):
                mb.quad((x0, yy, wall), (x1, yy, wall), (cx, yy, h), (cx, yy, h), (0.85, 0.85, 0.85, 1), ((0, 0), (w / 2, 0), (w / 4, 0.7), (w / 4, 0.7)), n=(0, sg, 0))
            self.plain_box(cx - 0.6, y0 - 0.02, 0, cx + 0.6, y0 + 0.01, 1.9, (0.12, 0.11, 0.09, 1))      # door flap shadow
        else:
            tbox(mb, x0, y0, 0, x1, y1, wall, W, 2.0, top=False)
            mb.quad((x1, y0 - 0.15, wall - 0.1), (x0, y0 - 0.15, wall - 0.1), (x0, cy, h), (x1, cy, h), W, ((0, 0), (w / 2, 0), (w / 2, 1.5), (0, 1.5)))
            mb.quad((x0, y1 + 0.15, wall - 0.1), (x1, y1 + 0.15, wall - 0.1), (x1, cy, h), (x0, cy, h), W, ((0, 0), (w / 2, 0), (w / 2, 1.5), (0, 1.5)))
            for xx, sg in ((x0, -1), (x1, 1)):
                mb.quad((xx, y1, wall), (xx, y0, wall), (xx, cy, h), (xx, cy, h), (0.85, 0.85, 0.85, 1), ((0, 0), (l / 2, 0), (l / 4, 0.7), (l / 4, 0.7)), n=(sg, 0, 0))
        self.col(x0 - 0.1, y0 - 0.1, 0, x1 + 0.1, y1 + 0.1, h, "cloth")

    def plain_box(self, x0, y0, z0, x1, y1, z1, col, collide=None):
        self.mbs["plain"].box(x0, y0, z0, x1, y1, z1, col)
        if collide: self.col(x0, y0, z0, x1, y1, z1, collide)

    def tower(self, cx, cy, hgt=6.0):
        """watchtower: 4 timber legs, platform, sandbag rail, tin roof. sniper post at (cx,cy,hgt)"""
        wood = (0.42, 0.33, 0.22, 1)
        for sx in (-1, 1):
            for sy in (-1, 1):
                self.plain_box(cx + sx * 1.5 - 0.12, cy + sy * 1.5 - 0.12, 0, cx + sx * 1.5 + 0.12, cy + sy * 1.5 + 0.12, hgt + 2.6, wood, "wood")
        for z in (1.8, 3.8):
            self.plain_box(cx - 1.5, cy - 1.56, z, cx + 1.5, cy - 1.44, z + 0.12, wood); self.plain_box(cx - 1.5, cy + 1.44, z, cx + 1.5, cy + 1.56, z + 0.12, wood)
        tbox(self.mbs["plywood"], cx - 1.8, cy - 1.8, hgt - 0.2, cx + 1.8, cy + 1.8, hgt, W, 1.5); self.col(cx - 1.8, cy - 1.8, hgt - 0.2, cx + 1.8, cy + 1.8, hgt, "wood")
        for (a, b, c, d) in ((-1.8, -1.8, 1.8, -1.5), (-1.8, 1.5, 1.8, 1.8), (-1.8, -1.5, -1.5, 1.5), (1.5, -1.5, 1.8, 1.5)):
            tbox(self.mbs["sandbag"], cx + a, cy + b, hgt, cx + c, cy + d, hgt + 0.9, W, 1.0); self.col(cx + a, cy + b, hgt, cx + c, cy + d, hgt + 0.9, "sand")
        self.mbs["plain"].quad((cx - 2.1, cy - 2.1, hgt + 2.6), (cx + 2.1, cy - 2.1, hgt + 2.6), (cx + 2.1, cy + 2.1, hgt + 2.9), (cx - 2.1, cy + 2.1, hgt + 2.9), (0.36, 0.36, 0.34, 1))
        self.mbs["plain"].quad((cx - 2.1, cy + 2.1, hgt + 2.9), (cx + 2.1, cy + 2.1, hgt + 2.9), (cx + 2.1, cy - 2.1, hgt + 2.6), (cx - 2.1, cy - 2.1, hgt + 2.6), (0.3, 0.3, 0.28, 1))
        for i in range(int(hgt / 0.4)):       # ladder rungs
            self.plain_box(cx - 0.35, cy - 1.75, 0.3 + i * 0.4, cx + 0.35, cy - 1.68, 0.36 + i * 0.4, wood)

    def mast(self, cx, cy, hgt=14.0):
        m = self.mbs["plain"]; c = (0.55, 0.55, 0.52, 1)
        for i in range(3):
            a = 2 * math.pi * i / 3
            cyl(m, cx + 0.35 * math.cos(a), cy + 0.35 * math.sin(a), 0, 0.04, hgt, c, axis="z", seg=5, caps=False)
        for z in range(1, int(hgt)):
            for i in range(3):
                a0, a1 = 2 * math.pi * i / 3, 2 * math.pi * (i + 1) / 3
                m.box(cx + 0.35 * math.cos(a0) - 0.02, cy + 0.35 * math.sin(a0) - 0.02, z, cx + 0.35 * math.cos(a0) + 0.02, cy + 0.35 * math.sin(a0) + 0.02, z + 0.04, c)
        m.box(cx - 0.4, cy - 0.4, hgt - 0.6, cx + 0.4, cy + 0.4, hgt - 0.2, (0.3, 0.3, 0.3, 1))
        m.box(cx - 0.6, cy - 0.5, 0, cx + 0.6, cy + 0.5, 1.2, (0.3, 0.33, 0.26, 1))
        self.col(cx - 0.6, cy - 0.5, 0, cx + 0.6, cy + 0.5, 1.2, "metal"); self.col(cx - 0.4, cy - 0.4, 1.2, cx + 0.4, cy + 0.4, hgt, "metal")

    def pole(self, x, y, h=9.0):
        cyl(self.mbs["plain"], x, y, 0, 0.07, h, (0.7, 0.7, 0.68, 1), axis="z", seg=8)
        self.col(x - 0.1, y - 0.1, 0, x + 0.1, y + 0.1, h, "metal")

    def camo_net(self, x0, y0, x1, y1, z):
        m = self.mbs["camo"]
        for i in range(4):
            for j in range(4):
                a, b = x0 + (x1 - x0) * i / 4, y0 + (y1 - y0) * j / 4; c, d = a + (x1 - x0) / 4, b + (y1 - y0) / 4
                sag = lambda u, v: z - 0.35 * math.sin(math.pi * (u - x0) / (x1 - x0)) * math.sin(math.pi * (v - y0) / (y1 - y0))
                m.quad((a, b, sag(a, b)), (c, b, sag(c, b)), (c, d, sag(c, d)), (a, d, sag(a, d)), W)
        for (px, py) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            self.plain_box(px - 0.06, py - 0.06, 0, px + 0.06, py + 0.06, z, (0.35, 0.3, 0.22, 1), "wood")

    # -- the camp -----------------------------------------------------------------------------------------------------
    def build(self):
        r = self.rnd; mb = self.mbs
        # ground and roads
        G = 340
        mb["dirt"].quad((-G, -G, 0), (G, -G, 0), (G, G, 0), (-G, G, 0), W, ((0, 0), (2 * G / 5, 0), (2 * G / 5, 2 * G / 5), (0, 2 * G / 5)), n=(0, 0, 1))
        road = [(-122, -40), (-60, -40), (-20, -24), (20, -24), (60, 20), (122, 20)]
        self.road = road
        for (ax, ay), (bx, by) in zip(road, road[1:]):
            dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy); nx, ny = -dy / L * 3.2, dx / L * 3.2
            mb["road"].quad((ax - nx, ay - ny, 0.02), (bx - nx, by - ny, 0.02), (bx + nx, by + ny, 0.02), (ax + nx, ay + ny, 0.02), (0.78, 0.72, 0.64, 1),
                            ((0, 0), (L / 7, 0), (L / 7, 1), (0, 1)), n=(0, 0, 1))
        # perimeter (gabion wall + wire), gates W/E/N
        for sx in (-EDGE, EDGE):
            gap = (-46, -34) if sx < 0 else (14, 26)
            self.gabions(sx, -EDGE, sx, gap[0], 2.2); self.gabions(sx, gap[1], sx, EDGE, 2.2)
        self.gabions(-EDGE, EDGE, -6, EDGE, 2.2); self.gabions(6, EDGE, EDGE, EDGE, 2.2); self.gabions(-EDGE, -EDGE, EDGE, -EDGE, 2.2)
        for t in range(-110, 112, 4):        # razor wire coils along the top
            for (x, y, ax) in ((t, EDGE, "x"), (t, -EDGE, "x"), (EDGE, t, "y"), (-EDGE, t, "y")):
                if ax == "x": cyl(mb["plain"], x, y, 2.45, 0.22, 4.0, (0.25, 0.25, 0.24, 1), axis="x", seg=6, caps=False)
                else: cyl(mb["plain"], x, y, 2.45, 0.22, 4.0, (0.25, 0.25, 0.24, 1), axis="y", seg=6, caps=False)
        # HQ command tent with sandbag ring and flag
        self.tent(0, 0, 9, 12); self.pole(0, 9.5, 9.0); self.spots["flag_hq"] = (0, 9.5, 9.0); self.spots["hq"] = (0, 0)
        for a0 in range(0, 360, 30):
            if a0 in (90, 270): continue
            a = math.radians(a0); x, y = 15 * math.cos(a), 15 * math.sin(a)
            if abs(math.cos(a)) > abs(math.sin(a)): self.sandbags(x, y - 3.4, x, y + 3.4, 1.05)
            else: self.sandbags(x - 3.4, y, x + 3.4, y, 1.05)
        self.camo_net(-14, -10, -6, -3, 3.0); self.crate(-11, -7); self.crate(-9.7, -7, 0.8); self.crate(-10.3, -5.6, 0.9)
        for k in range(5): self.drum(8 + k * 0.7, -9)
        # north tents (barracks)
        for i in range(5):
            for j in range(2):
                self.tent(-66 + i * 13, 52 + j * 18, 5.5, 8)
        for k in range(6): self.crate(-72 + k * 11, 62, 1.0)
        self.sandbags(-78, 44, -78, 86); self.sandbags(-30, 92, -6, 92)
        self.spots["north_tents"] = (-40, 61)
        # truck depot NE + motor pool
        self.trucks = []
        for k, (x, y, h) in enumerate(((20, 62, 0), (28, 62, 0), (36, 62, 0), (46, 72, 90))):
            self.trucks.append((x, y, h)); build_truck(mb["plain"], mb["canvas"], mb["camo"], x, y, h)
            self.obox_col(x, y, h, 1.3, 4.0, 2.75)
        self.spots["depot_truck"] = (36, 62)
        for k in range(8): self.drum(54 + (k % 4) * 0.7, 56 + (k // 4) * 0.7)
        self.camo_net(16, 55, 40, 70, 4.2)
        for k in range(4): self.crate(16 + k * 1.2, 50, 1.1)
        # shooting range (east): firing line sandbags at x=46, lanes towards +x, berm at x=106
        tbox(mb["dirt"], 104, -34, 0, 110, 14, 4.5, (0.85, 0.8, 0.72, 1), 3.0); self.col(104, -34, 0, 110, 14, 4.5, "dirt")
        for k in range(7):
            y = -31 + k * 6.5
            self.sandbags(44, y - 0.4, 44, y + 0.4, 1.0, 0.8) if False else None
            tbox(self.mbs["plywood"], 44.2, y - 0.04, 0, 46, y + 0.04, 0.95, W, 1.2); self.col(44.2, y - 0.04, 0, 46, y + 0.04, 0.95, "wood")      # lane dividers
        self.sandbags(47, -32, 47, 10, 0.95, 0.6)
        self.mbs["plain"].quad((40, -33, 3.8), (46, -33, 3.8), (46, 11, 3.6), (40, 11, 3.6), (0.32, 0.31, 0.27, 1))   # firing line shade roof
        self.mbs["plain"].quad((40, 11, 3.6), (46, 11, 3.6), (46, -33, 3.8), (40, -33, 3.8), (0.3, 0.3, 0.27, 1))
        for y in (-33, -11, 11):
            for x in (40, 46): self.plain_box(x - 0.08, y - 0.08, 0, x + 0.08, y + 0.08, 3.8, (0.4, 0.33, 0.22, 1), "wood")
        self.lanes = [-28 + k * 6.5 for k in range(6)]; self.range_x = [58, 70, 82, 94]
        self.spots["range"] = (42, -9)
        for x in self.range_x:      # distance markers
            for y in self.lanes: self.plain_box(x - 0.3, y - 0.1 - 1.4, 0, x + 0.3, y + 0.1 - 1.4, 0.35, (0.55, 0.5, 0.4, 1))
        self.tower(36, 12)
        # obstacle course (south), gates in order
        self.gates = []
        course = [(-60, -70), (-48, -64), (-36, -76), (-24, -66), (-12, -78), (2, -68), (16, -78), (30, -70)]
        for k, (x, y) in enumerate(course):
            self.plain_box(x - 2.2, y - 0.1, 0, x - 2.0, y + 0.1, 3.0, (0.75, 0.2, 0.15, 1)); self.plain_box(x + 2.0, y - 0.1, 0, x + 2.2, y + 0.1, 3.0, (0.75, 0.2, 0.15, 1))
            self.plain_box(x - 2.2, y - 0.1, 2.8, x + 2.2, y + 0.1, 3.1, (0.85, 0.8, 0.2, 1))
            self.gates.append((x, y))
        for (x, y) in ((-54, -67), (-30, -71), (8, -73)):    # low walls (jump)
            tbox(mb["plywood"], x - 2.0, y - 0.15, 0, x + 2.0, y + 0.15, 0.85, W, 1.0); self.col(x - 2.0, y - 0.15, 0, x + 2.0, y + 0.15, 0.85, "wood")
        for (x, y) in ((-42, -70), (-6, -73), (22, -74)):    # crawl wire (crouch or slide under it)
            for sx in (-2, 2):
                for sy in (-2, 2): self.plain_box(x + sx - 0.05, y + sy - 0.05, 0, x + sx + 0.05, y + sy + 0.05, 1.2, (0.35, 0.3, 0.22, 1))
            for k in range(6): cyl(mb["plain"], x - 2, y - 2 + k * 0.8, 1.15, 0.015, 4.0, (0.2, 0.2, 0.2, 1), axis="x", seg=4, caps=False)
            self.col(x - 2, y - 2, 1.12, x + 2, y + 2, 1.2, "wire")
        self.spots["course_start"] = (-66, -72)
        # kill house (west): plywood rooms, no roof
        kx0, ky0 = -100, -16; self.kill_rooms = []
        for i in range(3):
            for j in range(2):
                self.kill_rooms.append((kx0 + 3 + i * 8, ky0 + 4 + j * 8))
        P = mb["plywood"]; th = 0.15; Hh = 2.6
        def wall(x0, y0, x1, y1, doors=()):
            """axis-aligned wall with door gaps (centre positions along the wall)"""
            horiz = abs(y1 - y0) < 0.01; a0, a1 = (x0, x1) if horiz else (y0, y1)
            segs = [a0]
            for d in sorted(doors): segs += [d - 0.8, d + 0.8]
            segs.append(a1)
            for s0, s1 in zip(segs[::2], segs[1::2]):
                if s1 - s0 < 0.05: continue
                if horiz: tbox(P, s0, y0 - th, 0, s1, y0 + th, Hh, W, 1.2); self.col(s0, y0 - th, 0, s1, y0 + th, Hh, "wood")
                else: tbox(P, x0 - th, s0, 0, x0 + th, s1, Hh, W, 1.2); self.col(x0 - th, s0, 0, x0 + th, s1, Hh, "wood")
        wall(kx0 - 1, ky0, kx0 + 23, ky0, doors=(kx0 + 11 + 0.5,)); wall(kx0 - 1, ky0 + 16, kx0 + 23, ky0 + 16, doors=(kx0 + 3 + 0.5,))
        wall(kx0 - 1, ky0, kx0 - 1, ky0 + 16); wall(kx0 + 23, ky0, kx0 + 23, ky0 + 16, doors=(ky0 + 4 + 0.5,))
        wall(kx0 - 1, ky0 + 8, kx0 + 23, ky0 + 8, doors=(kx0 + 3 + 0.5, kx0 + 13 + 0.5, kx0 + 19 + 0.5,))
        wall(kx0 + 7, ky0, kx0 + 7, ky0 + 16, doors=(ky0 + 4 + 0.5, ky0 + 12 + 0.5,)); wall(kx0 + 15, ky0, kx0 + 15, ky0 + 16, doors=(ky0 + 4 + 0.5, ky0 + 12 + 0.5,))
        self.spots["killhouse_door"] = (kx0 + 25.5, ky0 + 4.5); self.spots["killhouse"] = (kx0 + 11, ky0 + 8)
        for (cx_, cy_) in ((kx0 + 0.2, ky0 + 1.2), (kx0 + 13.5, ky0 + 6.6), (kx0 + 5.8, ky0 + 14.8), (kx0 + 21.8, ky0 + 9.4)): self.crate(cx_, cy_, 0.9)
        # east compound (final assault)
        self.gabions(70, 42, 92, 42, 2.0); self.gabions(98, 42, 106, 42, 2.0); self.gabions(70, 92, 106, 92, 2.0)
        self.gabions(70, 42, 70, 60, 2.0); self.gabions(70, 66, 70, 92, 2.0); self.gabions(106, 42, 106, 92, 2.0)
        self.mast(84, 82); self.mast(98, 54); self.spots["mast1"] = (84, 82); self.spots["mast2"] = (98, 54)
        self.tower(98, 84); self.spots["sniper"] = (98, 84, 6.0)
        self.pole(86, 66, 8.0); self.spots["flag_east"] = (86, 66, 8.0)
        self.tent(80, 50, 5.5, 7, rot=True); self.tent(94, 72, 5.5, 7)
        for (a, b, c, d) in ((76, 58, 82, 58), (90, 62, 90, 68), (78, 74, 84, 74), (100, 64, 100, 70)): self.sandbags(a, b, c, d)
        for k in range(5): self.crate(73 + k * 1.1, 88, 1.0)
        self.spots["east"] = (88, 66)
        # misc cover around the camp (sandbag nests, gabion blocks, crates)
        for (x, y) in ((-30, 20), (25, 22), (-45, -30), (-20, -45), (15, -40), (60, -50), (60, 35), (-60, 25), (-85, 40), (-25, 40), (5, 40), (75, 10), (-90, -50), (85, -70)):
            k = r.randint(0, 2)
            if k == 0: self.sandbags(x - 2, y, x + 2, y); self.sandbags(x - 2, y + 2.5, x - 2, y)
            elif k == 1: self.gabions(x - 1.5, y, x + 1.5, y, 1.6)
            else: self.crate(x, y, 1.2); self.crate(x + 1.3, y + 0.2, 1.0); self.crate(x + 0.6, y + 0.1, 0.8, 1.2) if False else self.crate(x + 0.6, y + 1.2, 0.9)
        for (x, y, h) in ((-50, -22, 90), (62, -52, 0)):
            build_truck(mb["plain"], mb["canvas"], mb["camo"], x, y, h, cover=(h == 0)); self.obox_col(x, y, h, 1.3, 4.0, 2.75)
        for (x, y) in ((-80, 100), (100, -100), (-100, -100)): self.tower(x, y)
        # distant hills (outside the wall) for the horizon
        for k in range(40):
            a = 2 * math.pi * k / 40; a2 = 2 * math.pi * (k + 1) / 40; R0, R1 = 190, 300
            h0 = 14 + 9 * math.sin(k * 1.7) + 6 * math.sin(k * 0.6); h1 = 14 + 9 * math.sin((k + 1) * 1.7) + 6 * math.sin((k + 1) * 0.6)
            mb["dirt"].quad((R0 * math.cos(a), R0 * math.sin(a), 0), (R0 * math.cos(a2), R0 * math.sin(a2), 0),
                            (R1 * math.cos(a2), R1 * math.sin(a2), h1), (R1 * math.cos(a), R1 * math.sin(a), h0), (0.8, 0.76, 0.7, 1),
                            ((0, 0), (12, 0), (12, 10), (0, 10)))

    def obox_col(self, x, y, h, hw, hl, z1):
        c, s = abs(math.cos(math.radians(h))), abs(math.sin(math.radians(h)))
        ex, ey = hw * c + hl * s, hw * s + hl * c
        self.col(x - ex, y - ey, 0, x + ex, y + ey, z1, "metal")

    def finish(self):
        T = self.tex; self.season_nodes = {}; self.season_fx = None; self.season_id = None
        texmap = {"dirt": "dirt", "road": "dirt", "canvas": "canvas", "sandbag": "sandbag", "gabion": "gabion", "plywood": "plywood", "olive": "olive"}
        for k, mb in self.mbs.items():
            if not mb.t: continue
            n = node(mb, self.root, k, camo=(k == "camo"), gloss=0.05 if k in ("dirt", "road", "canvas", "sandbag") else 0.25,
                     tex=T[texmap[k]] if k in texmap else None)
            if k == "road": n.set_depth_offset(2)
            if k in ("dirt", "road"): n.set_shader_input("gvar", 1.0); n.set_shader_input("tint", Vec4(1.22, 1.2, 1.16, 1) if k == "dirt" else Vec4(1.14, 1.1, 1.06, 1))
            if k == "canvas": n.set_two_sided(True)
            if k == "camo": n.set_two_sided(True); n.set_shader_input("camoscale", 2.2)
            if k in ("dirt", "road", "canvas", "olive"): self.season_nodes[k] = n
        # do not flatten dirt/road/canvas/olive so season tints can update; flatten the rest
        keep = set(self.season_nodes.values())
        for ch in list(self.root.get_children()):
            if ch not in keep:
                ch.flatten_strong()
        a = np.array([b[:6] for b in self.boxes], dtype=np.float32)
        self.B0 = a[:, 0:3].copy(); self.B1 = a[:, 3:6].copy(); self.kinds = [b[6] for b in self.boxes]
        self.dyn = []        # dynamic boxes (targets, convoy truck): list of [x0,y0,z0,x1,y1,z1,kind,owner]
        self.build_nav()

    def apply_season(self, sid, rebuild=False):
        """Retint ground/canvas and add a light seasonal overlay (blossom / heat haze tint / autumn leaves / snow). No bloom."""
        import coka_seasons as SE
        from panda3d.core import CardMaker, TransparencyAttrib, Vec4
        if self.season_id == sid and not rebuild and self.season_fx is not None:
            return
        self.season_id = sid
        gt = SE.GROUND[sid]; rt = SE.ROAD[sid]
        if "dirt" in self.season_nodes:
            self.season_nodes["dirt"].set_shader_input("tint", Vec4(*gt))
        if "road" in self.season_nodes:
            self.season_nodes["road"].set_shader_input("tint", Vec4(*rt))
        if "canvas" in self.season_nodes:
            # winter: cooler canvas; spring: slight green bounce; autumn: warmer canvas
            ct = {"spring": (0.95, 1.05, 0.92, 1), "summer": (1.08, 1.02, 0.9, 1),
                  "autumn": (1.12, 0.9, 0.72, 1), "winter": (1.05, 1.08, 1.15, 1)}[sid]
            self.season_nodes["canvas"].set_shader_input("tint", Vec4(*ct))
        if "olive" in self.season_nodes:
            ot = {"spring": (0.85, 1.2, 0.75, 1), "summer": (1.05, 1.1, 0.8, 1),
                  "autumn": (1.25, 0.7, 0.35, 1), "winter": (0.85, 0.9, 0.95, 1)}[sid]
            self.season_nodes["olive"].set_shader_input("tint", Vec4(*ot))
        if self.season_fx is not None:
            self.season_fx.remove_node(); self.season_fx = None
        fx = self.root.attach_new_node("season_fx"); self.season_fx = fx
        rnd = self.rnd
        if sid == "winter":
            # snow patches on ground + light roof caps near HQ / tents
            cm = CardMaker("snow"); cm.set_frame(-1, 1, -1, 1)
            for _ in range(48):
                x, y = rnd.uniform(-110, 110), rnd.uniform(-110, 110)
                s = rnd.uniform(2.5, 7.0); q = fx.attach_new_node(cm.generate())
                q.set_pos(x, y, 0.04); q.set_scale(s, 1, s * 0.7); q.set_p(-90)
                q.set_color(0.92, 0.95, 1.0, 0.72); q.set_transparency(TransparencyAttrib.M_alpha)
                q.set_bin("transparent", 20); q.set_depth_write(False); q.set_light_off(1); q.set_shader_off(1)
            for (x, y, s) in ((0, 0, 5.5), (-66, 52, 3.2), (-40, 61, 3.5), (80, 50, 3.0), (94, 72, 3.0)):
                q = fx.attach_new_node(cm.generate()); q.set_pos(x, y, 2.7); q.set_scale(s, 1, s * 0.55); q.set_p(-90)
                q.set_color(0.95, 0.97, 1.0, 0.85); q.set_transparency(TransparencyAttrib.M_alpha)
                q.set_bin("transparent", 22); q.set_depth_write(False); q.set_light_off(1); q.set_shader_off(1)
        elif sid == "spring":
            cm = CardMaker("blossom"); cm.set_frame(-0.15, 0.15, -0.15, 0.15)
            for _ in range(60):
                x, y = rnd.uniform(-90, 90), rnd.uniform(-90, 90); z = rnd.uniform(1.5, 5.5)
                q = fx.attach_new_node(cm.generate()); q.set_pos(x, y, z); q.set_billboard_point_eye()
                q.set_color(1.0, 0.72, 0.82, 0.75); q.set_transparency(TransparencyAttrib.M_alpha)
                q.set_bin("transparent", 25); q.set_depth_write(False); q.set_light_off(1); q.set_shader_off(1)
        elif sid == "autumn":
            cm = CardMaker("leaf"); cm.set_frame(-0.18, 0.18, -0.12, 0.12)
            for _ in range(55):
                x, y = rnd.uniform(-100, 100), rnd.uniform(-100, 100); z = rnd.uniform(0.05, 4.5)
                q = fx.attach_new_node(cm.generate()); q.set_pos(x, y, z); q.set_h(rnd.uniform(0, 360)); q.set_billboard_point_eye()
                q.set_color(0.85, 0.35, 0.08, 0.8); q.set_transparency(TransparencyAttrib.M_alpha)
                q.set_bin("transparent", 25); q.set_depth_write(False); q.set_light_off(1); q.set_shader_off(1)
        elif sid == "summer":
            # subtle dry heat haze cards near horizon (low alpha, no glow)
            cm = CardMaker("haze"); cm.set_frame(-40, 40, 0, 8)
            for a in range(0, 360, 45):
                rad = math.radians(a); x, y = 160 * math.cos(rad), 160 * math.sin(rad)
                q = fx.attach_new_node(cm.generate()); q.set_pos(x, y, 0.5); q.look_at(0, 0, 2)
                q.set_color(1.0, 0.9, 0.65, 0.07); q.set_transparency(TransparencyAttrib.M_alpha)
                q.set_bin("transparent", 5); q.set_depth_write(False); q.set_light_off(1); q.set_shader_off(1)

    # -- queries ------------------------------------------------------------------------------------------------------
    def ray(self, o, d, maxd):
        """nearest box hit along ray. returns (t, kind, owner) or (maxd, None, None)"""
        o = np.asarray(o, np.float32); d = np.asarray(d, np.float32)
        inv = 1.0 / np.where(np.abs(d) < 1e-6, 1e-6, d)
        t0 = (self.B0 - o) * inv; t1 = (self.B1 - o) * inv
        tn = np.minimum(t0, t1).max(axis=1); tf = np.maximum(t0, t1).min(axis=1)
        ok = (tf >= np.maximum(tn, 0)) & (tn < maxd)
        best, kind, own = maxd, None, None
        if ok.any():
            tt = np.where(ok, np.maximum(tn, 0), 1e9); i = int(tt.argmin())
            if tt[i] < best: best, kind = float(tt[i]), self.kinds[i]
        for b in self.dyn:
            if not b[8]: continue
            t = _slab(o, d, b)
            if t is not None and t < best: best, kind, own = t, b[6], b[7]
        return best, kind, own

    def los(self, a, b):
        d = np.array(b, np.float32) - np.array(a, np.float32); L = float(np.linalg.norm(d))
        if L < 0.01: return True
        t, _, _ = self.ray(a, d / L, L)
        return t >= L - 0.05

    def ground(self, x, y, z, r=0.3):
        """height of the highest walkable top under the circle that is not above z+0.5"""
        g = 0.0
        m = (self.B0[:, 0] <= x + r) & (self.B1[:, 0] >= x - r) & (self.B0[:, 1] <= y + r) & (self.B1[:, 1] >= y - r) & (self.B1[:, 2] <= z + 0.5)
        if m.any(): g = max(g, float(self.B1[m, 2].max()))
        for b in self.dyn:
            if b[8] and b[0] <= x + r and b[3] >= x - r and b[1] <= y + r and b[4] >= y - r and b[5] <= z + 0.5: g = max(g, b[5])
        return g

    def push(self, x, y, z, hgt, r=0.35):
        """resolve circle-vs-box overlap for boxes that block at this height"""
        m = (self.B0[:, 0] < x + r) & (self.B1[:, 0] > x - r) & (self.B0[:, 1] < y + r) & (self.B1[:, 1] > y - r) & (self.B1[:, 2] > z + 0.5) & (self.B0[:, 2] < z + hgt)
        idx = list(np.nonzero(m)[0]); bl = [(self.B0[i], self.B1[i]) for i in idx]
        for b in self.dyn:
            if b[8] and b[0] < x + r and b[3] > x - r and b[1] < y + r and b[4] > y - r and b[5] > z + 0.5 and b[2] < z + hgt:
                bl.append(((b[0], b[1], b[2]), (b[3], b[4], b[5])))
        for b0, b1 in bl:
            cx, cy = min(max(x, b0[0]), b1[0]), min(max(y, b0[1]), b1[1]); dx, dy = x - cx, y - cy; dd = dx * dx + dy * dy
            if dd < r * r:
                if dd > 1e-8:
                    dl = math.sqrt(dd); x += dx / dl * (r - dl); y += dy / dl * (r - dl)
                else:   # centre inside the box: push out along the shortest axis
                    opts = [(x - b0[0], -1, 0), (b1[0] - x, 1, 0), (y - b0[1], 0, -1), (b1[1] - y, 0, 1)]; dist, sx, sy = min(opts)
                    x += sx * (dist + r); y += sy * (dist + r)
        lim = EDGE - 1.0
        return max(-lim, min(lim, x)), max(-lim, min(lim, y))

    # -- navigation ---------------------------------------------------------------------------------------------------
    def build_nav(self):
        self.cs = 1.0; self.n = int(2 * EDGE / self.cs)
        g = np.zeros((self.n, self.n), dtype=bool); cc = -EDGE + (np.arange(self.n) + 0.5) * self.cs
        for (x0, y0, z0, x1, y1, z1, k) in self.boxes:      # block cells whose centre is within 0.35 m of a box
            if z1 < 0.6 or z0 > 1.6: continue
            xi = np.nonzero((cc >= x0 - 0.35) & (cc <= x1 + 0.35))[0]; yi = np.nonzero((cc >= y0 - 0.35) & (cc <= y1 + 0.35))[0]
            if len(xi) and len(yi): g[xi[0]:xi[-1] + 1, yi[0]:yi[-1] + 1] = True
        g[0, :] = g[-1, :] = g[:, 0] = g[:, -1] = True
        self.block = g

    def cell(self, x, y):
        return (max(0, min(self.n - 1, int((x + EDGE) / self.cs))), max(0, min(self.n - 1, int((y + EDGE) / self.cs))))

    def cpos(self, c):
        return (-EDGE + (c[0] + 0.5) * self.cs, -EDGE + (c[1] + 0.5) * self.cs)

    def free_near(self, c):
        if not self.block[c]: return c
        for rr in range(1, 6):
            for dx in range(-rr, rr + 1):
                for dy in range(-rr, rr + 1):
                    q = (c[0] + dx, c[1] + dy)
                    if 0 <= q[0] < self.n and 0 <= q[1] < self.n and not self.block[q]: return q
        return c

    def path(self, a, b, maxn=14000):
        s, g = self.free_near(self.cell(*a)), self.free_near(self.cell(*b))
        if s == g: return [b]
        op = [(0, s)]; came = {s: None}; cost = {s: 0}; n = 0
        while op and n < maxn:
            _, c = heapq.heappop(op); n += 1
            if c == g: break
            for dx, dy, w in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
                q = (c[0] + dx, c[1] + dy)
                if not (0 <= q[0] < self.n and 0 <= q[1] < self.n) or self.block[q]: continue
                if dx and dy and (self.block[c[0] + dx, c[1]] or self.block[c[0], c[1] + dy]): continue
                nc = cost[c] + w
                if nc < cost.get(q, 1e9):
                    cost[q] = nc; came[q] = c; heapq.heappush(op, (nc + math.hypot(g[0] - q[0], g[1] - q[1]), q))
        if g not in came: return None
        pts = []; c = g
        while c is not None: pts.append(self.cpos(c)); c = came[c]
        pts.reverse()
        if not self.block[self.cell(*b)]: pts[-1] = b
        out = [pts[0]]; i = 0        # string pulling with line of sight at hip height
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.fat_los(pts[i], pts[j]): j -= 1
            out.append(pts[j]); i = j
        return out[1:]


def _fat(w, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1; nx, ny = -dy / L * 0.4, dx / L * 0.4
    return all(w.los((a[0] + k * nx, a[1] + k * ny, 0.9), (b[0] + k * nx, b[1] + k * ny, 0.9)) for k in (-1, 0, 1))


World.fat_los = _fat


def _slab(o, d, b):
    tn, tf = -1e9, 1e9
    for k in range(3):
        if abs(d[k]) < 1e-7:
            if o[k] < b[k] or o[k] > b[k + 3]: return None
            continue
        t0, t1 = (b[k] - o[k]) / d[k], (b[k + 3] - o[k]) / d[k]
        if t0 > t1: t0, t1 = t1, t0
        tn, tf = max(tn, t0), min(tf, t1)
        if tn > tf: return None
    if tf < 0: return None
    return max(tn, 0.0)
