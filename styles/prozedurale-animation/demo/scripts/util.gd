extends RefCounted
## Deterministische Hilfsfunktionen: ganzzahliges Hash-Rauschen (ohne sin), 1D-Wertrauschen, fBm.


static func hash1(i: int, seed_: int) -> float:
	var h: int = (i * 374761393 + seed_ * 668265263) & 0xffffffff
	h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
	h = h ^ (h >> 16)
	return float(h & 0xffff) / 65535.0


## Wertrauschen in [-1, 1], weich interpoliert.
static func vnoise(x: float, seed_: int) -> float:
	var i: int = floori(x)
	var f: float = x - float(i)
	var u: float = f * f * (3.0 - 2.0 * f)
	return lerpf(hash1(i, seed_), hash1(i + 1, seed_), u) * 2.0 - 1.0


static func fbm(x: float, seed_: int) -> float:
	return 0.6 * vnoise(x, seed_) + 0.28 * vnoise(x * 2.13, seed_ + 17) + 0.12 * vnoise(x * 4.71, seed_ + 31)


static func smooth01(u: float) -> float:
	u = clampf(u, 0.0, 1.0)
	return u * u * (3.0 - 2.0 * u)


## Glatter Übergang mit Ruck 0 an beiden Enden (min. Ruck).
static func minjerk(u: float) -> float:
	u = clampf(u, 0.0, 1.0)
	return u * u * u * (10.0 + u * (-15.0 + 6.0 * u))
