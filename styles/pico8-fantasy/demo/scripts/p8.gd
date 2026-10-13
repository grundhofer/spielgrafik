class_name P8
extends RefCounted
## Kleine Fantasy-Konsole: 128x128 Bildspeicher mit 16 Farbnummern, Sprite-Blatt 128x128 (256 Sprites 8x8),
## Karte 128x32 Felder, Zeichenpalette, Füllmuster und eine 3x5-Schrift. Die Befehle heißen wie in der
## Vorbild-Konsole (cls, pset, line, rectfill, circfill, spr, sspr, map, print, pal, palt, fillp, clip,
## camera), damit ein Spielprogramm sich so liest wie eines für die Konsole. Es gibt keine andere
## Zeichenmöglichkeit: Alles, was im Bild steht, ist eine der 16 Farbnummern.
## Daten: cart/lornholm.p8 (__gfx__, __map__ im Textformat der Konsole), cart/font35.json.

const W := 128
const H := 128

var fb := PackedByteArray()      # Bildspeicher, eine Farbnummer 0-15 je Pixel
var gfx := PackedByteArray()     # Sprite-Blatt 128x128
var mapd := PackedByteArray()    # Karte 128x32
var dpal := PackedByteArray()    # Zeichenpalette (pal)
var transp := PackedByteArray()  # durchsichtige Farben für spr/map (palt)
var fillpat := 0                 # 16-Bit-Füllmuster (fillp), Bit 15 = Pixel (0,0) der 4x4-Zelle
var fill_transp := false         # Musterbits durchsichtig statt Zweitfarbe
var cx0 := 0
var cy0 := 0
var cx1 := W
var cy1 := H
var cam_x := 0
var cam_y := 0
var font := {}
var stat_pixels := 0             # gezeichnete Pixel im Bild (nur zur Information)


func _init() -> void:
	fb.resize(W * H)
	gfx.resize(128 * 128)
	mapd.resize(128 * 32)
	dpal.resize(16)
	transp.resize(16)
	pal()
	palt()


func load_cart(path: String) -> void:
	var f := FileAccess.open(path, FileAccess.READ)
	assert(f != null, "Cart fehlt: " + path)
	var section := ""
	var gy := 0
	var my := 0
	while not f.eof_reached():
		var l := f.get_line().strip_edges()
		if l.begins_with("__") and l.ends_with("__"):
			section = l
			continue
		if l == "":
			continue
		if section == "__gfx__" and gy < 128:
			for x in range(min(128, l.length())):
				gfx[gy * 128 + x] = l[x].hex_to_int()
			gy += 1
		elif section == "__map__" and my < 32:
			for x in range(min(128, l.length() / 2)):
				mapd[my * 128 + x] = l.substr(x * 2, 2).hex_to_int()
			my += 1


func load_font(path: String) -> void:
	var txt := FileAccess.get_file_as_string(path)
	font = JSON.parse_string(txt)


# --- Zustand -------------------------------------------------------------------------------------------

func pal(c0: int = -1, c1: int = -1) -> void:
	if c0 < 0:
		for i in 16:
			dpal[i] = i
	else:
		dpal[c0 & 15] = c1 & 15


func palt(c: int = -1, t: bool = false) -> void:
	if c < 0:
		for i in 16:
			transp[i] = 0
		transp[0] = 1
	else:
		transp[c & 15] = 1 if t else 0


func fillp(p: int = 0, transparent: bool = false) -> void:
	fillpat = p & 0xffff
	fill_transp = transparent


func clip(x: int = 0, y: int = 0, w: int = W, h: int = H) -> void:
	cx0 = max(0, x)
	cy0 = max(0, y)
	cx1 = min(W, x + w)
	cy1 = min(H, y + h)


func camera(x: int = 0, y: int = 0) -> void:
	cam_x = x
	cam_y = y


# --- Pixel ---------------------------------------------------------------------------------------------

## Farbe c: untere 4 Bit = Farbe, obere 4 Bit = Zweitfarbe für gesetzte Musterbits (wie auf der Konsole).
func _plot(x: int, y: int, c: int) -> void:
	if x < cx0 or y < cy0 or x >= cx1 or y >= cy1:
		return
	var col := c & 15
	if fillpat != 0 and (fillpat >> (15 - ((y & 3) * 4 + (x & 3)))) & 1 == 1:
		if fill_transp:
			return
		col = (c >> 4) & 15
	fb[y * W + x] = dpal[col]


func cls(c: int = 0) -> void:
	fb.fill(c & 15)


func pset(x: int, y: int, c: int) -> void:
	_plot(x - cam_x, y - cam_y, c)


func pget(x: int, y: int) -> int:
	x -= cam_x
	y -= cam_y
	if x < 0 or y < 0 or x >= W or y >= H:
		return 0
	return fb[y * W + x]


func rectfill(x0: int, y0: int, x1: int, y1: int, c: int) -> void:
	if x0 > x1:
		var t := x0; x0 = x1; x1 = t
	if y0 > y1:
		var t := y0; y0 = y1; y1 = t
	x0 -= cam_x; x1 -= cam_x; y0 -= cam_y; y1 -= cam_y
	var xa: int = max(x0, cx0)
	var xb: int = min(x1, cx1 - 1)
	var ya: int = max(y0, cy0)
	var yb: int = min(y1, cy1 - 1)
	if xa > xb or ya > yb:
		return
	if fillpat == 0:
		var col := dpal[c & 15]
		for y in range(ya, yb + 1):
			var o := y * W
			for x in range(xa, xb + 1):
				fb[o + x] = col
	else:
		for y in range(ya, yb + 1):
			for x in range(xa, xb + 1):
				_plot(x, y, c)


func rect(x0: int, y0: int, x1: int, y1: int, c: int) -> void:
	line(x0, y0, x1, y0, c)
	line(x0, y1, x1, y1, c)
	line(x0, y0, x0, y1, c)
	line(x1, y0, x1, y1, c)


func line(x0: int, y0: int, x1: int, y1: int, c: int) -> void:
	var dx: int = abs(x1 - x0)
	var dy: int = -abs(y1 - y0)
	var sx := 1 if x0 < x1 else -1
	var sy := 1 if y0 < y1 else -1
	var err := dx + dy
	while true:
		_plot(x0 - cam_x, y0 - cam_y, c)
		if x0 == x1 and y0 == y1:
			break
		var e2 := 2 * err
		if e2 >= dy:
			err += dy
			x0 += sx
		if e2 <= dx:
			err += dx
			y0 += sy


## Gefüllter Kreis: Pixel mit dx²+dy² <= r²+0,8r (r=1: Kreuz, r=2: 5x5 ohne Ecken), wie die Konsole sie setzt.
func circfill(x: int, y: int, r: int, c: int) -> void:
	if r < 0:
		return
	var lim := r * r + int(r * 0.8)
	for dy in range(-r, r + 1):
		for dx in range(-r, r + 1):
			if dx * dx + dy * dy <= lim:
				_plot(x + dx - cam_x, y + dy - cam_y, c)


func circ(x: int, y: int, r: int, c: int) -> void:
	if r < 0:
		return
	var lim := r * r + int(r * 0.8)
	var rin := r - 1
	var lim_in := rin * rin + int(rin * 0.8) if rin >= 0 else -1
	for dy in range(-r, r + 1):
		for dx in range(-r, r + 1):
			var d := dx * dx + dy * dy
			if d <= lim and d > lim_in:
				_plot(x + dx - cam_x, y + dy - cam_y, c)


func ovalfill(x0: int, y0: int, x1: int, y1: int, c: int) -> void:
	var cx := (x0 + x1) * 0.5
	var cy := (y0 + y1) * 0.5
	var rx := (x1 - x0) * 0.5 + 0.5
	var ry := (y1 - y0) * 0.5 + 0.5
	for y in range(y0, y1 + 1):
		for x in range(x0, x1 + 1):
			var u := (x - cx) / rx
			var v := (y - cy) / ry
			if u * u + v * v <= 1.0:
				_plot(x - cam_x, y - cam_y, c)


# --- Sprites und Karte -----------------------------------------------------------------------------------

func sspr(sx: int, sy: int, sw: int, sh: int, dx: int, dy: int, dw: int = -1, dh: int = -1,
		flip_x: bool = false, flip_y: bool = false) -> void:
	if dw < 0: dw = sw
	if dh < 0: dh = sh
	dx -= cam_x
	dy -= cam_y
	for y in range(dh):
		var py := dy + y
		if py < cy0 or py >= cy1:
			continue
		var ty := (y * sh) / dh
		if flip_y: ty = sh - 1 - ty
		var row := (sy + ty) * 128
		for x in range(dw):
			var px := dx + x
			if px < cx0 or px >= cx1:
				continue
			var tx := (x * sw) / dw
			if flip_x: tx = sw - 1 - tx
			var c := gfx[row + sx + tx]
			if transp[c] == 1:
				continue
			fb[py * W + px] = dpal[c]


func spr(n: int, x: int, y: int, w: int = 1, h: int = 1, flip_x: bool = false, flip_y: bool = false) -> void:
	sspr((n % 16) * 8, (n / 16) * 8, w * 8, h * 8, x, y, w * 8, h * 8, flip_x, flip_y)


## Karte: Felder (cx,cy) bis (cx+cw-1, cy+ch-1) ab Bildpunkt (sx,sy); Feld 0 wird nicht gezeichnet.
func map(cx: int, cy: int, sx: int, sy: int, cw: int, ch: int) -> void:
	for j in range(ch):
		for i in range(cw):
			var n := mapd[(cy + j) * 128 + cx + i]
			if n != 0:
				spr(n, sx + i * 8, sy + j * 8)


func mget(cx: int, cy: int) -> int:
	return mapd[cy * 128 + cx]


# --- Text ------------------------------------------------------------------------------------------------

func _glyph(ch: String) -> Dictionary:
	if font.has(ch):
		return font[ch]
	var u := ch.to_upper()
	if font.has(u):
		return font[u]
	return font["?"]


## Gibt die Breite in Pixeln zurück (Vorschub je Zeichen: Breite + 1).
func text_width(s: String) -> int:
	var w := 0
	for i in s.length():
		w += int(_glyph(s[i])["w"]) + 1
	return max(0, w - 1)


func prnt(s: String, x: int, y: int, c: int) -> int:
	for i in s.length():
		var g := _glyph(s[i])
		var gw := int(g["w"])
		var top := int(g["top"])
		var rows: Array = g["rows"]
		for ry in rows.size():
			var m := int(rows[ry])
			if m == 0:
				continue
			for rx in gw:
				if (m >> rx) & 1:
					_plot(x + rx - cam_x, y + top + ry - cam_y, c)
		x += gw + 1
	return x
