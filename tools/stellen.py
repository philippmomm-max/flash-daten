#!/usr/bin/env python3
"""Fasst die Radiomeldungen der letzten 7 Tage zu radio-stellen.json fuer die App Flash zusammen.

- ROCK ANTENNE: Koordinaten kommen von der Seite; Meldungen an fast gleicher Stelle (~100 m) werden eins.
- radio ffn: Ort und Kreis aus dem Meldungstext werden ueber Nominatim (OpenStreetMap) in Koordinaten
  umgesetzt, hoechstens 1 Anfrage pro Sekunde, Ergebnisse im Zwischenspeicher cache/geocode.json.
  Die Lage ist damit nur ungefaehr (Ortsmitte).
Format: [{"id":"...","name":"...","lat":..,"lon":..,"source":"ffn|rockantenne"}]
Nur Python-Standardbibliothek.
"""
import datetime, glob, hashlib, json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rockantenne import inside  # noqa: E402

DAYS = 7
UA = "FlashSammler/1.0 (privat; github.com/philippmomm-max/flash-daten)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

def rows(pattern, since):
    out = []
    for path in sorted(glob.glob(pattern)):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("abruf", "") >= since:
                    out.append(r)
    return out

def geocode(query, cache, state):
    if query in cache:
        return cache[query]
    wait = 1.1 - (time.time() - state["last"])
    if wait > 0:
        time.sleep(wait)
    url = NOMINATIM + "?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "de"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            hits = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("Geocodierung fehlgeschlagen:", query, e)
        state["last"] = time.time()
        return None  # nicht zwischenspeichern, beim naechsten Lauf erneut
    state["last"] = time.time()
    res = None
    if hits:
        lat, lon = round(float(hits[0]["lat"]), 5), round(float(hits[0]["lon"]), 5)
        if inside(lon, lat):
            res = [lat, lon]
    cache[query] = res
    return res

def main(root="."):
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {}

    for r in rows(os.path.join(root, "data/rockantenne/*.jsonl"), since):
        if "lat" not in r:
            continue
        k = (round(r["lat"], 3), round(r["lon"], 3))
        ort, strasse = r.get("ort", ""), r.get("strasse", "")
        name = ort if strasse and strasse in ort else ", ".join(x for x in (ort, strasse) if x)
        out.setdefault(("ra",) + k, {"id": "ra-%.3f_%.3f" % k, "name": name,
                                      "lat": r["lat"], "lon": r["lon"], "source": "rockantenne"})

    cache_path = os.path.join(root, "cache/geocode.json")
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    state = {"last": 0.0}
    missing = 0
    for r in rows(os.path.join(root, "data/ffn/*.jsonl"), since):
        ort, kreis = r.get("ort", ""), r.get("kreis", "")
        if not ort:
            continue
        pos = None
        for q in ([f"{ort}, Landkreis {kreis}, Niedersachsen"] if kreis else []) + [f"{ort}, Niedersachsen"]:
            pos = geocode(q, cache, state)
            if pos:
                break
        if not pos:
            missing += 1
            continue
        key = "|".join((ort, kreis, r.get("strasse", ""), r.get("richtung", "")))
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        out.setdefault(("ffn", h), {"id": "ffn-" + h, "name": r.get("text", "")[:120],
                                     "lat": pos[0], "lon": pos[1], "source": "ffn"})

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0, sort_keys=True)
    result = sorted(out.values(), key=lambda s: s["id"])
    with open(os.path.join(root, "radio-stellen.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    n_ra = sum(1 for s in result if s["source"] == "rockantenne")
    print(f"radio-stellen.json: {len(result)} Stellen (ROCK ANTENNE {n_ra}, ffn {len(result) - n_ra}), "
          f"ffn ohne Koordinaten: {missing}")

if __name__ == "__main__":
    main()
