# Hafenszene `harbor.glb`: Notizen

Gemeinsame, stilneutrale 3D-Grundszene „Hafen von Lornholm“ (nach `data/motif.json`) für alle 3D-Stile. Stile ändern Materialien, Shader, Auflösung und Nachbearbeitung, nicht die Geometrie.
Diese Datei erzeugt das Bauskript bei jedem Lauf; alle Zahlen kommen direkt aus dem Skript.

## Bauen

```
blender -b --factory-startup -P shared/3d/blender/build_harbor.py --
blender -b --factory-startup -P shared/3d/blender/build_harbor.py -- --no-preview
blender -b --factory-startup -P shared/3d/blender/build_harbor.py -- \
    --views main,overview,top,side,cottage,boats,lighthouse,props --preview-dir /tmp/harbor
```

Ausgaben: `harbor.glb`, diese Notizen und die Vorschaubilder `preview_harbor_main.png` (Hauptkamera) und `preview_harbor_overview.png` (Übersicht). Weitere Ansichten über `--views`. Deterministisch (feste Seeds; das glb ist bei gleichem Skript Byte für Byte gleich), Laufzeit wenige Sekunden, Blender 5.2 LTS, Vorschau mit EEVEE.

Geprüft in Godot 4.7.2: glb importiert ohne Fehler, Knoten- und Materialnamen bleiben erhalten, Empties werden zu `Node3D`, und das Bild der Hauptkamera mit den Werten unten deckt sich mit `preview_harbor_main.png`.

## Achsen und Maßstab

- 1 Einheit = 1 m. Export als glTF mit +Y oben.
- Umrechnung: **Godot (x, y, z) = Blender (x, z, −y)**. Die Godot-Kamera blickt entlang −Z auf die Szene; „vorn“ (zur Kamera) ist +Z, „hinten“ (Meer, Leuchtturm) ist −Z.
- Kai entlang X. Kaioberfläche (Pflaster) bei y = 0. Wasserlinie bei y = -0,80. Meeresboden und Mauerunterkante bei y = -2,60.
- Laufweg des Dachses: y = 0, z = 1,20, x von -6 bis +2 (Empties `WalkStart`, `WalkEnd`). Pflaster reicht nach vorn bis z = 8; die Kaikante zum Wasser liegt bei z = -1,00 (Kantensteine ab z = -0,38).
- Links (x < −6,6) steht das Häuschen, in der Mitte liegt das Hafenbecken mit Steg (x 2,65 bis 4,25) und Booten, rechts hinten die Felsnase mit dem Leuchtturm, dahinter offenes Meer mit fernen Inseln.
- Kein Himmel, keine Lichter, keine Kameras im glb; das macht Godot.

## Hauptkamera

| | Godot | Blender |
|---|---|---|
| Position | `(-1.80, 3.40, 14.50)` | `(-1.80, -14.50, 3.40)` |
| Rotation | `rotation_degrees = (-3.0, 0.0, 0.0)` | rotation_euler XYZ = (87.0°, 0°, 0.0°) |
| Blickrichtung | −Z, 3° nach unten geneigt | +Y, 3° nach unten |
| Bildwinkel | `fov = 42.0` (vertikal; `keep_aspect` = Keep Height, Standard) | Sensor vertikal, 42,0° |
| horizontal bei 16:9 | 68,6° | 68,6° |
| near / far | 0,1 / 3000 | 0,1 / 3000 |

Bildaufbau bei 1280×720: Kai mit Laufweg im unteren Drittel, Häuschen links, Boote und Steg in der Mitte, Laterne und Kisten rechts, Leuchtturm rechts oben (Spitze etwa 3° bzw. 55 px unter dem oberen Bildrand), Horizont etwa 50 px über der Bildmitte.

Übersicht (nur Vorschau): Godot-Position `(-26.00, 25.00, 30.00)`, Blick auf `(2.00, 0.00, -9.00)`, fov 42.

## Objekte

Knotennamen in Godot = Objektnamen. Ursprung in Godot-Weltkoordinaten. Kinder hängen am genannten Elternknoten.

| Objekt | Eltern | Ursprung (Godot) | Dreiecke | Materialien | Inhalt |
|---|---|---|---:|---|---|
| `Barrel1` | – | `(-5.25, 0.00, -0.15)` | 308 | Wood, Metal | Fass |
| `Barrel2` | – | `(-4.55, 0.00, -0.62)` | 308 | Wood, Metal | Fass |
| `BoatA` | – | `(0.05, -0.80, -6.10)` | 1012 | RedPaint, WhitePaint, Wood, WoodDark, Metal | Fischerboot mit Ruderhaus (weiß/rot); Ursprung an der Wasserlinie, Bug lokal +X |
| `BoatB` | – | `(6.75, -0.80, -6.40)` | 1096 | WhitePaint, RedPaint, Wood, WoodDark, Rope | offenes Fischerboot mit Mast (rot/weiß); Ursprung an der Wasserlinie, Bug lokal +X |
| `Bollards` | – | `(0.00, 0.00, 0.00)` | 468 | Metal | drei eiserne Poller an der Kaikante |
| `Cottage` | – | `(-8.40, 0.00, -1.00)` | 1006 | Stone, StoneDark, Roof, WoodDark, Wood, WhitePaint, RedPaint | Hafenmeisterhäuschen aus Stein: Dach, Tür, Klappläden, Schornstein |
| `CottageWindow` | Cottage | `(-9.20, 1.45, 0.52)` | 24 | Glass | Fensterglas (Front- und Seitenfenster), emissiv |
| `CrateStack` | – | `(6.55, 0.00, 0.20)` | 624 | Wood, WoodDark | Kistenstapel (drei gestapelt, eine daneben) |
| `Headland` | – | `(0.00, 0.00, 0.00)` | 998 | Sand, Rock, Grass | Felsnase rechts mit Plateau für den Leuchtturm |
| `IslandsFar` | – | `(0.00, 0.00, 0.00)` | 262 | Sand, Rock, Grass | ferne Inseln am Horizont (185 bis 320 m hinter dem Kai) |
| `Jetty` | – | `(0.00, 0.00, 0.00)` | 730 | Wood, WoodDark | Holzsteg: Planken, Träger, Pfähle, zwei Paar Festmachpfähle |
| `LanternGlass` | LanternPost | `(4.10, 1.79, -0.12)` | 12 | Glass | Laternenglas, emissiv |
| `LanternPost` | – | `(4.60, 0.00, -0.12)` | 322 | StoneDark, WoodDark, Metal | Holzpfahl mit Ausleger und eiserner Laterne |
| `Lighthouse` | – | `(10.20, 2.80, -25.60)` | 1674 | StoneDark, WhitePaint, RedPaint, Metal, WoodDark | Leuchtturm: Sockel, Turm mit rotem Band, Galerie, Geländer, Laternendach |
| `LighthouseLamp` | Lighthouse | `(10.20, 12.58, -25.60)` | 44 | Glass | Verglasung des Laternenhauses = Lampe, emissiv; Ursprung im Lichtzentrum |
| `Quay` | – | `(0.00, 0.00, 0.00)` | 3070 | StoneDark, Stone | Steinkai: Mauern, Fugenfläche, Pflaster, Kantensteine |
| `RocksSea` | – | `(0.00, 0.00, 0.00)` | 640 | Rock | Felsbrocken im Wasser |
| `RopeCoil` | – | `(1.05, 0.00, 0.05)` | 566 | Rope | Taurolle |
| `Sea` | – | `(0.00, -0.80, 0.00)` | 3200 | Water | Meeresgitter für Wellen-Shader, Ursprung auf der Wasserlinie |
| `WestHill` | – | `(0.00, 0.00, 0.00)` | 1568 | Sand, Rock, Grass | Insel links mit Hügel hinter dem Häuschen, schließt bündig an den Kai an |
| **Summe** | | | **17932** | | |

`Sea` hat 40 × 40 Zellen: 1,5-m-Raster im Hafen (x −21 bis 21, z −33 bis 10,5), nach außen geometrisch gröber bis 700 m seitlich und 900 m nach hinten, damit das Wasser bis zum Horizont reicht. Es läuft unter Kai und Gelände durch.

## Empties

| Empty | Eltern | Position (Godot, Welt) | Zweck |
|---|---|---|---|
| `ChimneySmoke` | Cottage | `(-9.58, 4.90, -1.35)` | Austritt des Rauchs über dem Schornstein (Partikel) |
| `LanternLight` | LanternPost | `(4.10, 1.79, -0.12)` | Mitte der Laterne (OmniLight3D zum Flackern) |
| `LighthouseLight` | Lighthouse | `(10.20, 12.58, -25.60)` | Lichtzentrum des Leuchtturms (Strahl, Licht, Blinken) |
| `WalkEnd` | – | `(2.00, 0.00, 1.20)` | Laufweg des Dachses: Ende |
| `WalkStart` | – | `(-6.00, 0.00, 1.20)` | Laufweg des Dachses: Start |

## Materialien

Stilneutral: nur Grundfarbe (sRGB), Rauheit, Metall, keine Texturen. Die Namen bleiben beim Import erhalten (`resource_name` der `StandardMaterial3D`), Stile erkennen und ersetzen sie daran.

| Material | Farbe | Rauheit | Metall | Emission | Verwendet in |
|---|---|---:|---:|---|---|
| `Stone` | #8C877D | 0,90 | 0,0 | – | Cottage, Quay |
| `StoneDark` | #5A5650 | 0,90 | 0,0 | – | Cottage, LanternPost, Lighthouse, Quay |
| `Wood` | #8E6440 | 0,80 | 0,0 | – | Barrel1, Barrel2, BoatA, BoatB, Cottage, CrateStack, Jetty |
| `WoodDark` | #4E3726 | 0,85 | 0,0 | – | BoatA, BoatB, Cottage, CrateStack, Jetty, LanternPost, Lighthouse |
| `WhitePaint` | #E8E4DA | 0,60 | 0,0 | – | BoatA, BoatB, Cottage, Lighthouse |
| `RedPaint` | #B02A22 | 0,55 | 0,0 | – | BoatA, BoatB, Cottage, Lighthouse |
| `Roof` | #4A5361 | 0,80 | 0,0 | – | Cottage |
| `Glass` | #FFD27A | 0,20 | 0,0 | #FFC060, Stärke 4 | CottageWindow, LanternGlass, LighthouseLamp |
| `Rope` | #BFA77A | 0,95 | 0,0 | – | BoatB, RopeCoil |
| `Metal` | #3C3D40 | 0,50 | 0,7 | – | Barrel1, Barrel2, BoatA, Bollards, LanternPost, Lighthouse |
| `Rock` | #6E6A64 | 0,95 | 0,0 | – | Headland, IslandsFar, RocksSea, WestHill |
| `Sand` | #C9B48A | 1,00 | 0,0 | – | Headland, IslandsFar, WestHill |
| `Grass` | #6E8048 | 1,00 | 0,0 | – | Headland, IslandsFar, WestHill |
| `Water` | #2B5A6B | 0,15 | 0,0 | – | Sea |

`Grass` kommt zur vorgegebenen Liste hinzu, für flache, höher gelegene Geländeflächen (Kuppen von Insel und Felsnase). Ohne Grün wirkten die Kuppen wie Wüste. Wer es nicht braucht, gibt ihm die Farbe von `Rock`.

Gelände (`WestHill`, `Headland`, `IslandsFar`): Flächen steiler als etwa 37° sind `Rock`, flache Flächen bis 0,5 m über der Wasserlinie `Sand`, darüber `Grass`.

## UVs und Normalen

- Alle Meshes haben die UV-Map `UVMap` aus Smart UV Project (Winkelgrenze 66°). Danach ist jedes Objekt auf dieselbe Dichte skaliert: **1 UV-Einheit = 1 m**. Kacheltexturen erscheinen dadurch auf allen Objekten gleich groß (zum Beispiel 64 px pro Meter für den PS1-Look). Die UVs liegen deshalb nicht in 0..1.
- Für Unikat-Texturen oder Lightmaps: beim Import in Godot UV2 erzeugen lassen oder in Blender neu abwickeln.
- `Sea` hat planare UVs in Metern statt Smart UV; in Godot gilt UV = (x, z + 1), weil glTF V umdreht. Für Wellen besser Weltkoordinaten im Shader nehmen.
- Normalen: geglättet bis zu einem Kantenwinkel je Objekt (Taurolle 60°, Boote und Poller 50°, Leuchtturm, Fässer und Steg 40°, Gelände 38°, Häuschen, Kisten und Laternenpfahl 30°); `Quay`, `RocksSea`, `IslandsFar` und die Glasteile flach schattiert. Flat-Shading-Stile erzwingen Flächennormalen im Shader.
- Keine Vertexfarben.

## Maße

- Dachs ca. 1,0 m. Tür des Häuschens 0,90 × 1,88 m, Frontfenster 0,82 × 0,90 m (Unterkante 1,0 m).
- Häuschen 3,6 × 3,0 m, Traufe 2,45 m, First 3,80 m, Schornstein bis ca. 4,8 m.
- Fässer 0,90 m hoch, ca. 0,65 m Durchmesser. Kisten 0,62, 0,58 und 0,44 m. Taurolle ca. 0,7 m Durchmesser.
- Laternenpfahl 2,45 m hoch, Laterne hängt am Ausleger, Glasmitte ca. 1,8 m über dem Kai.
- Poller 0,53 m auf den Kantensteinen (Oberkante 0,10 m), Kantensteine 0,62 m breit.
- Steg 1,6 m breit, reicht 7,6 m ins Wasser, Deck 0,04 m, Festmachpfähle bis 0,64 und 0,79 m.
- BoatA 4,6 × 1,75 m, Ruderhaus bis 1,3 m über Wasser. BoatB 4,0 × 1,55 m, Mast 3 m. Tiefgang ca. 0,4 m.
- Leuchtturm: Fuß auf 2,8 m, Turm 8,4 m, Lampenmitte 12,58 m, Spitze 14,4 m über dem Kai. Tür und Fenster zeigen zur Hauptkamera.

## Hinweise für Stile

- Szene instanzieren (`load("res://harbor.glb").instantiate()`). Materialien per Name tauschen: alle `MeshInstance3D` durchgehen, `mesh.surface_get_material(i).resource_name` prüfen und `set_surface_override_material(i, …)` setzen.
- Leuchtende Teile sind eigene Objekte (`CottageWindow`, `LighthouseLamp`, `LanternGlass`); sie lassen sich einzeln flackern oder blinken. Lichter an die Empties hängen.
- Boote um ihren Ursprung (Wasserlinie) schaukeln: kleine Drehung um x und z, leichtes Heben in y.
- Rauch an `ChimneySmoke`, Leuchtturmstrahl an `LighthouseLight` (Drehung um y).
- Keine Kollisionen im glb; für den Laufweg genügt eine Ebene bei y = 0.

## Grenzen

- Das Meer endet 900 m hinter dem Kai knapp unter dem Horizont. Mit Nebel oder einem Himmel in Wasserfarbe am Horizont ist die Kante unsichtbar.
- Das Pflaster vorn ist absichtlich ruhig: Dort stehen Figur und Textbox.
- Das Gelände ist ein Höhenfeld (keine Überhänge).
- Ohne die Vorschau-Lichter (Sonne, Punktlichter an den Empties) wirkt die Szene in Godot flach; Licht und Himmel setzt jeder Stil selbst.
