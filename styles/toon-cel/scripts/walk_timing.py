#!/usr/bin/env python3
"""Zeitplan des Laufs vorab rechnen (ohne Godot): wie main.gd (_update_badger) mit 30 Bildern/s.

Der Dachs läuft mit Walk (speed_scale 2 = 0,73 m/s), dreht in den letzten Schritten auf TURN_DEG und
bremst ab BRAKE_T über 0,4 s (Tempo und Abspieltempo gemeinsam). Ausgegeben werden für verschiedene
BRAKE_T die Phase des Laufzyklus beim Umschalten auf Idle und der Endpunkt. Gewählt wird eine
Durchgangsphase (0,3 oder 0,8: ein Fuß schwingt neben dem Standfuß durch), dann senkt die Überblendung
auf Idle nur den Schwungfuß ab, statt die Füße über den Boden zu ziehen.

    .venv/bin/python styles/toon-cel/scripts/walk_timing.py
"""
import math


def ss(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sim(brake_t, brake_time=0.4, idle_t=None, turn0=2.6, turn1=3.4, turn_deg=-60.0,
        x0=-5.0, z0=1.2, rate0=2.0, v=0.367):
    idle_t = idle_t or brake_t + brake_time - 0.05
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
    for i in range(280, 340, 2):
        bt = i / 100
        ph, x, z, r = sim(bt)
        print(f"BRAKE_T {bt:.2f}: Phase {ph:.3f}, Ende x={x:.2f} z={z:.2f}, Abspieltempo {r:.3f}")
