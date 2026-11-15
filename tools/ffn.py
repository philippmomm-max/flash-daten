#!/usr/bin/env python3
"""Sammler radio ffn: liest die Blitzer-Meldungen der Verkehrsseite und haengt sie als JSON-Zeilen an.

Nur Python-Standardbibliothek. Prueft vor dem Abruf die robots.txt; sperrt sie die Seite, wird nichts
abgerufen (Lauf endet mit Hinweis, ohne Fehler). Aenderung des Seitenaufbaus -> Fehler (Lauf rot).

Aufruf: ffn.py --out DATEI.jsonl   (haengt an; Doppelte zum letzten Lauf werden uebersprungen)
        ffn.py --html DATEI        (Test mit gespeicherter Seite, gibt Zeilen aus)
"""
import argparse, datetime, html.parser, json, os, re, sys, urllib.request, urllib.robotparser

URL = "https://www.ffn.de/programm/flitzer-blitzer-staus-und-schulausfaelle/aktuelle-verkehrsmeldungen/"
ROBOTS = "https://www.ffn.de/robots.txt"
UA = "FlashSammler/1.0 (privat, einmal taeglich; github.com/philippmomm-max/flash-daten)"
BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "section", "article", "ul", "ol", "tr"}

class Text(html.parser.HTMLParser):
    """Seitentext als Zeilen; Bloecke (Absatz, Ueberschrift, Liste) werden zu eigenen Zeilen."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.cur, self.skip = [], [], 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in BLOCK:
            self.flush()
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
        if tag in BLOCK:
            self.flush()
    def handle_data(self, d):
        if not self.skip:
            self.cur.append(d)
    def flush(self):
        t = re.sub(r"\s+", " ", "".join(self.cur)).strip()
        if t:
            self.lines.append(t)
        self.cur = []

def parse(page):
    """Liefert (stand_von, [Meldungstexte]). Wirft ValueError, wenn der Blitzer-Abschnitt fehlt."""
    p = Text(); p.feed(page); p.flush()
    lines = p.lines
    try:
        i = next(n for n, l in enumerate(lines) if l == "Blitzer")
    except StopIteration:
        raise ValueError("Abschnitt 'Blitzer' nicht gefunden (Seitenaufbau geaendert?)")
    stand, out = "", []
    for l in lines[i + 1:]:
        if l.startswith("Teilt diese Seite") or l in ("Autobahnen", "Staus", "Blitzer"):
            break
        m = re.match(r"Stand von:?\s*(.+)", l)
        if m:
            stand = m.group(1).strip()
            continue
        if re.match(r"^-?\s*Danke\b", l):
            continue
        out.append(l)
    return stand, out

def fields(text):
    kreis = re.search(r"\bKreis(?:es)? ([A-ZÄÖÜ][\wäöüß\-]+(?:[ -][A-ZÄÖÜ][\wäöüß\-]+)*)", text)
    ort = re.search(r"\b(?:in|In) ([A-ZÄÖÜ][\wäöüß\-\.]+(?: [A-ZÄÖÜ][\wäöüß\-]+)*)", re.sub(r"Im Kreis [^,]+,", "", text))
    if "beiden Richtungen" in text:
        richtung = "beide"
    else:
        r = re.search(r"Richtung ([A-ZÄÖÜ][\wäöüß\-]+(?: [A-ZÄÖÜ][\wäöüß\-]+)*)", text)
        richtung = r.group(1) if r else ""
    strasse = re.search(r"\b((?:A|B|L|K) ?\d+[a-z]?)\b", text)
    return {
        "kreis": kreis.group(1) if kreis else "",
        "ort": re.split(r" (?:Richtung|Höhe|Hoehe|Ortsausgang|Ortseingang)\b", ort.group(1))[0] if ort else "",
        "richtung": richtung,
        "strasse": strasse.group(1) if strasse else "",
    }

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

def last_texts(path):
    """Meldungstexte des letzten gespeicherten Laufs (fuer die Doppelten-Pruefung)."""
    if not os.path.exists(path):
        return set()
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not rows:
        return set()
    last = rows[-1]["abruf"]
    return {r.get("text", "") for r in rows if r["abruf"] == last}

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
    stand, texts = parse(page)
    rows = [dict({"quelle": "ffn", "abruf": now, "stand_von": stand, "text": t, "url": URL}, **fields(t)) for t in texts]
    if not rows:
        rows = [{"quelle": "ffn", "abruf": now, "stand_von": stand, "anzahl": 0, "url": URL}]
    if not a.out:
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        return
    if texts and {r["text"] for r in rows} == last_texts(a.out):
        print(f"{len(texts)} Meldungen, Stand {stand}: gleich wie beim letzten Lauf, nichts gespeichert.")
        return
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(texts)} Meldungen, Stand {stand}: gespeichert in {a.out}.")

if __name__ == "__main__":
    try:
        main()
    except ValueError as e:
        print("FEHLER:", e)
        sys.exit(1)
