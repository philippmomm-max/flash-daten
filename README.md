# flash-daten

Öffentliche Daten für die private Android-App **Flash** (Blitzer-Warner für Beifahrer, NI · SH · HH).

## radio-stellen.json
Mögliche Blitzer an einer Stelle aus Radiomeldungen der **letzten 7 Tage**. Die App lädt die Datei beim
Start der Überwachung und sagt diese Stellen als „Möglicher Blitzer in der Nähe“ an.

Format: `[{"id":"…","name":"…","lat":…,"lon":…,"source":"ffn|rockantenne"}]`

| Quelle | Seite | Lage |
|---|---|---|
| radio ffn | ffn.de – Aktuelle Verkehrsmeldungen, Abschnitt „Blitzer“ | ungefähr: Ort aus dem Meldungstext, über Nominatim (© OpenStreetMap-Mitwirkende, ODbL) in Koordinaten umgesetzt |
| ROCK ANTENNE Hamburg | rockantenne.hamburg – Aktuelle Blitzer | Koordinaten von der Seite; nur Einträge im groben Umriss von NI, HH und SH |

## Ablauf
Der Workflow `.github/workflows/sammler.yml` läuft einmal täglich um 06:00 UTC (07:00 Winterzeit):
1. `tools/ffn.py` und `tools/rockantenne.py` prüfen die robots.txt der Sender, rufen je eine Seite ab und
   hängen die Meldungen an `data/<quelle>/<JJJJ-MM>.jsonl` an.
2. `tools/stellen.py` erzeugt daraus `radio-stellen.json` (Zwischenspeicher der Ortsabfragen: `cache/geocode.json`).

Nur Python-Standardbibliothek. Die Rechte an den Meldungstexten liegen bei den Sendern; gespeichert werden
sie hier nur zur Nachvollziehbarkeit der abgeleiteten Stellen.
