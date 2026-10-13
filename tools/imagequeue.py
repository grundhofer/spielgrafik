#!/usr/bin/env python3
"""Zentrale Bild-Warteschlange: arbeitet die Bildaufträge mehrerer Einträge im Takt des Bildkontingents ab.

Hintergrund: Jeder Bildweg hat ein Kontingent (agy etwa ein Dutzend Bilder, dann einige Stunden Pause, Codex
zeitweise ohne Guthaben). Statt dass jeder
Agent selbst Bilder anfordert und am Kontingent scheitert, schreibt jeder Eintrag seine Aufträge nach
styles/<slug>/assets/image_jobs.json (Format wie genimg.py --jobs, Pfade relativ zum Projektordner, in
Prioritätsreihenfolge). Dieses Werkzeug erzeugt sie reihum (erst das wichtigste Bild jedes Eintrags, dann das
zweite …), wartet bei erschöpftem Kontingent bis zur gemeldeten Freigabe und macht dann weiter.

    .venv/bin/python tools/imagequeue.py styles/a/assets/image_jobs.json styles/b/assets/image_jobs.json
    .venv/bin/python tools/imagequeue.py --all            # alle styles/*/assets/image_jobs.json

Ergebnis je Auftrag wie bei genimg.py (<out>, <out>.json bzw. <out>.fail.json). Zusätzlich schreibt das Werkzeug
neben jede Auftragsdatei image_jobs.status.json (Status je Auftrag) und beendet sich, wenn alles erledigt ist
oder --max-hours erreicht sind. Vorhandene Ziele werden übersprungen.
"""
import argparse, datetime, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import genimg  # noqa: E402

RETRY_SOFT = 2  # Wiederholungen bei Fehlern, die kein Kontingentproblem sind


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def load(files):
    queues = []
    for f in files:
        f = pathlib.Path(f)
        jobs = json.loads(f.read_text())
        if not isinstance(jobs, list):
            raise SystemExit(f"{f}: erwartet eine Liste von Aufträgen")
        for j in jobs:
            for k in ("out", "prompt"):
                if k not in j:
                    raise SystemExit(f"{f}: Auftrag ohne {k!r}")
        queues.append({"file": f, "jobs": jobs, "i": 0, "state": [None] * len(jobs), "tries": [0] * len(jobs)})
    return queues


def save_status(q):
    st = []
    for j, s, t in zip(q["jobs"], q["state"], q["tries"]):
        st.append({"out": j["out"], "status": s or "offen", "tries": t})
    q["file"].with_name("image_jobs.status.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-hours", type=float, default=48)
    ap.add_argument("--timeout", type=int, default=480)
    ap.add_argument("--backend", default="auto", choices=["auto", "codex", "agy"])
    a = ap.parse_args()
    files = list(a.files)
    if a.all:
        files += sorted(str(p) for p in ROOT.glob("styles/*/assets/image_jobs.json"))
    if not files:
        ap.error("Auftragsdateien angeben oder --all")
    import os
    os.chdir(ROOT)
    for name, cmd in (("codex", ["codex", "--version"]), ("agy", ["agy", "--version"])):
        try:
            import subprocess
            genimg.VERSIONS[name] = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            genimg.VERSIONS[name] = ""
    queues = load(files)
    total = sum(len(q["jobs"]) for q in queues)
    print(f"{now()} {total} Aufträge aus {len(queues)} Dateien", flush=True)
    deadline = time.time() + a.max_hours * 3600
    made = 0
    while time.time() < deadline:
        open_q = [q for q in queues if q["i"] < len(q["jobs"])]
        if not open_q:
            break
        progressed, blocked = False, []
        for q in open_q:  # reihum: je Eintrag ein Auftrag pro Durchgang
            if q["i"] >= len(q["jobs"]):
                continue
            k = q["i"]
            job = q["jobs"][k]
            backend = job.get("backend", a.backend)
            until = genimg.blocked_until(backend, job)
            if until:
                blocked.append(until)  # dieser Eintrag wartet, die übrigen laufen weiter
                continue
            job, status, secs = genimg.run(job, a.timeout, False, a.backend)
            q["tries"][k] += status != "skip"
            print(f"{now()} {status[:160]:40} {secs:6.1f}s  {job['out']}", flush=True)
            if status in ("ok", "skip"):
                q["state"][k] = status
                q["i"] += 1
                made += status == "ok"
                progressed = True
            elif status.startswith("usage limit"):
                q["tries"][k] -= 1  # Kontingentfehler zählen nicht als Versuch
                if not genimg.blocked_until(backend, job):
                    time.sleep(60)  # Limit ohne Zeitangabe oder noch freie Plätze: kurz warten, dann weiter
            elif q["tries"][k] > RETRY_SOFT or status.startswith("ref-missing"):
                q["state"][k] = "failed: " + status[:200]
                q["i"] += 1
                progressed = True
            else:
                time.sleep(60)
            save_status(q)
        for q in queues:
            save_status(q)
        if not progressed and blocked and len(blocked) == len(open_q):
            until = min(blocked)
            wait = max(30, until - time.time() + 30)
            print(f"{now()} Kontingent erschöpft, warte bis {time.strftime('%H:%M', time.localtime(until))}"
                  f" ({wait / 60:.0f} min)", flush=True)
            time.sleep(min(wait, max(1, deadline - time.time())))
        elif not progressed:
            time.sleep(30)  # nie ohne Pause kreisen
    for q in queues:
        save_status(q)
    left = sum(len(q["jobs"]) - q["i"] for q in queues)
    failed = sum(1 for q in queues for s in q["state"] if s and s.startswith("failed"))
    print(f"{now()} fertig: {made} neue Bilder, {failed} gescheitert, {left} offen", flush=True)
    return 0 if left == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
