"""Grundriss der Bucht (Meter) für die Mode-7-Karte und die Platzierung der Sprites.

Wird von build_plane.py (Karte) und build_sprites.py / main.gd (Objektpositionen über data/objects.json)
genutzt. Kai und Steg liegen auf dem 8×8-Kachelraster (0,8 m), die Felsufer sind frei geformt.
"""
import math

import numpy as np

from m7lib import MAP, TPM, X_MIN, Y_MAX

# Kai (Pflaster) und Steg, in Metern; alle Kanten auf Vielfachen von 0,8 m in Texelkoordinaten
QUAY = dict(x0=-12.0, x1=-3.2, y0=-30.0, y1=24.4)
JETTY = dict(x0=-3.2, x1=14.4, y0=5.2, y1=7.6)
PILE_STEP = 2.4           # Pfähle an beiden Stegkanten alle 2,4 m (3 Kacheln)

# Felsufer rechts (Osten) als Linienzug, Land liegt östlich davon
EAST_SHORE = [(18.5, -32.0), (19.5, -12.0), (21.5, 4.0), (25.0, 19.0), (31.0, 33.0), (39.0, 46.0),
              (47.0, 56.0), (55.0, 64.0)]
# Küste nördlich vom Kai nach Westen (Land liegt südlich davon)
WEST_SHORE = [(-20.0, 24.4), (-24.0, 29.0), (-31.0, 33.5), (-40.0, 36.0), (-55.0, 38.0)]
# Felsen im Wasser: (x, y, Radius)
SEA_ROCKS = [(10.8, 20.5, 1.3), (15.6, 28.5, 1.8), (13.2, 30.8, 1.0), (6.6, 35.0, 1.1), (23.6, 11.0, 1.2),
             (-9.0, 31.0, 1.2)]
ROCK_BAND = 3.2           # Breite des Felsstreifens am Ufer, dahinter Gras


def texel_grid():
    """Weltkoordinaten (m) der Texelmitten: x[u], y[v]."""
    u = np.arange(MAP) + 0.5
    v = np.arange(MAP) + 0.5
    return X_MIN + u / TPM, Y_MAX - v / TPM


def _side_of_polyline(px, py, pts):
    """Vorzeichenbehafteter Abstand zur Linie (positiv = rechts der Laufrichtung)."""
    best = np.full(px.shape, np.inf)
    sign = np.ones(px.shape)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
        qx, qy = ax + t * dx, ay + t * dy
        dist = np.hypot(px - qx, py - qy)
        cross = dx * (py - ay) - dy * (px - ax)
        m = dist < best
        best = np.where(m, dist, best)
        sign = np.where(m, np.where(cross < 0, 1.0, -1.0), sign)
    return best * sign


def land_field(px, py):
    """> 0 an Land (Fels/Gras), < 0 im Wasser, in Metern (ungefährer Abstand zur Küste).

    Kai und Steg sind hier nicht enthalten (eigene Kacheln).
    """
    east = _side_of_polyline(px, py, EAST_SHORE)          # rechts der Linie (nach Norden laufend) = Osten
    west = -_side_of_polyline(px, py, WEST_SHORE)         # Land südlich
    west = np.where(px < QUAY["x0"] + 0.01, west, -99)    # nur westlich vom Kai
    behind_quay = np.where(px < QUAY["x0"] + 0.4, QUAY["y1"] - py, -99)   # Land hinter dem Kai, Küste bei y1
    f = np.maximum(np.maximum(east, west), behind_quay)
    for (rx, ry, r) in SEA_ROCKS:
        f = np.maximum(f, r - np.hypot(px - rx, py - ry))
    return f


# Die Objekte (Sprites) stehen mit ihren Weltpositionen in demo/scripts/main.gd (OBJECTS).
