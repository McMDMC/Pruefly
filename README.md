# Prüfly

Parallelarbeiten für die Grundschule (Kl. 1–4, BW): Foto vom Test → geprüfte neue Variante als PDF, plus Lösungsblatt.

```
Foto → Derender (LLM Vision) → IR → Regenerate (Code) / Wörter (LLM, validiert) → Render → PDF
```

**Garantien (im Code erzwungen, nicht per Prompt erhofft):** Lücken bleiben Lücken · Ergebnisse werden berechnet, nie vom Modell übernommen · Zahlenraum der Klassenstufe wird eingehalten · Struktur der Vorlage bleibt erhalten · keine Fotos/Arbeitsblätter werden gespeichert.

Details und Roadmap: [PLAN.md](PLAN.md).

## Lokal starten
```bash
pip install -e ".[dev]"
cp .env.example .env   # ANTHROPIC_API_KEY eintragen
PRUEFLY_ENV=dev uvicorn pruefly.main:app_factory --factory --reload   # http://localhost:8000
pytest
```
Ohne API-Key testen: `PRUEFLY_DERENDER_PROVIDERS=fake PRUEFLY_TRANSFORM_PROVIDERS=fake`.

## Modelle
`ModelRouter` probiert pro Aufgabe die Provider in der konfigurierten Reihenfolge (Anthropic → Gemini/Vertex); Fallback bei Aufruf- **und** Parse-Fehler. Wechsel = Env-Variable, kein Code.

## Deploy (Cloud Run, EU)
```bash
PROJECT=<gcp-projekt> ./deploy/deploy.sh
```
Fragt Zugangscode + API-Key ab (Secret Manager) und gibt die URL aus. Ohne `PRUEFLY_ACCESS_CODE` antwortet die API in `prod` mit 503 (fail closed).

## Offen
- `PRUEFLY_GEMINI_MODEL` gegen die Vertex-Modellliste prüfen (Fallback-Provider).
- Verlagsmaterial als Vorlage: entschieden – nur privater Gebrauch (Joanna), keine Weitergabe, kein kommerzieller Einsatz vor rechtlicher Klärung.
- Schülernamen auf Fotos: UI warnt, technischer Schutz fehlt noch.
