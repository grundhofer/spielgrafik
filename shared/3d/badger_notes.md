# Dachs-Kurier `badger.glb`: Notizen

Geriggte, animierte Figur des Dachs-Kuriers (Referenz: `shared/badger/master_sheet.png`, vorn/Seite/hinten) für alle 3D-Stile. Stile ändern Materialien, Shader, Auflösung und Nachbearbeitung, nicht Geometrie, Knochen oder Animationen. Diese Datei erzeugt das Bauskript bei jedem Lauf; alle Zahlen kommen direkt aus dem Skript bzw. aus der Prüfung der exportierten Dateien.

## Bauen

```
blender -b --factory-startup -P shared/3d/blender/build_badger.py --
blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --no-preview
blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --parcel-side L --out /tmp/badger_l
blender -b --factory-startup -P shared/3d/blender/preview_badger.py -- --glb shared/3d/badger.glb \
    --views front,side,back,threequarter,walk,wave,idle --check
```

Ausgaben: `badger.glb`, `badger_low.glb`, diese Notizen und die Vorschaubilder `preview_badger_*.png`. Die Figur entsteht vollständig im Skript aus Grundformen (Ring-Lofts, Ellipsoide, Röhren entlang Kurven, gefaste Quader), ohne Zufall und ohne .blend-Vorlage; ein Neubau ergibt bytegleiche GLB-Dateien. Die Vorschaubilder rendert `preview_badger.py` mit EEVEE aus den **exportierten** GLBs, sie zeigen also genau das, was Godot bekommt. Laufzeit dieses Laufs 4 s (mit Vorschau und Prüfung), Blender 5.2 LTS.

## Ausrichtung und Maße

- 1 Einheit = 1 m, glTF mit +Y oben. Umrechnung wie bei `harbor.glb`: **Godot (x, y, z) = Blender (x, z, −y)**.
- Die Figur **blickt nach +X** (läuft nach rechts). Ihre rechte Körperseite zeigt nach **+Z**, also zur Hafenkamera (Kamera auf +Z, Blick nach −Z); die linke Seite zeigt nach −Z.
- Ursprung = Knochen `root` auf dem Boden (y = 0) zwischen den Füßen. Fußsohlen bei y = 0,003.
- Höhe 1,011 m (Mützendeckel), Länge 0,51 m (hinten Tasche/Schwanz bis Nasenspitze, x -0,24 bis 0,27), Breite 0,70 m (z -0,34 bis 0,36, Ellbogen und Paket).
- Augenhöhe 0,84 m, Nasenspitze bei x = 0,27. Bauch am breitesten (0,47 m) auf 0,34 m Höhe. Hüftgelenk auf 0,27 m.
- Im Hafen auf den Laufweg setzen: `position = Vector3(x, 0, 1.2)`, keine Drehung nötig (`WalkStart` → `WalkEnd` ist +X). Nach links laufen: `rotation_degrees.y = 180` (dann ist die linke Seite und nicht das Paket zur Kamera gewandt; siehe `--parcel-side`).

## Paketseite (Entscheidung)

Gebaut ist die Fassung `--parcel-side R`: Paket unter dem **rechten** Arm, gewinkt wird mit der **linken** Hand. Tasche hinten an der Hüfte der Paketseite, Riemen über die Schulter der freien Seite, ein Schalende vorn auf der freien Seite, eines hinten auf der Paketseite.

Grund: Das Referenzblatt zeigt das Paket in allen drei Ansichten unter dem **rechten** Arm (vorn: im Bild links; Seitenansicht nach rechts blickend: auf der zugewandten Seite; hinten: im Bild rechts). Wer nach rechts läuft, wendet der Kamera die rechte Seite zu; so ist das Paket in der Hafenansicht sichtbar wie im gemalten Laufzyklus `shared/badger/walk_painted.png`. Der Bauauftrag nannte den linken Arm; damit läge das Paket in der Hafenansicht hinter dem Körper. Wer die linke Fassung braucht: `--parcel-side L` spiegelt Paket, Tasche, Riemen, Schalenden und Winkarm (Knochen bleiben gleich). Abwägung: Mit `R` ist in der Seitenansicht das Paket zu sehen, die winkende Hand aber verdeckt; mit `L` ist es umgekehrt.

## Knoten in Godot

```
badger (Node3D)
├─ Armature (Node3D)
│  └─ Skeleton3D
│     ├─ Badger   (MeshInstance3D, Figur)
│     └─ Parcel   (MeshInstance3D, Paket; einzeln ausblendbar)
└─ AnimationPlayer   (Idle, Walk, Wave)
```

`badger_low.glb` hat denselben Aufbau, dieselben Knochen und dieselben Animationen.

## Knochen

Positionen in Godot-Koordinaten (Meter, Ruhepose). Namen mit `.L`/`.R` = linke/rechte Körperseite der Figur.

| Knochen | Eltern | Kopf | Spitze | bewegt |
|---|---|---|---|---|
| `root` | – | `(0.000, 0.000, 0.000)` | `(0.120, 0.000, 0.000)` | Ursprung am Boden zwischen den Füßen, zeigt nach vorn; ohne Gewichte, in allen Animationen in Ruhe |
| `hips` | root | `(0.000, 0.285, 0.000)` | `(0.000, 0.400, 0.000)` | Becken und Bauch unten; Wippen, Seitwärtsschaukeln und Drehen im Lauf |
| `spine` | hips | `(0.000, 0.400, 0.000)` | `(0.000, 0.520, 0.000)` | unterer Rücken, Bauch |
| `chest` | spine | `(0.000, 0.520, 0.000)` | `(0.000, 0.655, 0.000)` | Brust, Schultern, Schalwicklung unten, vorderes Schalende |
| `neck` | chest | `(0.000, 0.655, 0.000)` | `(0.030, 0.750, 0.000)` | Hals, Schalwicklung oben |
| `head` | neck | `(0.030, 0.750, 0.000)` | `(0.030, 0.950, 0.000)` | Kopf mit Mütze, Ohren, Augen, Nase, Mund (starr) |
| `upper_arm.L` | chest | `(0.000, 0.605, -0.195)` | `(0.005, 0.453, -0.272)` | Oberarm mit Hemdsärmel |
| `forearm.L` | upper_arm.L | `(0.005, 0.453, -0.272)` | `(0.022, 0.310, -0.286)` | Unterarm |
| `hand.L` | forearm.L | `(0.022, 0.310, -0.286)` | `(0.030, 0.236, -0.288)` | Pfote |
| `upper_arm.R` | chest | `(0.000, 0.605, 0.195)` | `(-0.051, 0.482, 0.301)` | Oberarm mit Hemdsärmel |
| `forearm.R` | upper_arm.R | `(-0.051, 0.482, 0.301)` | `(0.065, 0.395, 0.301)` | Unterarm |
| `hand.R` | forearm.R | `(0.065, 0.395, 0.301)` | `(0.114, 0.338, 0.297)` | Pfote; hält das Paket (Mesh `Parcel` hängt zu 100 % hier) |
| `thigh.L` | hips | `(0.000, 0.270, -0.110)` | `(0.022, 0.165, -0.120)` | Oberschenkel |
| `shin.L` | thigh.L | `(0.022, 0.165, -0.120)` | `(0.000, 0.065, -0.125)` | Unterschenkel |
| `foot.L` | shin.L | `(0.000, 0.065, -0.125)` | `(0.120, 0.020, -0.125)` | Fuß (Pfote mit Krallen) |
| `thigh.R` | hips | `(0.000, 0.270, 0.110)` | `(0.022, 0.165, 0.120)` | Oberschenkel |
| `shin.R` | thigh.R | `(0.022, 0.165, 0.120)` | `(0.000, 0.065, 0.125)` | Unterschenkel |
| `foot.R` | shin.R | `(0.000, 0.065, 0.125)` | `(0.120, 0.020, 0.125)` | Fuß (Pfote mit Krallen) |
| `scarf_1` | chest | `(-0.116, 0.664, 0.068)` | `(-0.158, 0.551, 0.089)` | hinteres Schalende, obere Hälfte |
| `scarf_2` | scarf_1 | `(-0.158, 0.551, 0.089)` | `(-0.170, 0.442, 0.097)` | hinteres Schalende, untere Hälfte |
| `tail` | hips | `(-0.180, 0.300, 0.000)` | `(-0.180, 0.165, 0.000)` | Schwanz |

## Animationen

| Name | Länge | Bilder bei 30 fps | Schleife | Inhalt |
|---|---|---|---|---|
| `Idle` | 2,0 s | 60 | ja | Atmen (Brust hebt und senkt sich, Schultern gehen mit), leichte Gewichtsverlagerung, Kopf nickt und schaut minimal umher, Schwanz und hinteres Schalende wippen. Füße stehen fest (IK). |
| `Walk` | 1,0 s | 30 | ja | Laufzyklus auf der Stelle, zwei Schritte. Ferse setzt auf, Fuß rollt ab, Zehen drücken ab, Schwungbein hebt den Fuß bis 7,2 cm. Becken wippt, schaukelt und dreht sich, Oberkörper dreht gegen, freier Arm schwingt gegen das Bein, Paketarm bleibt fast ruhig, hinteres Schalende fliegt nach hinten und schwingt, Schwanz wedelt. |
| `Wave` | 1,5 s | 45 | nein | Winkt mit der freien (linken) Hand: Arm hoch (0–0,38 s), zwei Mal hin und her (bis 1,12 s), wieder ab. Kopf neigt sich zur Hand, Oberkörper lehnt leicht zur anderen Seite. Beginnt und endet in der Ruhepose, Füße fest. |

- **Laufgeschwindigkeit 0,367 m/s.** Die Figur in Godot mit dieser Geschwindigkeit nach +X bewegen, dann rutschen die Füße nicht (bei `speed_scale` s entsprechend v · s). Kein Root-Motion: `root` bleibt in allen Animationen in Ruhe.
- Phasen im `Walk`: 0,00 s linke Ferse setzt auf · 0,30 s rechter Fuß schwingt durch (höchster Punkt) · 0,50 s rechte Ferse setzt auf · 0,80 s linker Fuß schwingt durch. Das letzte Bild gleicht dem ersten, die Schleife ist nahtlos.
- **Schleife einschalten:** glTF kennt kein Loop-Flag, Godot importiert alle drei Animationen mit `LOOP_NONE`. Entweder in den erweiterten Importeinstellungen je Animation „Loop Mode“ setzen oder im Code:

```gdscript
var badger: Node3D = load("res://badger.glb").instantiate()
add_child(badger)
var player: AnimationPlayer = badger.get_node("AnimationPlayer")
for n in ["Idle", "Walk"]:
    player.get_animation(n).loop_mode = Animation.LOOP_LINEAR
player.play("Walk")
# in _process: badger.position.x += 0.367 * delta
```

## Materialien

Stilneutral wie beim Hafen: nur Grundfarbe (sRGB), Rauheit, Metall, keine Texturen. Die Namen bleiben beim Import erhalten (`resource_name`), Stile erkennen und ersetzen sie daran.

| Material | Farbe | Rauheit | Metall | verwendet für |
|---|---|---:|---:|---|
| `FurDark` | #4A3F3B | 0,90 | 0,0 | Fell dunkel: Körper, Beine, Unterarme, Pfoten, Augenstreifen, Ohrinneres |
| `FurLight` | #F0E2C8 | 0,90 | 0,0 | Fell hell: Gesichtsstreifen, Wangen, Bauch, Ohrränder, Schwanz |
| `Cap` | #4C5530 | 0,80 | 0,0 | Schirmmütze (Kopf und Schirm) |
| `Brass` | #C08D35 | 0,35 | 1,0 | Messing: Mützenknöpfe, Westenknöpfe, Taschenschnalle |
| `Vest` | #59613A | 0,80 | 0,0 | Weste mit Taschenklappen und Rückenriegel |
| `Shirt` | #EDD9B8 | 0,80 | 0,0 | Hemd (hochgekrempelte Ärmel, Ausschnitt) und Paketschnur |
| `Scarf` | #A8242A | 0,90 | 0,0 | Strickschal |
| `Satchel` | #6E3A25 | 0,60 | 0,0 | Leder: Umhängetasche, Riemen, Mützenband |
| `Parcel` | #C08B57 | 0,85 | 0,0 | Packpapier des Pakets |
| `Nose` | #2A201D | 0,35 | 0,0 | Nase, Mund, Krallen |
| `Eye` | #2B170D | 0,15 | 0,0 | Augen |

Hinweise: Das Mützenband und der Riemen nutzen `Satchel` (gleiches Leder). Die Paketschnur nutzt `Shirt`, der Glanzpunkt in den Augen `FurLight`. Die Nase ist in der hohen Fassung eine eigene Kugel, in der Low-Fassung die Schnauzenspitze.

## Meshes und Dreiecke

| Datei | Mesh | Dreiecke | Punkte (Blender) | Materialien |
|---|---|---:|---:|---|
| `badger.glb` | `Badger` | 7032 | 3601 | FurDark, FurLight, Cap, Brass, Vest, Shirt, Scarf, Satchel, Nose, Eye |
| `badger.glb` | `Parcel` | 316 | 166 | Shirt, Parcel |
| `badger_low.glb` | `Badger` | 864 | 472 | FurDark, FurLight, Cap, Brass, Vest, Shirt, Scarf, Satchel, Nose, Eye |
| `badger_low.glb` | `Parcel` | 12 | 8 | Parcel |

`badger.glb` zusammen: **7348 Dreiecke**.

`badger_low.glb` zusammen: **876 Dreiecke**.

Die Low-Fassung hat dieselbe Silhouette mit 4–8 Segmenten je Ring; es fehlen Mund, Westenknöpfe, Taschenklappen, Rückenriegel, Paketschnur, Krallen und Glanzpunkte, der Schal hat eine statt zwei Wicklungen, die Augen sind etwas größer.

## Gewichte

- Automatische Gewichte (Bone Heat) je Körperteil, jeweils nur mit den Knochen, die das Teil bewegen sollen: Rumpf `hips, spine, chest, neck`; Bein `thigh, shin, foot`; Fuß `shin, foot`; Arm `upper_arm, forearm, hand`; Schwanz `hips, tail`. So zieht ein schwingender Arm nicht an der Weste.
- Fußsohlen (unter 2,5 cm) hängen ganz an `foot`, bis 5 cm übergeblendet: Der aufgesetzte Fuß bleibt exakt am Boden.
- Starr: Kopf samt Mütze, Ohren, Augen, Nase, Mund → `head`; Krallen → `foot`; vorderes Schalende → `chest`; Paket → `hand.R`.
- Schalwicklungen nach Höhe von `chest` nach `neck`; hinteres Schalende nach Höhe `chest` → `scarf_1` → `scarf_2`.
- Riemen, Westenknöpfe, Taschenklappen: Gewichte vom nächstgelegenen Rumpfpunkt übernommen. Die Tasche bekommt für alle Punkte die Gewichte an ihrem Mittelpunkt, damit sie starr bleibt.
- Höchstens 4 Einflüsse je Punkt, normiert.

## UVs und Normalen

- UV-Map `UVMap` aus Smart UV Project (66°), danach **1 UV-Einheit = 1 m** wie bei `harbor.glb` (Kacheltexturen erscheinen auf Figur und Hafen gleich groß). Die UVs liegen deshalb nicht in 0..1. Die Inseln überlappen nicht und werden in fester Reihenfolge angeordnet, ein Neubau ergibt dieselben UVs (eine aufgemalte Textur bleibt gültig).
- Weiche Normalen. Harte Kanten ab 40° bei Tasche, Paket, Schnur; ab 50° am Mützenschirm; ab 60° bei Riemen und Westenklappen.
- Jedes Teil ist eine geschlossene Hülle; Arme, Beine, Schwanz, Kopf und Schal stecken im Rumpf, statt mit ihm verschmolzen zu sein. Für Umriss-Shader (umgedrehte Hülle) und Flat-Shading unproblematisch.
- Fellzeichnung, Weste und Bauch sind Materialgrenzen auf Kanten (die Ringpunkte liegen genau auf den Streifengrenzen), daher saubere Kanten ohne Textur. Die Weste ist 7 mm aufgesetzt (echte Kante am Saum).

## Prüfung

Werte aus `preview_badger.py --check` (ausgewertet am verformten Mesh, jedes Bild der Animation):

| Datei | tiefster Punkt Idle | tiefster Punkt Walk | tiefster Punkt Wave | Fußhub Walk L / R |
|---|---:|---:|---:|---:|
| `badger.glb` | 3,0 mm | 3,0 mm | 3,0 mm | 7,2 / 7,2 cm |
| `badger_low.glb` | 3,0 mm | 3,0 mm | 3,0 mm | 7,3 / 7,3 cm |

Kein Punkt geht unter den Boden (alle Werte ≥ 0). Die Knöchelziele des Laufzyklus sind alle erreichbar (IK-Begrenzungen: 0).

Zusätzlich von Hand geprüft: Import beider Dateien in Godot 4.7.2 (headless, keine Fehler; Knochen, Animationslängen, Material- und Knotennamen wie oben; Paket auf der +Z-Seite) und Sichtprüfung der Vorschaubilder gegen das Referenzblatt.

Vorschaubilder (EEVEE, aus den GLBs): `preview_badger_front.png`, `preview_badger_side.png`, `preview_badger_back.png`, `preview_badger_walk_1.png`, `preview_badger_walk_2.png`, `preview_badger_walk_3.png`, `preview_badger_wave.png`, `preview_badger_low_front.png`, `preview_badger_low_side.png`. `walk_1..3` = Seitenansicht wie die Hafenkamera bei 0,00 s, 0,30 s und 0,50 s.

## Hinweise für Stile

- Materialien per Name tauschen (wie beim Hafen): alle `MeshInstance3D` durchgehen, `mesh.surface_get_material(i).resource_name` prüfen, `set_surface_override_material(i, …)` setzen.
- Paket ausblenden (z. B. nach der Übergabe): `badger.get_node("Armature/Skeleton3D/Parcel").visible = false`.
- PS1/N64: `badger_low.glb` mit niedriger Auflösung und Nearest-Filter; gleiche Knochen, Animationen und Materialnamen, Code bleibt gleich.
- Pixel-3D, 1-Bit, Toon: geschlossene Hüllen und Materialgrenzen auf Kanten funktionieren mit Umriss- und Stufen-Shadern; Farben je Material ersetzen.
- Animationen überblenden: `Wave` beginnt und endet in der Ruhepose, `Idle` liegt nahe daran; `player.play("Wave", 0.2)` blendet weich ein.
- Winken in der Hafenszene: Die Seitenansicht verdeckt den Winkarm. Figur zur Kamera drehen (`rotation_degrees.y = -90`, Blick nach +Z), dann `Wave` spielen. Das ergibt die Vorderansicht des Referenzblatts mit dem Paket im Bild links.

## Grenzen

- In der reinen Seitenansicht (Hafenkamera) ist die winkende linke Hand ganz hinter dem Kopf verborgen. `Wave` ist für Ansichten von vorn oder schräg vorn gebaut; in der Hafenszene die Figur vorher zur Kamera drehen (siehe Hinweise).
- Das Paket liegt ein paar Zentimeter im Bauch (angedrückt) und folgt der Hand; im Lauf verschiebt es sich mit dem Paketarm um etwa 1–2 cm gegen den Körper.
- Keine Gesichtsanimation (kein Blinzeln, kein Mund), keine Fingerknochen; die Pfoten sind geschlossene Formen.
- Nur das hintere Schalende hat Knochen; das vordere Ende hängt fest an der Brust.
- Arme und Beine stecken als eigene Hüllen im Rumpf. Bei starkem Beugen (Arm über Kopf beim Winken, Beinschwung) sieht man an Schulter und Hüfte die Durchdringungskante; bei den gezeigten Animationen liegt sie im Ärmel bzw. unter dem Bauch.
- Fell nur als Fläche ohne Fellkanten; die Strickstruktur des Schals ist nur durch Rippen in der Geometrie angedeutet (hohe Fassung). Feinheiten wie Taschenklappen, Knöpfe und Schnur sind klein und verschwinden bei niedriger Auflösung.
