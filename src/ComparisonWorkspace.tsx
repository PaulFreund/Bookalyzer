import { useEffect, useState } from "react";
import { ArrowDownToLine, BookOpen, Plus, Pin, Trash2 } from "lucide-react";
import { renderToStaticMarkup } from "react-dom/server";
import { call, saveFile } from "./api";
import { Histogram, ProfileChart, number } from "./charts";
import type {
  Baseline,
  BaselineComparison,
  BaselineScore,
  Bootstrap,
  Chapter,
  Chapters,
  Document,
} from "./types";

type Props = {
  mode: string;
  documents: Document[];
  data: Bootstrap;
  refresh: () => Promise<void>;
};
type Metric =
  | "sentenceMean"
  | "sentenceVariation"
  | "vocabulary"
  | "dialogue"
  | "distance";
const labels: Record<Metric, string> = {
  sentenceMean: "Satzlänge · Wörter",
  sentenceVariation: "Satzrhythmus · relative Streuung",
  vocabulary: "Wortvielfalt · je 100 Wörter",
  dialogue: "Wörtliche Rede · % (Differenz in pp)",
  distance: "Narrative Distanz",
};
const palette = [
  "#7262c4",
  "#239d95",
  "#d39542",
  "#c56882",
  "#508bc4",
  "#7d9961",
];
const signed = (value: number | null | undefined) =>
  value == null ? "–" : (value > 0 ? "+" : "") + number(value, 2);
const scoreValue = (score: BaselineScore | undefined, metric: Metric) =>
  metric === "distance"
    ? (score?.distance ?? null)
    : (score?.delta[metric] ?? null);

export function DeltaChart({
  rows,
  metric,
}: {
  rows: { title: string; value: number | null; color?: string }[];
  metric: Metric;
}) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.value ?? 0)));
  const width = 760,
    middle = metric === "distance" ? 230 : 478,
    range = metric === "distance" ? 460 : 222;
  return (
    <svg
      viewBox={"0 0 " + width + " " + (55 + rows.length * 46)}
      className="chart delta-chart"
      role="img"
      aria-label={"Abweichungen zur Baseline: " + labels[metric]}
    >
      <text x={middle} y="16" textAnchor="middle" className="tick">
        0 · {metric === "distance" ? "identisches Profil" : "Baseline"}
      </text>
      <line
        x1={middle}
        x2={middle}
        y1="25"
        y2={35 + rows.length * 46}
        stroke="#a9a5b9"
        strokeDasharray="3 4"
      />
      {rows.map((r, i) => {
        const dx = ((r.value ?? 0) / max) * range,
          y = 44 + i * 46;
        return (
          <g key={i}>
            <title>{r.title + ": " + signed(r.value)}</title>
            <text x="0" y={y + 5} className="axis-label">
              {r.title.length > 27 ? r.title.slice(0, 26) + "…" : r.title}
            </text>
            {r.value != null && (
              <>
                <rect
                  x={middle + Math.min(0, dx)}
                  y={y - 9}
                  width={Math.max(2, Math.abs(dx))}
                  height="18"
                  rx="4"
                  fill={r.color || palette[i % 6]}
                />
                <text x="750" y={y + 5} textAnchor="end" className="axis-label">
                  {metric === "distance" ? number(r.value, 2) : signed(r.value)}
                </text>
              </>
            )}
            {r.value == null && (
              <text x="730" y={y + 5} textAnchor="end" className="tick">
                nicht verfügbar
              </text>
            )}
          </g>
        );
      })}
      <text
        x={middle}
        y={51 + rows.length * 46}
        textAnchor="middle"
        className="tick"
      >
        {metric === "distance"
          ? "Kleiner = ähnlicher"
          : "← geringere Ausprägung · höhere Ausprägung →"}
      </text>
    </svg>
  );
}

export function ChapterCurve({
  rows,
  metric,
  baseline,
  onSelect,
}: {
  rows: Chapter[];
  metric: Metric;
  baseline: boolean;
  onSelect?: (index: number) => void;
}) {
  const values = rows.map((r) =>
    baseline
      ? scoreValue(r.comparison, metric)
      : metric === "distance"
        ? null
        : r.metrics[metric],
  );
  const finite = values.filter((v): v is number => v != null);
  const min = Math.min(0, ...finite),
    max = Math.max(min + 1, ...finite);
  const x = (i: number) => 52 + (i / Math.max(1, rows.length - 1)) * 675,
    y = (v: number) => 192 - ((v - min) / (max - min)) * 154;
  return (
    <svg
      viewBox="0 0 775 240"
      className="chart chapter-curve"
      role="img"
      aria-label={"Kapitelverlauf: " + labels[metric]}
    >
      {[min, (min + max) / 2, max].map((v, i) => (
        <g key={i}>
          <line x1="52" x2="727" y1={y(v)} y2={y(v)} stroke="#e6e3ef" />
          <text x="43" y={y(v) + 4} textAnchor="end" className="tick">
            {number(v, 1)}
          </text>
        </g>
      ))}
      {baseline && (
        <g>
          <line
            x1="52"
            x2="727"
            y1={y(0)}
            y2={y(0)}
            stroke="#92889e"
            strokeDasharray="5 4"
          />
          <text x="726" y={y(0) - 7} textAnchor="end" className="tick">
            0 · Baseline
          </text>
        </g>
      )}
      {values.map((v, i) =>
        v == null ? null : (
          <g key={rows[i].id}>
            {i > 0 && values[i - 1] != null && (
              <line
                x1={x(i - 1)}
                x2={x(i)}
                y1={y(values[i - 1]!)}
                y2={y(v)}
                stroke="#7262c4"
                strokeWidth="2.5"
              />
            )}
            <circle
              cx={x(i)}
              cy={y(v)}
              r="5"
              fill="#7262c4"
              stroke="white"
              strokeWidth="2"
              tabIndex={onSelect ? 0 : undefined}
              role={onSelect ? "button" : undefined}
              aria-label={rows[i].title + ": " + number(v, 2)}
              onClick={() => onSelect?.(rows[i].index)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect?.(rows[i].index);
                }
              }}
            >
              <title>{rows[i].title + ": " + number(v, 2)}</title>
            </circle>
            {(rows.length <= 20 ||
              i % Math.ceil(rows.length / 15) === 0 ||
              i === rows.length - 1) && (
              <text x={x(i)} y="214" textAnchor="middle" className="tick">
                {i + 1}
              </text>
            )}
          </g>
        ),
      )}
      {!finite.length && (
        <text x="390" y="118" textAnchor="middle" className="axis-label">
          Für diese Metrik liegen keine vergleichbaren Werte vor.
        </text>
      )}
      <text x="390" y="237" textAnchor="middle" className="tick">
        Kapitel in Lesereihenfolge{" "}
        {baseline ? "· Abweichung zur festen Baseline" : "· absolute Werte"}
      </text>
    </svg>
  );
}

export function comparisonExport(
  format: string,
  result: BaselineComparison | Chapters,
  metric: Metric,
) {
  if (format === "json")
    return JSON.stringify(
      { generatedAt: new Date().toISOString(), ...result },
      null,
      2,
    );
  const isChapters = "chapters" in result;
  const rows = isChapters
    ? result.chapters.map((c) => ({
        title: c.title,
        metrics: c.metrics,
        score: c.comparison,
        words: c.words,
        short: c.short,
      }))
    : result.rows.map((r) => ({
        title: r.title,
        metrics: r.metrics,
        score: r,
        words: r.metrics.words,
        short: false,
      }));
  const headers = [
    "Text / Kapitel",
    "Wörter",
    "Satzlänge",
    "Satzstreuung",
    "Wortvielfalt / 100",
    "Rede %",
    "Δ Satzlänge",
    "Δ Satzstreuung",
    "Δ Wortvielfalt",
    "Δ Rede (pp)",
    "Narrative Distanz",
    "Hinweis",
    "Baseline",
    "Baseline-ID",
  ];
  const cells = rows.map((r) => [
    r.title,
    r.words,
    r.metrics.sentenceMean,
    r.metrics.sentenceVariation,
    r.metrics.vocabulary,
    r.metrics.dialogue,
    r.score?.delta.sentenceMean,
    r.score?.delta.sentenceVariation,
    r.score?.delta.vocabulary,
    r.score?.delta.dialogue,
    r.score?.distance,
    [
      r.short ? "Kurzes Kapitel" : "",
      r.score?.reason,
      ...(r.score?.warnings || []),
    ]
      .filter(Boolean)
      .join(" · "),
    result.baseline?.name,
    result.baseline?.id,
  ]);
  if (format === "csv") {
    const escape = (value: unknown) =>
      '"' +
      (typeof value === "string"
        ? value.replace(/^[\s]*[=+\-@]/, "'$&")
        : String(value ?? "")
      ).replaceAll('"', '""') +
      '"';
    return (
      "\uFEFF" +
      [headers, ...cells].map((row) => row.map(escape).join(";")).join("\r\n")
    );
  }
  return (
    "<!doctype html>" +
    renderToStaticMarkup(
      <html lang="de">
        <head>
          <meta charSet="utf-8" />
          <title>Bookalyzer · Vergleich</title>
          <style>
            {
              "body{font:14px system-ui;color:#292637;margin:38px}h1{font-family:Georgia}.chart{width:100%;max-height:450px}text{font:12px system-ui;fill:#555}table{border-collapse:collapse;width:100%;font-size:10px}td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left}svg,tr{break-inside:avoid}p{line-height:1.6}thead{display:table-header-group}small{color:#666;display:block;overflow-wrap:anywhere}@page{size:A4 landscape;margin:14mm}"
            }
          </style>
        </head>
        <body>
          <h1>
            {isChapters
              ? result.title + " · Kapitelvergleich"
              : "Vergleich mit fester Baseline"}
          </h1>
          <p>
            Baseline:{" "}
            {result.baseline?.name || "Keine · direkter Kapitelvergleich"}{" "}
            {result.baseline &&
              " · Stand " +
                new Date(result.baseline.createdAt).toLocaleString("de-DE")}
          </p>
          <h2>{labels[metric]}</h2>
          {isChapters ? (
            <ChapterCurve
              rows={result.chapters}
              metric={metric}
              baseline={!!result.baseline}
            />
          ) : (
            <DeltaChart
              rows={result.rows.map((r) => ({
                title: r.title,
                value: scoreValue(r, metric),
              }))}
              metric={metric}
            />
          )}
          <table>
            <thead>
              <tr>
                {headers.slice(0, 12).map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cells.map((row, i) => (
                <tr key={i}>
                  {row.slice(0, 12).map((v, j) => (
                    <td key={j}>
                      {typeof v === "number" ? number(v, 2) : (v ?? "–")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p>{result.baseline?.note}</p>
          <p>{isChapters && result.note}</p>
          <p>
            Deskriptive Merkmale und Abweichungen. Kein Nachweis menschlicher
            oder KI-Urheberschaft; höhere Werte bedeuten keine bessere Qualität.
          </p>
          <small>
            Baseline-ID: {result.baseline?.id || "–"} · Hashes:{" "}
            {JSON.stringify(result.baseline?.hashes || {})}
          </small>
        </body>
      </html>,
    )
  );
}

export function ComparisonWorkspace({ mode, documents, data, refresh }: Props) {
  const [baselineId, setBaselineId] = useState(data.baselines?.[0]?.id || "");
  const [bookId, setBookId] = useState(documents[0]?.id || "");
  const [sourceId, setSourceId] = useState(documents[0]?.id || "");
  const [name, setName] = useState("");
  const [metric, setMetric] = useState<Metric>("sentenceMean");
  const [result, setResult] = useState<BaselineComparison | null>(null);
  const [chapters, setChapters] = useState<Chapters | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [reader, setReader] = useState<{ title: string; text: string } | null>(
    null,
  );
  const [format, setFormat] = useState("html");
  const available = data.documents.filter((d) => d.status === "ready");
  const baselines = data.baselines || [];
  const key = documents.map((d) => d.id + d.completedAt).join("|");
  useEffect(() => {
    if (!baselineId && metric === "distance") setMetric("sentenceMean");
  }, [baselineId, metric]);
  useEffect(() => {
    if (!available.some((d) => d.id === bookId))
      setBookId(available[0]?.id || "");
    if (!available.some((d) => d.id === sourceId))
      setSourceId(available[0]?.id || "");
  }, [data.documents, bookId, sourceId]);
  useEffect(() => {
    if (baselineId && !baselines.some((b) => b.id === baselineId))
      setBaselineId("");
  }, [baselines, baselineId]);
  useEffect(() => {
    let alive = true;
    setError("");
    setResult(null);
    setChapters(null);
    setReader(null);
    setLoading(false);
    if (
      (mode === "baseline" && !baselineId) ||
      (mode === "chapters" && (!bookId || !enabled))
    )
      return;
    setLoading(true);
    const request =
      mode === "baseline"
        ? call<BaselineComparison>("baseline_compare", {
            ids: documents.map((d) => d.id),
            baselineId,
          })
        : call<Chapters>("chapters", {
            id: bookId,
            baselineId: baselineId || null,
          });
    request
      .then((r) => {
        if (!alive) return;
        if ("chapters" in r) {
          setChapters(r);
          setSelected((previous) => {
            const kept = previous.filter((i) =>
              r.chapters.some((c) => c.index === i),
            );
            return kept.length
              ? kept
              : r.chapters.slice(0, 3).map((c) => c.index);
          });
        } else setResult(r);
      })
      .catch((e) => {
        if (alive) setError(String(e.message));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [mode, key, bookId, baselineId, enabled]);
  const mutate = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const addBaseline = () =>
    mutate(async () => {
      const b = await call<Baseline>("baseline_create", { id: sourceId, name });
      await refresh();
      setBaselineId(b.id);
      setName("");
    });
  const exportData = () =>
    mutate(async () => {
      const current = mode === "chapters" ? chapters : result;
      if (!current) return;
      await saveFile(
        "Bookalyzer-" +
          (mode === "chapters" ? "Kapitel" : "Baseline") +
          "." +
          format,
        comparisonExport(format, current, metric),
        format,
      );
    });
  const readChapter = (index: number) =>
    mutate(async () => {
      setReader(await call("chapter_text", { id: bookId, index }));
    });
  const currentBaseline =
    mode === "chapters" ? chapters?.baseline : result?.baseline;
  const book = available.find((d) => d.id === bookId);
  const chapterDocs: Document[] = (
    chapters?.chapters.filter((c) => selected.includes(c.index)) || []
  ).map((c, i) => ({
    ...book!,
    id: c.id,
    title: c.title,
    color: palette[i % 6],
    metrics: c.metrics,
    narrative:
      c.narrativeComplete && book?.narrative
        ? { ...book.narrative, profiles: c.profiles }
        : null,
  }));
  const toggleChapter = (index: number) => {
    setError("");
    setSelected((prev) =>
      prev.includes(index)
        ? prev.filter((i) => i !== index)
        : prev.length < 6
          ? [...prev, index]
          : prev,
    );
    if (!selected.includes(index) && selected.length >= 6)
      setError("Bis zu sechs Kapitel gleichzeitig auswählen.");
  };
  return (
    <div className="comparison-workspace">
      <section className="panel baseline-controls">
        <div className="workspace-heading">
          <div>
            <span className="eyebrow">
              {mode === "chapters"
                ? "DAS BUCH IM DETAIL"
                : "DEIN FESTER MASSSTAB"}
            </span>
            <h2>
              {mode === "chapters"
                ? "Kapitel unter der Lupe"
                : "Vergleich mit einer Baseline"}
            </h2>
          </div>
          <Pin size={24} />
        </div>
        <div className="form-row">
          {mode === "chapters" && (
            <label>
              Buch
              <select
                aria-label="Buch für Kapitelvergleich"
                value={bookId}
                onChange={(e) => {
                  setBookId(e.target.value);
                  setSelected([]);
                }}
              >
                {available.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Feste Baseline
            <select
              aria-label="Feste Baseline"
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            >
              <option value="">
                {mode === "chapters"
                  ? "Ohne Baseline · Kapitel untereinander"
                  : "Baseline auswählen"}
              </option>
              {baselines.map((b) => (
                <option value={b.id} key={b.id}>
                  {b.name} · {new Date(b.createdAt).toLocaleDateString("de-DE")}
                </option>
              ))}
            </select>
          </label>
          <label>
            Diagramm-Metrik
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as Metric)}
            >
              {Object.entries(labels)
                .filter(([k]) => baselineId || k !== "distance")
                .map(([k, label]) => (
                  <option value={k} key={k}>
                    {label}
                  </option>
                ))}
            </select>
          </label>
        </div>
        {mode === "chapters" && (
          <label className="chapter-switch">
            <input
              type="checkbox"
              role="switch"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Kapitel erkennen und vergleichen{" "}
            <span>Überschriften aus dem Import verwenden</span>
          </label>
        )}
        <details className="baseline-create" open={!baselines.length}>
          <summary>
            <Plus size={16} /> Neue Baseline aus einer Analyse speichern
          </summary>
          <div className="form-row">
            <label>
              Referenztext
              <select
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
              >
                {available.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Name
              <input
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
                placeholder="z. B. Mein Stil · Romanentwurf"
              />
            </label>
            <button
              className="button primary"
              disabled={busy || !sourceId}
              onClick={addBaseline}
            >
              <Pin size={15} /> Baseline speichern
            </button>
          </div>
          <p className="field-hint">
            Eine unveränderliche Kopie dieser Analyse. Neue Uploads verändern
            ihren Maßstab nicht. Mehrere Baselines sind möglich.
          </p>
        </details>
        {baselineId && (
          <div className="baseline-meta">
            {currentBaseline && metric !== "distance" && (
              <strong>
                Basiswert: {number(currentBaseline.metrics[metric], 2)} ·{" "}
                {labels[metric]}
              </strong>
            )}
            <span>
              {number(baselines.find((b) => b.id === baselineId)?.wordCount)}{" "}
              Wörter ·{" "}
              {baselines.find((b) => b.id === baselineId)?.segmentCount}{" "}
              Referenzsegmente ·{" "}
              {baselines.find((b) => b.id === baselineId)?.narrative
                ? "StoryScope & Textprofil"
                : "Lokales Textprofil"}
            </span>
            <button
              className="text-button"
              disabled={busy}
              onClick={() =>
                mutate(async () => {
                  await call("baseline_remove", { id: baselineId });
                  setBaselineId("");
                  await refresh();
                })
              }
            >
              <Trash2 size={14} /> Baseline ausblenden
            </button>
          </div>
        )}
      </section>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {loading && (
        <p role="status" className="notice neutral">
          Vergleich wird berechnet …
        </p>
      )}
      {mode === "baseline" && !baselineId && (
        <div className="workspace-empty">
          <Pin size={32} />
          <h3>Welcher Text ist dein Maßstab?</h3>
          <p>
            Speichere eine fertige Analyse als Baseline. Alle ausgewählten Texte
            werden dann gegen denselben Stand verglichen.
          </p>
        </div>
      )}
      {mode === "chapters" && !enabled && (
        <div className="workspace-empty">
          <BookOpen size={32} />
          <p>Kapitelvergleich ist ausgeschaltet.</p>
        </div>
      )}
      {result && mode === "baseline" && (
        <section className="panel">
          <h2>Was unterscheidet deine Texte vom Referenztext?</h2>
          <p className="field-hint">
            {labels[metric]} ·{" "}
            {metric === "distance"
              ? "Abstand im festen Referenzraum"
              : "Absolute Differenz, keine Prozentänderung"}
          </p>
          <DeltaChart
            rows={result.rows.map((r) => ({
              title: r.title,
              value: scoreValue(r, metric),
              color: documents.find((d) => d.id === r.id)?.color,
            }))}
            metric={metric}
          />
          <div className="table-scroll">
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Text</th>
                  <th>Δ Satzlänge</th>
                  <th>Δ Wortvielfalt</th>
                  <th>Δ Rede (pp)</th>
                  <th>Narrative Distanz</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.id}>
                    <th>{r.title}</th>
                    <td>{signed(r.delta.sentenceMean)}</td>
                    <td>{signed(r.delta.vocabulary)}</td>
                    <td>{signed(r.delta.dialogue)}</td>
                    <td>{number(r.distance, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.rows.map(
            (r) =>
              (r.reason || r.warnings.length > 0) && (
                <p key={r.id} className="field-hint">
                  <strong>{r.title}: </strong>
                  {[r.reason, ...r.warnings].filter(Boolean).join(" ")}
                </p>
              ),
          )}
          <p className="field-hint">{result.baseline.note}</p>
        </section>
      )}
      {chapters && mode === "chapters" && (
        <>
          <section className="panel">
            <div className="workspace-heading">
              <div>
                <span className="eyebrow">
                  {chapters.chapters.length} KAPITEL ·{" "}
                  {chapters.baseline
                    ? "GEGEN " + chapters.baseline.name
                    : "UNTEREINANDER"}
                </span>
                <h2>{labels[metric]} im Buchverlauf</h2>
              </div>
            </div>
            <ChapterCurve
              rows={chapters.chapters}
              metric={metric}
              baseline={!!chapters.baseline}
              onSelect={(index) => void readChapter(index)}
            />
            <p className="field-hint">
              {chapters.note} Klicke einen Punkt, um das Kapitel zu lesen.
            </p>
            {chapters.chapters.length < 2 && (
              <p className="notice neutral">
                Keine weiteren Kapitelgrenzen erkannt. Für TXT/PDF nutze eigene
                Zeilen wie „Kapitel 1 – Ankunft“, für DOCX
                Überschrift-Formatvorlagen.
              </p>
            )}
            <div className="table-scroll chapter-table-wrap">
              <table className="compare-table chapter-table">
                <thead>
                  <tr>
                    <th>Vergleichen</th>
                    <th>Kapitel</th>
                    <th>Wörter</th>
                    <th>Satzlänge</th>
                    <th>Vielfalt / 100</th>
                    {chapters.baseline && (
                      <>
                        <th>Δ Satzlänge</th>
                        <th>Δ Vielfalt</th>
                        <th>Narrative Distanz</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {chapters.chapters.map((c, i) => (
                    <tr
                      key={c.id}
                      className={
                        selected.includes(c.index) ? "is-selected" : ""
                      }
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.includes(c.index)}
                          onChange={() => toggleChapter(c.index)}
                          aria-label={c.title + " vergleichen"}
                        />
                      </td>
                      <th>
                        <button
                          className="text-button"
                          onClick={() => void readChapter(c.index)}
                        >
                          {i + 1}. {c.title}
                        </button>
                        {c.short && (
                          <small className="chapter-tag">kurzes Kapitel</small>
                        )}
                        {book?.narrative && !c.narrativeComplete && (
                          <small className="chapter-tag">
                            Merkmale über Kapitelgrenzen
                          </small>
                        )}
                      </th>
                      <td>{number(c.words)}</td>
                      <td>{number(c.metrics.sentenceMean, 1)}</td>
                      <td>{number(c.metrics.vocabulary, 1)}</td>
                      {chapters.baseline && (
                        <>
                          <td>{signed(c.comparison?.delta.sentenceMean)}</td>
                          <td>{signed(c.comparison?.delta.vocabulary)}</td>
                          <td
                            title={[
                              c.comparison?.reason,
                              ...(c.comparison?.warnings || []),
                            ]
                              .filter(Boolean)
                              .join(" ")}
                          >
                            {number(c.comparison?.distance, 2)}
                            {c.comparison?.reason && (
                              <small className="chapter-reason">
                                {c.comparison.reason}
                              </small>
                            )}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {chapters.baseline && (
              <p className="field-hint">{chapters.baseline.note}</p>
            )}
          </section>
          <section className="panel">
            <h2>Ausgewählte Kapitel direkt vergleichen</h2>
            <p className="field-hint">
              Bis zu sechs Kapitel über die Liste auswählen. Gleiche Achsen und
              Einheiten für alle Kapitel.
            </p>
            <div className="chapter-legend">
              {chapterDocs.map((d) => (
                <span key={d.id}>
                  <i style={{ background: d.color }} />
                  {d.title}
                </span>
              ))}
            </div>
            {chapterDocs.length ? (
              <>
                <div className="chapter-metric-cards">
                  {chapterDocs.map((d) => (
                    <article key={d.id} style={{ borderTopColor: d.color }}>
                      <strong>{d.title}</strong>
                      <span>
                        {number(d.metrics!.sentenceMean, 1)}{" "}
                        <small>Wörter / Satz</small>
                      </span>
                      <span>
                        {number(d.metrics!.vocabulary, 1)}{" "}
                        <small>Vielfalt / 100</small>
                      </span>
                      <span>
                        {number(d.metrics!.dialogue, 1)} %{" "}
                        <small>wörtliche Rede</small>
                      </span>
                    </article>
                  ))}
                </div>
                <Histogram documents={chapterDocs} />
                {chapterDocs.some((d) => d.narrative) && (
                  <ProfileChart
                    documents={chapterDocs}
                    reference={{ available: false, profiles: [] }}
                  />
                )}
              </>
            ) : (
              <p>Wähle Kapitel aus der Liste aus.</p>
            )}
            {chapters.distance &&
              chapterDocs.filter((d) => d.narrative).length > 1 && (
                <div className="table-scroll">
                  <table className="compare-table matrix-table">
                    <caption>
                      Narrative Kapitelabstände · kleiner = ähnlicher · – =
                      keine getrennten Merkmale
                    </caption>
                    <thead>
                      <tr>
                        <th>Kapitel</th>
                        {chapterDocs.map((d) => (
                          <th key={d.id}>{d.title}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {chapterDocs.map((a) => (
                        <tr key={a.id}>
                          <th>{a.title}</th>
                          {chapterDocs.map((b) => {
                            const i = chapters.chapters.findIndex(
                                (c) => c.id === a.id,
                              ),
                              j = chapters.chapters.findIndex(
                                (c) => c.id === b.id,
                              ),
                              v = chapters.distance![i][j];
                            return (
                              <td
                                key={b.id}
                                style={{
                                  background:
                                    v == null
                                      ? undefined
                                      : "rgba(114,98,196," +
                                        (0.04 + Math.min(v / 30, 0.35)) +
                                        ")",
                                }}
                              >
                                {number(v, 2)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </section>
        </>
      )}
      {reader && (
        <section className="panel chapter-reader" aria-label="Kapiteltext">
          <div className="workspace-heading">
            <h2>{reader.title}</h2>
            <button className="text-button" onClick={() => setReader(null)}>
              Schließen
            </button>
          </div>
          <pre>{reader.text}</pre>
        </section>
      )}
      {(result || chapters) && (
        <section className="panel workspace-export">
          <div>
            <h3>Diesen Vergleich mitnehmen</h3>
            <p className="field-hint">
              Diagramm, alle Werte und der genaue Baseline-Stand.
            </p>
          </div>
          <select
            aria-label="Vergleich Exportformat"
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            <option value="html">HTML · mit Diagramm</option>
            {window.bookalyzer && <option value="pdf">PDF</option>}
            <option value="csv">CSV · alle Werte</option>
            <option value="json">JSON · vollständig</option>
          </select>
          <button
            disabled={busy || loading}
            className="button primary"
            onClick={exportData}
          >
            <ArrowDownToLine size={16} /> Vergleich exportieren
          </button>
        </section>
      )}
    </div>
  );
}
