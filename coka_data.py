"""COKA - CALL OF KIMS ARMY: game data (all names fictional).  ©2026 EX Inc./HYPERION DIGITAL ©2026"""

RANKS = [("RECRUIT", 0), ("PRIVATE", 600), ("PRIVATE FIRST CLASS", 1500), ("CORPORAL", 3000), ("SERGEANT", 5200), ("STAFF SERGEANT", 8000),
         ("LIEUTENANT", 11500), ("CAPTAIN", 16000), ("MAJOR", 21500), ("COLONEL", 28000), ("COMMANDER", 36000)]


def rank_of(xp):
    i = 0
    for k, (_, need) in enumerate(RANKS):
        if xp >= need: i = k
    return i


# id, name, class, damage, rpm, mag, reserve, hip spread (deg), ads spread, recoil (deg), range (m), ads fov, unlock rank, slot, sound, rate
WEAPONS = [
    dict(id="km9", name="KM-9 KESTREL", cls="SMG", dmg=22, rpm=820, mag=32, res=160, hip=3.2, ads=1.1, rec=0.55, rng=32, fov=55, rank=0, slot=0, snd="smg", rate=1.0, auto=True),
    dict(id="p11", name="P-11 WASP", cls="PISTOL", dmg=30, rpm=380, mag=12, res=72, hip=2.6, ads=0.9, rec=1.3, rng=28, fov=60, rank=0, slot=1, snd="pistol", rate=1.0, auto=False),
    dict(id="kr4", name="KR-4 RIDGEBACK", cls="RIFLE", dmg=29, rpm=640, mag=30, res=150, hip=3.6, ads=0.55, rec=0.75, rng=60, fov=48, rank=2, slot=0, snd="smg", rate=0.78, auto=True),
    dict(id="sg12", name="SG-12 MULE", cls="SHOTGUN", dmg=14, rpm=75, mag=7, res=35, hip=6.0, ads=4.5, rec=4.5, rng=16, fov=60, rank=4, slot=0, snd="shotgun", rate=1.0, auto=False, pellets=9),
    dict(id="sr50", name="SR-50 LONGREACH", cls="SNIPER", dmg=110, rpm=46, mag=5, res=30, hip=7.0, ads=0.05, rec=6.0, rng=160, fov=18, rank=6, slot=0, snd="shotgun", rate=0.62, auto=False),
]
W = {w["id"]: w for w in WEAPONS}

# attachment id, name, unlock rank, effect
ATTACH = [
    ("reddot", "RED-DOT SIGHT", 1, "Clearer aim, ADS 10% tighter"),
    ("grip", "VERTICAL GRIP", 3, "Recoil -25%"),
    ("extmag", "EXTENDED MAG", 5, "Magazine +50%"),
    ("suppressor", "SUPPRESSOR", 7, "Quiet shots, stay off the bots' radar, damage -8%"),
    ("scope4", "4x SCOPE", 8, "Rifles zoom in further when aiming"),
]
CAMOS = [("desert", "DESERT DIGITAL", 0, [(0.58, 0.52, 0.42), (0.45, 0.40, 0.32), (0.70, 0.66, 0.58), (0.33, 0.30, 0.25)]),
         ("urban", "URBAN DIGITAL", 1, [(0.55, 0.55, 0.53), (0.38, 0.38, 0.37), (0.72, 0.71, 0.68), (0.25, 0.25, 0.25)]),
         ("woodland", "WOODLAND DIGITAL", 3, [(0.34, 0.37, 0.24), (0.24, 0.27, 0.17), (0.48, 0.44, 0.31), (0.15, 0.15, 0.12)]),
         ("night", "NIGHT OPS", 5, [(0.16, 0.17, 0.20), (0.10, 0.11, 0.13), (0.26, 0.27, 0.30), (0.06, 0.06, 0.07)]),
         ("redline", "KIMS RED", 7, [(0.45, 0.12, 0.10), (0.25, 0.06, 0.05), (0.62, 0.52, 0.40), (0.12, 0.10, 0.09)]),
         ("gold", "COMMANDER GOLD", 10, [(0.78, 0.62, 0.26), (0.58, 0.44, 0.16), (0.92, 0.80, 0.45), (0.38, 0.28, 0.10)])]
CAMO = {c[0]: c for c in CAMOS}
PERKS = [("quickhands", "QUICK HANDS", 0, "Reload 30% faster"), ("marathon", "MARATHON", 1, "Sprint longer and slide further"),
         ("flak", "FLAK VEST", 2, "Grenade damage -45%"), ("ironlungs", "IRON LUNGS", 4, "Steadier aim: ADS spread -25%"),
         ("scavenger", "SCAVENGER", 6, "Kills refill a magazine of ammo"), ("tough", "HARD AS NAILS", 9, "120 health")]

XP = {"kill": 100, "headshot": 50, "melee": 60, "assist": 40, "target": 25, "objective": 250, "mission": 1200, "win": 500, "match": 250}

FRIENDS = ["PVT. HANA RIX", "CPL. DAVO MERRIN", "PVT. JUNO SALK", "SGT. OREN VALE", "PVT. TESS KORRO", "CPL. MILO BRANDT"]
BOTS = ["VIPER-21", "DUSTJAW", "K. NARVIK", "GRIT", "SANDCAT", "R. OKONKWO", "MARLOW", "IRONWOOD", "BLITZEN", "T. VASQUEZ", "NOMAD-7",
        "FALKE", "CHALK", "S. IBARRA", "WOLFRAM", "HOLLOWAY", "PIKE", "J. ADEYEMI", "STATIC", "BRISK", "RUST", "M. KOVAC"]
DIFF = [("RECRUIT", dict(react=0.9, aim=3.6, dmg=0.55, burst=3)), ("REGULAR", dict(react=0.55, aim=2.2, dmg=0.8, burst=4)),
        ("VETERAN", dict(react=0.3, aim=1.2, dmg=1.0, burst=6))]

# campaign: id, title, subtitle, time-of-day, briefing [(speaker, line)], objective script id
MISSIONS = [
    ("m1", "BASIC TRAINING", "Range qualification and obstacle course", "golden",
     [("KIM", "Recruit Ana. Welcome to Camp Kim. Today you earn your place in this army."),
      ("KIM", "Hit twelve pop-up targets on the range, then run the obstacle course through every gate."),
      ("ANA", "Understood, Colonel. Twelve targets, every gate. Let's go.")]),
    ("m2", "KILL HOUSE", "Clear every room. Training rounds only", "day",
     [("KIM", "Good shooting. Now the kill house. Eight opposing force soldiers are waiting inside."),
      ("KIM", "Clear every room. Check your corners. Grenades are allowed."),
      ("ANA", "Moving to the door. Clearing room by room.")]),
    ("m3", "NIGHT OPS", "Infiltrate the north tents, sabotage the depot", "night",
     [("KIM", "Tonight's drill is a night raid. Red team holds the north tents and the truck depot."),
      ("KIM", "Take out the patrol quietly, plant a charge on the depot truck, then get to the extraction point."),
      ("ANA", "Lights off. Going in.")]),
    ("m4", "DEFEND THE CAMP", "Hold the HQ against three waves", "dusk",
     [("KIM", "Alert. A large red team force is moving on the HQ. This is the big exercise."),
      ("KIM", "Hold the command tent with your squad. Three waves. Do not let them take it."),
      ("ANA", "Squad, on me. Nobody gets past the sandbags.")]),
    ("m5", "CONVOY ESCORT", "Keep the supply truck alive", "golden",
     [("KIM", "The supply truck has to cross the camp to the east gate. Red team will ambush it."),
      ("KIM", "Stay with the truck. If it is destroyed, the drill fails."),
      ("ANA", "Escort copied. Driver, keep it steady.")]),
    ("m6", "FINAL ASSAULT", "Take the east compound and raise the flag", "dusk",
     [("KIM", "Final exam, Ana. Red team is dug in at the east compound, with a sniper in the watchtower."),
      ("KIM", "Take out the sniper, destroy both radio masts, and raise our flag at the compound."),
      ("ANA", "This is what we trained for. Squad, move up!")]),
]
COPYRIGHT = "©2026 EX Inc./HYPERION DIGITAL ©2026"
FICTION = "All characters, units and events in this game are fictional."
