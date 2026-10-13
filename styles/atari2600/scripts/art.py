"""Grafikdaten des Eintrags atari2600: Spielerbilder (8 Bit je Zeile, eine Farbe je Zeile).

Spieler: Liste von (Bitmuster, Farbregister) von oben nach unten; '#' = gesetztes Bit, '.' = durchsichtig.
Bit 7 ist das linke Pixel (wie GRP0/GRP1 ohne Spiegelung). Dunkles Fell ist durchsichtig: Vor dem dunklen
Meer liest es sich als Schwarz (so entstehen die Augenstreifen).
"""

# Farbregister (Farbton << 4 | Helligkeit), Werte aus der NTSC-Palette
CAP = 0xD4        # dunkles Olivgrün (Mütze)
VEST = 0xD6       # Weste
WHITEF = 0x0E     # weißes Fell
SCARF = 0x44      # roter Schal
PARCEL = 0x2A     # Packpapier
LEGS = 0x00       # schwarze Beine (heben sich vom grauen Kai ab)
STRIPE = 0x02     # dunkler Augenstreif, Nase
W = WHITEF

# ---------------------------------------------------------------- Dachs im Profil (nach rechts), 22 Zeilen
# Oberkörper für beide Laufbilder gleich, die unteren 5 Zeilen (Beine) je Bild.
BADGER_SIDE_TOP = [
    ("...###..", CAP),
    ("..#####.", CAP),
    ("..######", CAP),     # Schirm nach vorn
    (".#.###..", W),       # Ohrrand hinten, weißer Stirnstreif
    ("##.#####", STRIPE),  # dunkler Augenstreif vom Ohr bis zur Nase (x7)
    (".#######", W),       # weiße Wange bis zur Schnauzenspitze
    ("..#####.", W),       # Unterkiefer
    ("...##...", W),       # Kinn
    (".#####..", SCARF),
    ("######..", SCARF),   # Schalende hinten
    (".#####..", VEST),
    ("..######", PARCEL),  # Paket unter dem Arm, ragt nach vorn
    ("..######", PARCEL),
    (".#####..", VEST),
    (".#####..", VEST),
    (".#####..", VEST),
    ("..####..", LEGS),
]
# Laufbilder: A = Ausschritt (Füße bei x 1-2 und 5-6), B = Durchgang (Füße bei x 3-4).
# Wechsel A->B->A mit 2 px Vorschub: der Standfuß bleibt an derselben Stelle.
BADGER_LEGS = {
    "A": [(".#####..", LEGS), (".##..##.", LEGS), (".##..##.", LEGS), (".##..##.", LEGS), (".##..##.", LEGS)],
    "B": [("..####..", LEGS), ("...##...", LEGS), ("...##...", LEGS), ("...##...", LEGS), ("...##...", LEGS)],
}

# ---------------------------------------------------------------- Dachs von vorn, 22 Zeilen
BADGER_FRONT = [
    ("..####..", CAP),
    (".######.", CAP),
    ("########", CAP),
    ("#..##..#", W),       # Ohrränder außen, weißer Mittelstreif, dazwischen dunkle Augenstreifen
    ("#..##..#", W),
    ("##.##.##", W),       # Wangen
    (".######.", W),       # Schnauze
    ("..####..", W),
    ("...##...", STRIPE),  # Nase
    (".######.", SCARF),
    ("########", SCARF),
    ("#.####.#", VEST),
    ("########", PARCEL),
    ("########", PARCEL),
    (".######.", VEST),
    (".######.", VEST),
    (".######.", LEGS),
    (".##..##.", LEGS),
    (".##..##.", LEGS),
    (".##..##.", LEGS),
    (".##..##.", LEGS),
    ("###..###", LEGS),
]
# Wind: Schalende weht zur Seite (nur die Schalzeile ändert sich)
BADGER_FRONT_WIND = list(BADGER_FRONT)
BADGER_FRONT_WIND[9] = (".#######", SCARF)


def breath(rows):
    """Atmen: Oberkörper (Zeilen 0-15) eine Zeile tiefer, zweite Westenzeile entfällt, Beine bleiben."""
    return [("........", 0)] + rows[0:15] + rows[16:]


def badger_side(frame):
    return BADGER_SIDE_TOP + BADGER_LEGS[frame]
