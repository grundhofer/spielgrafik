"""Die feste 16-Farben-Palette der Fantasy-Konsole (wie tools/sprites.py --palette pico8)."""
HEX = "000000 1d2b53 7e2553 008751 ab5236 5f574f c2c3c7 fff1e8 ff004d ffa300 ffec27 00e436 29adff 83769c ff77a8 ffccaa".split()
PAL = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in HEX]
