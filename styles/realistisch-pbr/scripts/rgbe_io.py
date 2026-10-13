"""Radiance-HDR (.hdr, RGBE) lesen und schreiben mit NumPy (ohne weitere Pakete).

Lesen versteht flache und lauflängenkodierte Zeilen ("new RLE"), Schreiben legt flache Zeilen ab.
"""
import numpy as np


def read_hdr(path):
    data = open(path, "rb").read()
    pos = 0
    # Kopfzeilen bis zur Leerzeile, dann die Auflösungszeile "-Y h +X w"
    while True:
        end = data.index(b"\n", pos)
        line = data[pos:end]
        pos = end + 1
        if line.strip() == b"":
            break
    end = data.index(b"\n", pos)
    parts = data[pos:end].split()
    pos = end + 1
    assert parts[0] == b"-Y" and parts[2] == b"+X", parts
    h, w = int(parts[1]), int(parts[3])
    buf = np.frombuffer(data, dtype=np.uint8, offset=pos)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    p = 0
    for y in range(h):
        if 8 <= w < 32768 and buf[p] == 2 and buf[p + 1] == 2 and (int(buf[p + 2]) << 8 | int(buf[p + 3])) == w:
            p += 4
            for c in range(4):
                x = 0
                row = out[y, :, c]
                while x < w:
                    n = int(buf[p]); p += 1
                    if n > 128:
                        n -= 128
                        row[x:x + n] = buf[p]; p += 1
                    else:
                        row[x:x + n] = buf[p:p + n]; p += n
                    x += n
        else:
            out[y] = buf[p:p + 4 * w].reshape(w, 4)
            p += 4 * w
    rgbe = out.astype(np.float32)
    e = out[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)
    return rgbe[..., :3] * scale[..., None]


def write_hdr(path, img):
    img = np.asarray(img, dtype=np.float32)
    h, w, _ = img.shape
    m = img.max(axis=2)
    mant, expo = np.frexp(m)
    scale = np.where(m > 1e-32, mant * 256.0 / np.maximum(m, 1e-32), 0.0)
    rgbe = np.zeros((h, w, 4), dtype=np.uint8)
    rgbe[..., :3] = np.clip(img * scale[..., None], 0, 255).astype(np.uint8)
    rgbe[..., 3] = np.where(m > 1e-32, expo + 128, 0).astype(np.uint8)
    with open(path, "wb") as f:
        f.write(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n")
        f.write(f"-Y {h} +X {w}\n".encode())
        f.write(rgbe.tobytes())
