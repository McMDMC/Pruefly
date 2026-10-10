"""Prompts (German). The model only reads structure and invents words; maths is done in code."""
from __future__ import annotations

import json

DERENDER_SYSTEM = (
    "Du bist ein präziser Analysator für Grundschul-Arbeitsblätter und Klassenarbeiten (Klasse 1-4, "
    "Baden-Württemberg). Du antwortest ausschließlich mit einem einzigen gültigen JSON-Objekt, ohne Markdown "
    "und ohne Erklärung."
)

DERENDER_RULES = """Lies das Foto des Arbeitsblatts und gib es als JSON (IR) zurück.

REGELN FÜR PLATZHALTER (sehr wichtig):
- GEGEBEN: Zahlen/Wörter, die auf dem Blatt vorgegeben sind -> werden später neu gewürfelt. Schreibe sie als {name} in "tpl" und den Wert in "giv".
- LÜCKE: alles, was das Kind ausfüllen soll (leere Kästchen, Linien, Punkte) -> immer genau "_". NIEMALS eine Lösung eintragen, auch wenn handschriftlich schon etwas steht.
- FIX: Überschriften, Anweisungen, Bilder-Beschreibungen -> unverändert in title/instr.
- Rechne NICHT. Trage keine Ergebnisse ein.

SCHEMA:
{"title": str, "subject": "mathe"|"deutsch"|"sachunterricht", "grade": 1-4,
 "tasks": [{"id": "t1", "type": <Typ>, "title": str, "instr": str, "c": {...}}]}

TYPEN und Inhalt "c":
- eq_grid: {"items":[{"tpl":"{a} + {b} = _","giv":{"a":7,"b":5}}]}  Operatoren + - × : ; genau ein "_" je Gleichung, z.B. "{a} + _ = {r}" mit giv {"a":6,"r":14}.
- table_vn: Vorgänger/Zahl/Nachfolger. {"rows":[{"vor":"_","zahl":45,"nach":"_"}]}  genau eine Zahl je Zeile, Rest "_".
- alphabet_errors: Buchstabenreihen mit einem Fehler. {"rows":[{"seq":["D","E","X","G","H"]}]}
- word_sort: Wörter alphabetisch ordnen. {"words":["Haus","Apfel","Ball"]}
- chain: Rechenkette. {"chains":[{"start":7,"steps":["+5","-3","+8"]}]}
- number_line: {"from":0,"to":20,"ask":[4,13],"given":[10]}  ask = gesuchte Stellen, given = beschriftete.
- measure: Längen messen. {"items":[{"label":"Bleistift","len":7,"unit":"cm"}]}
- draw_lines: {"cols":6,"rows":4,"segments":[[[0,0],[2,3]]]}
- shapes: Formen zählen. {"items":[{"shape":"circle"|"square"|"triangle"|"rect","count":4}]}
- info_box: Merkkasten. {"title":"Würfel","facts":{"Ecken":8,"Kanten":12,"Flächen":6}}
- gap_text: {"sentences":[{"s":"Das Kind _ im Garten.","a":"spielt"}]}
- text: {"text":"..."}  Fließtext oder Aufgabe, die in keinen anderen Typ passt.

Gib nur Aufgaben zurück, die du sicher erkennst. Bei Unsicherheit nimm type "text" mit dem sichtbaren Wortlaut."""


def derender_prompt() -> str:
    return DERENDER_RULES


TRANSFORM_SYSTEM = (
    "Du erstellst Parallelversionen von Grundschul-Aufgaben (Klasse 1-4, Baden-Württemberg). "
    "Du antwortest ausschließlich mit einem einzigen gültigen JSON-Objekt, ohne Markdown."
)


def transform_prompt(subset: dict, grade: int, variant_hint: str = "") -> str:
    ir_json = json.dumps(subset, ensure_ascii=False)
    return f"""Erzeuge eine NEUE Version dieser Aufgaben für Klasse {grade}. {variant_hint}

REGELN:
- Gleiche Struktur: gleiche Aufgaben-IDs, gleiche Typen, gleiche Anzahl Wörter/Sätze, gleiche Lückenpositionen ("_" bleibt "_").
- Alle Inhalte (Wörter, Sätze) sind NEU: andere Wörter als im Original, gleiche Schwierigkeit und Wortart/Thema, altersgerecht.
- word_sort: nur einzelne deutsche Wörter (nur Buchstaben), keine Duplikate, ähnliche Länge, gleiche Anzahl.
- gap_text: genau ein "_" je Satz; "a" ist das fehlende Wort; kurze, einfache Sätze.
- Titel und Anweisungen unverändert lassen.

Gib das vollständige JSON im selben Schema zurück: {{"tasks":[...]}}

<<<IR
{ir_json}
IR>>>"""
