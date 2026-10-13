#!/usr/bin/env python3
"""Erzeugt Bilder über Codex CLI (image_gen, gpt-image) oder Antigravity CLI (agy, generate_image).

Übernommen aus bildsprache/tools/generate.py und erweitert um Referenzbilder, damit Figuren
und Paletten über mehrere Bilder gleich bleiben, und um agy als zweiten Weg.

Einzelbild:
    python3 tools/genimg.py --out styles/x/assets/raw/bg.png --size 1536x1024 --prompt-file p.txt
    python3 tools/genimg.py --out ... --size 1024x1024 --prompt "..." --ref figur.png --ref palette.png

Mehrere Aufträge parallel:
    python3 tools/genimg.py --jobs jobs.json --workers 2
    jobs.json: [{"out": "...png", "size": "1536x1024", "prompt": "...", "refs": ["a.png"], "backend": "auto"}]
    Optional je Auftrag: "key_color" (agy-Freistellfarbe), "ref_note" (Satz zu den Referenzbildern für agy;
    Standard "Keep the character design and palette from them.", "" lässt ihn weg, z. B. bei Masken oder
    Strichvorlagen, deren Farben nicht übernommen werden sollen).

Backends (--backend, oder "backend" im Auftrag):
  auto   (Standard) wählt je Auftrag (auto_order, Begründung als backend_choice in der .json):
         1. Gibt es das Ziel schon (--force) oder ein Referenzbild aus derselben Bildgruppe (styles/<slug>/,
            außerhalb des Katalogs derselbe Ordner) und nennt dessen .json ein Backend: nur dieses Backend, ohne
            Ausweichen. So bleiben Masken, Tiefenkarten, Varianten und Bildserien deckungsgleich, gleich groß und
            im selben Strich. Ist es gesperrt, endet der Aufruf mit "usage limit"; das andere Modell nur bewusst
            mit --backend.
         2. Sonst verlangt der Prompt Transparenz: Codex zuerst (echter Alphakanal statt Freistellen).
         3. Sonst SPIELGRAFIK_PREFER, Standard agy, auch für andere Projekte, die das Werkzeug mitbenutzen
            (agy trägt die Hauptlast, Codex ist Reserve).
         Bei 2. und 3. werden gesperrte Wege übersprungen; meldet der erste Weg sein Kontingent erschöpft, folgt
         der zweite (Codex wird dann für eine Stunde gesperrt, bei "out of credits" für sechs Stunden). Sind alle
         Wege gesperrt, endet der Aufruf sofort mit "usage limit (… gesperrt bis …)".
  codex  nur Codex (gpt-image). Echte Transparenz möglich ("isolated on a fully transparent background").
  agy    nur Antigravity (Gemini-Bildmodell). Liefert JPEG ohne Alphakanal: verlangt der Prompt einen
         transparenten Hintergrund, ersetzt das Werkzeug ihn durch reines Magenta und stellt danach
         automatisch frei (sprites.py key). Beides steht in der .json neben dem Bild. Hat das Motiv
         Glas oder Magenta-Töne, eine andere Schlüsselfarbe wählen (--key-color 00ff00 bzw. "key_color").

Neben jedes Bild schreibt das Werkzeug <name>.json mit Prompt, tatsächlich verwendetem Prompt (agy),
Referenzen, Backend und Dauer. Vorhandene Ziele werden übersprungen (--force überschreibt).
Rechnerweit laufen höchstens SPIELGRAFIK_IMAGE_SLOTS (Standard 4) Codex-Erzeugungen gleichzeitig, auch wenn
mehrere Agenten das Werkzeug parallel aufrufen; weitere warten auf einen freien Platz.
agy: Antigravity CLI, Befehl agy. Abweichende Befehle stehen in der nicht eingecheckten Datei tools/local.json
({"agy": ["agy"]}) oder in SPIELGRAFIK_AGY_CMDS (kommagetrennt). Ein Befehl hat SPIELGRAFIK_AGY_SLOTS (Standard 2)
Plätze; ist er gesperrt, endet ein Aufruf mit "usage limit (agy …)".
Größen: 1024x1024, 1536x1024, 1024x1536.
"""
import argparse, concurrent.futures as cf, contextlib, datetime, fcntl, glob, json, os, pathlib, re, shutil, subprocess, sys, threading, time

CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex"))
LIMIT_FILE = pathlib.Path.home() / ".cache" / "spielgrafik" / "codex_image_limit"
LOCAL_FILE = pathlib.Path(__file__).resolve().parent / "local.json"  # lokal, nicht eingecheckt


def _agy_entries():
    """Lokale Einrichtung: [{"cmd", "home"?}] aus SPIELGRAFIK_AGY_CMDS bzw. local.json, sonst agy."""
    entries = []
    if LOCAL_FILE.exists():
        try:
            entries = [{"cmd": e} if isinstance(e, str) else dict(e)
                       for e in json.loads(LOCAL_FILE.read_text()).get("agy", [])]
        except (ValueError, AttributeError, TypeError) as exc:
            raise SystemExit(f"{LOCAL_FILE.name}: ungültig ({exc})")
        if not all(isinstance(e.get("cmd"), str) for e in entries):
            raise SystemExit(f"{LOCAL_FILE.name}: jeder Eintrag unter \"agy\" braucht \"cmd\"")
    env = os.environ.get("SPIELGRAFIK_AGY_CMDS", "").strip()
    if env:
        known = {e["cmd"]: e for e in entries}
        entries = [known.get(n, {"cmd": n}) for n in (s.strip() for s in env.split(",")) if n]
    return entries or [{"cmd": "agy"}]


def _agy_accounts():
    """agy-Befehle aus der lokalen Einrichtung: (Name, Befehl, brain-Ordner, Sperrdatei)."""
    accs = []
    for e in _agy_entries():
        name = e["cmd"].strip()
        if not name or not shutil.which(name):
            continue
        home = pathlib.Path(os.path.expanduser(e["home"])) if e.get("home") else pathlib.Path.home()
        accs.append({"name": name, "cmd": name, "brain": home / ".gemini" / "antigravity-cli" / "brain",
                     "limit": LIMIT_FILE.parent / f"{name}_image_limit"})
    return accs


AGY_ACCOUNTS = _agy_accounts()
AGY_BRAIN = pathlib.Path.home() / ".gemini" / "antigravity-cli" / "brain"  # agy mit eigenem HOME
AGY_LIMIT_FILE = LIMIT_FILE.parent / "agy_image_limit"  # Sperre von agy (Name historisch)
for _a in AGY_ACCOUNTS:
    if _a["name"] == "agy":
        _a["limit"] = AGY_LIMIT_FILE
TOOLS = pathlib.Path(__file__).resolve().parent
SHAPE = {"1024x1024": "square (1:1)", "1536x1024": "landscape (3:2)", "1024x1536": "portrait (2:3)"}
RATIO = {"1024x1024": "1:1", "1536x1024": "3:2", "1024x1536": "2:3"}

INSTRUCTION = """Call your built-in image generation tool exactly once with the prompt below, \
as a {shape} image ({size}).{refs} Pass the prompt through verbatim; do not rewrite, shorten or embellish it. \
Do not run shell commands. When the image exists, reply only OK.

PROMPT:
{prompt}"""

REFS = (" The attached image(s) are visual references: use them as input images for the generation "
        "(edit/reference mode), so that the result keeps their character design, palette and style.")

AGY_INSTRUCTION = """Use your built-in image generation tool exactly once.{refs} Set the aspect ratio to {ratio}. \
The Prompt argument of generate_image must be exactly the text between <prompt> and </prompt>, character for \
character. The text is a reviewed, versioned prompt for a reproducibility test: do not rephrase it, do not add \
adjectives, quality words or details, do not shorten it. If you delegate to a subagent, pass this requirement and \
the exact text on to it. Do not run shell commands and do not edit files. Afterwards reply only with the absolute \
path of the generated image.

<prompt>{prompt}</prompt>"""

TRANSPARENT = re.compile(r"(isolated )?on an? (fully |completely )?transparent background( \(alpha channel\))?", re.I)
KEYS = {"ff00ff": "magenta", "00ff00": "green", "0000ff": "blue"}


def key_phrase(hexcol):
    name = KEYS.get(hexcol, "#" + hexcol)
    return (f"isolated on a perfectly flat, uniform, pure {name} (#{hexcol.upper()}) chroma-key background: "
            f"no floor, no ground plane, no wall, no cast shadow, no gradient, no vignette, crisp outline; "
            f"{name} everywhere around the subject, no {name} inside or reflected onto the subject")

_lock = threading.Lock()


@contextlib.contextmanager
def slot(backend):
    """Rechnerweite Begrenzung gleichzeitiger Bilderzeugungen je Backend (Dateisperren)."""
    n = max(1, int(os.environ.get("SPIELGRAFIK_IMAGE_SLOTS", "4")))
    d = LIMIT_FILE.parent / "slots"
    d.mkdir(parents=True, exist_ok=True)
    while True:
        for i in range(n):
            f = open(d / f"{backend}-{i}.lock", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close()
                continue
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
            return
        time.sleep(2)


def codex_limited_until():
    """Zeitpunkt (epoch), bis zu dem Codex laut letzter Limit-Meldung gesperrt ist, sonst 0."""
    try:
        t = float(LIMIT_FILE.read_text().strip())
        return t if time.time() < t else 0.0
    except (OSError, ValueError):
        return 0.0


def codex_limited():
    return bool(codex_limited_until())


def mark_codex_limited(hours=1.0):
    """Codex sperren; eine längere, inzwischen von einem anderen Prozess gesetzte Sperre bleibt bestehen."""
    LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIMIT_FILE.write_text(str(max(codex_limited_until(), time.time() + hours * 3600)))


def account_limited_until(acc):
    """Zeitpunkt (epoch), bis zu dem dieses agy-Programm laut letzter Kontingentmeldung gesperrt ist, sonst 0."""
    try:
        t = float(acc["limit"].read_text().strip())
        return t if time.time() < t else 0.0
    except (OSError, ValueError):
        return 0.0


def agy_limited_until():
    """Sind alle agy-Programme gesperrt: frühester Freigabezeitpunkt (epoch), sonst 0."""
    untils = [account_limited_until(a) for a in AGY_ACCOUNTS]
    if not untils or not all(untils):
        return 0.0
    return min(untils)


def mark_agy_limited(reply, acc=None):
    """Liest aus der agy-Antwort die Wartezeit ("reset in approximately 2 hours") und sperrt das Programm bis dahin."""
    low = reply.lower()
    secs = 2 * 3600.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hr|minute|min)", low)
    if m:
        secs = float(m.group(1)) * (3600 if m.group(2).startswith("h") else 60)
    f = acc["limit"] if acc else AGY_LIMIT_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(str(time.time() + secs + 300))
    return time.time() + secs + 300


def _next_rr(n):
    """Rechnerweiter Rundlauf-Zähler, damit parallele Aufrufe bei verschiedenen agy-Programmen beginnen."""
    f = LIMIT_FILE.parent / "agy_rr"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a+") as h:
        fcntl.flock(h, fcntl.LOCK_EX)
        h.seek(0)
        try:
            k = int(h.read().strip() or 0)
        except ValueError:
            k = 0
        h.seek(0)
        h.truncate()
        h.write(str(k + 1))
    return k % max(1, n)


@contextlib.contextmanager
def agy_account():
    """Freies, nicht gesperrtes agy-Programm belegen (je SPIELGRAFIK_AGY_SLOTS Plätze); None, wenn alle gesperrt."""
    per = max(1, int(os.environ.get("SPIELGRAFIK_AGY_SLOTS", "2")))
    d = LIMIT_FILE.parent / "slots"
    d.mkdir(parents=True, exist_ok=True)
    start = _next_rr(len(AGY_ACCOUNTS))
    order = AGY_ACCOUNTS[start:] + AGY_ACCOUNTS[:start]
    while True:
        free = [a for a in order if not account_limited_until(a)]
        if not free:
            yield None
            return
        for acc in free:
            for i in range(per):
                f = open(d / f"{acc['name']}-{i}.lock", "w")
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    f.close()
                    continue
                try:
                    yield acc
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
                    f.close()
                return
        time.sleep(2)


def run_agy_pool(job, out, size, refs, timeout):
    """run_agy mit einem freien agy-Programm; ist es danach gesperrt, mit dem nächsten freien."""
    tried = []
    for _ in range(max(1, len(AGY_ACCOUNTS))):
        with agy_account() as acc:
            if acc is None:
                until = agy_limited_until()
                when = time.strftime("%H:%M", time.localtime(until)) if until else "?"
                return (f"usage limit (agy, gesperrt bis frühestens {when}; versucht: "
                        f"{', '.join(tried) or 'keins'})"), {}
            status, info = run_agy(job, out, size, refs, timeout, acc)
            tried.append(acc["name"])
            if not (status.startswith("usage limit") and account_limited_until(acc)):
                return status, info
            print(f"{acc['name']}: gesperrt – nächstes agy-Programm.", flush=True)
    return status, info


def run_codex(job, out, size, refs, timeout):
    text = INSTRUCTION.format(shape=SHAPE.get(size, size), size=size, prompt=job["prompt"],
                              refs=REFS if refs else "")
    cmd = ["codex", "exec", "--json", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
           "-C", str(out.parent)]
    for r in refs:
        cmd += ["-i", r]
    cmd += ["--", text]
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", {}
    thread, reply, errors = None, "", []
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "thread.started":
            thread = ev["thread_id"]
        if ev.get("type") in ("error", "turn.failed"):
            errors.append(ev.get("message") or (ev.get("error") or {}).get("message", ""))
        item = ev.get("item") or {}
        if item.get("type") == "agent_message":
            reply = item.get("text", "")
    blob = (reply + " " + " ".join(errors) + " " + p.stderr[-2000:]).lower()
    if "out of credits" in blob:
        return "usage limit (codex, out of credits): " + " ".join(errors)[:200], {"hours": 6.0}
    if not thread:
        return "no-thread: " + p.stderr[-300:].replace("\n", " "), {}
    pngs = sorted((CODEX_HOME / "generated_images" / thread).glob("*.png"), key=lambda f: f.stat().st_mtime)
    if not pngs:
        if "usage limit" in blob or "usage_limit" in blob or "429" in blob:
            return "usage limit (codex): " + (reply or " ".join(errors))[:200].replace("\n", " "), {}
        return "no-image: " + (reply or " ".join(errors))[:300].replace("\n", " "), {}
    shutil.copy2(pngs[-1], out)
    return "ok", {"tool": "Codex CLI built-in image_gen", "thread_id": thread, "pngs_in_thread": len(pngs),
                  "tool_version": VERSIONS.get("codex", "")}


def logged_matches(logged, sent):
    """agy protokolliert lange Prompts gekürzt ("…\\n<truncated N bytes>") und mit maskierten Zeilenumbrüchen.
    True, wenn der protokollierte Text (bzw. sein erhaltener Anfang) wörtlich dem gesendeten entspricht."""
    if not isinstance(logged, str):
        return False
    cut = re.search(r"\n?<truncated \d+ bytes>\s*$", logged)
    text = logged[:cut.start()] if cut else logged
    text = text.replace("\\n", "\n").replace('\\"', '"')
    if text.startswith('"'):  # agy protokolliert den Prompt als JSON-Zeichenkette
        text = text[1:]
        if not cut and text.endswith('"'):
            text = text[:-1]
    if not cut:
        return text == sent
    text = text[:-8] if len(text) > 8 else text  # Schnitt kann mitten in einer Maskierung liegen
    return sent.startswith(text)


def agy_generate_calls(conv, brain=AGY_BRAIN):
    """Liest aus den Protokollen der agy-Unteragenten die tatsächlichen generate_image-Aufrufe."""
    calls = []
    for f in glob.glob(str(brain / conv / ".system_generated" / "subagents" / "*.json")):
        try:
            sub = json.load(open(f))["conversationId"]
        except (OSError, ValueError, KeyError):
            continue
        tr = brain / sub / ".system_generated" / "logs" / "transcript.jsonl"
        if not tr.exists():
            continue
        for line in tr.read_text().splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            for tc in d.get("tool_calls") or []:
                if tc.get("name") == "generate_image":
                    args = {}
                    for k, v in (tc.get("args") or {}).items():
                        try:
                            args[k] = json.loads(v) if isinstance(v, str) else v
                        except ValueError:
                            args[k] = v
                    calls.append({k: args.get(k) for k in ("Prompt", "AspectRatio", "ImagePaths") if k in args})
    return calls


def run_agy(job, out, size, refs, timeout, acc=None):
    acc = acc or {"name": "agy", "cmd": "agy", "brain": AGY_BRAIN, "limit": AGY_LIMIT_FILE}
    prompt = job["prompt"]
    keycol = job.get("key_color", "ff00ff").lower().lstrip("#")
    keyed = bool(TRANSPARENT.search(prompt))
    if keyed:
        prompt = TRANSPARENT.sub(key_phrase(keycol), prompt)
    reftext = ""
    if refs:
        note = job.get("ref_note", "Keep the character design and palette from them.")
        reftext = (" Pass these image files to the tool as reference/input images: "
                   + ", ".join(refs) + "." + (" " + note if note else ""))
    text = AGY_INSTRUCTION.format(refs=reftext, ratio=RATIO.get(size, "1:1"), prompt=prompt)
    cmd = [acc["cmd"], "-p", text, "--sandbox", "--output-format", "json", "--print-timeout", f"{timeout}s"]
    if refs:
        for d in sorted({str(pathlib.Path(r).parent) for r in refs}):
            cmd += ["--add-dir", d]
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=timeout + 60, cwd=str(out.parent))
    except subprocess.TimeoutExpired:
        return "timeout", {}
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "agy-error: " + (p.stderr or p.stdout)[-300:].replace("\n", " "), {}
    conv = res.get("conversation_id", "")
    reply = res.get("response", "")
    imgs = []
    for ext in ("png", "jpg", "jpeg", "webp"):
        imgs += (acc["brain"] / conv).glob(f"*.{ext}")
    imgs = sorted(imgs, key=lambda f: f.stat().st_mtime)
    if not imgs:
        low = reply.lower()
        info = {"conversation_id": conv, "reply": reply, "agy_account": acc["name"]}
        if "429" in low or "resource_exhausted" in low or "quota" in low or "exhausted" in low:
            with _lock:
                until = mark_agy_limited(reply, acc)
            tag = (f"usage limit ({acc['name']}, gesperrt bis "
                   + time.strftime("%H:%M", time.localtime(until)) + ")")
        elif "limit" in low:
            tag = "usage limit (agy)"
        else:
            tag = "no-image (agy)"
        return f"{tag}: " + reply[:400].replace("\n", " "), info
    from PIL import Image
    Image.open(imgs[-1]).convert("RGB").save(out)
    calls = agy_generate_calls(conv, acc["brain"])
    meta = {"tool": "Antigravity CLI (agy) generate_image", "agy_account": acc["name"], "conversation_id": conv,
            "tool_version": VERSIONS.get("agy", ""), "images_in_conversation": len(imgs),
            "actual_calls": calls, "verbatim": bool(calls) and logged_matches(calls[-1].get("Prompt"), prompt),
            "source_format": imgs[-1].suffix.lstrip(".")}
    if keyed:
        raw = out.with_name(out.stem + ".keyed-src.png")
        shutil.copy2(out, raw)
        k = subprocess.run([sys.executable, str(TOOLS / "sprites.py"), "key", str(raw), str(out),
                            "--color", keycol, "--tol", "70", "--soft", "50"], capture_output=True, text=True)
        meta["transparency"] = (f"Schlüsselfarbe #{keycol} statt Transparenz, automatisch freigestellt; Original: "
                                + raw.name + (" (Freistellen fehlgeschlagen: " + k.stderr[-200:] + ")" if k.returncode else ""))
        meta["prompt_sent"] = prompt
        with Image.open(out) as im:
            share = (sum(im.getchannel("A").histogram()[:8]) / (im.width * im.height)) if im.mode == "RGBA" else 0.0
        meta["key_transparent_share"] = round(share, 3)
        if share < 0.03:
            # Freistellen hat praktisch nichts entfernt (Hintergrund nicht flach): laut scheitern, damit neu erzeugt wird.
            bad = out.with_name(out.stem + ".keyfail.png")
            out.replace(bad)
            (bad.with_suffix(".json")).write_text(json.dumps({"prompt": job["prompt"], **meta}, ensure_ascii=False, indent=1))
            return (f"key-failed (agy): nur {share:.1%} transparent, Hintergrund nicht flach; "
                    f"Versuch liegt in {bad.name} und {raw.name}"), {}
    return "ok", meta


def limited_until(backend):
    """Sperre eines Wegs (epoch) oder 0; agy gilt erst als gesperrt, wenn alle agy-Programme gesperrt sind."""
    return agy_limited_until() if backend == "agy" else codex_limited_until()


def _group_dir(p):
    """Bildgruppe eines Pfads: styles/<slug> im Katalog, sonst der Ordner der Datei (andere Projekte)."""
    p = pathlib.Path(p)
    parts = p.parts
    if "styles" in parts:
        i = len(parts) - 1 - parts[::-1].index("styles")
        if i + 1 < len(parts) - 1:
            return pathlib.Path(*parts[:i + 2])
    return p.parent


def _backend_of(img):
    """Backend eines erzeugten Bilds laut seiner .json (ältere nennen es nur über "tool"), sonst None."""
    img = pathlib.Path(img)
    names = [img.with_suffix(".json")]
    if img.stem.endswith(".keyed-src"):
        names.append(img.with_name(img.stem[:-len(".keyed-src")] + ".json"))
    for f in names:
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        if d.get("backend") in ("codex", "agy"):
            return d["backend"]
        tool = str(d.get("tool", ""))
        if "Antigravity" in tool:
            return "agy"
        if "Codex" in tool:
            return "codex"
    return None


def anchor_backend(out, refs):
    """Backend, an das ein Auftrag gebunden ist, und das Bild, das es vorgibt: das eigene, schon erzeugte Bild
    (Neuerzeugung mit --force) oder ein Referenzbild aus derselben Bildgruppe. Sonst (None, None)."""
    group = _group_dir(out)
    for r in [pathlib.Path(out)] + [pathlib.Path(x) for x in refs]:
        if _group_dir(r) != group:
            continue
        b = _backend_of(r)
        if b:
            return b, r
    return None, None


def auto_order(job, out, refs):
    """Wege für backend auto in Reihenfolge, mit Begründung (siehe Kopfkommentar)."""
    b, src = anchor_backend(out, refs)
    if b:
        return [b], f"gebunden an {src.name} ({b}), kein Ausweichen"
    if TRANSPARENT.search(job["prompt"]):
        return ["codex", "agy"], "Transparenz"
    pref = os.environ.get("SPIELGRAFIK_PREFER", "agy")
    if pref not in ("codex", "agy"):
        pref = "agy"  # Standard: agy zuerst, Codex als Reserve
    return [pref, "agy" if pref == "codex" else "codex"], "Lastverteilung"


def blocked_until(backend, job=None):
    """Bis wann ein Auftrag gar nicht laufen kann (epoch), sonst 0. Für Warteschlangen: auto ist blockiert, wenn
    alle Wege seiner auto_order gesperrt sind; ein fest gewähltes codex probiert es trotz Sperre."""
    if backend == "auto":
        if job is None:
            order = ["agy", "codex"]
        else:
            order = auto_order(job, pathlib.Path(job["out"]).resolve(),
                               [str(pathlib.Path(r).resolve()) for r in job.get("refs", [])])[0]
    elif backend == "agy":
        order = ["agy"]
    else:
        return 0.0
    locks = [limited_until(b) for b in order]
    return min(locks) if all(locks) else 0.0


def run(job, timeout, force=False, backend="auto"):
    out = pathlib.Path(job["out"]).resolve()
    meta = out.with_suffix(".json")
    if out.exists() and not force:
        return job, "skip", 0.0
    out.parent.mkdir(parents=True, exist_ok=True)
    size = job.get("size", "1024x1024")
    refs = [str(pathlib.Path(r).resolve()) for r in job.get("refs", [])]
    for r in refs:
        if not pathlib.Path(r).exists():
            return job, f"ref-missing: {r}", 0.0
    backend = job.get("backend", backend)
    t0 = time.time()
    hhmm = lambda t: time.strftime("%H:%M", time.localtime(t))
    status, info, used, first_status = "", {}, backend, None
    lock_txt = lambda b: f"{b} gesperrt bis {'frühestens ' if b == 'agy' else ''}{hhmm(limited_until(b))}"
    if backend == "auto":
        order, why = auto_order(job, out, refs)
        free = [b for b in order if not limited_until(b)]
        if not free:
            status = f"usage limit ({', '.join(lock_txt(b) for b in order)}; {why})"
        elif free[0] != order[0]:
            print(f"{lock_txt(order[0])} – nehme {free[0]}.", flush=True)
            why += f"; {order[0]} gesperrt, daher {free[0]}"
        order = free
    else:
        order, why = ["agy" if backend == "agy" else "codex"], "fest gewählt"
    for k, used in enumerate(order):
        if used == "agy":
            status, info = run_agy_pool(job, out, size, refs, timeout)
        else:
            with slot("codex"):
                status, info = run_codex(job, out, size, refs, timeout)
            if status.startswith("usage limit") and backend == "auto":
                with _lock:
                    mark_codex_limited(info.get("hours", 1.0))
        if not (status.startswith("usage limit") and k + 1 < len(order)) or limited_until(order[k + 1]):
            break
        print(f"{used}: Kontingent erschöpft ({status[:80]}) – weiter mit {order[k + 1]}.", flush=True)
        first_status = status
        why += f"; {used} Kontingent erschöpft, daher {order[k + 1]}"
    info = {**(info or {}), "backend_choice": why}
    if first_status:
        info["first_status"] = first_status[:300]
    if status != "ok":
        # Fehlschläge mit voller Antwort festhalten, damit der Grund nachprüfbar bleibt.
        out.with_suffix(".fail.json").write_text(json.dumps({
            "status": status, "backend": used, "prompt": job["prompt"], "size": size,
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **(info or {}),
        }, ensure_ascii=False, indent=1))
        return job, status, time.time() - t0
    secs = time.time() - t0
    from PIL import Image
    with Image.open(out) as im:
        actual = f"{im.width}x{im.height}"
    if actual != size:
        print(f"WARNUNG {out.name}: angefragt {size}, geliefert {actual} (Seitenverhältnis prüfen)", flush=True)
    meta.write_text(json.dumps({
        "prompt": job["prompt"],
        "size": size,
        "actual_size": actual,
        "refs": [os.path.relpath(r, out.parent) for r in refs],
        "backend": used,
        "seconds": round(secs, 1),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        **info,
    }, ensure_ascii=False, indent=1))
    return job, "ok", secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs")
    ap.add_argument("--out")
    ap.add_argument("--size", default="1024x1024", choices=sorted(SHAPE))
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--backend", choices=["auto", "codex", "agy"], default="auto")
    ap.add_argument("--key-color", default="ff00ff", help="nur agy: Ersatzfarbe für transparente Hintergründe")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=480)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for name, cmd in (("codex", ["codex", "--version"]), ("agy", ["agy", "--version"])):
        try:
            VERSIONS[name] = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            VERSIONS[name] = ""
    if a.jobs:
        jobs = json.loads(pathlib.Path(a.jobs).read_text())
    else:
        prompt = a.prompt or (pathlib.Path(a.prompt_file).read_text() if a.prompt_file else None)
        if not (a.out and prompt):
            ap.error("--out und --prompt/--prompt-file oder --jobs angeben")
        jobs = [{"out": a.out, "size": a.size, "prompt": prompt.strip(), "refs": a.ref, "key_color": a.key_color}]
    fails = 0
    with cf.ThreadPoolExecutor(max(1, min(a.workers, 3))) as ex:
        for job, status, secs in ex.map(lambda j: run(j, a.timeout, a.force, a.backend), jobs):
            fails += status not in ("ok", "skip")
            print(f"{status[:240]:30} {secs:6.1f}s  {job['out']}", flush=True)
    print(f"{len(jobs) - fails}/{len(jobs)} ok", flush=True)
    return 1 if fails else 0


VERSIONS = {}

if __name__ == "__main__":
    sys.exit(main())
