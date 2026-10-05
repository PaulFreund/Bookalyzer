import type { Comparison, Document, Reference } from "./types";

export const number = (n: number | null | undefined, digits = 0) =>
  n == null
    ? "–"
    : n.toLocaleString("de-DE", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
const HUMAN = "#319c91",
  AI = "#d49a50";
const tip = (text: string) => <title>{text}</title>;

export function ProfileChart({
  documents,
  reference,
}: {
  documents: Document[];
  reference: Reference;
}) {
  const docs = documents.filter((d) => d.narrative);
  const axes = docs[0]?.narrative?.profiles || reference.profiles;
  const left = 195,
    width = 410,
    top = 43,
    row = 43;
  const x = (v: number) => left + (v / 100) * width;
  return (
    <svg
      viewBox="0 0 655 340"
      className="chart"
      role="img"
      aria-label="Narrative Merkmale auf einer Skala von 0 bis 100. Menschliche und KI-Referenzen mit den ausgewählten Texten."
    >
      {[0, 25, 50, 75, 100].map((t) => (
        <g key={t}>
          <line className="grid" x1={x(t)} x2={x(t)} y1="27" y2="296" />
          <text className="tick" x={x(t)} y="16" textAnchor="middle">
            {t}
          </text>
        </g>
      ))}
      {axes.map((axis, i) => {
        const y = top + i * row,
          ref = reference.profiles.find((p) => p.id === axis.id);
        return (
          <g key={axis.id}>
            <text className="axis-label" x="0" y={y + 5}>
              {axis.label}
            </text>
            <line
              stroke="#ebedf3"
              strokeWidth="3"
              x1={left}
              x2={left + width}
              y1={y}
              y2={y}
            />
            {ref &&
              (["human", "ai"] as const).map((key, j) =>
                ref[key].mean == null ? null : (
                  <g key={key} tabIndex={0}>
                    {tip(
                      `${key === "human" ? "Mensch" : "KI"}: ${number(ref[key].mean, 1)} · gültig ${number(ref[key].n)} / ${number(ref[key].total)}. ${axis.description}`,
                    )}
                    <line
                      stroke={j ? AI : HUMAN}
                      strokeOpacity=".18"
                      strokeWidth="8"
                      strokeLinecap="round"
                      x1={x(ref[key].q25!)}
                      x2={x(ref[key].q75!)}
                      y1={y + (j ? 4 : -4)}
                      y2={y + (j ? 4 : -4)}
                    />
                    <path
                      d={`M${x(ref[key].mean!)},${y - 6} l5,6 l-5,6 l-5,-6Z`}
                      fill={j ? AI : HUMAN}
                      stroke="white"
                      strokeWidth="1.5"
                    />
                  </g>
                ),
              )}
            {docs.map((doc, di) => {
              const p = doc.narrative!.profiles.find((p) => p.id === axis.id);
              return p?.mean == null ? null : (
                <circle
                  key={doc.id}
                  tabIndex={0}
                  cx={x(p.mean)}
                  cy={y + (di - (docs.length - 1) / 2) * 4}
                  r="5.5"
                  fill={doc.color}
                  stroke="white"
                  strokeWidth="2"
                >
                  {tip(
                    `${doc.title}: ${number(p.mean, 1)} · ${p.n} / ${p.total} Segmente. ${p.description}`,
                  )}
                </circle>
              );
            })}
          </g>
        );
      })}
      <text className="tick" x={left} y="326">
        Geringere Ausprägung
      </text>
      <text className="tick" x={left + width} y="326" textAnchor="end">
        Stärkere Ausprägung
      </text>
    </svg>
  );
}

export function ViolinChart({
  comparison,
  documents,
}: {
  comparison: Comparison;
  documents: Document[];
}) {
  const series = comparison.series;
  const values = series.flatMap((s) => s.values);
  const bottom = Math.max(0, Math.floor(Math.min(...values) * 0.86)),
    top = Math.max(bottom + 1, Math.ceil(Math.max(...values) * 1.08));
  const y = (n: number) => 248 - ((n - bottom) / (top - bottom)) * 216;
  const slot = 315 / Math.max(1, series.length);
  return (
    <svg
      viewBox="0 0 385 340"
      className="chart"
      role="img"
      aria-label="Verteilung interner narrativer Seltenheit. Punkte sind Segmente, durchgezogene Linie Mittelwert, gestrichelte Linie Median."
    >
      {Array.from(
        { length: 5 },
        (_, i) => bottom + ((top - bottom) * i) / 4,
      ).map((v, i) => (
        <g key={i}>
          <line className="grid" x1="43" x2="368" y1={y(v)} y2={y(v)} />
          <text className="tick" x="34" y={y(v) + 4} textAnchor="end">
            {number(v, 0)}
          </text>
        </g>
      ))}
      {series.map((s, i) => {
        const cx = 48 + slot * (i + 0.5),
          color = documents.find((d) => d.id === s.id)?.color || "#7262c4";
        const mean = s.mean,
          sd = Math.sqrt(
            s.values.reduce((a, v) => a + (v - mean) ** 2, 0) / s.values.length,
          );
        const bandwidth = Math.max(
          (top - bottom) / 30,
          1.06 * sd * s.values.length ** -0.2,
        );
        const points = Array.from(
          { length: 65 },
          (_, n) =>
            Math.max(bottom, Math.min(...s.values) - bandwidth) +
            (n / 64) *
              (Math.min(top, Math.max(...s.values) + bandwidth) -
                Math.max(bottom, Math.min(...s.values) - bandwidth)),
        );
        const density = points.map((v) =>
          s.values.reduce(
            (a, u) => a + Math.exp(-0.5 * ((v - u) / bandwidth) ** 2),
            0,
          ),
        );
        const max = Math.max(...density),
          half = Math.min(slot * 0.3, 46);
        const outline = [
          ...points.map((v, j) => `${cx - (density[j] / max) * half},${y(v)}`),
          ...points
            .map((v, j) => `${cx + (density[j] / max) * half},${y(v)}`)
            .reverse(),
        ].join(" ");
        return (
          <g key={s.id}>
            {s.values.length >= 5 && (
              <polygon
                points={outline}
                fill={color}
                fillOpacity=".16"
                stroke={color}
                strokeOpacity=".6"
              />
            )}
            {s.values.map((v, j) => (
              <circle
                key={j}
                cx={cx + Math.sin(j * 4.6) * Math.min(half * 0.4, 13)}
                cy={y(v)}
                r="3"
                fill={color}
                fillOpacity=".65"
                tabIndex={0}
              >
                {tip(
                  `${s.title} · Segment ${s.indices[j] + 1}: ${number(v, 2)}`,
                )}
              </circle>
            ))}
            <line
              x1={cx - half * 0.8}
              x2={cx + half * 0.8}
              y1={y(s.mean)}
              y2={y(s.mean)}
              stroke={color}
              strokeWidth="2.5"
            />
            <line
              x1={cx - half * 0.8}
              x2={cx + half * 0.8}
              y1={y(s.median)}
              y2={y(s.median)}
              stroke={color}
              strokeDasharray="3 3"
            />
            <text x={cx} y="274" textAnchor="middle" className="axis-label">
              {s.title.length > 15 ? s.title.slice(0, 13) + "…" : s.title}
            </text>
            <text x={cx} y="294" textAnchor="middle" className="tick">
              n = {s.values.length}
            </text>
            <text
              x={cx}
              y="316"
              textAnchor="middle"
              fill={color}
              className="value-label"
            >
              Ø {number(s.mean, 2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function TrendChart({
  documents,
  comparison,
  metric,
  onSegment,
}: {
  documents: Document[];
  comparison: Comparison | null;
  metric: string;
  onSegment?: (id: string, index: number) => void;
}) {
  const series =
    metric === "rarity"
      ? (comparison?.series || []).map((s) => ({
          id: s.id,
          title: s.title,
          values: s.values,
          indices: s.indices,
        }))
      : documents
          .filter((d) => d.segmentMetrics)
          .map((d) => ({
            id: d.id,
            title: d.title,
            values: d.segmentMetrics!.map((m) =>
              metric === "vocabulary" ? m.vocabulary : m.sentenceMean,
            ),
            indices: d.segments.map((s) => s.index),
          }));
  const all = series
    .flatMap((s) => s.values)
    .filter((v): v is number => v != null);
  const low = all.length ? Math.max(0, Math.floor(Math.min(...all) * 0.85)) : 0,
    high = all.length
      ? Math.max(low + 1, Math.ceil(Math.max(...all) * 1.08))
      : 1;
  const x = (i: number, n: number) => 54 + (n > 1 ? i / (n - 1) : 0.5) * 818,
    y = (v: number) => 198 - ((v - low) / (high - low)) * 164;
  return (
    <svg
      viewBox="0 0 910 246"
      className="chart"
      role="img"
      aria-label="Verlauf über die Segmente. Position relativ zur Anzahl der Segmente des jeweiligen Textes."
    >
      {Array.from({ length: 5 }, (_, i) => low + ((high - low) * i) / 4).map(
        (v, i) => (
          <g key={i}>
            <line className="grid" x1="54" x2="872" y1={y(v)} y2={y(v)} />
            <text className="tick" x="40" y={y(v) + 4} textAnchor="end">
              {number(v, 0)}
            </text>
          </g>
        ),
      )}
      {[0, 25, 50, 75, 100].map((t) => (
        <text
          key={t}
          className="tick"
          x={54 + (t / 100) * 818}
          y="225"
          textAnchor="middle"
        >
          {t === 0 ? "Anfang" : t === 100 ? "Ende" : `${t} %`}
        </text>
      ))}
      {series.map((s) => {
        const color = documents.find((d) => d.id === s.id)?.color || "#7262c4";
        let pen = false;
        const path = s.values
          .map((v, i) => {
            if (v == null) {
              pen = false;
              return "";
            }
            const op = pen ? "L" : "M";
            pen = true;
            return `${op}${x(i, s.values.length)},${y(v)}`;
          })
          .join(" ");
        return (
          <g key={s.id}>
            <path
              d={path}
              fill="none"
              stroke={color}
              strokeWidth="2.4"
              strokeLinejoin="round"
            />
            {s.values.map((v, i) =>
              v == null ? null : (
                <circle
                  className={onSegment ? "interactive-point" : ""}
                  key={i}
                  cx={x(i, s.values.length)}
                  cy={y(v)}
                  r="4.2"
                  fill="white"
                  stroke={color}
                  strokeWidth="2"
                  tabIndex={onSegment ? 0 : undefined}
                  role={onSegment ? "button" : undefined}
                  aria-label={`${s.title}, Segment ${s.indices[i] + 1}, ${number(v, 2)}`}
                  onClick={() => onSegment?.(s.id, s.indices[i])}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ")
                      onSegment?.(s.id, s.indices[i]);
                  }}
                >
                  {tip(
                    `${s.title} · Segment ${s.indices[i] + 1} · ${number(v, 2)}${onSegment ? " · Zum Text öffnen" : ""}`,
                  )}
                </circle>
              ),
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function Histogram({ documents }: { documents: Document[] }) {
  const docs = documents.filter((d) => d.metrics),
    labels = ["1–5", "6–10", "11–15", "16–20", "21–30", "31–40", "41+"];
  const percentages = docs.map((d) =>
    d.metrics!.histogram.map(
      (v) => (v / Math.max(1, d.metrics!.sentences)) * 100,
    ),
  );
  const max = Math.min(100, Math.max(10, ...percentages.flat()) * 1.12);
  return (
    <svg
      viewBox="0 0 570 240"
      className="chart"
      role="img"
      aria-label="Verteilung der Satzlängen in Prozent"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line
            className="grid"
            x1="42"
            x2="554"
            y1={188 - t * 157}
            y2={188 - t * 157}
          />
          <text className="tick" x="34" y={192 - t * 157} textAnchor="end">
            {number(t * max)}%
          </text>
        </g>
      ))}
      {labels.map((label, i) => (
        <g key={label}>
          <text className="tick" x={76 + i * 72} y="211" textAnchor="middle">
            {label}
          </text>
          {docs.map((d, j) => (
            <rect
              key={d.id}
              x={49 + i * 72 + (j * 52) / Math.max(1, docs.length)}
              y={188 - (percentages[j][i] / max) * 157}
              width={Math.max(2, 48 / Math.max(1, docs.length))}
              height={(percentages[j][i] / max) * 157}
              rx="3"
              fill={d.color}
              opacity=".8"
            >
              {tip(
                `${d.title} · ${label} Wörter: ${number(percentages[j][i], 1)} %`,
              )}
            </rect>
          ))}
        </g>
      ))}
      <text x="299" y="235" textAnchor="middle" className="tick">
        Wörter pro Satz
      </text>
    </svg>
  );
}

export function DistanceMatrix({
  comparison,
  documents,
}: {
  comparison: Comparison;
  documents: Document[];
}) {
  const series = comparison.series,
    matrix = comparison.distance!;
  const max = Math.max(1, ...matrix.flat()),
    size = Math.min(64, 280 / Math.max(1, series.length));
  return (
    <svg
      viewBox={`0 0 460 ${90 + series.length * size}`}
      className="chart"
      role="img"
      aria-label="Abstand zwischen den mittleren narrativen Profilen der Texte"
    >
      {series.map((s, i) => (
        <g key={s.id}>
          <text
            className="axis-label"
            x="150"
            y={42 + i * size + size / 2}
            textAnchor="end"
          >
            {s.title.slice(0, 20)}
          </text>
          <text
            className="tick"
            x={170 + i * size + size / 2}
            y="22"
            textAnchor="middle"
          >
            {i + 1}
          </text>
          {matrix[i].map((v, j) => (
            <g key={j}>
              <rect
                x={170 + j * size}
                y={30 + i * size}
                width={size - 5}
                height={size - 5}
                rx="5"
                fill={
                  i === j
                    ? "#f2f1f8"
                    : `rgba(114,98,196,${0.12 + (v / max) * 0.65})`
                }
              />
              <text
                x={170 + j * size + (size - 5) / 2}
                y={30 + i * size + size / 2 + 2}
                textAnchor="middle"
                fill={v / max > 0.6 ? "white" : "#655983"}
                className="tick"
              >
                {number(v, 1)}
              </text>
              {tip(
                `${documents.find((d) => d.id === s.id)?.title} ↔ ${series[j].title}: ${number(v, 2)}`,
              )}
            </g>
          ))}
        </g>
      ))}
    </svg>
  );
}
