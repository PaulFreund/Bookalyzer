import { QualityBars } from "./QualityCharts";
import { withConsistencyReference } from "./qualityPresentation";
import type { QualityMetric, QualityRow } from "./types";

export function QualityDeviations({
  row,
  metrics,
  onMetric,
}: {
  row: QualityRow;
  metrics: QualityMetric[];
  onMetric?: (metric: string) => void;
}) {
  if (!row.summary.deviations.length) return null;
  return (
    <section className="quality-card qo-deviations" id="quality-deviations">
      <h2>Was fällt beim Stil auf?</h2>
      <p>
        Diese Unterschiede sind Hinweise zum Nachlesen. Eine Abweichung bedeutet
        nicht schlechtere Qualität.
      </p>
      {row.summary.deviations.map((finding) => {
        const metric = metrics.find((m) => m.id === finding.metric)!;
        return (
          <article className="qo-deviation" key={finding.metric}>
            <h3>
              {finding.label}: {finding.title.toLocaleLowerCase("de-DE")}
            </h3>
            <p>{finding.explanation}</p>
            <p>
              <strong>{finding.detail}</strong>
            </p>
            <QualityBars
              rows={[withConsistencyReference(row)]}
              metric={metric}
              compact
            />
            <p className="quality-fine">
              Gold zeigt die mittleren 50 % und den Median von {finding.band.n}{" "}
              {finding.referenceKind === "baseline"
                ? "passenden Referenzausschnitten"
                : "anderen Kapiteln"}
              . Referenz: {finding.reference}.
            </p>
            <p>{finding.suggestion}</p>
            {onMetric && (
              <button
                className="text-button"
                onClick={() => onMetric(finding.metric)}
              >
                Kennzahl im Vergleich zeigen
              </button>
            )}
          </article>
        );
      })}
    </section>
  );
}
