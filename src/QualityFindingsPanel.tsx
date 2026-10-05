import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { call } from "./api";
import type {
  QualityEvidence,
  QualityFindings,
  QualityMetric,
  QualityRow,
} from "./types";

export function QualityFindingsPanel({
  row,
  metrics,
  onEvidence,
  onIntentional,
}: {
  row: QualityRow;
  metrics: QualityMetric[];
  onEvidence: (e: QualityEvidence) => void;
  onIntentional: (e: QualityEvidence, intentional: boolean) => void;
}) {
  const [metric, setMetric] = useState("all");
  const [status, setStatus] = useState("open");
  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState<QualityFindings | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    setResult(null);
    call<QualityFindings>("quality_findings", {
      id: row.documentId,
      chapterIndex: row.chapterIndex,
      textSha256: row.quality.textSha256,
      metric: metric === "all" ? null : metric,
      status,
      offset,
      limit: 6,
    })
      .then((page) => {
        if (alive) setResult(page);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [
    row.id,
    row.quality.textSha256,
    row.summary.intentional,
    metric,
    status,
    offset,
    retry,
  ]);
  return (
    <section className="quality-card quality-findings" aria-busy={loading}>
      <div className="quality-card-heading">
        <div>
          <h2>Fundstellen zum Nachlesen</h2>
          <p>
            Alle erkannten Fundstellen sind durchblätterbar. Die Hinweise sind
            Prüfhilfen, keine Fehlerliste.
          </p>
        </div>
        <Search size={19} />
      </div>
      <div className="quality-findings-filters">
        <label>
          Hinweise filtern
          <select
            value={metric}
            onChange={(e) => {
              setMetric(e.target.value);
              setOffset(0);
            }}
          >
            <option value="all">Alle Regeln</option>
            {metrics
              .filter((m) => row.quality.evidenceCounts[m.id])
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} · {row.quality.evidenceCounts[m.id]} Treffer
                </option>
              ))}
          </select>
        </label>
        <label>
          Bearbeitungsstatus
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="open">Noch offen</option>
            <option value="intentional">Als beabsichtigt markiert</option>
            <option value="all">Alle Fundstellen</option>
          </select>
        </label>
      </div>
      {loading && <p role="status">Fundstellen werden geladen …</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button onClick={() => setRetry((r) => r + 1)}>
            Fundstellen erneut laden
          </button>
        </div>
      )}
      {result && (
        <>
          <p className="quality-fine" aria-live="polite">
            {result.total.toLocaleString("de-DE")}{" "}
            {status === "open"
              ? "offene"
              : status === "intentional"
                ? "als beabsichtigt markierte"
                : "erkannte"}{" "}
            Fundstellen
          </p>
          <div className="quality-evidence-list">
            {result.items.map((e) => (
              <div
                key={e.key}
                className={e.intentional ? "quality-intentional" : ""}
              >
                <button
                  className="quality-evidence"
                  onClick={() => onEvidence(e)}
                >
                  <span>
                    {metrics.find((m) => m.id === e.metric)?.label}
                    <small>{e.label}</small>
                  </span>
                  <p>
                    …{e.before}
                    <mark>
                      {e.text}
                      {e.truncated ? "…" : ""}
                    </mark>
                    {e.after}…
                  </p>
                  <small>Im Textkontext lesen ↗</small>
                </button>
                <button
                  className="text-button quality-intentional-action"
                  onClick={() => onIntentional(e, !e.intentional)}
                >
                  {e.intentional
                    ? "Beabsichtigt · wieder berücksichtigen"
                    : "Als beabsichtigt markieren"}
                </button>
              </div>
            ))}
            {!result.total && (
              <p className="quality-empty">
                Für diese Auswahl liegen keine Fundstellen vor. Ein fehlender
                Treffer ist keine Qualitätsgarantie.
              </p>
            )}
          </div>
          {result.total > 6 && (
            <div className="quality-pagination">
              <button
                disabled={!result.offset}
                onClick={() => setOffset(result.offset - 6)}
              >
                Zurück
              </button>
              <span>
                Seite {result.offset / 6 + 1} von {Math.ceil(result.total / 6)}
              </span>
              <button
                disabled={result.offset + 6 >= result.total}
                onClick={() => setOffset(result.offset + 6)}
              >
                Weiter
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
