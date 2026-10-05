import {
  QualityBars,
  QualityHeatmap,
  QualityProgression,
  CadenceChart,
  label,
  qualityUnit,
} from "./QualityCharts";
import { QualityOverview } from "./QualityOverview";
import { QualityFindingsPanel } from "./QualityFindingsPanel";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, BookOpen, SlidersHorizontal } from "lucide-react";
import { call, saveFile } from "./api";
import { number } from "./charts";
import { qualityExport } from "./qualityExport";
import type {
  Bootstrap,
  QualityEvidence,
  QualityPoint,
  QualityReport,
  QualityRow,
} from "./types";

const COLORS = [
  "#7262c4",
  "#239d95",
  "#c58b32",
  "#c56882",
  "#508bc4",
  "#718b57",
];
const KIND: Record<string, string> = {
  index: "Etablierter Index",
  estimate: "Näherung",
  heuristic: "Heuristik",
  descriptive: "Deskriptives Maß",
};
export function QualityLab({
  data,
  initialIds,
  onRefresh,
}: {
  data: Bootstrap;
  initialIds: string[];
  onRefresh: () => Promise<void>;
}) {
  const documents = data.documents.filter((d) => d.status === "ready");
  const [ids, setIds] = useState(
    (initialIds.length
      ? initialIds
      : documents.slice(0, 3).map((d) => d.id)
    ).slice(0, 6),
  );
  const [scope, setScope] = useState<"documents" | "chapters">("documents");
  const [bookId, setBookId] = useState(initialIds[0] || documents[0]?.id || "");
  const [baselineId, setBaselineId] = useState("");
  const [delta, setDelta] = useState(false);
  const [group, setGroup] = useState("vocabulary");
  const [metricId, setMetricId] = useState("mattr");
  const [display, setDisplay] = useState<"overview" | "details">("overview");
  const [overviewMetric, setOverviewMetric] = useState("longSentences");
  const [appendix, setAppendix] = useState(false);
  const [chapterPreview, setChapterPreview] = useState<QualityReport | null>(
    null,
  );
  const [chapterLoading, setChapterLoading] = useState(false);
  const [chapterError, setChapterError] = useState("");
  const previousScope = useRef("");
  const previousRequest = useRef("");
  const requestedFocus = useRef("");
  const [result, setResult] = useState<QualityReport | null>(null);
  const [focusedId, setFocusedId] = useState("");
  const [chapterIds, setChapterIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [format, setFormat] = useState("html");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [reader, setReader] = useState<{
    before: string;
    text: string;
    after: string;
    truncated?: boolean;
  } | null>(null);
  const [readerError, setReaderError] = useState("");
  const [readerLoading, setReaderLoading] = useState(false);
  const readerDialog = useRef<HTMLDialogElement>(null);
  const readerGeneration = useRef(0);
  const [progression, setProgression] = useState<QualityPoint[]>([]);
  const [progressError, setProgressError] = useState("");
  const [progressLoading, setProgressLoading] = useState(false);
  const activeIds = ids.filter((id) => documents.some((d) => d.id === id));
  const activeBook = documents.some((d) => d.id === bookId)
    ? bookId
    : documents[0]?.id || "";
  const activeBaseline = data.baselines.some((b) => b.id === baselineId)
    ? baselineId
    : "";
  const selectionKey = activeIds.join(",");
  const revision = documents.map((d) => d.id + ":" + d.completedAt).join(",");
  const knownDocuments = useRef(new Set(documents.map((d) => d.id)));
  useEffect(() => {
    const arrivals = documents
      .filter(
        (d) => !knownDocuments.current.has(d.id) && initialIds.includes(d.id),
      )
      .map((d) => d.id);
    knownDocuments.current = new Set(documents.map((d) => d.id));
    if (arrivals.length) {
      requestedFocus.current = arrivals[arrivals.length - 1];
      setIds((current) => [...new Set([...current, ...arrivals])].slice(-6));
      setScope("documents");
    }
  }, [revision, initialIds.join(",")]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const request = [
      selectionKey,
      scope,
      activeBook,
      activeBaseline,
      revision,
    ].join("|");
    if (previousRequest.current !== request) setResult(null);
    previousRequest.current = request;
    setReader(null);
    readerGeneration.current++;
    call<QualityReport>("quality", {
      ids: activeIds,
      bookId: scope === "chapters" ? activeBook : null,
      baselineId: activeBaseline || null,
    })
      .then((report) => {
        if (!alive) return;
        setResult(report);
        const valid = new Set(report.rows.map((r) => r.id));
        const requested = requestedFocus.current;
        setFocusedId((current) =>
          valid.has(requested)
            ? requested
            : valid.has(current)
              ? current
              : report.rows[0]?.id || "",
        );
        requestedFocus.current = "";
        const sameScope = previousScope.current === scope + ":" + activeBook;
        setChapterIds((current) => {
          const next = sameScope
            ? current.filter((id) => valid.has(id))
            : report.rows.slice(0, 6).map((r) => r.id);
          return scope === "chapters" &&
            valid.has(requested) &&
            !next.includes(requested)
            ? [...next, requested].slice(-6)
            : next;
        });
        previousScope.current = scope + ":" + activeBook;
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
  }, [selectionKey, scope, activeBook, activeBaseline, revision, retry]);
  const rows = useMemo(
    () =>
      (result?.rows || []).map((r, i) => ({
        ...r,
        color: scope === "chapters" ? COLORS[i % COLORS.length] : r.color,
      })),
    [result, scope],
  );
  const focused = rows.find((r) => r.id === focusedId) || rows[0];
  const metrics =
    result?.catalog.metrics.filter((m) => m.group === group) || [];
  const metric = metrics.find((m) => m.id === metricId) || metrics[0];
  const useDelta = !!activeBaseline && delta;
  const compared =
    scope === "chapters"
      ? rows.filter((row) => chapterIds.includes(row.id))
      : rows;
  useEffect(() => {
    setReader(null);
    setReaderError("");
    setReaderLoading(false);
    readerGeneration.current++;
  }, [focusedId]);
  useEffect(() => {
    let alive = true;
    setProgression([]);
    setProgressError("");
    if (!focused || scope === "chapters" || display !== "details") {
      setProgressLoading(false);
      return;
    }
    setProgressLoading(true);
    call<QualityPoint[]>("quality_progression", {
      id: focused.documentId,
      baselineId: activeBaseline || null,
    })
      .then((p) => {
        if (alive) setProgression(p);
      })
      .catch((e) => {
        if (alive) setProgressError(e.message);
      })
      .finally(() => {
        if (alive) setProgressLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [focused?.id, scope, activeBaseline, display, revision]);
  useEffect(() => {
    let alive = true;
    setChapterPreview(null);
    setChapterError("");
    if (!focused || scope === "chapters" || display !== "overview") {
      setChapterLoading(false);
      return;
    }
    setChapterLoading(true);
    call<QualityReport>("quality", {
      ids: [],
      bookId: focused.documentId,
      baselineId: activeBaseline || null,
    })
      .then((report) => {
        if (alive) setChapterPreview(report);
      })
      .catch((e) => {
        if (alive) setChapterError(e.message);
      })
      .finally(() => {
        if (alive) setChapterLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [focused?.documentId, scope, activeBaseline, display, revision, retry]);
  useEffect(() => {
    const dialog = readerDialog.current;
    if (!dialog) return;
    if ((reader || readerLoading || readerError) && !dialog.open)
      dialog.showModal();
    else if (!reader && !readerLoading && !readerError && dialog.open)
      dialog.close();
  }, [reader, readerLoading, readerError]);
  useEffect(() => {
    if (reader)
      requestAnimationFrame(() =>
        readerDialog.current
          ?.querySelector("mark")
          ?.scrollIntoView({ block: "center" }),
      );
  }, [reader]);
  const points =
    scope === "chapters"
      ? rows.map((r, i) => ({
          index: i,
          title: r.title,
          words: r.quality.words,
          values: r.quality.values,
          reasons: r.quality.reasons,
          delta: r.delta,
          comparison: r.comparison,
        }))
      : progression;
  const selectedGroup = result?.catalog.groups.find((g) => g.id === group);
  const openEvidence = async (e: QualityEvidence) => {
    if (!focused) return;
    setReader(null);
    setReaderError("");
    setReaderLoading(true);
    const generation = ++readerGeneration.current;
    try {
      const excerpt = await call<typeof reader>("quality_excerpt", {
        id: focused.documentId,
        chapterIndex: focused.chapterIndex,
        start: e.start,
        end: e.end,
      });
      if (generation === readerGeneration.current) {
        setReader(excerpt);
        setReaderLoading(false);
      }
    } catch (e) {
      if (generation === readerGeneration.current) {
        setReaderError((e as Error).message);
        setReaderLoading(false);
      }
    }
  };
  const markIntentional = async (e: QualityEvidence, intentional: boolean) => {
    if (!focused) return;
    try {
      await call("quality_decision", {
        id: focused.documentId,
        textSha256: focused.quality.textSha256,
        metric: e.metric,
        start: e.start,
        end: e.end,
        chapterIndex: focused.chapterIndex,
        intentional,
      });
      setMessage(
        intentional
          ? "Als beabsichtigt markiert. Messwerte bleiben erhalten; der Hinweis wird nicht mehr priorisiert."
          : "Hinweis wieder aktiv.",
      );
      setRetry((v) => v + 1);
    } catch (e) {
      setMessage((e as Error).message);
    }
  };
  const createBaseline = async () => {
    if (!focused) return;
    try {
      const doc = documents.find((d) => d.id === focused.documentId)!;
      const saved = await call<{ id: string }>("baseline_create", {
        id: doc.id,
        name: doc.title + " · Referenzstand",
      });
      await onRefresh();
      setBaselineId(saved.id);
      setDelta(true);
      setMessage(
        "Referenztext gespeichert. Du kannst ihn jetzt auch mit anderen Uploads vergleichen.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    }
  };
  const save = async () => {
    if (!result || !metric) return;
    setSaving(true);
    setMessage("");
    try {
      const chapterOverview =
        scope === "documents" && format !== "csv"
          ? (
              await Promise.all(
                rows.map(async (row) => {
                  try {
                    return (
                      await call<QualityReport>("quality", {
                        ids: [],
                        bookId: row.documentId,
                        baselineId: activeBaseline || null,
                      })
                    ).rows;
                  } catch {
                    return [];
                  } // A legacy import can lack recoverable chapter structure.
                }),
              )
            ).flat()
          : [];
      const content = qualityExport(
        format,
        { ...result, rows },
        metric.id,
        useDelta,
        chapterIds,
        appendix,
        chapterOverview,
      );
      const ok = await saveFile(
        "Bookalyzer-Qualitaetslabor." + format,
        content,
        format,
      );
      if (ok) setMessage("Bericht gespeichert.");
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  if (!documents.length)
    return (
      <div className="empty-card welcome-empty">
        <BookOpen size={30} />
        <h2>Dein Qualitätslabor wartet auf den ersten Text.</h2>
        <p>Füge oben einen Text hinzu und starte die lokale Analyse.</p>
      </div>
    );
  return (
    <div className="quality-lab">
      <section className="quality-controls compact">
        <div className="quality-control-top">
          <div className="segmented" aria-label="Ergebnistiefe">
            <button
              className={display === "overview" ? "active" : ""}
              onClick={() => setDisplay("overview")}
            >
              Auf einen Blick
            </button>
            <button
              className={display === "details" ? "active" : ""}
              onClick={() => setDisplay("details")}
            >
              Details · 51 Kennzahlen
            </button>
          </div>
          <div className="quality-export">
            <select
              aria-label="Format des Qualitätsberichts"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              <option value="html">HTML</option>
              {window.bookalyzer && <option value="pdf">PDF</option>}
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
            <button
              className="button secondary"
              disabled={!result || saving || !rows.length}
              onClick={() => void save()}
            >
              <ArrowDownToLine size={15} />
              {saving ? "Exportiert …" : "Kurzbericht"}
            </button>
          </div>
        </div>
        <div className="quality-primary-selectors">
          <label>
            {scope === "chapters" ? "Kapitel im Fokus" : "Text im Fokus"}
            <select
              value={focused?.id || ""}
              onChange={(e) => {
                const id = e.target.value;
                setFocusedId(id);
                if (scope === "chapters" && display === "overview")
                  setChapterIds((current) =>
                    current.includes(id) ? current : [...current, id].slice(-6),
                  );
              }}
            >
              {rows.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Referenztext (optional)
            <select
              value={activeBaseline}
              onChange={(e) => {
                setBaselineId(e.target.value);
                setDelta(!!e.target.value);
              }}
            >
              <option value="">Ohne Baseline</option>
              {data.baselines.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <details className="quality-compare-settings">
          <summary>
            Texte und Kapitel auswählen · Vergleich und Bericht anpassen
          </summary>
          <div className="segmented" aria-label="Analyseeinheiten">
            <button
              className={scope === "documents" ? "active" : ""}
              onClick={() => setScope("documents")}
            >
              Texte vergleichen
            </button>
            <button
              className={scope === "chapters" ? "active" : ""}
              onClick={() => {
                if (focused) setBookId(focused.documentId);
                setScope("chapters");
              }}
            >
              Kapitel vergleichen
            </button>
          </div>
          {scope === "documents" ? (
            <fieldset className="quality-document-picker">
              <legend>Bis zu sechs Texte nebeneinander</legend>
              {documents.map((doc) => (
                <label key={doc.id}>
                  <input
                    type="checkbox"
                    checked={activeIds.includes(doc.id)}
                    disabled={
                      !activeIds.includes(doc.id) && activeIds.length >= 6
                    }
                    onChange={(e) =>
                      setIds(
                        e.target.checked
                          ? [...activeIds, doc.id]
                          : activeIds.filter((id) => id !== doc.id),
                      )
                    }
                  />
                  <i style={{ background: doc.color }} />
                  {doc.title}
                </label>
              ))}
            </fieldset>
          ) : (
            <label className="quality-book">
              Buch
              <select
                value={activeBook}
                onChange={(e) => setBookId(e.target.value)}
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title}
                  </option>
                ))}
              </select>
              <small>
                Alle erkannten Kapitel werden separat berechnet, auch bei
                älteren Analysen mit kapitelübergreifenden Segmenten.
              </small>
            </label>
          )}
          <div className="quality-baseline">
            <label>
              Fester Referenztext
              <select
                value={activeBaseline}
                onChange={(e) => {
                  setBaselineId(e.target.value);
                  setDelta(!!e.target.value);
                }}
              >
                <option value="">Ohne Baseline</option>
                {data.baselines.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="quality-toggle">
              <input
                type="checkbox"
                checked={useDelta}
                disabled={!activeBaseline}
                onChange={(e) => setDelta(e.target.checked)}
              />
              Abweichung zur Baseline anzeigen
            </label>
            <button
              className="text-button"
              disabled={!focused}
              onClick={() => void createBaseline()}
            >
              Buch im Fokus als Referenz speichern
            </button>
          </div>
          <label className="quality-toggle">
            <input
              type="checkbox"
              checked={appendix}
              onChange={(e) => setAppendix(e.target.checked)}
            />{" "}
            Vollständige Kennzahlen und Methoden an den Bericht anhängen
          </label>
        </details>
      </section>
      {message && (
        <p className="quality-message" role="status">
          {message}
        </p>
      )}
      {loading && (
        <div className="quality-loading" role="status">
          Lokale Kennzahlen werden berechnet. Bei langen Büchern kann der erste
          Aufruf etwas dauern.
        </div>
      )}
      {error && (
        <div className="notice error" role="alert">
          {error}
          <button
            className="button secondary"
            onClick={() => setRetry((v) => v + 1)}
          >
            Erneut versuchen
          </button>
        </div>
      )}
      {result && (
        <>
          {display === "overview" && focused && (
            <QualityOverview
              focused={focused}
              compared={compared}
              metrics={result.catalog.metrics}
              active={overviewMetric}
              onMetric={setOverviewMetric}
              onEvidence={(e) => void openEvidence(e)}
              onIntentional={(e, v) => void markIntentional(e, v)}
              chapters={
                scope === "chapters" ? { ...result, rows } : chapterPreview
              }
              chapterLoading={chapterLoading}
              chapterError={chapterError}
              onChapter={(row, metric) => {
                if (metric) setOverviewMetric(metric);
                requestedFocus.current = row.id;
                setBookId(row.documentId);
                if (scope === "chapters") {
                  setFocusedId(row.id);
                  setChapterIds((current) =>
                    current.includes(row.id)
                      ? current
                      : [...current, row.id].slice(-6),
                  );
                  requestedFocus.current = "";
                } else setScope("chapters");
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              onDetails={() => {
                setDisplay("details");
                setGroup(
                  overviewMetric === "mattr"
                    ? "vocabulary"
                    : overviewMetric === "sentenceRepeat"
                      ? "repetition"
                      : "rhythm",
                );
                setMetricId(overviewMetric);
              }}
            />
          )}
          <div hidden={display !== "details"}>
            <div className="quality-principle">
              <span className="quality-local">
                LOKAL · {result.catalog.metrics.length} KENNZAHLEN
              </span>
              <p>{result.catalog.note}</p>
            </div>
            <div className="quality-groups" aria-label="Analysebereiche">
              {result.catalog.groups.map((g) => (
                <button
                  key={g.id}
                  className={group === g.id ? "active" : ""}
                  onClick={() => {
                    setGroup(g.id);
                    setMetricId(
                      result.catalog.metrics.find((m) => m.group === g.id)
                        ?.id || "",
                    );
                  }}
                >
                  <span>{g.label}</span>
                  <small>
                    {
                      result.catalog.metrics.filter((m) => m.group === g.id)
                        .length
                    }{" "}
                    Kennzahlen
                  </small>
                </button>
              ))}
            </div>
            {metric && rows.length > 0 && (
              <>
                <section className="quality-card">
                  <div className="quality-card-heading">
                    <div>
                      <span className="eyebrow purple">
                        {selectedGroup?.label}
                      </span>
                      <h2>
                        {useDelta
                          ? "Abstand zu deiner Baseline."
                          : "Ein Merkmal, mehrere Perspektiven."}
                      </h2>
                      <p>
                        {useDelta
                          ? "0 = gleicher Messwert. Plus und Minus beschreiben Unterschiede, keine Verbesserung."
                          : "Gleiche Einheit und gemeinsame Achse für alle ausgewählten Texte."}
                      </p>
                    </div>
                    <label>
                      Kennzahl
                      <select
                        value={metric.id}
                        onChange={(e) => setMetricId(e.target.value)}
                      >
                        {metrics.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <QualityBars
                    rows={compared}
                    metric={metric}
                    delta={useDelta}
                  />
                  {new Set(rows.map((r) => r.quality.language)).size > 1 && (
                    <p className="quality-fine">
                      Mehrere Textsprachen in der Auswahl: absolute Werte sind
                      nur explorativ vergleichbar. Baseline-Deltas zwischen
                      verschiedenen Sprachen werden ausgelassen.
                    </p>
                  )}
                  {result.baseline && (
                    <p className="quality-baseline-caption">
                      Referenz: <strong>{result.baseline.name}</strong> ·{" "}
                      {number(result.baseline.wordCount)} Wörter · unveränderter
                      Textstand. Goldene Markierungen zeigen den passenden
                      Referenzmedian je Text; Bänder die mittleren 50 % ab drei
                      Referenzausschnitten.
                    </p>
                  )}
                  <details className="quality-method" key={metric.id}>
                    <summary>
                      {KIND[metric.kind]} · So wird „{metric.label}“ berechnet
                    </summary>
                    <p className="quality-formula">{metric.formula}</p>
                    <p>{metric.note}</p>
                    <p>
                      Mindestens {metric.minWords} Wörter · Sprachen:{" "}
                      {metric.languages.join(", ")} · Methodenversion{" "}
                      {result.catalog.version}
                    </p>
                    {metric.source &&
                      result.catalog.sources
                        .filter((s) => s.id === metric.source)
                        .map((s) => (
                          <a
                            key={s.id}
                            href={s.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {s.label}
                          </a>
                        ))}
                  </details>
                </section>
                <section className="quality-card">
                  <div className="quality-card-heading">
                    <div>
                      <h2>{selectedGroup?.label} auf einen Blick.</h2>
                      <p>
                        {useDelta
                          ? "Blau = niedriger, Violett = höher als die passende Referenz. Null bleibt neutral; feste Farbskala je Kennzahl."
                          : "Dunkler = höherer Messwert auf einer festen Skala je Kennzahl. Die Auswahl verändert die Farbe nicht."}{" "}
                        Keine Gut-/Schlecht-Skala. Kennzahl anklicken für
                        Details.
                      </p>
                    </div>
                  </div>
                  <QualityHeatmap
                    rows={compared}
                    metrics={metrics}
                    delta={useDelta}
                    selected={metric.id}
                    onSelect={setMetricId}
                  />
                </section>
                {scope === "chapters" && (
                  <section className="quality-card">
                    <h2>Jedes Kapitel im Vergleich.</h2>
                    <p>
                      Die Liste enthält alle Kapitel. Wähle bis zu sechs für
                      Diagramm und Merkmalsmatrix; klicke einen Kapitelnamen für
                      Fundstellen.
                    </p>
                    <div className="quality-chapters-scroll">
                      <table className="quality-chapters">
                        <thead>
                          <tr>
                            <th>Diagramm</th>
                            <th>Kapitel</th>
                            <th>Wörter</th>
                            <th>{metric.label}</th>
                            <th>Δ Baseline · {qualityUnit(metric, true)}</th>
                            <th>Verfügbarkeit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((row) => (
                            <tr
                              key={row.id}
                              className={
                                focused?.id === row.id ? "selected" : ""
                              }
                            >
                              <td>
                                <input
                                  type="checkbox"
                                  aria-label={row.title + " im Diagramm"}
                                  checked={chapterIds.includes(row.id)}
                                  disabled={
                                    !chapterIds.includes(row.id) &&
                                    chapterIds.length >= 6
                                  }
                                  onChange={(e) =>
                                    setChapterIds(
                                      e.target.checked
                                        ? [...chapterIds, row.id]
                                        : chapterIds.filter(
                                            (id) => id !== row.id,
                                          ),
                                    )
                                  }
                                />
                              </td>
                              <th>
                                <button onClick={() => setFocusedId(row.id)}>
                                  {row.title}
                                </button>
                              </th>
                              <td>{number(row.quality.words)}</td>
                              <td>{label(row.quality.values[metric.id])}</td>
                              <td>
                                {label(
                                  row.delta?.values[metric.id] ?? null,
                                  true,
                                )}
                              </td>
                              <td>
                                {(useDelta
                                  ? row.delta?.reasons[metric.id]
                                  : row.quality.reasons[metric.id]) ||
                                  (row.quality.words < 300
                                    ? "Kurzes Kapitel; vorsichtig einordnen"
                                    : "Verfügbar")}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )}
                <section className="quality-card">
                  <div className="quality-card-heading">
                    <div>
                      <h2>
                        {scope === "chapters"
                          ? "Der Verlauf durch das Buch."
                          : "Der Verlauf durch den Text."}
                      </h2>
                      <p>
                        {scope === "chapters"
                          ? "Ein Punkt pro Kapitel; anklicken, um die Fundstellen zu öffnen."
                          : "Ein Punkt pro Analysesegment. Fehlende Messwerte bleiben als Lücken sichtbar."}
                      </p>
                    </div>
                    <label>
                      Detailansicht für
                      <select
                        value={focused?.id || ""}
                        onChange={(e) => setFocusedId(e.target.value)}
                      >
                        {rows.map((row) => (
                          <option key={row.id} value={row.id}>
                            {row.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {progressLoading ? (
                    <p role="status">Segmentverlauf wird lokal berechnet …</p>
                  ) : progressError ? (
                    <p role="alert">{progressError}</p>
                  ) : (
                    <QualityProgression
                      points={points}
                      metric={metric}
                      delta={useDelta}
                      onPoint={
                        scope === "chapters"
                          ? (index) => setFocusedId(rows[index].id)
                          : undefined
                      }
                    />
                  )}
                </section>
                {focused && (
                  <div className="quality-detail-grid">
                    <section className="quality-card">
                      <h2>Rhythmus-Fingerabdruck</h2>
                      <p>
                        {focused.title} · {number(focused.quality.sentences)}{" "}
                        Sätze · {number(focused.quality.paragraphs)} Absätze
                      </p>
                      <CadenceChart row={focused} />
                      <p className="quality-fine">
                        Bis zu 160 Gruppen in Lesereihenfolge. Linie:
                        Mittelwert, Band: kürzester bis längster Satz je Gruppe.
                        Kein „Humanitätswert“.
                      </p>
                      <div className="quality-wordlists">
                        <div>
                          <h3>Häufige Nicht-Stoppwörter</h3>
                          {focused.quality.keywords.slice(0, 10).map((w) => (
                            <span className="quality-word" key={w.word}>
                              {w.word}
                              <b>{w.count}</b>
                            </span>
                          ))}
                        </div>
                        <div>
                          <h3>Wiederkehrende Dreierphrasen</h3>
                          {focused.quality.phrases.slice(0, 6).map((p) => (
                            <p key={p.text} className="quality-phrase">
                              <span>{p.text}</span>
                              <b>{p.count}×</b>
                            </p>
                          ))}
                          {!focused.quality.phrases.length && (
                            <p className="quality-fine">
                              Keine Treffer oder Bereich deaktiviert.
                            </p>
                          )}
                        </div>
                      </div>
                    </section>
                    <QualityFindingsPanel
                      key={focused.id}
                      row={focused}
                      metrics={result.catalog.metrics}
                      onEvidence={(e) => void openEvidence(e)}
                      onIntentional={(e, value) =>
                        void markIntentional(e, value)
                      }
                    />
                  </div>
                )}
                <details className="quality-card quality-dictionary">
                  <summary>
                    <SlidersHorizontal size={17} />
                    Methoden, Wortlisten und Vergleichsgrenzen
                  </summary>
                  <p>
                    Alle Methoden laufen offline. Wörter werden
                    kleingeschrieben; Flexionsformen bleiben getrennt.
                    Mehrwortausdrücke, Ironie, Figurenpsychologie,
                    Faktenrichtigkeit und semantische Kohärenz werden damit
                    nicht zuverlässig erfasst. Satz- und Absatzgrenzen hängen
                    von der Textqualität des Imports ab. Die Mindestlängen sind
                    vorsichtige Anzeigegrenzen, keine statistische Validierung.
                    Gesamttexte und Kapitel verwenden die Absatzgrenzen des
                    Imports. Bei alten Importen ohne Originalstruktur wird die
                    eingeschränkte Grundlage angezeigt. Bei Dreierphrasen zählt
                    die Trefferzahl verschiedene wiederholte Formulierungen; die
                    Beispiele sind nach Häufigkeit ausgewählt.
                  </p>
                  <p>
                    {result.baseline?.derivation ||
                      "Gleiche Methodenversion, Sprache und Einstellungen verbessern die Vergleichbarkeit."}{" "}
                    Unterschiedliche Genres, Textlängen und Dialoganteile können
                    große Abweichungen verursachen. Alte Analysen erhalten diese
                    lokalen Auswertungen beim Öffnen des Labors.
                  </p>
                  <h3>Offene Wortlisten</h3>
                  {Object.entries(result.catalog.lexicons).map(
                    ([key, lists]) => (
                      <details key={key}>
                        <summary>
                          {
                            result.catalog.metrics.find((m) => m.id === key)
                              ?.label
                          }
                        </summary>
                        {Object.entries(lists).map(([language, words]) => (
                          <p key={language}>
                            <b>{language}:</b> {words}
                          </p>
                        ))}
                      </details>
                    ),
                  )}
                  <details>
                    <summary>Stoppwörter</summary>
                    {Object.entries(result.catalog.stopwords).map(
                      ([language, words]) => (
                        <p key={language}>
                          <b>{language}:</b> {words.join(", ")}
                        </p>
                      ),
                    )}
                  </details>
                  <h3>Quellen</h3>
                  {result.catalog.sources.map((s) => (
                    <p key={s.id}>
                      <a href={s.url} target="_blank" rel="noreferrer">
                        {s.label}
                      </a>
                    </p>
                  ))}
                </details>
              </>
            )}
          </div>
          {!rows.length && (
            <p className="quality-empty">
              Wähle mindestens einen fertig analysierten Text.
            </p>
          )}
        </>
      )}
      <dialog
        ref={readerDialog}
        className="quality-reader-dialog"
        aria-label="Originaltext der Fundstelle"
        onClose={() => {
          readerGeneration.current++;
          setReader(null);
          setReaderError("");
          setReaderLoading(false);
        }}
      >
        <div className="quality-reader-toolbar">
          <div>
            <span className="eyebrow">TEXTSTELLE PRÜFEN</span>
            <h2>{focused?.title}</h2>
          </div>
          <button
            className="button secondary"
            autoFocus
            onClick={() => readerDialog.current?.close()}
          >
            Schließen
          </button>
        </div>
        {readerLoading && <p role="status">Textkontext wird geladen …</p>}
        {readerError && <p role="alert">{readerError}</p>}
        {reader && (
          <p className="quality-reader-content">
            {reader.before}
            <mark tabIndex={-1}>{reader.text}</mark>
            {reader.truncated ? " … [lange Fundstelle gekürzt] … " : ""}
            {reader.after}
          </p>
        )}
        <p className="quality-fine">
          Lies die Stelle im Zusammenhang. Der Hinweis kann ein bewusstes
          Stilmittel betreffen. Esc schließt diese Ansicht.
        </p>
      </dialog>
    </div>
  );
}
