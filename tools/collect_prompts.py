#!/usr/bin/env python3
"""Sammelt die Prompts der KI-Bilder je Eintrag in styles/<slug>/prompts.json.

    python3 tools/collect_prompts.py                    # alle Einträge mit assets/raw/
    python3 tools/collect_prompts.py vga-adventure      # nur diese Einträge
    python3 tools/collect_prompts.py --styles DIR ...   # anderes styles-Verzeichnis (Tests)

tools/genimg.py legt neben jedes Rohbild <name>.json mit Prompt, Größe und Referenzen ab. assets/raw/ wird nicht
eingecheckt (zu groß), prompts.json schon: so zeigt build.py die Prompts auch in CI. Lokal vor build.py ausführen.

Format: Liste von {"file", "prompt", "refs", "size", "backend"[, "prompt_sent"]}, sortiert nach Erzeugungszeit.
  file         Rohbild relativ zum Eintragsordner, z. B. "assets/raw/bg.png"
  refs         Referenzbilder relativ zum Projektverzeichnis, z. B. "shared/badger/master_sheet.png"
  backend      "codex" (gpt-image) oder "agy" (Gemini); ältere Begleitdateien ohne Angabe stammen von Codex
  prompt_sent  nur wenn das Bildmodell einen anderen Wortlaut bekam (agy: Schlüsselfarbe statt Transparenz
               oder vom Agenten umformuliert, laut actual_calls)
Einträge ohne assets/raw/ oder ohne Begleitdateien bleiben unverändert (ein frischer Klon hat kein raw/).
Nur Standardbibliothek.
"""
import argparse, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def sidecars(raw):
    """Begleitdateien von genimg.py: JSON-Objekte mit Prompt. Auftragslisten (jobs.json) u. Ä. werden übersprungen."""
    out = []
    for p in sorted(raw.rglob("*.json")):
        if p.name.endswith((".fail.json", ".keyfail.json")):
            continue  # gescheiterte Versuche ohne Bild (genimg.py)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            print(f"  WARNUNG: {p}: kein gültiges JSON ({exc})", file=sys.stderr)
            continue
        if isinstance(data, dict) and isinstance(data.get("prompt"), str) and data["prompt"].strip():
            out.append((p, data))
    return out


def image_for(sidecar):
    for ext in IMAGE_EXT:
        if sidecar.with_suffix(ext).exists():
            return sidecar.with_suffix(ext)
    return sidecar.with_suffix(".png")  # genimg.py schreibt PNG; das Bild selbst darf fehlen


def normalize_ref(ref, raw, project):
    path = pathlib.Path(os.path.normpath(raw / ref))
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return pathlib.PurePath(ref).name


def backend_of(data):
    if data.get("backend"):
        return data["backend"]
    return "agy" if "Antigravity" in str(data.get("tool", "")) else "codex"


def logged_matches(logged, sent):
    """agy protokolliert lange Prompts gekürzt ("…\\n<truncated N bytes>") und mit maskierten Zeilenumbrüchen."""
    cut = re.search(r"\n?<truncated \d+ bytes>\s*$", logged)
    text = logged[:cut.start()] if cut else logged
    text = text.replace("\\n", "\n").replace('\\"', '"')
    if text.startswith('"'):  # agy protokolliert den Prompt als JSON-Zeichenkette
        text = text[1:]
        if not cut and text.endswith('"'):
            text = text[:-1]
    if not cut:
        return text.strip() == sent.strip()
    text = text[:-8] if len(text) > 8 else text
    return sent.startswith(text)


def sent_prompt(data):
    """Wortlaut, den das Bildmodell tatsächlich bekam, falls er vom Auftrag abweicht; sonst None."""
    calls = data.get("actual_calls") or []
    actual = calls[-1].get("Prompt") if calls and isinstance(calls[-1], dict) else None
    own = (data.get("prompt_sent") or data["prompt"]).strip()
    if isinstance(actual, str) and actual.strip():
        if logged_matches(actual, own):
            actual = None  # wörtlich angekommen (Protokoll nur gekürzt)
    sent = actual if isinstance(actual, str) and actual.strip() else data.get("prompt_sent")
    if isinstance(sent, str) and sent.strip() and sent.strip() != data["prompt"].strip():
        return sent.strip()
    return None


def collect(style_dir, project):
    """Gibt die Liste für prompts.json zurück oder None, wenn es keine Begleitdateien gibt."""
    raw = style_dir / "assets" / "raw"
    if not raw.is_dir():
        return None
    found = sidecars(raw)
    if not found:
        return None
    found.sort(key=lambda item: (str(item[1].get("generated_at") or ""), item[0].as_posix()))
    items = []
    for side, data in found:
        item = {
            "file": image_for(side).relative_to(style_dir).as_posix(),
            "prompt": data["prompt"].strip(),
            "refs": [normalize_ref(r, side.parent, project) for r in data.get("refs") or []],
            "size": data.get("size"),
            "backend": backend_of(data),
        }
        sent = sent_prompt(data)
        if sent:
            item["prompt_sent"] = sent
        items.append(item)
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description="Schreibt styles/<slug>/prompts.json aus den Begleitdateien in assets/raw/.")
    ap.add_argument("slugs", nargs="*", help="Einträge (Standard: alle)")
    ap.add_argument("--styles", default=str(ROOT / "styles"), help="styles-Verzeichnis (Standard: styles/ im Projekt)")
    a = ap.parse_args(argv)
    styles = pathlib.Path(a.styles).resolve()
    project = styles.parent
    if a.slugs:
        dirs = [styles / s for s in a.slugs]
        missing = [d for d in dirs if not d.is_dir()]
        if missing:
            print("fehlt: " + ", ".join(str(d) for d in missing), file=sys.stderr)
            return 1
    else:
        dirs = sorted(d for d in styles.iterdir() if d.is_dir() and not d.name.startswith(".")) if styles.is_dir() else []
    written = unchanged = skipped = 0
    for d in dirs:
        items = collect(d, project)
        if items is None:
            skipped += 1
            continue
        target = d / "prompts.json"
        text = json.dumps(items, ensure_ascii=False, indent=1) + "\n"
        old = target.read_text(encoding="utf-8") if target.exists() else None
        if old == text:
            unchanged += 1
            continue
        if old is not None:
            try:
                before = {p.get("file") for p in json.loads(old)}
                gone = before - {p["file"] for p in items}
                if gone:
                    print(f"  WARNUNG: {d.name}: {len(gone)} Prompt(s) ohne Begleitdatei in raw/ entfallen: "
                          + ", ".join(sorted(map(str, gone))), file=sys.stderr)
            except (ValueError, AttributeError, TypeError):
                pass
        target.write_text(text, encoding="utf-8")
        written += 1
        print(f"  {d.name}: {len(items)} Prompts -> {target.relative_to(project)}")
    print(f"{written} geschrieben, {unchanged} unverändert, {skipped} ohne assets/raw/-Begleitdateien")
    return 0


if __name__ == "__main__":
    sys.exit(main())
