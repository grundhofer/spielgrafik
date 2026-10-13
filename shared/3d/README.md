# Gemeinsame 3D-Grundlage (`shared/3d/`)

Anleitung für alle 3D-Stile im Katalog (PS1, N64, Toon, Voxel, Diorama, HD-2D, Pixel-3D, 1-Bit-3D, Knete,
realistisch PBR, vorgerenderte Hintergründe …). Alle Stile zeigen **dieselbe Geometrie**: den Hafen von Lornholm
und den Dachs-Kurier. Ein Stil ändert Materialien, Shader, Auflösung, Licht und Nachbearbeitung, nicht die
Modelle. Nur so lassen sich die Stile vergleichen.

Die vollständigen Tabellen (alle Objekte, Knochen, Maße, Farben) stehen in `harbor_notes.md` und
`badger_notes.md`. Beide Dateien erzeugen die Bauskripte bei jedem Lauf neu. Diese README fasst zusammen, was
ein Stil braucht, und nennt die Fallstricke, die beim Bau der Probeszene aufgefallen sind.

## Dateien

| Datei | Inhalt |
|---|---|
| `harbor.glb` | Hafenszene, 17 932 Dreiecke, 14 Materialien, 5 Empties, ohne Lichter und Kameras |
| `badger.glb` | Dachs-Kurier, geriggt (21 Knochen), 7 348 Dreiecke, Animationen `Idle`, `Walk`, `Wave` |
| `badger_low.glb` | dieselbe Figur mit 876 Dreiecken, gleiche Knochen, Animationen und Materialnamen (für PS1/N64) |
| `harbor_notes.md`, `badger_notes.md` | vom Skript erzeugte Notizen mit allen Zahlen |
| `preview_*.png` | EEVEE-Vorschaubilder aus Blender (Hafen mit Hauptkamera, Dachs von allen Seiten) |
| `blender/build_harbor.py` | baut `harbor.glb`, Notizen und Vorschau |
| `blender/build_badger.py` | baut `badger.glb` und `badger_low.glb`, Notizen, Vorschau und Prüfwerte |
| `blender/preview_badger.py` | Vorschaubilder und Messwerte (Bodenkontakt, Fußhub) aus einer fertigen Dachs-glb |
| `demo/` | stilneutrale Godot-4.7-Probeszene (Vorlage für eigene Demos, siehe unten) |
| `media/` | Aufnahme der Probeszene von `tools/capture.py` (`frames.jpg`, `poster.png`, `demo.mp4` …) |

## Koordinaten, Maßstab, Kamera

- 1 Einheit = 1 m. In Godot ist +Y oben. Umrechnung: **Godot (x, y, z) = Blender (x, z, −y)**.
- Die Kamera blickt entlang −Z. Vorn (zur Kamera) ist +Z, hinten (Meer, Leuchtturm) ist −Z.
- Kaioberfläche bei y = 0, Wasserlinie bei y = −0,8. Der Laufweg des Dachses liegt auf y = 0, z = 1,2 und reicht
  von x = −6 (`WalkStart`) bis x = +2 (`WalkEnd`).
- Hauptkamera (bitte unverändert übernehmen, damit die Bilder vergleichbar bleiben):

```
[node name="Camera" type="Camera3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 0.9986295, 0.05233596, 0, -0.05233596, 0.9986295, -1.8, 3.4, 14.5)
current = true
fov = 42.0
near = 0.1
far = 3000.0
```

  Das entspricht `position = (-1.8, 3.4, 14.5)`, `rotation_degrees = (-3, 0, 0)`, `fov = 42` (vertikal,
  `keep_aspect` = Keep Height). In Godot nachgemessen: Der Bildausschnitt deckt sich mit
  `preview_harbor_main.png`.
- Der Dachs ist in dieser Totale etwa 71 px hoch bei 720 px Bildhöhe, bei 180 px Bildhöhe also nur etwa 18 px.

## Was in den glb steckt

### Hafen (`harbor.glb`)

Knotennamen in Godot = Objektnamen aus Blender. Die Wurzel heißt nach der Datei (`harbor`), als Instanz in
einer Szene trägt sie den Namen aus der `.tscn`.

```
harbor
├─ Quay, Jetty, Bollards, Sea, WestHill, Headland, RocksSea, IslandsFar
├─ BoatA, BoatB                  Ursprung auf der Wasserlinie, Bug lokal +X
├─ Barrel1, Barrel2, CrateStack, RopeCoil
├─ Cottage
│  ├─ CottageWindow              Glas, emissiv (Front- und Seitenfenster)
│  └─ ChimneySmoke               Empty: Rauchaustritt
├─ LanternPost
│  ├─ LanternGlass               Glas, emissiv
│  └─ LanternLight               Empty: Mitte der Laterne
├─ Lighthouse
│  ├─ LighthouseLamp             Glas, emissiv
│  └─ LighthouseLight            Empty: Lichtzentrum (12,58 m über dem Kai)
└─ WalkStart, WalkEnd            Empties: Laufweg
```

Empties werden in Godot zu `Node3D`. Sie hängen zum Teil unter Objekten. Gesucht wird deshalb mit
`harbor.find_child("LanternLight", true, false)` und nicht mit einem festen Pfad ab der Wurzel.

Materialien (nur Farbe, Rauheit, Metall; keine Texturen):
`Stone`, `StoneDark`, `Wood`, `WoodDark`, `WhitePaint`, `RedPaint`, `Roof`, `Glass` (emissiv, Stärke 4),
`Rope`, `Metal`, `Rock`, `Sand`, `Grass`, `Water`.

### Dachs (`badger.glb`, `badger_low.glb`)

```
badger
├─ Armature
│  └─ Skeleton3D
│     ├─ Badger     MeshInstance3D, die Figur
│     └─ Parcel     MeshInstance3D, das Paket (einzeln ausblendbar)
└─ AnimationPlayer  Idle (2,0 s), Walk (1,0 s), Wave (1,5 s)
```

- Die Figur blickt nach **+X**. Ihre rechte Seite mit dem Paket zeigt nach +Z, also zur Kamera.
  `rotation_degrees.y = -90` dreht sie zur Kamera (Vorderansicht), `180` lässt sie nach links laufen
  (dann ist das Paket verdeckt).
- Höhe 1,011 m, Ursprung am Boden zwischen den Füßen.
- `Walk` läuft auf der Stelle. Die Figur mit **0,367 m/s × `speed_scale`** verschieben, dann rutschen die Füße
  nicht (in der Probeszene nachgemessen: Der Standfuß bleibt auf 1 mm genau stehen).
- `Wave` winkt mit der linken Hand. In der Seitenansicht ist sie hinter dem Kopf verdeckt, deshalb vorher zur
  Kamera drehen.
- Materialien: `FurDark`, `FurLight`, `Cap`, `Brass`, `Vest`, `Shirt`, `Scarf`, `Satchel`, `Parcel`, `Nose`,
  `Eye`. Die Low-Fassung hat dieselben Namen, der Code bleibt also gleich.
- UVs bei Hafen und Dachs: Map `UVMap`, **1 UV-Einheit = 1 m** (nicht 0..1). Eine Kacheltextur mit
  `uv1_scale = (1, 1, 1)` erscheint überall gleich groß, zum Beispiel 64 px pro Meter.

## Probeszene `demo/`

Ein eigenständiges Godot-4.7-Projekt ohne Stil, aber mit allen Bausteinen, die ein Stil braucht:

| Datei | Inhalt |
|---|---|
| `project.godot` | 1280×720, Forward+, MSAA 2× |
| `main.tscn` | Kamera, Abendsonne (`DirectionalLight3D` 14° hoch von links vorn, orange, Schatten), `WorldEnvironment` (ProceduralSky in Abendfarben, Tiefennebel 30–700 m, Glow, Tonemapping AgX), Instanzen von Hafen und Dachs, Zusatzlichter unter `Attach` |
| `main.gd` | hängt die Lichter an die Empties, ersetzt `Water` per Name, animiert alles über die aufsummierte Zeit `t` |
| `shaders/water.gdshader` | einfache Dünung als Verschiebung, Kräuselung in der Normale, Farbe aus dem glTF-Material |
| `shaders/beam.gdshader` | additiver Lichtkegel des Leuchtturms |
| `models/` | **Kopien** von `harbor.glb`, `badger.glb`, `badger_low.glb` samt `.import` |

Ablauf der 6 s: Der Dachs läuft ab `WalkStart` mit `Walk` (`speed_scale` 2, also 0,73 m/s) nach rechts, bremst
ab 3,1 s (Tempo und Animation gemeinsam), blendet auf `Idle`, dreht sich zur Kamera, winkt ab 4,05 s (`Wave`)
und steht dann wieder in `Idle`. Dazu schaukeln die Boote, das Wasser bewegt sich, die Laterne flackert
(`FastNoiseLite` mit festem Seed), das Leuchtfeuer dreht sich (`SpotLight3D` und sichtbarer Kegel, die Lampe
blitzt auf, wenn der Strahl zur Kamera zeigt), aus dem Schornstein steigt Rauch (Billboards).

`Attach`-Muster: Jeder Knoten unter `Attach` in `main.tscn` heißt wie ein Ziel im Hafen (`LanternLight`,
`CottageWindow`, `LighthouseLight`). `main.gd` hängt seine Kinder mit `reparent(target, false)` dorthin. Die
lokale Transformation bleibt erhalten. Fehlt ein Ziel, meldet das Skript einen Fehler. So stehen die Lichter
als Text in der Szene und sitzen trotzdem genau an den Empties. Wer `main.tscn` übernimmt, aber ein eigenes
Skript schreibt, muss das Umhängen mitnehmen, sonst bleiben die Lichter und der Lichtkegel am Weltursprung.

Aufnehmen (aus dem Projektordner):

```
.venv/bin/python tools/capture.py shared/3d          # schreibt shared/3d/media/
```

Stand der Prüfung: Import und Lauf ohne `ERROR` und `WARNING`. Zwei Läufe mit `--write-movie` ergaben alle
180 Bilder (6 s) bytegleich. Kamera in Godot nachgemessen: Position, Drehung und fov wie oben. `frames.jpg` und Ausschnitte der
Einzelbilder angesehen: Lauf, Bremsen, Drehung und Winken sind sichtbar, es gibt keine Bildsprünge.

## In die eigene Demo übernehmen

Nur die Modelle:

```
mkdir -p styles/<slug>/demo/models
cp shared/3d/harbor.glb shared/3d/badger.glb shared/3d/badger_low.glb styles/<slug>/demo/models/
godot --headless --path styles/<slug>/demo --import
```

Oder die ganze Probeszene als Ausgangspunkt (ohne den Godot-Cache):

```
rsync -a --exclude .godot shared/3d/demo/ styles/<slug>/demo/
```

Danach `config/name` in `project.godot` anpassen. Geprüft: Die Kopie importiert und läuft ohne Fehler.

In einer Szene instanzieren:

```
[ext_resource type="PackedScene" path="res://models/harbor.glb" id="2_harbor"]
[ext_resource type="PackedScene" path="res://models/badger.glb" id="3_badger"]

[node name="Harbor" parent="." instance=ExtResource("2_harbor")]

[node name="Badger" parent="." instance=ExtResource("3_badger")]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -6, 0, 1.2)
```

oder im Code: `var harbor := (load("res://models/harbor.glb") as PackedScene).instantiate(); add_child(harbor)`.

Animationen vorbereiten (glTF kennt kein Loop-Flag):

```gdscript
var player: AnimationPlayer = $Badger/AnimationPlayer
for a in ["Idle", "Walk"]:
	player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
player.play("Walk")
player.speed_scale = 2.0
# in _process: $Badger.position.x += 0.367 * player.speed_scale * delta
```

## Materialien per Skript nach Namen ersetzen

Jede Fläche trägt das glTF-Material als `StandardMaterial3D` mit `resource_name` = Materialname. Ein Stil
geht alle `MeshInstance3D` durch und setzt Overrides. Das funktioniert beim Hafen wie beim geriggten Dachs, da
auch `Badger` und `Parcel` `MeshInstance3D` sind.

```gdscript
extends Node3D
## Beispiel: Stil über Materialnamen anwenden.

const TOON := preload("res://shaders/toon.gdshader")    # Shader des Stils (Uniforms albedo, emission)

## Feste Ersatzmaterialien für einzelne Namen; alle anderen erzeugt style_material().
var overrides := {
	"Water": preload("res://materials/water.tres"),
}
var _cache := {}    # resource_name -> Material, damit jedes Material nur einmal entsteht


func _ready() -> void:
	apply_style($Harbor)
	apply_style($Badger)


func apply_style(root: Node) -> void:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			mi.set_surface_override_material(i, style_material(src))


func style_material(src: StandardMaterial3D) -> Material:
	var key := src.resource_name
	if not _cache.has(key):
		if overrides.has(key):
			_cache[key] = overrides[key]
		else:
			var m := ShaderMaterial.new()
			m.shader = TOON
			m.set_shader_parameter("albedo", src.albedo_color)
			if src.emission_enabled:    # Glass leuchtet
				m.set_shader_parameter("emission", src.emission * src.emission_energy_multiplier)
			_cache[key] = m
	return _cache[key]
```

Ohne eigenen Shader genügt oft eine angepasste Kopie des glTF-Materials:

```gdscript
var m := src.duplicate() as StandardMaterial3D
m.albedo_texture = preload("res://textures/stone_64.png")
m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
m.uv1_scale = Vector3.ONE    # UVs sind in Metern: eine Textur je Meter
```

Ein Objekt einzeln animieren (zum Beispiel nur die Laterne flackern lassen, obwohl `CottageWindow`,
`LanternGlass` und `LighthouseLamp` dasselbe `Glass` teilen):

```gdscript
var mi := harbor.find_child("LanternGlass", true, false) as MeshInstance3D
var lantern_mat := (mi.mesh.surface_get_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
mi.set_surface_override_material(0, lantern_mat)
# in _process: lantern_mat.emission_energy_multiplier = 4.0 * flicker
```

`replace_material()`, `find_material()` und `unique_material()` in `demo/main.gd` sind fertige Helfer dafür.

## Eigene Varianten exportieren (Blender)

Nur nötig, wenn ein Stil andere Geometrie braucht (Voxel, gröbere Fassung, vorgerendertes Bild). Ausgaben
gehören in den eigenen Ordner. `shared/` wird nicht verändert.

**Bauskripte mit eigenem Ziel.** Die Standardwerte schreiben nach `shared/3d/`. Deshalb immer Ziel, Notizen
und Vorschau mitgeben:

```
# Hafen (identisch zum gemeinsamen, nur woanders hin)
blender -b --factory-startup -P shared/3d/blender/build_harbor.py -- \
    --out styles/<slug>/demo/models/harbor.glb --notes "" --no-preview

# Dachs, Paket links und Winken rechts (schreibt badger.glb und badger_low.glb in den Ordner)
blender -b --factory-startup -P shared/3d/blender/build_badger.py -- \
    --out styles/<slug>/assets/badger_l --parcel-side L --no-preview --no-notes
```

| Skript | Parameter |
|---|---|
| `build_harbor.py` | `--out PATH` (glb), `--notes PATH` (`""` = keine), `--preview-dir DIR`, `--views main,overview,top,side,cottage,boats,lighthouse,props`, `--no-preview`, `--samples N`, `--blend PATH` (.blend zum Nachsehen, nicht einchecken) |
| `build_badger.py` | `--out DIR` (Ordner für beide glb, Notizen und Vorschau), `--parcel-side R\|L`, `--no-preview`, `--no-notes`, `--save-blend PATH` |
| `preview_badger.py` | `--glb PATH`, `--out DIR`, `--prefix NAME`, `--views front,side,back,threequarter,walk,wave,idle` oder `none`, `--walk-frames 0,9,15`, `--size 720x900`, `--samples N`, `--check` (Bodenkontakt und Fußhub messen) |

Beide Bauskripte sind deterministisch. Ein Lauf mit eigenem `--out` ergab ein glb, das Byte für Byte dem
gemeinsamen gleicht.

**Importieren, verändern, exportieren.** Für Geometrie-Varianten des Hafens ist das der kürzeste Weg. Namen,
Empties, Eltern und Materialnamen bleiben erhalten (geprüft mit Blender 5.2 und Godot 4.7.2):

```python
# styles/<slug>/blender/variant.py
# blender -b --factory-startup -P styles/<slug>/blender/variant.py -- shared/3d/harbor.glb styles/<slug>/demo/models/harbor_x.glb
import sys, bpy
src, out = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)          # zurück in Blender-Achsen (Z oben)
for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.name != "Sea":
        pass                                      # hier verändern: Modifier, Materialfarben …
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True, export_apply=True,
                          export_cameras=False, export_lights=False)
```

**Vorgerenderte Hintergründe.** Die Hauptkamera in Blender: Position `(-1.8, -14.5, 3.4)`,
`rotation_euler = (87°, 0°, 0°)`, `sensor_fit = "VERTICAL"`, `sensor_height = 24`,
`lens = 12 / tan(21°)` (= 31,26 mm), clip 0,1 bis 3000. Ein Bild mit diesen Werten deckt sich mit der
Godot-Kamera. So kann eine 3D-Figur vor einem gerenderten Bild stehen. `setup_preview()` und `add_camera()` in
`build_harbor.py` zeigen den Aufbau mit Himmel und Lichtern.

Den Dachs nicht über Import und Export umbauen, sondern `build_badger.py` nutzen. Ein Durchlauf durch den
Blender-Import funktioniert zwar: Knochen- und Animationsnamen bleiben, und Godot spielt die Animationen. Die
Knochenpositionen weichen danach aber um bis zu 4 mm ab, und Blender legt ein zusätzliches Objekt `Icosphere`
für die Knochenanzeige an. Das wird nicht exportiert.

Nach einem Neubau der gemeinsamen glb die Kopien in `demo/models/` erneuern
(`cp shared/3d/*.glb shared/3d/demo/models/`). Godot liest nur Dateien innerhalb des Projektordners.

## Bekannte Fallstricke

1. **Schleifen fehlen.** glTF hat kein Loop-Flag. Godot importiert `Idle`, `Walk` und `Wave` mit `LOOP_NONE`,
   deshalb `loop_mode` im Code setzen (siehe oben).
2. **Füße rutschen**, wenn Verschiebung und `speed_scale` nicht zusammenpassen: v = 0,367 m/s × `speed_scale`.
   Beim Bremsen beide gemeinsam senken. `speed_scale` des `AnimationPlayer` beschleunigt auch Überblendungen,
   deshalb vor `play("Idle", 0.3)` wieder auf 1 setzen.
3. **Geteilte Materialien.** Ein Material aus dem glb ist eine gemeinsame Ressource für alle Flächen und alle
   Instanzen. Wer `surface_get_material(i)` direkt verändert, verändert alle Nutzer. Für Einzelanimationen das
   Material duplizieren und als Override setzen.
4. **Alle glTF-Materialien sind doppelseitig** (Blender-Standard: Backface Culling aus). In Godot ist deshalb
   `cull_mode = Disabled`. Eigene Materialien dürfen `cull_back` nutzen: Ein Test mit `CULL_BACK` auf allen
   Materialien zeigte aus fünf Ansichten (Hauptkamera, Übersicht, von hinten, bodennah, Nahaufnahme Dachs) keine
   sichtbaren Löcher (höchstens 7 Pixel Unterschied je Bild).
5. **Licht im Glas.** Die Lichter sitzen in geschlossenen Glaskörpern (`LanternGlass`, `LighthouseLamp`). Wirft
   ein solches Licht Schatten, sperrt das Glas es ein. Die Probeszene schaltet bei den Glasobjekten
   `cast_shadow` aus, ihre Punktlichter werfen keine Schatten.
6. **Wasser.** `Sea` ist ein flaches Gitter mit AABB-Höhe 0. Wer es im Shader anhebt, setzt
   `extra_cull_margin` (die Probeszene: 1 m). Das Gitter läuft unter Kai und Gelände durch, der Kai liegt
   0,8 m über dem Wasser. Wellen bleiben deshalb deutlich unter 0,8 m. Außerhalb des Hafens ist das Gitter grob
   (Zellen bis zu Hunderte Meter): Verschiebung dort ausblenden, Wellen über Weltkoordinaten statt über UVs
   rechnen. Das Meer endet 900 m hinter dem Kai; Nebel bis höchstens 700 m oder ein Himmel in Wasserfarbe am
   Horizont verdeckt die Kante.
7. **Shader-Zeit.** Für reproduzierbare Aufnahmen die Zeit als Uniform aus dem Skript übergeben (aufsummiertes
   `delta`), nicht `TIME`.
8. **Schwarze Punkte mit MSAA.** Varyings werden an Dreieckskanten extrapoliert. `pow()` auf einen leicht
   negativen Wert ergibt NaN, das als schwarzer Pixel erscheint. In der Probeszene war das ein Ring aus Punkten
   am Ende des Leuchtturmkegels. Werte vor `pow()` mit `clamp()` begrenzen.
9. **Andere Seitenverhältnisse.** Keep Height hält den vertikalen Bildwinkel fest, schmalere Bilder verlieren
   die Ränder. Auf Höhe des Häuschens (14 m vor der Kamera) ist bei 16:9 x von −11,4 bis 7,8 zu sehen, bei 16:10
   (320×200) −10,4 bis 6,8 (die Kisten werden angeschnitten), bei 4:3 nur −9,0 bis 5,4 (vom Häuschen bleibt ein Teil, die
   Kisten fehlen ganz). Für 4:3 lieber ein 16:9-Bild mit Rand oder einen eigenen, im `style.json` begründeten
   Ausschnitt wählen.
10. **Kleine Figur.** In der Totale ist der Dachs etwa 71 px hoch bei 720 px Bildhöhe (bei 180 px etwa 18 px).
    Feinheiten wie Knöpfe, Schnur und Augenglanz verschwinden bei niedriger Auflösung. Für Retro-Stile
    `badger_low.glb` nehmen.
11. **Winken in der Seitenansicht** ist unsichtbar. Den Dachs vorher mit `rotation.y = -PI / 2` zur Kamera
    drehen.
12. **Automatische LODs.** Godot erzeugt beim Import LOD-Stufen (`meshes/generate_lods=true` in der
    `.import`-Datei), der Dachs hat drei. Bei der Standardschwelle von 1 px ist der Unterschied nicht zu sehen.
    Wer Vertex-Snapping oder Flat Shading nutzt und feste Geometrie braucht, setzt in der `.import`-Datei
    `meshes/generate_lods=false` und importiert neu.
13. **Namensendungen.** Godot wertet Endungen wie `-col`, `-noimp`, `-rigid` in Objektnamen als
    Importanweisungen aus (`nodes/use_name_suffixes=true`). In eigenen Varianten solche Namen vermeiden.
14. **Varianten überschreiben `shared/`**, wenn bei den Bauskripten `--notes`/`--no-notes` und
    `--preview-dir`/`--no-preview` fehlen. Notizen und Vorschaubilder landen sonst in `shared/3d/`.
15. **Remesh verliert Materialien.** Ein Remesh-Modifier im Blocks-Modus (Voxel) behält nur das erste
    Material eines Objekts: Das Häuschen wurde im Test komplett `Stone`. Die Materialien danach neu zuweisen,
    zum Beispiel nach der nächstgelegenen Fläche des Originals.
16. **Kopien veralten.** `demo/models/` und die Ordner der Stile enthalten Kopien. Nach einem Neubau der
    gemeinsamen glb neu kopieren und mit `cmp` prüfen.
