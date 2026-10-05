import { QualityBars } from "./QualityCharts";
import { STATUS, overviewCards } from "./qualityPresentation";
import { QualityDeviations } from "./QualityDeviations";
import type { QualityReport, QualityRow } from "./types";

export function QualityBrief({
  report,
  rows,
  chapterOverview = [],
}: {
  report: QualityReport;
  rows: QualityRow[];
  chapterOverview?: QualityRow[];
}) {
  const metric = report.catalog.metrics.find((m) => m.id === "longSentences")!;
  return (
    <section className="brief">
      <h1>Dein Text auf einen Blick.</h1>
      <p>Schreibziele, passende Vergleiche und konkrete nächste Schritte.</p>
      {rows.map((row) => (
        <article className="brief-text" key={row.id}>
          <h2>{row.title}</h2>
          <p>
            {row.summary.profile} · {row.quality.words.toLocaleString("de-DE")}{" "}
            Wörter · Sprache: {row.quality.language} · Methodenversion{" "}
            {row.quality.version}
          </p>
          <div className="brief-cards">
            {overviewCards(row, chapterOverview).map((c) => (
              <div className={"brief-card " + c.status} key={c.id}>
                <strong>{c.label}</strong>
                <small>{STATUS[c.status]}</small>
                <p>{c.title}</p>
                <span>
                  {c.id === "flow"
                    ? `Ziel: höchstens ${row.quality.longSentenceShare} % über ${row.quality.longSentenceWords} Wörtern`
                    : c.id === "vocabulary" && c.value != null
                      ? `${c.value.toLocaleString("de-DE", { maximumFractionDigits: 1 })} verschiedene Wortformen / 100 Wörter`
                      : c.id === "repetition"
                        ? "Gleiche Sätze ab 5 Wörtern und Absätze ab 12 Wörtern"
                        : c.note ||
                          "Deskriptiver Vergleich mit Referenz oder übrigen Kapiteln"}
                </span>
              </div>
            ))}
          </div>
          {(!row.summary.deviations.length ||
            row.summary.cards.find((c) => c.id === "flow")?.status ===
              "review") && (
            <>
              <h3>Lange Sätze und dein Schreibziel</h3>
              <QualityBars rows={[row]} metric={metric} showGoals compact />
              <p className="fine">
                Grün gestrichelt: dein Höchstanteil von{" "}
                {row.quality.longSentenceShare} % an Sätzen mit mehr als{" "}
                {row.quality.longSentenceWords} Wörtern. Gold: passender
                Referenzmedian, Band: mittlere 50 % ab drei Ausschnitten.
              </p>
            </>
          )}
          {row.comparison && (
            <p className="fine">
              Referenz: {row.comparison.name}. {row.comparison.note}
            </p>
          )}
          {row.quality.basis?.origin === "legacy_segments" && (
            <p className="fine">{row.quality.basis.note}</p>
          )}
          <QualityDeviations row={row} metrics={report.catalog.metrics} />
          <h3>Deine nächsten Schritte</h3>
          <ol>
            {row.summary.priorities.map((p) => (
              <li key={p.metric}>
                <strong>{p.title}.</strong> {p.explanation} {p.openCount} offen
                von {p.count} Treffern.
                {p.evidence[0] && (
                  <blockquote>
                    …{p.evidence[0].before.slice(-40)}
                    <mark>
                      {p.evidence[0].text.slice(0, 140)}
                      {p.evidence[0].text.length > 140 ? "…" : ""}
                    </mark>
                    {p.evidence[0].after.slice(0, 40)}…
                  </blockquote>
                )}
              </li>
            ))}
          </ol>
          {!row.summary.priorities.length && (
            <p>
              Keine weiteren priorisierten Fundstellen. Handlung und Fakten
              benötigen eine eigene Prüfung.
            </p>
          )}
          <p className="fine">
            {row.summary.note}
            {row.summary.intentional > 0
              ? ` ${row.summary.intentional} Beispiele als beabsichtigt markiert; Messwerte bleiben erhalten.`
              : ""}
          </p>
        </article>
      ))}
      {report.scope === "chapters" && (
        <section className="brief-chapter-list">
          <h2>Alle Kapitel im Überblick</h2>
          <table>
            <thead>
              <tr>
                <th>Kapitel</th>
                <th>Lesefluss</th>
                <th>Wortwahl</th>
                <th>Wiederholungen</th>
                <th>Konsistenz</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.id}>
                  <th>{row.title}</th>
                  {row.summary.cards.map((c) => (
                    <td key={c.id}>
                      {c.title}
                      <small>{STATUS[c.status]}</small>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </section>
  );
}
