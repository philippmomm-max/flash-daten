#!/usr/bin/env python3
"""Sammler ROCK ANTENNE Hamburg: liest die Blitzer-Liste der Serviceseite und haengt die Eintraege im
Gebiet Niedersachsen / Hamburg / Schleswig-Holstein (ungefaehrer Rahmen) als JSON-Zeilen an.

Die Seite liefert je Eintrag Strasse, Koordinaten, Ort, erlaubtes Tempo und Meldezeit; Geocodierung ist
nicht noetig. Nur Python-Standardbibliothek. Prueft vor dem Abruf die robots.txt; sperrt sie die Seite,
wird nichts abgerufen. Aenderung des Seitenaufbaus -> Fehler (Lauf rot).

Aufruf: rockantenne.py --out DATEI.jsonl   (haengt an; Doppelte zum letzten Lauf werden uebersprungen)
        rockantenne.py --html DATEI        (Test mit gespeicherter Seite, gibt Zeilen aus)
"""
import argparse, datetime, html, json, os, re, sys, urllib.request, urllib.robotparser

URL = "https://www.rockantenne.hamburg/service/aktuelle-blitzer"
ROBOTS = "https://www.rockantenne.hamburg/robots.txt"
UA = "FlashSammler/1.0 (privat, einmal taeglich; github.com/philippmomm-max/flash-daten)"
# Grober Umriss von Niedersachsen, Hamburg und Schleswig-Holstein (Laenge, Breite); an den Grenzen ungenau
# um einige Kilometer, Bremen liegt innerhalb.
AREA = [(6.6, 53.75), (7.0, 53.2), (7.1, 52.85), (6.7, 52.6), (6.95, 52.45), (7.1, 52.24), (7.6, 52.45),
        (7.95, 52.25), (8.1, 52.08), (8.45, 52.45), (8.75, 52.5), (9.0, 52.2), (9.4, 51.9), (9.6, 51.6),
        (9.6, 51.4), (9.95, 51.3), (10.3, 51.45), (10.65, 51.6), (10.65, 51.95), (11.0, 52.15), (11.0, 52.55),
        (11.35, 52.85), (11.6, 53.05), (10.6, 53.4), (10.95, 53.85), (11.35, 54.05), (11.35, 54.6),
        (10.0, 55.1), (8.2, 55.1), (8.0, 54.6), (8.2, 53.9)]

ENTRY = re.compile(
    r'<div class="u-flex"[^>]*?data-street="([^"]*)"[^>]*?data-coords="([-\d.]+),([-\d.]+)"[^>]*>(.*?)</div>',
    re.S)

def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def parse(page):
    """Alle Eintraege der Seite (ganz Deutschland). Wirft ValueError, wenn keine gefunden werden."""
    out = []
    for street, lat, lon, body in ENTRY.findall(page):
        name = re.search(r"<strong>(.*?)</strong>", body, re.S)
        tempo = re.search(r"Höchstgeschwindigkeit:\s*(\d+)", body)
        when = re.search(r"Zuletzt gemeldet:\s*(\d\d)\.(\d\d)\.(\d{4})\s+(\d\d):(\d\d)", body)
        out.append({
            "strasse": clean(street),
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "ort": clean(name.group(1)) if name else "",
            "tempo": int(tempo.group(1)) if tempo else None,
            "gemeldet": f"{when.group(3)}-{when.group(2)}-{when.group(1)}T{when.group(4)}:{when.group(5)}" if when else "",
        })
    if not out and "c-icon--blitzer" not in page:
        raise ValueError("keine Blitzer-Eintraege gefunden (Seitenaufbau geaendert?)")
    return out

def inside(lon, lat, poly=AREA):
    """Punkt-in-Polygon (Strahlverfahren)."""
    hit = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit

def in_area(r):
    return inside(r["lon"], r["lat"])

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def allowed():
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(fetch(ROBOTS).splitlines())
    except Exception:
        return True  # keine robots.txt erreichbar: keine Sperre bekannt
    return rp.can_fetch(UA, URL) and rp.can_fetch("*", URL)

def key(r):
    return (r["lat"], r["lon"], r["gemeldet"])

def last_keys(path):
    if not os.path.exists(path):
        return set()
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not rows:
        return set()
    last = rows[-1]["abruf"]
    return {key(r) for r in rows if r["abruf"] == last and "lat" in r}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--html")
    a = ap.parse_args()
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if a.html:
        page = open(a.html, encoding="utf-8").read()
    else:
        if not allowed():
            print("robots.txt sperrt den Abruf - nichts abgerufen.")
            return
        page = fetch(URL)
    every = parse(page)
    rows = [dict({"quelle": "rockantenne", "abruf": now}, **r, url=URL) for r in every if in_area(r)]
    print(f"{len(every)} Eintraege auf der Seite, davon {len(rows)} im Gebiet NI/HH/SH.")
    if not a.out:
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        return
    if not rows:
        rows = [{"quelle": "rockantenne", "abruf": now, "anzahl": 0, "url": URL}]
    elif {key(r) for r in rows} == last_keys(a.out):
        print("gleich wie beim letzten Lauf, nichts gespeichert.")
        return
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"gespeichert in {a.out}.")

if __name__ == "__main__":
    try:
        main()
    except ValueError as e:
        print("FEHLER:", e)
        sys.exit(1)
