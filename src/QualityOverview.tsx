import { ArrowRight, Check, CircleHelp, Eye, ScanText } from "lucide-react";
import { QualityBars, label } from "./QualityCharts";
import {
  overviewCards,
  STATUS,
  withConsistencyReference,
} from "./qualityPresentation";
import { QualityDeviations } from "./QualityDeviations";
import type {
  QualityEvidence,
  QualityMetric,
  QualityReport,
  QualityRow,
} from "./types";

export function QualityOverview({
  focused,
  compared,
  metrics,
  active,
  onMetric,
  onEvidence,
  onIntentional,
  chapters,
  chapterLoading,
  chapterError,
  onChapter,
  onDetails,
}: {
  focused: QualityRow;
  compared: QualityRow[];
  metrics: QualityMetric[];
  active: string;
  onMetric: (id: string) => void;
  onEvidence: (e: QualityEvidence) => void;
  onIntentional: (e: QualityEvidence, intentional: boolean) => void;
  chapters: QualityReport | null;
  chapterLoading: boolean;
  chapterError: string;
  onChapter: (row: QualityRow, metric?: string) => void;
  onDetails: () => void;
}) {
  const summary = focused.summary;
  const metric =
    metrics.find((m) => m.id === active) ||
    metrics.find((m) => m.id === "longSentences")!;
  const chapterRows = chapters?.rows || [];
  return (
    <div className="quality-overview">
      <div className="qo-context">
        <span>
          {summary.profile} · {focused.quality.words.toLocaleString("de-DE")}{" "}
          Wörter
        </span>
        <span>
          {focused.comparison
            ? `Referenz: ${focused.comparison.name}`
            : "Deine Schreibziele · ohne externen Referenztext"}
        </span>
      </div>
      <div className="qo-cards">
        {overviewCards(focused, chapterRows).map((card) => {
          const status = card.status;
          return (
            <button
              key={card.id}
              className={`qo-card ${status} ${active === card.metric && card.id !== "consistency" ? "chosen" : ""}`}
              title={card.detail}
              onClick={() => {
                if (card.id === "consistency")
                  document
                    .getElementById(
                      summary.deviations.length
                        ? "quality-deviations"
                        : "quality-chapter-overview",
                    )
                    ?.scrollIntoView({ behavior: "smooth", block: "start" });
                else onMetric(card.metric);
              }}
            >
              <span className="qo-label">
                {card.label}
                <span className={`qo-status ${status}`}>{STATUS[status]}</span>
              </span>
              <strong>{card.title}</strong>
              <span className="qo-card-note">
                {card.note
                  ? card.note
                  : card.id === "flow"
                    ? `Dein Ziel: höchstens ${focused.quality.longSentenceShare} % über ${focused.quality.longSentenceWords} Wörtern`
                    : card.id === "vocabulary"
                      ? `${label(card.value)} Wortformen je 100 Wörter`
                      : card.id === "repetition"
                        ? "Gleiche Sätze und Absätze"
                        : "Gegen Referenz oder übrige Kapitel"}
              </span>
            </button>
          );
        })}
      </div>
      <section className="quality-card qo-chart">
        <div className="quality-card-heading">
          <div>
            <span className="eyebrow">DEIN TEXT IM VERGLEICH</span>
            <h2>
              {metric.id === "longSentences"
                ? "Wie oft werden Sätze lang?"
                : metric.id === "mattr"
                  ? "Wie abwechslungsreich ist die Wortwahl?"
                  : metric.id === "sentenceMean"
                    ? "Wie lang sind die Sätze im Mittel?"
                    : metric.id === "nearRepeat"
                      ? "Wie oft wiederholen sich Wörter in der Nähe?"
                      : "Wie oft wiederholen sich Sätze?"}
            </h2>
          </div>
          <button className="text-button" onClick={onDetails}>
            Alle 51 Kennzahlen <ArrowRight size={15} />
          </button>
        </div>
        <QualityBars
          rows={compared.map(withConsistencyReference)}
          metric={metric}
          showGoals={metric.id === "longSentences"}
          compact
        />
        <p className="qo-explanation">
          {summary.cards.find(
            (c) => c.metric === metric.id && c.id !== "consistency",
          )?.detail || metric.note}
        </p>
        {focused.comparison && (
          <p className="quality-fine">{focused.comparison.note}</p>
        )}
        {focused.quality.basis?.origin === "legacy_segments" && (
          <p className="notice">{focused.quality.basis.note}</p>
        )}
      </section>
      <QualityDeviations
        row={focused}
        metrics={metrics}
        onMetric={(id) => {
          onMetric(id);
          document
            .querySelector(".qo-chart")
            ?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
      />
      <section className="qo-priorities">
        <div className="quality-card-heading">
          <div>
            <span className="eyebrow">DEINE NÄCHSTEN SCHRITTE</span>
            <h2>Hier lohnt sich ein zweiter Blick.</h2>
          </div>
          <span className="quality-fine">
            {summary.intentional
              ? `${summary.intentional} ${summary.intentional === 1 ? "Beispiel" : "Beispiele"} als beabsichtigt markiert`
              : "Bis zu drei verschiedene Schwerpunkte"}
          </span>
        </div>
        <div className="qo-priority-grid">
          {summary.priorities.map((p, index) => (
            <article className="qo-priority" key={p.metric}>
              <div className="qo-priority-number">{index + 1}</div>
              <span className="eyebrow">{p.group}</span>
              <h3>{p.title}</h3>
              <p>{p.explanation}</p>
              <small>
                {p.openCount.toLocaleString("de-DE")} offen von{" "}
                {p.count.toLocaleString("de-DE")} Treffern · Weitere Fundstellen
                rücken nach
              </small>
              {p.evidence.map((e) => (
                <div className="qo-example" key={e.key}>
                  <button onClick={() => onEvidence(e)}>
                    <ScanText size={15} />
                    <span>
                      {e.text.slice(0, 95)}
                      {e.text.length > 95 ? "…" : ""}
                    </span>
                    <ArrowRight size={14} />
                  </button>
                  <button
                    className="qo-intent"
                    aria-label={`Als beabsichtigt markieren: ${e.text.slice(0, 95)}`}
                    onClick={() => onIntentional(e, true)}
                  >
                    <Check size={12} /> Beabsichtigt
                  </button>
                </div>
              ))}
            </article>
          ))}
          {!summary.priorities.length && (
            <div className="quality-card qo-no-priority">
              <Eye size={20} />
              <p>
                Aktuell keine weiteren priorisierten Fundstellen. Die Analyse
                deckt ausgewählte Spracheigenschaften ab; Handlung und Fakten
                brauchen eine eigene Prüfung.
              </p>
            </div>
          )}
        </div>
      </section>
      <section
        className="quality-card qo-chapters"
        id="quality-chapter-overview"
      >
        <div className="quality-card-heading">
          <div>
            <span className="eyebrow">DAS GANZE BUCH</span>
            <h2>Welche Kapitel verdienen Aufmerksamkeit?</h2>
            <p>
              Kapitel auswählen, um die Messwerte und Textstellen zu öffnen.
            </p>
          </div>
          <CircleHelp size={18} />
        </div>
        {chapterLoading ? (
          <p role="status">Kapitel werden verglichen …</p>
        ) : chapterError ? (
          <p className="quality-fine">{chapterError}</p>
        ) : chapterRows.length ? (
          <div className="quality-table-scroll">
            <table className="qo-chapter-table">
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
                {chapterRows.map((row) => (
                  <tr
                    key={row.id}
                    className={row.id === focused.id ? "focused" : ""}
                  >
                    <th>
                      <button onClick={() => onChapter(row)}>
                        {row.title}
                        <small>
                          {row.quality.words.toLocaleString("de-DE")} Wörter
                        </small>
                      </button>
                    </th>
                    {row.summary.cards.map((card) => (
                      <td key={card.id}>
                        <button
                          className={`qo-cell ${card.status}`}
                          onClick={() => onChapter(row, card.metric)}
                          title={card.title + " · " + card.detail}
                        >
                          <span>
                            {card.id === "flow"
                              ? `${label(card.value)} % lang`
                              : card.id === "vocabulary"
                                ? `${label(card.value)} /100`
                                : card.id === "repetition"
                                  ? `${label(card.value)} % gleich`
                                  : card.status === "review"
                                    ? card.title
                                    : card.status === "unknown"
                                      ? "Zu wenige Daten"
                                      : "Ohne starken Ausreißer"}
                          </span>
                          <small>{STATUS[card.status]}</small>
                        </button>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>Für diesen Text sind noch keine Kapitel verfügbar.</p>
        )}
        <p className="quality-fine">
          Grün = eingestelltes Längenziel eingehalten · Orange = prüfen · Blau =
          Beobachtung · Grau = zu wenig Grundlage. Stilabweichung bedeutet nicht
          schlechtere Qualität.
        </p>
      </section>
      <p className="quality-fine qo-footer">
        {summary.note} Schreibziele kannst du vor jedem Upload anpassen.
      </p>
    </div>
  );
}
