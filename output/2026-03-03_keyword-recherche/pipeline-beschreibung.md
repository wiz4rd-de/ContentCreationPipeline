# SEO Content Pipeline — Detaillierter Ablauf

## Eingaben zu Beginn

Bevor die Pipeline startet, werden folgende Informationen abgefragt:

1. **Seed Keyword / Thema** (Pflicht)
2. **Eigene Domain** (optional — wird aus der Konkurrenzanalyse ausgeschlossen)
3. **Business-Kontext** — Was bietest du an? Wer ist die Zielgruppe?
4. **Content-Ziele** — Traffic, Leads, Authority, Conversions?
5. **Brand Voice / Tonalität** (optional)

---

## Step 1: Keyword Research

- Lädt die API-Konfiguration aus `api.env` (unterstützt DataForSEO, SEMrush, Ahrefs oder generische APIs)
- Ruft die Keyword-API mit dem Seed Keyword auf
- Extrahiert pro Keyword: **Suchvolumen, Keyword Difficulty, CPC, Search Intent**
- Klassifiziert den Intent (informational, commercial, transactional, navigational)
- **Gruppiert Keywords in thematische Cluster** mit jeweils einem Primary Keyword und Supporting Keywords
- Speichert als `keywords-<slug>.json`
- **Pause: Ergebnisse werden dem User gezeigt** — er kann den Keyword-Fokus anpassen, bevor es weitergeht

## Step 2: Competitor Analysis

- Nutzt die Primary Keywords aus Step 1
- Ruft SERP-Daten ab (Top-10-Ergebnisse pro Keyword)
- **Analysiert jede Konkurrenz-Seite** per WebFetch/curl und extrahiert:
  - Title Tag, Meta Description, Heading-Struktur (H1–H3)
  - Geschätzte Wortanzahl, Content-Format (Listicle, Guide, How-To etc.)
  - Abgedeckte Themen/Unterthemen, einzigartige Winkel
- Erstellt eine **Vergleichsmatrix** aller Wettbewerber
- Identifiziert: gemeinsame Themen (Table Stakes), **Content Gaps**, Differenzierungschancen, Schwächen
- Speichert als `competitors-<slug>.json`
- **Pause: Competitive Landscape wird gezeigt** — User kann weitere Wettbewerber analysieren lassen

## Step 3: Content Strategy

- Liest Keyword- und Competitor-Daten aus Steps 1–2
- Bewertet jeden Keyword-Cluster nach: Suchvolumen, Wettbewerb, Business-Relevanz, Content-Gap-Score
- Berechnet einen **Opportunity Score**: `(volume × relevance × gap_score) / difficulty`
- Empfiehlt pro Cluster: Content-Typ, Ziel-Keywords, Differenzierungs-Winkel, Funnel-Stage, Priorität
- Organisiert in einen **priorisierten Content-Kalender**:
  1. Quick Wins (niedrige Difficulty, schnell produzierbar)
  2. Strategische Pillar Pages (hohes Volumen, Topical Authority)
  3. Long-Tail Content (unterstützende Cluster-Inhalte)
- Speichert als `strategy-<slug>.json`
- **Pause: User wählt, welches Content Piece gebrieft werden soll**

## Step 4: Content Briefing

- Scannt `templates/` nach verfügbaren Content-Templates und lässt den User eines wählen (oder generisches Briefing)
- Lädt alle Pipeline-Daten (Keywords, Competitors, Strategy)
- **Mit Template:** Folgt exakt der Template-Struktur (Sektionen, Zeichenlimits, CMS-Elemente wie Infoboxen, Image Walls etc.)
- **Ohne Template:** Erstellt ein generisches Briefing mit: Meta-Daten, Zielgruppe, Search Intent Analyse, Titel-Vorschläge, detailliertem Outline (H1–H3), Key Points, Competitor Reference, interne Verlinkung, CTAs, SEO-Checkliste, Meta Description
- Speichert als `brief-<slug>.md`
- **Pause: Briefing wird zur Review gezeigt**

## Step 5: Content Draft (optional)

- User wird gefragt, ob direkt ein Artikel-Entwurf erstellt werden soll
- Falls ja: Lädt das Briefing + Keyword- und Competitor-Daten
- Schreibt den vollständigen Artikel gemäß Briefing-Outline
- **SEO-Optimierung:** Primary Keyword in Titel, H1, ersten 100 Wörtern; Secondary Keywords natürlich verteilt
- **Qualitätskontrolle:** Kurze Absätze, variierende Satzlängen, konkrete Beispiele, kein Filler
- **Self-Review** gegen SEO-Checkliste (Keyword-Platzierung, Wortanzahl ±10%, CTAs vorhanden)
- Markiert offene Punkte mit `<!-- TODO -->` und zu verifizierende Fakten mit `<!-- VERIFY -->`
- Speichert als `draft-<slug>.md`

---

## Endergebnis im Output-Ordner

```
output/YYYY-MM-DD_<seed-keyword-slug>/
├── keywords-<slug>.json      ← Keyword-Recherche mit Clustern
├── competitors-<slug>.json   ← Wettbewerbsanalyse
├── strategy-<slug>.json      ← Priorisierte Content-Strategie
├── brief-<slug>.md           ← Detailliertes Content Briefing
└── draft-<slug>.md           ← Fertiger Artikel-Entwurf (optional)
```

Jeder Schritt hat einen **User-Checkpoint** — du kannst den Fokus anpassen, bevor der nächste Schritt läuft. Die Pipeline ist also nicht vollautomatisch, sondern interaktiv mit Freigabeschleifen.
