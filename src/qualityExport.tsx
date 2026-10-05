import { renderToStaticMarkup } from "react-dom/server";
import { CadenceChart, QualityBars, QualityHeatmap } from "./QualityCharts";
import type { QualityReport, QualityRow } from "./types";
import { QualityBrief } from "./qualityBrief";

export function qualityExport(
  format: string,
  report: QualityReport,
  metricId: string,
  delta: boolean,
  chapterIds: string[],
  appendix = false,
  chapterOverview: QualityRow[] = [],
) {
  const metric =
    report.catalog.metrics.find((m) => m.id === metricId) ||
    report.catalog.metrics[0];
  const compared =
    report.scope === "chapters"
      ? report.rows.filter((r) => chapterIds.includes(r.id))
      : report.rows;
  const payload = {
    generatedAt: new Date().toISOString(),
    ...report,
    chapterOverview,
    display: {
      metricId: metric.id,
      delta,
      comparedIds: compared.map((r) => r.id),
      appendix,
    },
  };
  if (format === "json") return JSON.stringify(payload, null, 2);
  if (format === "csv") {
    const escape = (value: unknown) =>
      '"' +
      (typeof value === "string"
        ? value.replace(/^\s*[=+\-@]/, "'$&")
        : String(value ?? "")
      ).replaceAll('"', '""') +
      '"';
    const rows: unknown[][] = [
      [
        "Text",
        "Dokument-ID",
        "Kapitelindex (0-basiert)",
        "Sprache",
        "Wörter",
        "Methodenversion",
        "Bereich",
        "Kennzahl-ID",
        "Kennzahl",
        "Art",
        "Einheit",
        "Wert",
        "Nicht verfügbar",
        "Baseline",
        "Baseline-ID",
        "Baseline-Wert",
        "Referenzbasis",
        "Wörter je Referenzausschnitt",
        "Anzahl Referenzausschnitte",
        "Referenzband unten",
        "Referenzband oben",
        "Delta",
        "Delta nicht verfügbar",
        "Wortgrenze lange Sätze",
      ],
    ];
    report.rows.forEach((row) =>
      report.catalog.metrics.forEach((m) =>
        rows.push([
          row.title,
          row.documentId,
          row.chapterIndex,
          row.quality.language,
          row.quality.words,
          row.quality.version,
          m.group,
          m.id,
          m.label,
          m.kind,
          m.unit,
          row.quality.values[m.id],
          row.quality.reasons[m.id] || "",
          report.baseline?.name,
          report.baseline?.id,
          row.comparison?.values[m.id],
          row.comparison?.basis,
          row.comparison?.words,
          row.comparison?.windows,
          row.comparison?.bands[m.id]?.low,
          row.comparison?.bands[m.id]?.high,
          row.delta?.values[m.id],
          row.delta?.reasons[m.id] || "",
          row.quality.longSentenceWords,
        ]),
      ),
    );
    return "\uFEFF" + rows.map((row) => row.map(escape).join(";")).join("\r\n");
  }
  const display = (v: number | null | undefined) =>
    v == null ? "—" : v.toLocaleString("de-DE", { maximumFractionDigits: 2 });
  return (
    "<!doctype html>" +
    renderToStaticMarkup(
      <html lang="de">
        <head>
          <meta charSet="utf-8" />
          <meta
            name="bookanalyzer-baseline-id"
            content={report.baseline?.id || ""}
          />
          <title>Bookalyzer · Qualitätslabor</title>
          <meta
            httpEquiv="Content-Security-Policy"
            content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"
          />
          <style>
            {
              "*{box-sizing:border-box}body{font:12px/1.5 Arial,sans-serif;color:#343247;max-width:1050px;margin:30px auto;padding:0 24px}h1{font:34px Georgia,serif}h2{font-size:21px;margin:24px 0 8px}h3{font-size:15px}p{color:#666278}svg{width:100%;max-height:330px}table{width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed}td,th{padding:7px;border-bottom:1px solid #e3e1eb;text-align:left;overflow-wrap:anywhere}thead{display:table-header-group}tr{break-inside:avoid}th small{display:block;font-weight:normal}.tick{font-size:11px;fill:#78738a}.axis-label{font-size:12px;fill:#443e56}.quality-na{margin-left:4px}.quality-heatmap i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}.chart-panel{break-inside:avoid}.fine{font-size:10px;overflow-wrap:anywhere}mark{background:#eee8fb}a{color:#6850b3}.method{margin-top:16px}.method p{margin:3px 0}li{margin:5px 0}@page{size:A4 landscape;margin:14mm}@media print{body{margin:0;padding:0}h2,h3{break-after:avoid}svg{max-height:230px}.new-group{break-before:page}}"
            }
          </style>
          <style>{`.brief-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.brief-card{padding:10px;border:1px solid #dedbe8;border-top:3px solid #7185a0;border-radius:6px}.brief-card.fit{border-top-color:#238474}.brief-card.review{border-top-color:#bb8739}.brief-card.unknown{border-top-color:#a2a5ad}.brief-card strong,.brief-card small,td small{display:block}.brief-card small{font-size:10px;color:#6a667a}.brief-card span{font-size:10px}.brief-card p{margin:6px 0;color:#343247}.brief-text{break-before:page}.brief-text:first-of-type{break-before:auto}.brief svg{max-height:110px}.brief blockquote{font-size:10px;margin:4px 0 8px;padding:6px 10px;background:#f7f5fc}.brief-chapter-list{break-before:page}@media print{.brief-card p{font-size:11px}.brief .fine{font-size:9px}}`}</style>
          <style>
            {
              "body{font-size:10.5px;line-height:1.45}h1{font-size:30px;margin:12px 0}h2{font-size:19px;margin:18px 0 8px}h3{font-size:12px;margin:10px 0 4px}.method-grid{columns:2;column-gap:28px;margin-top:14px}.method{break-inside:avoid;margin:0 0 12px}.method p{font-size:10px}.fine{font-size:9px}td,th{padding:6px}li{break-inside:avoid}.chart-panel svg{max-height:180px}@media print{.chart-panel svg{max-height:160px}p{orphans:3;widows:3}}"
            }
          </style>
          <style>{`.brief .qo-deviations h2{font-size:13px;margin:10px 0 4px}.brief .qo-deviations>p{font-size:9px;margin:3px 0}.brief .qo-deviation{break-inside:avoid;margin-top:8px}.brief .qo-deviation h3{margin:5px 0 3px}.brief .qo-deviation p{font-size:10px;margin:3px 0}.brief .qo-deviation svg{height:90px;max-height:90px}.brief .qo-deviation .quality-fine{font-size:8px}.brief>p{margin:5px 0}`}</style>
        </head>
        <body>
          <p>BOOKALYZER / QUALITÄTSLABOR · Version {report.catalog.version}</p>
          <QualityBrief
            report={report}
            rows={compared}
            chapterOverview={chapterOverview}
          />
          {appendix && (
            <>
              <h1>Qualitäten sichtbar machen.</h1>
              <p>{report.catalog.note}</p>
              <p>
                {report.rows.length}{" "}
                {report.scope === "chapters" ? "Kapitel" : "Texte"} ·{" "}
                {report.catalog.metrics.length} Kennzahlen ·{" "}
                {delta
                  ? "Diagramme zeigen Abweichungen zur Baseline."
                  : "Diagramme zeigen absolute Messwerte."}
              </p>
              {report.baseline && (
                <p>
                  Baseline: <b>{report.baseline.name}</b> ·{" "}
                  {report.baseline.wordCount.toLocaleString("de-DE")} Wörter ·{" "}
                  {report.baseline.createdAt}
                  <br />
                  {report.baseline.derivation}
                </p>
              )}
              <div className="chart-panel">
                <h2>{metric.label}</h2>
                <p>
                  {delta
                    ? "Null = gleicher Messwert. Plus/Minus ist kein Qualitätsurteil."
                    : "Gleiche Einheit für alle Texte."}{" "}
                  {metric.unit} · {metric.note}
                </p>
                <QualityBars rows={compared} metric={metric} delta={delta} />
              </div>
              {report.scope === "chapters" && (
                <>
                  <h2>Alle Kapitel gegen die Baseline</h2>
                  <p>
                    Diagramme und Merkmalsmatrizen enthalten {compared.length}{" "}
                    ausgewählte Kapitel. Diese Liste enthält alle Kapitel für{" "}
                    {metric.label}. CSV und JSON enthalten sämtliche Kennzahlen
                    für sämtliche Kapitel.
                  </p>
                  <table>
                    <thead>
                      <tr>
                        <th>Kapitel</th>
                        <th>Wörter</th>
                        <th>{metric.label}</th>
                        <th>Δ Baseline</th>
                        <th>Hinweis</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.rows.map((row) => (
                        <tr key={row.id}>
                          <th>{row.title}</th>
                          <td>{row.quality.words}</td>
                          <td>{display(row.quality.values[metric.id])}</td>
                          <td>{display(row.delta?.values[metric.id])}</td>
                          <td>
                            {row.quality.reasons[metric.id] ||
                              row.delta?.reasons[metric.id] ||
                              ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              {report.catalog.groups.map((group) => (
                <section className="new-group" key={group.id}>
                  <h2>{group.label}</h2>
                  <p>
                    Dunklere Zellen:{" "}
                    {delta
                      ? "größere absolute Differenz zur Baseline"
                      : "höherer Wert innerhalb der Zeile, relativ zur Auswahl"}
                    . Keine Gut-/Schlecht-Skala. — bedeutet nicht verfügbar.
                  </p>
                  <QualityHeatmap
                    rows={compared}
                    metrics={report.catalog.metrics.filter(
                      (m) => m.group === group.id,
                    )}
                    delta={delta}
                  />
                  <div className="method-grid">
                    {report.catalog.metrics
                      .filter((m) => m.group === group.id)
                      .map((m) => (
                        <div className="method" key={m.id}>
                          <h3>
                            {m.label} · {m.unit}
                          </h3>
                          <p>
                            {m.formula}. {m.note} Mindestlänge: {m.minWords}{" "}
                            Wörter.
                          </p>
                          {compared
                            .filter((row) =>
                              delta
                                ? row.delta?.reasons[m.id]
                                : row.quality.reasons[m.id],
                            )
                            .map((row) => (
                              <p key={row.id} className="fine">
                                {row.title}:{" "}
                                {delta
                                  ? row.delta?.reasons[m.id]
                                  : row.quality.reasons[m.id]}
                              </p>
                            ))}
                        </div>
                      ))}
                  </div>
                </section>
              ))}
              {compared.map((row) => (
                <section className="new-group" key={row.id}>
                  <h2>{row.title} · Rhythmus und Fundstellen</h2>
                  <p>
                    {row.quality.words.toLocaleString("de-DE")} Wörter ·{" "}
                    {row.quality.sentences.toLocaleString("de-DE")} Sätze ·
                    Sprache {row.quality.language} · Wortgrenze für lange Sätze:{" "}
                    {row.quality.longSentenceWords}
                  </p>
                  <div className="chart-panel">
                    <CadenceChart row={row} />
                    <p>
                      Linie: mittlere Satzlänge; Band: Minimum bis Maximum je
                      Gruppe. Bis zu 160 Gruppen in Lesereihenfolge.
                    </p>
                  </div>
                  <h3>Beispielhafte Fundstellen</h3>
                  <p>
                    Erste sechs gespeicherte Hinweise dieses Textes.
                    Vollständige Regelübersicht und bis zu sechs Stellen je
                    Regel im JSON-Bericht.
                  </p>
                  <ol>
                    {row.quality.evidence.slice(0, 6).map((e, i) => (
                      <li key={i}>
                        <b>
                          {
                            report.catalog.metrics.find(
                              (m) => m.id === e.metric,
                            )?.label
                          }
                        </b>{" "}
                        · {e.label}
                        <p>
                          …{e.before}
                          <mark>
                            {e.text}
                            {e.truncated ? "…" : ""}
                          </mark>
                          {e.after}…
                        </p>
                      </li>
                    ))}
                  </ol>
                </section>
              ))}
              <section className="new-group">
                <h2>Methodik und Nachvollziehbarkeit</h2>
                <p>
                  Wortformen ohne Lemmatisierung; regelbasierte Satzgrenzen und
                  Absätze anhand von Leerzeilen. Silbenzahlen sind Näherungen
                  aus Vokalgruppen, nicht aus Aussprachewörterbüchern. Die
                  Gesamttexte werden aus gespeicherten Segmenten mit Leerzeilen
                  verbunden; zusätzliche Segmentgrenzen können Absatzwerte
                  beeinflussen. Kapitel verwenden die ursprünglichen
                  Abschnittstexte. Die Mindesttextlängen sind Anzeigegrenzen,
                  keine Validierung. Genres und Textlängen beeinflussen die
                  Messwerte. Es erfolgt keine Prüfung auf Faktentreue, Grammatik
                  oder semantische Kohärenz.
                </p>
                <p>
                  Die Wortlisten sind im Qualitätslabor und im JSON-Export
                  vollständig enthalten. Prozentdeltas sind Prozentpunkte;
                  andere Deltas behalten die Einheit. Bei unterschiedlichen
                  Sprachen oder Wortgrenzen werden nicht vergleichbare Deltas
                  ausgelassen.
                </p>
                {report.catalog.sources.map((s) => (
                  <p key={s.id}>
                    <a href={s.url}>{s.label}</a>
                  </p>
                ))}
                {report.baseline && (
                  <p className="fine">
                    Baseline-ID: {report.baseline.id}
                    <br />
                    Baseline-Text SHA-256: {report.baseline.textSha256}
                    <br />
                    {Object.entries(report.baseline.hashes).map(
                      ([key, value]) => (
                        <span key={key}>
                          {key}: {value}
                          <br />
                        </span>
                      ),
                    )}
                  </p>
                )}
                <p className="fine">Erstellt: {payload.generatedAt}</p>
              </section>
            </>
          )}
        </body>
      </html>,
    )
  );
}
