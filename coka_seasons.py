"""COKA rotating seasons (UTC, shared by all players).
Schedule: each season lasts 7 real days, aligned to UTC Mondays (same pattern as FIREOUT SHINE).
Index = (ISO year * 53 + ISO week) % 4 -> spring, summer, autumn, winter.
A full loop is 28 days (~13 cycles/year), so the camp never feels stuck on one look.
Force override: settings["force_season"] or env COKA_SEASON = spring|summer|autumn|winter (off by default).
©2026 EX Inc./HYPERION DIGITAL ©2026"""
import datetime, os

SEASONS = ("spring", "summer", "autumn", "winter")
NAMES = {"spring": "SPRING", "summer": "SUMMER", "autumn": "AUTUMN", "winter": "WINTER"}
LABELS = {
    "spring": "SPRING AT  -  green camp, soft light, blossom hints",
    "summer": "SUMMER HEAT  -  bright sun, dry haze",
    "autumn": "AUTUMN DRILL  -  orange foliage, cooler air",
    "winter": "WINTER OPS  -  snow on the camp, cold blue light",
}
# short training modifiers (light + fair)
MODS = {
    "spring": {"fog_mul": 0.92, "stam_drain": 1.00, "warm": 0.95, "banner": "SPRING CLASS"},
    "summer": {"fog_mul": 1.08, "stam_drain": 1.18, "warm": 1.22, "banner": "SUMMER HEAT"},
    "autumn": {"fog_mul": 1.00, "stam_drain": 0.95, "warm": 0.78, "banner": "AUTUMN DRILL"},
    "winter": {"fog_mul": 1.35, "stam_drain": 1.05, "warm": 0.35, "banner": "WINTER OPS"},
}
# ground / canvas tint (RGBA multiplier via shader tint)
GROUND = {
    "spring": (0.92, 1.18, 0.88, 1),
    "summer": (1.28, 1.18, 0.92, 1),
    "autumn": (1.22, 0.92, 0.62, 1),
    "winter": (1.15, 1.18, 1.28, 1),
}
ROAD = {
    "spring": (1.05, 1.08, 1.00, 1),
    "summer": (1.18, 1.10, 0.98, 1),
    "autumn": (1.10, 0.95, 0.78, 1),
    "winter": (1.08, 1.10, 1.18, 1),
}
# sky overrides layered on tod keys: (zen, hor, sunc, haze) scale factors + optional fog density add
SKY_TINT = {
    "spring": {"zen": (0.92, 1.05, 0.98), "hor": (0.95, 1.05, 0.92), "sunc": (0.95, 1.0, 0.95), "haze": (0.9, 1.05, 0.88)},
    "summer": {"zen": (1.05, 1.02, 0.88), "hor": (1.08, 0.98, 0.82), "sunc": (1.15, 1.05, 0.85), "haze": (1.15, 1.0, 0.75)},
    "autumn": {"zen": (0.95, 0.88, 0.95), "hor": (1.12, 0.78, 0.55), "sunc": (1.1, 0.85, 0.55), "haze": (1.05, 0.75, 0.5)},
    "winter": {"zen": (0.78, 0.88, 1.12), "hor": (0.78, 0.85, 1.05), "sunc": (0.75, 0.85, 1.1), "haze": (0.7, 0.8, 1.0)},
}
LIGHT_MUL = {
    # suncol, skytop, skybot, fogcol, fogden mul, envtint
    "spring": ((0.95, 1.05, 0.95), (0.95, 1.08, 0.98), (0.9, 1.12, 0.85), (0.9, 1.05, 0.88), 0.92, (0.95, 1.05, 0.95)),
    "summer": ((1.2, 1.1, 0.85), (1.05, 1.0, 0.9), (1.1, 0.95, 0.75), (1.1, 0.95, 0.75), 1.1, (1.1, 1.0, 0.85)),
    "autumn": ((1.1, 0.85, 0.55), (0.95, 0.85, 0.9), (1.05, 0.7, 0.45), (1.0, 0.7, 0.45), 1.0, (1.05, 0.85, 0.7)),
    "winter": ((0.75, 0.85, 1.15), (0.7, 0.82, 1.1), (0.75, 0.82, 1.0), (0.65, 0.75, 0.95), 1.4, (0.75, 0.85, 1.1)),
}
MENU_GRADE = {  # overlay colour on menu poster (r,g,b,a)
    "spring": (0.35, 0.75, 0.45, 0.14),
    "summer": (0.95, 0.7, 0.25, 0.16),
    "autumn": (0.85, 0.4, 0.12, 0.18),
    "winter": (0.35, 0.5, 0.85, 0.20),
}
SCOL = {
    "spring": (0.55, 0.9, 0.55, 1),
    "summer": (1.0, 0.85, 0.35, 1),
    "autumn": (1.0, 0.55, 0.2, 1),
    "winter": (0.75, 0.88, 1.0, 1),
}


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def season_window(now=None):
    """Return (season_id, start_utc, end_utc) for the current 7-day UTC Monday window."""
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    d = now.astimezone(datetime.timezone.utc).date()
    iso = d.isocalendar()
    idx = (iso[0] * 53 + iso[1]) % 4
    # Monday 00:00 UTC of this ISO week
    start_d = d - datetime.timedelta(days=d.weekday())
    end_d = start_d + datetime.timedelta(days=7)
    start = datetime.datetime(start_d.year, start_d.month, start_d.day, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(end_d.year, end_d.month, end_d.day, tzinfo=datetime.timezone.utc)
    return SEASONS[idx], start, end


def resolve(settings=None, now=None):
    """Active season for this client. Force override (settings or COKA_SEASON) wins for testing."""
    force = ""
    if settings:
        force = (settings.get("force_season") or "").strip().lower()
    env = (os.environ.get("COKA_SEASON") or "").strip().lower()
    if force in SEASONS:
        s, s0, s1 = season_window(now); return force, s0, s1, True
    if env in SEASONS:
        s, s0, s1 = season_window(now); return env, s0, s1, True
    s, s0, s1 = season_window(now)
    return s, s0, s1, False


def countdown(end, now=None):
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    left = max(0, int((end - now).total_seconds()))
    d, rem = divmod(left, 86400); h, rem = divmod(rem, 3600); m = rem // 60
    if d > 0:
        return "%dd %02dh %02dm" % (d, h, m), left
    return "%02dh %02dm" % (h, m), left


def next_name(cur):
    return NAMES[SEASONS[(SEASONS.index(cur) + 1) % 4]]


def mul3(a, b):
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])
