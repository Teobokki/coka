"""COKA: procedural textures + icon/menu art (run once on the dev box)."""
import numpy as np, os
from PIL import Image, ImageDraw, ImageFilter
R = np.random.default_rng(7); T = "assets/tex/"
def save(a, n): Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(T + n)
def noise(s, oct_=5, seed=0):
    r = np.random.default_rng(seed); out = np.zeros((s, s))
    for o in range(oct_):
        n = 2 ** (o + 2); g = r.random((n, n))
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((s, s), Image.BICUBIC)
        out += (np.asarray(im) / 255.0 - .5) / (1.6 ** o)
    return out
S = 512
# dusty dirt (tiles)
n = noise(S, 7, 1); n2 = noise(S, 4, 2)
base = np.array([150, 128, 98]); dirt = base[None, None, :] * (1 + .35 * n[..., None]) + np.array([12, 6, -4]) * n2[..., None] * 3
peb = R.random((S, S)) > .996
dirt[peb] *= .7
dirt = np.asarray(Image.fromarray(np.clip(dirt, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))).astype(float)
# make it tile: blend with rolled copy
w = np.minimum(np.linspace(0, 1, S), np.linspace(1, 0, S)) * 2; w = np.minimum(w, 1); W2 = np.outer(w, w)[..., None]
dirt = dirt * W2 + np.roll(np.roll(dirt, S // 2, 0), S // 2, 1) * (1 - W2); save(dirt, "dirt.png")
# tent canvas
c = noise(256, 5, 3); can = np.array([92, 98, 68])[None, None] * (1 + .18 * c[..., None])
can += (np.sin(np.arange(256) * 2.2)[None, :, None] * 4); save(can, "canvas.png")
# sandbags: rows of rounded bags
im = Image.new("RGB", (256, 256), (120, 104, 76)); d = ImageDraw.Draw(im)
for row in range(4):
    off = 32 if row % 2 else 0
    for k in range(-1, 4):
        x = k * 64 + off; y = row * 64
        d.rounded_rectangle((x + 2, y + 3, x + 62, y + 61), 22, fill=(158, 140, 104), outline=(92, 80, 58), width=3)
a = np.asarray(im).astype(float) * (1 + .12 * noise(256, 5, 4)[..., None]); save(a, "sandbag.png")
# gabion: rocks behind a wire grid
rk = Image.new("RGB", (256, 256), (110, 100, 86)); d = ImageDraw.Draw(rk)
for i in range(260):
    x, y = R.integers(0, 256, 2); r = R.integers(8, 20); g = int(R.integers(90, 170))
    d.ellipse((x - r, y - r * .8, x + r, y + r * .8), fill=(g, int(g * .93), int(g * .82)), outline=(60, 55, 48))
d = ImageDraw.Draw(rk)
for k in range(0, 256, 32):
    d.line((k, 0, k, 256), fill=(70, 72, 70), width=3); d.line((0, k, 256, k), fill=(70, 72, 70), width=3)
rk.save(T + "gabion.png")
# plywood
p = noise(256, 6, 5); ply = np.array([176, 146, 104])[None, None] * (1 + .1 * p[..., None]) + (np.sin(np.arange(256)[:, None] * .35 + p * 9) * 7)[..., None]
save(ply, "plywood.png")
# olive paint (trucks)
o = noise(256, 6, 6); ol = np.array([84, 88, 58])[None, None] * (1 + .15 * o[..., None]); save(ol, "olive.png")
# range target (silhouette with rings), RGBA
im = Image.new("RGBA", (256, 256), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.ellipse((88, 8, 168, 88), fill=(214, 200, 168, 255), outline=(40, 30, 20, 255), width=4)
d.rounded_rectangle((40, 80, 216, 256), 40, fill=(214, 200, 168, 255), outline=(40, 30, 20, 255), width=4)
for r in (70, 48, 26):
    d.ellipse((128 - r, 170 - r, 128 + r, 170 + r), outline=(150, 30, 26, 255), width=4)
d.ellipse((120, 162, 136, 178), fill=(150, 30, 26, 255)); im.save(T + "target.png")
# smoke puff / fire puff (alpha), debris
yy, xx = np.mgrid[-1:1:128j, -1:1:128j]; rr = np.sqrt(xx ** 2 + yy ** 2)
nn = noise(128, 5, 8)
al = np.clip((1 - rr) * 1.4 + nn * .8 - .2, 0, 1) ** 1.3
sm = np.dstack([np.full_like(rr, 200) + nn * 40] * 3 + [al * 255]); save(sm, "smoke.png")
fi = np.dstack([np.full_like(rr, 255), 150 + 90 * (1 - rr) + nn * 60, 40 + 60 * (1 - rr) + nn * 30, np.clip(al * 1.2, 0, 1) * 255]); save(fi, "fire.png")
# muzzle flash (alpha star)
im = Image.new("RGBA", (128, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
for k in range(6):
    import math; a = k * math.pi / 3
    d.polygon([(64, 64), (64 + 60 * math.cos(a - .18), 64 + 60 * math.sin(a - .18)), (64 + 60 * math.cos(a + .18), 64 + 60 * math.sin(a + .18))], fill=(255, 196, 110, 200))
d.ellipse((44, 44, 84, 84), fill=(255, 230, 170, 230)); im.filter(ImageFilter.GaussianBlur(2)).save(T + "flash.png")
# sky dome gradient (dusty)
h = 256; sky = np.zeros((h, 8, 3))
for i in range(h):
    t = i / (h - 1); top = np.array([150, 166, 178]); hor = np.array([214, 196, 168])
    sky[i] = top * (1 - t) ** .6 + hor * (1 - (1 - t) ** .6)
save(sky, "sky.png")
# minimap blip + flag patch
im = Image.new("RGB", (60, 40)); d = ImageDraw.Draw(im)
for k, col in enumerate([(200, 30, 30), (240, 200, 30), (40, 150, 60)]): d.rectangle((0, k * 13, 60, k * 13 + 14), fill=col)
im.save(T + "flag.png")
# icon + menu art from the poster
po = Image.open("assets/poster.jpg").convert("RGB")
po.resize((256, 256), Image.LANCZOS).save("assets/icon.png")
po.save("assets/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
po.resize((1024, 1024), Image.LANCZOS).save("assets/menu_bg.jpg", quality=90)
po.crop((600, 180, 1040, 620)).resize((512, 512), Image.LANCZOS).save("assets/ana_portrait.jpg", quality=92)
print("ok")
