#!/usr/bin/env python3
"""Zeitplan des Laufs vorab rechnen (ohne Godot): wie main.gd (_update_badger) mit 30 Bildern/s.

Nach styles/toon-cel/scripts/walk_timing.py. Der Dachs läuft mit Walk (speed_scale 2 = 0,73 m/s),
dreht zwischen TURN_T0 und TURN_T1 auf TURN_DEG und bremst ab BRAKE_T über BRAKE_TIME. Ausgegeben werden
für verschiedene BRAKE_T die Phase des Laufzyklus beim Umschalten auf Idle und der Endpunkt. Gewählt
wird eine Durchgangsphase (etwa 0,3 oder 0,8: ein Fuß schwingt neben dem Standfuß durch), dann senkt
die Überblendung auf Idle nur den Schwungfuß ab. Die Drehung um den Standfuß (main.gd) verschiebt den
Endpunkt etwas; das genaue Ergebnis misst scripts/measure_badger.py.

    .venv/bin/python styles/gemaltes-3d/scripts/walk_timing.py
"""
import math


def ss(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sim(brake_t, brake_time=0.4, idle_gap=0.35, turn0=2.2, turn1=3.2, turn_deg=-62.0,
        x0=-4.75, z0=1.6, rate0=2.0, v=0.367):
    idle_t = brake_t + idle_gap
    dt = 1 / 30
    t, x, z, ph, rate = 0.0, x0, z0, 0.0, rate0
    while t < idle_t - 1e-9:
        t += dt
        rate = rate0 * (1 - ss(brake_t, brake_t + brake_time, t))
        th = math.radians(turn_deg) * ss(turn0, turn1, t)
        x += v * rate * dt * math.cos(th)
        z += -v * rate * dt * math.sin(th)
        ph += rate * dt
    return ph % 1.0, x, z, rate


if __name__ == "__main__":
    for i in range(270, 330, 2):
        bt = i / 100
        ph, x, z, r = sim(bt)
        print(f"BRAKE_T {bt:.2f}: Phase {ph:.3f}, Ende x={x:.2f} z={z:.2f}, Abspieltempo {r:.3f}")
