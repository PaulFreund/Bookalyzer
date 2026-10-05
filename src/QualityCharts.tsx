import { number } from "./charts";
import type { QualityRow, QualityPoint, QualityMetric } from "./types";
export const qValue = (row: QualityRow, metric: string, delta: boolean) =>
  (delta ? row.delta?.values[metric] : row.quality.values[metric]) ?? null;
const qReason = (row: QualityRow, metric: string, delta: boolean) =>
  (delta ? row.delta?.reasons[metric] : row.quality.reasons[metric]) ||
  "Nicht verfügbar";
export const label = (value: number | null, signed = false) =>
  value === null ? "—" : (signed && value > 0 ? "+" : "") + number(value, 2);
export const qualityUnit = (metric: QualityMetric, delta = false) =>
  delta && metric.unit === "%" ? "Prozentpunkte" : metric.unit;
export function qualityColor(
  value: number | null,
  metric: QualityMetric,
  delta = false,
) {
  if (value === null) return "#f5f5f7";
  const [low, high] = metric.displayRange || [0, 100];
  const intensity = delta
    ? Math.min(1, Math.abs(value) / Math.max(0.01, (high - low) / 4))
    : Math.max(0, Math.min(1, (value - low) / (high - low)));
  const rgb = delta && value < 0 ? "27, 126, 151" : "114, 98, 196";
  return `rgba(${rgb}, ${delta && value === 0 ? 0 : 0.045 + intensity * 0.3})`;
}

export function QualityBars({
  rows,
  metric,
  delta = false,
  showGoals = false,
  compact = false,
}: {
  rows: QualityRow[];
  metric: QualityMetric;
  delta?: boolean;
  showGoals?: boolean;
  compact?: boolean;
}) {
  const values = rows
    .map((row) => qValue(row, metric.id, delta))
    .filter((v): v is number => v !== null);
  if (!values.length)
    return (
      <p className="quality-empty">
        Für diese Kennzahl sind keine vergleichbaren Werte vorhanden. Die
        Tabelle zeigt den jeweiligen Grund.
      </p>
    );
  const domain = metric.displayRange || [0, 100];
  const references = rows.flatMap((row) => {
    const band = row.comparison?.bands[metric.id];
    const reference = row.delta?.reasons[metric.id]
      ? null
      : row.comparison?.values[metric.id];
    return band && band.n >= 3
      ? [
          band.low - (delta ? band.median : 0),
          band.high - (delta ? band.median : 0),
        ]
      : !delta && reference != null
        ? [reference]
        : [];
  });
  const low = Math.min(
    delta ? -(domain[1] - domain[0]) / 4 : domain[0],
    ...values,
    ...references,
  );
  const high = Math.max(
    delta ? (domain[1] - domain[0]) / 4 : domain[1],
    ...values,
    ...references,
  );
  const range = high - low || 1;
  const x = (v: number) => 192 + ((v - low) / range) * 480;
  const height = (compact ? 52 : 64) + rows.length * (compact ? 38 : 48);
  return (
    <svg
      viewBox={"0 0 770 " + height}
      className="quality-bars"
      role="img"
      aria-label={
        (delta ? "Abweichung zur Baseline: " : "Textvergleich: ") +
        metric.label +
        " in " +
        qualityUnit(metric, delta)
      }
    >
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line
            x1={192 + v * 480}
            x2={192 + v * 480}
            y1="24"
            y2={height - 29}
            stroke="#e6e5ef"
            strokeDasharray="3 4"
          />
          <text
            x={192 + v * 480}
            y={height - 9}
            textAnchor="middle"
            className="tick"
          >
            {label(low + v * range)}
          </text>
        </g>
      ))}
      <line x1={x(0)} x2={x(0)} y1="20" y2={height - 27} stroke="#aaa5bd" />
      {rows.map((row, i) => {
        const value = qValue(row, metric.id, delta),
          y = (compact ? 26 : 34) + i * (compact ? 38 : 48);
        const band = row.comparison?.bands[metric.id];
        const reference = row.delta?.reasons[metric.id]
          ? null
          : row.comparison?.values[metric.id];
        const offset = delta && band ? band.median : 0;
        return (
          <g key={row.id}>
            {band && band.n >= 3 && (
              <rect
                x={x(band.low - offset)}
                y={y - 17}
                width={Math.max(
                  2,
                  x(band.high - offset) - x(band.low - offset),
                )}
                height={34}
                fill="#ebd8b3"
                opacity=".55"
              >
                <title>{`Mittlere 50 % der Referenzausschnitte: ${label(band.low)} bis ${label(band.high)}`}</title>
              </rect>
            )}
            <text x="180" y={y + 5} textAnchor="end" className="axis-label">
              <title>{row.title}</title>
              {row.title.length > 25 ? row.title.slice(0, 23) + "…" : row.title}
            </text>
            {value !== null ? (
              <>
                <rect
                  x={Math.min(x(0), x(value))}
                  y={y - 10}
                  width={Math.max(2, Math.abs(x(value) - x(0)))}
                  height="21"
                  rx="4"
                  fill={row.color}
                  opacity=".85"
                >
                  <title>
                    {row.title +
                      ": " +
                      label(value, delta) +
                      " " +
                      qualityUnit(metric, delta) +
                      (metric.id === "longSentences"
                        ? ` · Sätze über ${row.quality.longSentenceWords} Wörter`
                        : "")}
                  </title>
                </rect>
                <text x="697" y={y + 5} className="axis-label">
                  {label(value, delta)}
                </text>
              </>
            ) : (
              <text x="198" y={y + 5} className="tick">
                Nicht verfügbar
              </text>
            )}
            {!delta && reference != null && (
              <line
                x1={x(reference)}
                x2={x(reference)}
                y1={y - 17}
                y2={y + 17}
                stroke="#936319"
                strokeWidth="2"
              >
                <title>{`Referenzmedian: ${label(reference)}`}</title>
              </line>
            )}
            {showGoals && (
              <line
                x1={x(row.quality.longSentenceShare)}
                x2={x(row.quality.longSentenceShare)}
                y1={y - 17}
                y2={y + 17}
                stroke="#268270"
                strokeWidth="2"
                strokeDasharray="3 2"
              >
                <title>{`Dein Ziel: höchstens ${row.quality.longSentenceShare} %`}</title>
              </line>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function QualityHeatmap({
  rows,
  metrics,
  delta,
  selected,
  onSelect,
}: {
  rows: QualityRow[];
  metrics: QualityMetric[];
  delta: boolean;
  selected?: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <div className="quality-table-scroll">
      <table className="quality-heatmap">
        <thead>
          <tr>
            <th>Kennzahl</th>
            {rows.map((row) => (
              <th key={row.id}>
                <i style={{ background: row.color }} />
                {row.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => {
            return (
              <tr
                key={metric.id}
                className={selected === metric.id ? "selected" : ""}
              >
                <th>
                  {onSelect ? (
                    <button onClick={() => onSelect(metric.id)}>
                      {metric.label}
                    </button>
                  ) : (
                    metric.label
                  )}
                  <small>
                    {delta ? "Δ " : ""}
                    {qualityUnit(metric, delta)}
                  </small>
                </th>
                {rows.map((row) => {
                  const value = qValue(row, metric.id, delta);
                  return (
                    <td
                      key={row.id}
                      style={{
                        background: qualityColor(value, metric, delta),
                      }}
                      title={
                        value === null
                          ? qReason(row, metric.id, delta)
                          : metric.note
                      }
                    >
                      {label(value, delta)}
                      {value === null && (
                        <span
                          className="quality-na"
                          aria-label={qReason(row, metric.id, delta)}
                        >
                          ⓘ
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function QualityProgression({
  points,
  metric,
  delta,
  onPoint,
}: {
  points: QualityPoint[];
  metric: QualityMetric;
  delta: boolean;
  onPoint?: (index: number) => void;
}) {
  const values = points.map(
    (point) =>
      (delta ? point.delta?.values[metric.id] : point.values[metric.id]) ??
      null,
  );
  const valid = values.filter((v): v is number => v !== null);
  if (!valid.length)
    return (
      <p className="quality-empty">
        Für diesen Verlauf reichen die Texteinheiten nicht aus oder die
        Einstellungen sind nicht vergleichbar.
      </p>
    );
  const bands = points.map((p) => p.comparison?.bands[metric.id]);
  const bandValues = bands.flatMap((b) =>
    b && b.n >= 3
      ? [b.low - (delta ? b.median : 0), b.high - (delta ? b.median : 0)]
      : [],
  );
  const min = Math.min(...valid, ...bandValues, delta ? 0 : Infinity),
    max = Math.max(...valid, ...bandValues, delta ? 0 : -Infinity);
  const pad = (max - min) * 0.12 || Math.max(1, Math.abs(max) * 0.1),
    lo = min - pad,
    hi = max + pad;
  const x = (i: number) => 55 + (i / Math.max(1, points.length - 1)) * 650,
    y = (v: number) => 170 - ((v - lo) / (hi - lo)) * 135;
  let path = "",
    connected = false;
  values.forEach((v, i) => {
    if (v === null) {
      connected = false;
      return;
    }
    path += (connected ? " L " : " M ") + x(i) + " " + y(v);
    connected = true;
  });
  const reference = delta ? 0 : null;
  return (
    <svg
      viewBox="0 0 770 214"
      className="quality-curve"
      role="img"
      aria-label={"Verlauf von " + metric.label}
    >
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <line
            x1="55"
            x2="705"
            y1={170 - v * 135}
            y2={170 - v * 135}
            stroke="#e6e5ef"
          />
          <text x="46" y={174 - v * 135} textAnchor="end" className="tick">
            {label(lo + v * (hi - lo))}
          </text>
        </g>
      ))}
      {reference != null && (
        <g>
          <line
            x1="55"
            x2="705"
            y1={y(reference)}
            y2={y(reference)}
            stroke="#bc8538"
            strokeDasharray="4 4"
          />
          <text x="705" y={y(reference) - 7} textAnchor="end" className="tick">
            Baseline {label(reference)}
          </text>
        </g>
      )}
      {bands.map(
        (band, i) =>
          band &&
          band.n >= 3 && (
            <g key={"band" + i}>
              <line
                x1={x(i)}
                x2={x(i)}
                y1={y(band.low - (delta ? band.median : 0))}
                y2={y(band.high - (delta ? band.median : 0))}
                stroke="#d8ba83"
                strokeWidth={Math.max(3, Math.min(20, 600 / points.length))}
                opacity=".45"
              >
                <title>{`Referenzband: ${label(band.low)} bis ${label(band.high)} · ${band.n} Ausschnitte`}</title>
              </line>
              {!delta && (
                <circle cx={x(i)} cy={y(band.median)} r={2} fill="#a77a31" />
              )}
            </g>
          ),
      )}
      <path d={path} stroke="#7262c4" strokeWidth="2.5" fill="none" />
      {values.map(
        (v, i) =>
          v !== null && (
            <circle
              key={i}
              cx={x(i)}
              cy={y(v)}
              r={points.length > 100 ? 2.5 : 4.5}
              fill="#7262c4"
              stroke="white"
              strokeWidth="1"
              role={onPoint ? "button" : undefined}
              tabIndex={onPoint ? 0 : undefined}
              aria-label={points[i].title + ": " + label(v, delta)}
              onClick={() => onPoint?.(i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPoint?.(i);
                }
              }}
            >
              <title>
                {i + 1 + ". " + points[i].title + ": " + label(v, delta)}
              </title>
            </circle>
          ),
      )}
      <text x="55" y="198" className="tick">
        1
      </text>
      <text x="705" y="198" textAnchor="end" className="tick">
        {points.length}
      </text>
      <text x="380" y="205" textAnchor="middle" className="tick">
        Reihenfolge im Text · {qualityUnit(metric, delta)}
      </text>
    </svg>
  );
}

export function CadenceChart({ row }: { row: QualityRow }) {
  const points = row.quality.cadence;
  if (!points.length)
    return (
      <p className="quality-empty">
        Rhythmusanalyse ist deaktiviert oder der Text enthält keine Sätze.
      </p>
    );
  const maximum = Math.max(
    row.quality.longSentenceWords,
    ...points.map((p) => p.high),
    1,
  );
  const x = (i: number) => 40 + (i / Math.max(1, points.length - 1)) * 660,
    y = (v: number) => 132 - (v / maximum) * 110;
  const upper = points.map((p, i) => x(i) + "," + y(p.high)).join(" "),
    lower = [...points]
      .reverse()
      .map((p, i) => x(points.length - 1 - i) + "," + y(p.low))
      .join(" ");
  return (
    <svg
      viewBox="0 0 740 168"
      className="quality-cadence"
      role="img"
      aria-label="Satzlängen in Lesereihenfolge: Band Minimum bis Maximum, Linie Mittelwert"
    >
      <line x1="40" x2="700" y1="132" y2="132" stroke="#ddd" />
      <text x="32" y="26" textAnchor="end" className="tick">
        {maximum}
      </text>
      <text x="32" y="136" textAnchor="end" className="tick">
        0
      </text>
      <polygon points={upper + " " + lower} fill={row.color} opacity=".12" />
      <polyline
        points={points.map((p, i) => x(i) + "," + y(p.mean)).join(" ")}
        stroke={row.color}
        strokeWidth="1.8"
        fill="none"
      />
      <line
        x1="40"
        x2="700"
        y1={y(row.quality.longSentenceWords)}
        y2={y(row.quality.longSentenceWords)}
        stroke="#bd8538"
        strokeDasharray="4 4"
      />
      <text
        x="700"
        y={y(row.quality.longSentenceWords) - 5}
        textAnchor="end"
        className="tick"
      >
        Wortgrenze {row.quality.longSentenceWords}
      </text>
      <text x="40" y="153" className="tick">
        Satz 1
      </text>
      <text x="700" y="153" textAnchor="end" className="tick">
        Satz {row.quality.sentences}
      </text>
    </svg>
  );
}
