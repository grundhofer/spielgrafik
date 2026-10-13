"""Requisiten als Pixeltext (zellgerecht gezeichnet): Buchstabe = Farbe, '.' = durchsichtig.

Kleinbuchstaben = normale Helligkeit, Großbuchstaben = hell (k b r m g c y w / K B R M G C Y W).
'p' = Papierfarbe der Zelle (wird beim Einsetzen durch die Farbe darunter ersetzt, z. B. Blau über Wasser).
Massive Requisiten mit Linien in Papierfarbe lesen sich über Wasser (Blau) und Kai (Schwarz) gleich.
"""

BARREL = """
..yyyyyyyy..
.yyyyyyyyyy.
yyyyyyyyyyyy
pppppppppppp
yyyyyyyypyyy
yyyyyyyypyyy
yyyyyyyypyyy
yyyyyyyypyyy
pppppppppppp
yyyyyyyyyyyy
.yyyyyyyyyy.
..yyyyyyyy..
"""

CRATE = """
yyyyyyyyyyyyyy
ypppppppppppyy
ypyyyyyyyyyppy
ypyyyyyyyyypyy
ypyyyyyyyypyyy
ypyyyyyyypyyyy
ypyyyyyypyyyyy
ypyyyyypyyyyyy
ypyyyypyyyyyyy
ypyyyypyyyyyyy
ypyyypyyyyyypy
yppppppppppppy
yyyyyyyyyyyyyy
"""

ROPE = """
....yyyyyyyyyy....
..yyppppppppppyy..
.ypppyyyyyyyypppy.
ypyyypppppppyyypy.
ypypppyyyyyyppypy.
ypyyyppppppppyypyy
.yppyyyyyyyyyyppy.
..yyppppppppppyy..
....yyyyyyyyyy....
"""

LANTERN = """
...YY...
..YYYY..
.YYYYYY.
.YpYYpY.
.YpYYpY.
.YYYYYY.
..YYYY..
"""

GULL = [
    # Flügel oben, Mitte, unten (1 = Pixel)
    """
1.......1
.1.....1.
..1.1.1..
...111...
""",
    """
.........
11.....11
..11111..
...111...
""",
    """
.........
.........
1111.1111
...111...
""",
]
