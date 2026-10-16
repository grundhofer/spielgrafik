# Vorgerenderte HD-Hintergründe

Eigenständige HD-Variante der Retro-Fixkamera: gleiche Kameras, Bahn, Hafen- und Dachsgrundlage.
Kein KI-Bildauftrag; alle Renderplatten, das Panorama und die Materialdetails werden per Code erzeugt.

Aus dem Projektordner neu bauen:

```sh
blender -b --factory-startup -P styles/vorgerendert-hd/blender/render_bg.py
.venv/bin/python styles/vorgerendert-hd/scripts/bake.py
.venv/bin/python styles/vorgerendert-hd/scripts/materials.py
godot --headless --path styles/vorgerendert-hd/demo --import
.venv/bin/python styles/vorgerendert-hd/scripts/probe.py
.venv/bin/python tools/capture.py styles/vorgerendert-hd --poster-at 0.82
.venv/bin/python build.py
```

Die Demo ist eigenständig, die Roh-EXR-Tiefenpässe und NPY-Zwischenstände sind nicht eingecheckt.
Die linearen HDR-Platten und das Panorama liegen zusammen mit verlustfreien RGB24-Tiefenbildern in `demo/bg/`.
`assets/probe.json` enthält die abschließenden Messwerte; Einschränkungen und Bewertungen stehen in `style.json`.
Die 180-Bilder-Aufnahme wurde geprüft; Forward+ und Mobile funktionieren, OpenGL liefert deutlich andere Farben.
Die beiden Eintragsseiten verweisen über `related` direkt aufeinander.
