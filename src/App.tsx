import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { ComparisonWorkspace } from "./ComparisonWorkspace";
import { QualityLab } from "./QualityLab";
import {
  Activity,
  Archive,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  FlaskConical,
  FolderOpen,
  GitCompareArrows,
  Layers3,
  Library,
  LoaderCircle,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { call, readFiles, saveFile } from "./api";
import {
  DistanceMatrix,
  Histogram,
  number,
  ProfileChart,
  TrendChart,
  ViolinChart,
} from "./charts";
import { SettingsFields } from "./SettingsFields";
import { StoryScopeForm } from "./StoryScopeForm";
import { LocalAnalysisForm } from "./LocalAnalysisForm";
import { LibraryTransferPanel } from "./LibraryTransferPanel";
import { exportContent } from "./export";
import type {
  Bootstrap,
  Comparison,
  Document,
  Segment,
  Settings,
  UploadFile,
} from "./types";

function Modal({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
  closeDisabled = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  closeDisabled?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const items = Array.from(
          ref.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]),input:not([disabled]),select,textarea,a[href],[tabindex="0"]',
          ) || [],
        ).filter((el) => el.offsetParent !== null);
        if (!items.length) {
          e.preventDefault();
          return;
        }
        if (
          e.shiftKey &&
          (document.activeElement === items[0] ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          items.at(-1)?.focus();
        } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
          e.preventDefault();
          items[0].focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = original;
      before?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop">
      <div
        className={"modal " + (wide ? "wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        tabIndex={-1}
        ref={ref}
      >
        <header className="modal-header">
          <div>
            <h2 id="dialog-title">{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button
            className="icon-button"
            aria-label="Dialog schließen"
            disabled={closeDisabled}
            onClick={onClose}
          >
            <X size={21} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return <span className="dot" style={{ background: color }} />;
}
function Legend({ documents }: { documents: Document[] }) {
  return (
    <div className="legend">
      {documents.map((d) => (
        <span key={d.id}>
          <Dot color={d.color} />
          {d.title}
        </span>
      ))}
    </div>
  );
}
function EmptyChart({ children }: { children: ReactNode }) {
  return (
    <div className="empty-chart">
      <BarChart3 size={32} strokeWidth={1.2} />
      <div>{children}</div>
    </div>
  );
}
function Panel({
  title,
  kicker,
  action,
  children,
  className = "",
}: {
  title: string;
  kicker?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"panel " + className}>
      <div className="panel-heading">
        <div>
          {kicker && <div className="eyebrow">{kicker}</div>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function UploadDialog({
  defaults,
  model,
  onClose,
  onComplete,
}: {
  defaults: Settings;
  model: string;
  onClose: () => void;
  onComplete: (ids: string[]) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<
    (UploadFile & { settings: Settings; draft?: Document })[]
  >([]);
  const [active, setActive] = useState(0),
    [paste, setPaste] = useState(false),
    [text, setText] = useState(""),
    [title, setTitle] = useState("Mein Text");
  const [step, setStep] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [consent, setConsent] = useState(false),
    [checked, setChecked] = useState(false),
    [approver, setApprover] = useState("");
  const [preview, setPreview] = useState<{
    text: string;
    title: string;
  } | null>(null);
  const add = (incoming: UploadFile[]) => {
    if (files.length + incoming.length > 12) {
      setError("Maximal 12 Dateien pro Upload.");
      return;
    }
    setFiles((prev) => [
      ...prev,
      ...incoming.map((f) => ({ ...f, settings: { ...defaults } })),
    ]);
    setError("");
  };
  const pick = async () => {
    try {
      if (window.bookalyzer) add(await window.bookalyzer.pickFiles());
      else input.current?.click();
    } catch (e) {
      setError(String((e as Error).message));
    }
  };
  const fromFiles = async (incoming: File[]) => {
    try {
      add(await readFiles(incoming));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const prepare = async () => {
    setBusy(true);
    setError("");
    try {
      let next = files.slice();
      if (paste && text.trim()) {
        const incoming = await readFiles([
          new File([text], (title.trim() || "Mein Text") + ".txt", {
            type: "text/plain",
          }),
        ]);
        next.push({ ...incoming[0], settings: { ...defaults } });
      }
      if (!next.length)
        throw new Error("Bitte mindestens einen Text hinzufügen.");
      if (next.length > 12) throw new Error("Maximal 12 Dateien pro Upload.");
      setFiles(next);
      setText("");
      setPaste(false);
      for (let i = 0; i < next.length; i++) {
        if (!next[i].draft)
          next[i] = {
            ...next[i],
            draft: await call<Document>("prepare", {
              name: next[i].name,
              base64data: next[i].base64,
              settings: next[i].settings,
            }),
          };
        setFiles(next.slice());
      }
      setStep(1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const external = files.some((f) => f.settings.mode === "codex");
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const ids = files.map((f) => f.draft!.id);
      await call("start", {
        ids,
        consent,
        previewConfirmed: checked,
        approver,
      });
      onComplete(ids);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <Modal
      title={step ? "Vorschau & Analyse" : "Neue Texte hinzufügen"}
      subtitle={
        step
          ? "Die Einstellungen gelten jeweils für diesen Upload."
          : "Dein nächster Text. Eine neue Perspektive."
      }
      onClose={onClose}
      wide
    >
      <div className="wizard-steps">
        <span className={step === 0 ? "current" : "done"}>
          <b>{step ? <Check size={12} /> : 1}</b>Texte & Einstellungen
        </span>
        <ChevronRight size={15} />
        <span className={step === 1 ? "current" : ""}>
          <b>2</b>Vorschau & Start
        </span>
      </div>
      <div className="modal-content">
        <fieldset className="wizard-fieldset" disabled={busy}>
          {step === 0 ? (
            <>
              <input
                ref={input}
                type="file"
                accept=".txt,.docx,.epub,.pdf"
                multiple
                hidden
                onChange={(e) => {
                  void fromFiles(Array.from(e.target.files || []));
                  e.target.value = "";
                }}
              />
              <div
                className="dropzone"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (!busy) void fromFiles(Array.from(e.dataTransfer.files));
                }}
              >
                <div className="upload-symbol">
                  <Upload size={25} />
                </div>
                <h3>Platz für deine Texte</h3>
                <p>Dateien hier ablegen oder von deinem Gerät auswählen</p>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={pick}
                >
                  <FolderOpen size={16} />
                  Dateien auswählen
                </button>
                <small>
                  TXT, DOCX, EPUB und textbasierte PDF · bis 30 MB je Datei
                </small>
              </div>
              <button
                className="text-button paste-toggle"
                onClick={() => setPaste(!paste)}
              >
                {paste
                  ? "Texteingabe schließen"
                  : "Oder einen Text direkt einfügen"}
                <ChevronDown size={15} />
              </button>
              {paste && (
                <div className="paste-area">
                  <label>
                    Titel
                    <input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </label>
                  <label>
                    Dein Text
                    <textarea
                      rows={6}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="Text hier einfügen …"
                    />
                  </label>
                  <button
                    className="button secondary"
                    disabled={!text.trim() || busy}
                    onClick={async () => {
                      try {
                        add(
                          await readFiles([
                            new File(
                              [text],
                              (title.trim() || "Mein Text") + ".txt",
                            ),
                          ]),
                        );
                        setText("");
                        setPaste(false);
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    <Plus size={15} />
                    Zur Auswahl hinzufügen
                  </button>
                  <p className="field-hint">
                    Anschließend kannst du die Einstellungen dieses Textes
                    anpassen.
                  </p>
                </div>
              )}
              {files.length > 0 && (
                <div className="upload-config">
                  <div className="upload-file-list">
                    {files.map((f, i) => (
                      <div
                        key={i}
                        className={
                          "upload-file " + (active === i ? "active" : "")
                        }
                      >
                        <button onClick={() => setActive(i)}>
                          <FileText size={17} />
                          <span>
                            {f.name}
                            <small>
                              {f.settings.mode === "local"
                                ? "Lokales Textprofil"
                                : "StoryScope"}{" "}
                              · {number(f.settings.targetWords)} Wörter
                            </small>
                          </span>
                        </button>
                        <button
                          className="icon-button"
                          aria-label={"Datei entfernen: " + f.name}
                          disabled={busy}
                          onClick={() => {
                            setFiles(files.filter((_, j) => j !== i));
                            setActive(0);
                          }}
                        >
                          <X size={15} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="upload-settings">
                    <div className="field-heading">
                      Einstellungen für diesen Text
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() =>
                          setFiles((prev) =>
                            prev.map((f, i) =>
                              i === active
                                ? {
                                    ...f,
                                    settings: { ...defaults },
                                    draft: undefined,
                                  }
                                : f,
                            ),
                          )
                        }
                      >
                        Standard laden
                      </button>
                    </div>
                    {files[active] && (
                      <SettingsFields
                        value={files[active].settings}
                        model={model}
                        onChange={(s) =>
                          setFiles((prev) =>
                            prev.map((f, i) =>
                              i === active
                                ? { ...f, settings: s, draft: undefined }
                                : f,
                            ),
                          )
                        }
                      />
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="notice neutral">
                <ShieldCheck size={19} />
                <p>
                  {external
                    ? "Noch wurde kein Text an OpenAI übertragen. Prüfe die Segmentierung und bestätige danach den Start."
                    : "Die lokale Analyse erstellt automatisch Textprofil, Diagramme und Bericht. Alle Berechnungen bleiben auf diesem Gerät."}
                </p>
              </div>
              {files.map((f) => (
                <div className="preview-file" key={f.draft!.id}>
                  <div className="preview-file-heading">
                    <FileText size={18} />
                    <h3>{f.draft!.title}</h3>
                    <span>
                      {number(f.draft!.wordCount)} Wörter ·{" "}
                      {f.draft!.segmentCount} Segmente
                    </span>
                  </div>
                  <div className="segment-preview-list">
                    {f.draft!.segments.map((s) => (
                      <details key={s.id}>
                        <summary>
                          <span>Segment {s.index + 1}</span>
                          <span>{s.title}</span>
                          <b>{number(s.words)} W.</b>
                        </summary>
                        <p>{s.preview}…</p>
                        <button
                          className="text-button"
                          onClick={async () => {
                            try {
                              setPreview(
                                await call("segment", {
                                  id: f.draft!.id,
                                  index: s.index,
                                }),
                              );
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Vollständiges Segment lesen
                          <ArrowUpRight size={14} />
                        </button>
                      </details>
                    ))}
                  </div>
                  {f.settings.mode === "codex" && (
                    <p className="field-hint">
                      {f.draft!.segmentCount * 10} Dimensionsaufrufe · Modell:{" "}
                      {f.settings.model || model} · Reasoning:{" "}
                      {f.settings.reasoningEffort || "Modellstandard"} · Nutzung
                      deines Codex-Kontingents
                    </p>
                  )}
                </div>
              ))}
              {preview && (
                <div className="preview-reader">
                  <div>
                    <strong>{preview.title}</strong>
                    <button
                      className="icon-button"
                      onClick={() => setPreview(null)}
                      aria-label="Textvorschau schließen"
                    >
                      <X size={16} />
                    </button>
                  </div>
                  <pre>{preview.text}</pre>
                </div>
              )}
              {external && (
                <div className="consent-box">
                  <label>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => setChecked(e.target.checked)}
                    />
                    Ich habe die Segmentvorschau geprüft.
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(e) => setConsent(e.target.checked)}
                    />
                    Als Rechteinhaber oder mit dessen Zustimmung gebe ich die
                    Übertragung der gewählten StoryScope-Texte an OpenAI über
                    meinen Codex-Zugang frei.
                  </label>
                  <label>
                    Freigebende Person
                    <input
                      value={approver}
                      onChange={(e) => setApprover(e.target.value)}
                      placeholder="Name"
                    />
                  </label>
                </div>
              )}
            </>
          )}
          {error && (
            <div role="alert" className="notice error">
              {error}
            </div>
          )}
        </fieldset>
      </div>
      <footer className="modal-footer">
        <span>
          {step
            ? files.length + " Texte bereit"
            : files.length + " Texte ausgewählt"}
        </span>
        <div>
          {step === 1 && (
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => {
                setStep(0);
                setConsent(false);
                setChecked(false);
              }}
            >
              Zurück
            </button>
          )}
          <button
            className="button primary"
            disabled={
              busy ||
              (step === 0 && !files.length && !text.trim()) ||
              (step === 1 &&
                external &&
                (!consent || !checked || !approver.trim()))
            }
            onClick={step ? start : prepare}
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : step ? (
              <Sparkles size={16} />
            ) : (
              <ArrowRight size={16} />
            )}{" "}
            {busy
              ? "Wird vorbereitet …"
              : step
                ? "Analysen starten"
                : "Segmentvorschau"}
          </button>
        </div>
      </footer>
    </Modal>
  );
}

export default function App() {
  const [comparisonMode, setComparisonMode] = useState("direct");
  const [data, setData] = useState<Bootstrap | null>(null),
    [selected, setSelected] = useState<string[]>([]),
    [view, setView] = useState("quality");
  const [modal, setModal] = useState<string | null>(null),
    [comparison, setComparison] = useState<Comparison | null>(null),
    [comparing, setComparing] = useState(false);
  const [message, setMessage] = useState(""),
    [loadError, setLoadError] = useState(""),
    [query, setQuery] = useState(""),
    [tab, setTab] = useState("all"),
    [metric, setMetric] = useState("rarity");
  const [draftSettings, setDraftSettings] = useState<Settings | null>(null),
    [saving, setSaving] = useState(false),
    [exportFormat, setExportFormat] = useState("html");
  const [segment, setSegment] = useState<
    (Segment & { text: string; documentTitle: string }) | null
  >(null);
  const [detail, setDetail] = useState<Document | null>(null),
    [showValues, setShowValues] = useState(false);
  const [storyscopeDocument, setStoryscopeDocument] = useState<Document | null>(
    null,
  );
  const initialized = useRef(false);
  const [localDocument, setLocalDocument] = useState<Document | null>(null);
  const [transferBusy, setTransferBusy] = useState(false);
  const closeTransfer = useCallback(() => {
    if (!transferBusy) setModal(null);
  }, [transferBusy]);
  const closeModal = useCallback(() => setModal(null), []);
  const closeSegment = useCallback(() => setSegment(null), []);
  const closeDetail = useCallback(() => setDetail(null), []);
  const closeStoryscope = useCallback(() => setStoryscopeDocument(null), []);
  const closeLocal = useCallback(() => setLocalDocument(null), []);
  const refresh = useCallback(async () => {
    try {
      const next = await call<Bootstrap>("bootstrap");
      setData(next);
      setDetail((previous) =>
        previous
          ? next.documents.find((doc) => doc.id === previous.id) || null
          : null,
      );
      setLoadError("");
      if (!initialized.current) {
        initialized.current = true;
        setSelected(
          next.documents
            .filter((d) => d.status === "ready")
            .slice(0, 3)
            .map((d) => d.id),
        );
      }
    } catch (e) {
      setLoadError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const pending = data?.documents.some(
    (d) =>
      d.status === "queued" || d.status === "analyzing" || storyscopePending(d),
  );
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [pending, refresh]);
  const selectedDocs = (data?.documents || []).filter((d) =>
    selected.includes(d.id),
  );
  const ready = selectedDocs.filter((d) => d.status === "ready"),
    narrative = ready.filter((d) => d.narrative);
  const key = ready.map((d) => d.id + ":" + d.completedAt).join("|");
  useEffect(() => {
    let alive = true;
    setComparison(null);
    if (!key) {
      setComparing(false);
      return;
    }
    setComparing(true);
    call<Comparison>("compare", { ids: ready.map((d) => d.id) })
      .then((result) => {
        if (alive) setComparison(result);
      })
      .catch((e) => {
        if (alive)
          setComparison({
            available: false,
            reason: (e as Error).message,
            series: [],
          });
      })
      .finally(() => {
        if (alive) setComparing(false);
      });
    return () => {
      alive = false;
    };
  }, [key]);
  const toggle = (id: string) => {
    if (selected.includes(id)) setSelected(selected.filter((s) => s !== id));
    else if (selected.length < 6) setSelected([...selected, id]);
    else setMessage("Du kannst bis zu sechs Texte gleichzeitig vergleichen.");
  };
  const openSegment = async (id: string, index: number) => {
    try {
      const result = await call<Segment & { text: string }>("segment", {
        id,
        index,
      });
      setSegment({
        ...result,
        documentTitle: data!.documents.find((d) => d.id === id)!.title,
      });
    } catch (e) {
      setMessage((e as Error).message);
    }
  };
  const openNarrative = (doc: Document) => {
    setSelected([doc.id]);
    setTab("narrative");
    setView("overview");
    setDetail(null);
  };
  const storyscopeAction = (doc: Document) => (
    <div className="storyscope-action">
      {doc.narrative ? (
        <button className="button secondary" onClick={() => openNarrative(doc)}>
          <BarChart3 size={16} /> StoryScope-Diagramme ansehen
        </button>
      ) : storyscopePending(doc) ? (
        <p className="field-hint">
          <LoaderCircle size={14} className="spin" />
          StoryScope{" "}
          {doc.storyscope?.status === "queued"
            ? "in der Warteschlange"
            : "wird ergänzt"}
          . Das lokale Textprofil ist verfügbar.
        </p>
      ) : doc.storyscope?.status === "error" ? (
        <>
          <p className="error-text">StoryScope: {doc.storyscope.error}</p>
          <button
            className="button secondary"
            onClick={async () => {
              try {
                await call("retry", { id: doc.id });
                await refresh();
              } catch (e) {
                setMessage((e as Error).message);
              }
            }}
          >
            <Sparkles size={16} /> StoryScope fortsetzen
          </button>
        </>
      ) : doc.status === "ready" ? (
        <button
          className="button secondary"
          onClick={() => {
            setDetail(null);
            setStoryscopeDocument(doc);
          }}
        >
          <Sparkles size={16} /> StoryScope mit Codex ergänzen
        </button>
      ) : null}
    </div>
  );
  const localActions = (doc: Document) => (
    <div className="local-actions">
      {doc.status === "ready" && (
        <button
          className="text-button"
          onClick={() => {
            setSelected([doc.id]);
            setView("quality");
            setDetail(null);
          }}
        >
          <Activity size={15} /> Qualitätslabor ansehen
        </button>
      )}
      <button
        className="text-button"
        onClick={() => {
          setDetail(null);
          setLocalDocument(doc);
        }}
      >
        <Settings2 size={15} /> Lokale Analyse erweitern
      </button>
    </div>
  );
  const exportReport = async () => {
    setSaving(true);
    try {
      const content = exportContent(exportFormat, ready, data!, comparison);
      const success = await saveFile(
        "Bookalyzer-Bericht." + exportFormat,
        content,
        exportFormat,
      );
      if (success) {
        setModal(null);
        setMessage("Bericht exportiert.");
      }
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  const activeMetric =
    metric === "rarity" && !comparison?.available ? "sentence" : metric;
  const filtered = (data?.documents || []).filter((d) =>
    (d.title + " " + d.name).toLowerCase().includes(query.toLowerCase()),
  );
  const totalWords = ready.reduce((sum, d) => sum + d.wordCount, 0),
    totalSegments = ready.reduce((sum, d) => sum + d.segmentCount, 0);
  const nav = [
    { id: "quality", label: "Textqualität", icon: Activity },
    { id: "overview", label: "Erzählweise", icon: BarChart3 },
    { id: "library", label: "Textbibliothek", icon: Library },
    { id: "compare", label: "Texte vergleichen", icon: GitCompareArrows },
  ];
  return (
    <div className="app">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("quality");
          }}
        >
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          <span>
            Bookalyzer<small>DAS TEXTLABOR</small>
          </span>
        </a>
        <div className="workspace">
          <div className="workspace-icon">
            <BookOpen size={19} />
          </div>
          <div>
            Mein Arbeitsbereich<small>Persönliche Bibliothek</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <div className="nav-label">ENTDECKEN</div>
        <nav>
          {nav.map((item) => (
            <button
              key={item.id}
              className={"nav-item " + (view === item.id ? "active" : "")}
              onClick={() => setView(item.id)}
            >
              <item.icon size={19} />
              {item.label}
              {item.id === "library" && (
                <span className="nav-count">{data?.documents.length || 0}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="nav-label tools-label">WERKZEUGE</div>
        <nav>
          <button
            className="nav-item"
            onClick={() => {
              if (data) {
                setDraftSettings({ ...data.settings });
                setModal("settings");
              }
            }}
          >
            <SlidersHorizontal size={19} />
            Standardeinstellungen
          </button>
          <button
            className="nav-item"
            disabled={!data}
            onClick={() => setModal("library-transfer")}
          >
            <Archive size={19} />
            Datenbestand sichern & laden
          </button>
          <button
            className={"nav-item " + (view === "method" ? "active" : "")}
            onClick={() => setView("method")}
          >
            <FlaskConical size={19} />
            Methode & Studie
            <ArrowUpRight className="nav-end" size={14} />
          </button>
        </nav>
        <div className="sidebar-study">
          <span className="study-orbit">
            <FlaskConical size={22} />
          </span>
          <h3>Literatur, messbar gemacht.</h3>
          <p>Erzählmuster entdecken mit den Methoden von StoryScope.</p>
          <button className="text-button" onClick={() => setView("method")}>
            Die Methode verstehen
            <ArrowRight size={14} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <span className="status-light" />
          <div>
            Lokal gespeichert<small>Deine Texte. Dein Arbeitsbereich.</small>
          </div>
          <ShieldCheck size={17} />
        </div>
      </aside>
      <main className={"main" + (view === "quality" ? " quality-page" : "")}>
        <header className="topbar">
          <span>
            Arbeitsbereich <ChevronRight size={14} />{" "}
            <strong>
              {view === "overview"
                ? "Erzählweise"
                : view === "library"
                  ? "Textbibliothek"
                  : view === "compare"
                    ? "Vergleich"
                    : view === "quality"
                      ? "Textqualität"
                      : "Methode & Studie"}
            </strong>
          </span>
          <div>
            <span className="version">
              STORYSCOPE <span>v4</span>
            </span>
            <button
              className="icon-button"
              aria-label="Hilfe zur Methodik"
              onClick={() => setView("method")}
            >
              <CircleHelp size={18} />
            </button>
            <span className="avatar">BA</span>
          </div>
        </header>
        <div className="page">
          <div className="page-heading">
            <div>
              <div className="eyebrow purple">
                {view === "method"
                  ? "WISSENSCHAFTLICHE GRUNDLAGE"
                  : view === "library"
                    ? "DEINE SAMMLUNG"
                    : "EIN NEUER BLICK AUF DEINE TEXTE"}
              </div>
              <h1>
                {view === "overview"
                  ? "Zwischen den Zeilen."
                  : view === "library"
                    ? "Deine Textbibliothek."
                    : view === "compare"
                      ? "Unterschiede entdecken."
                      : view === "quality"
                        ? "Dein Text auf einen Blick."
                        : "Verstehen, was wir messen."}
              </h1>
              <p>
                {view === "library"
                  ? "Alle Uploads, Einstellungen und Analyseberichte an einem Ort."
                  : view === "method"
                    ? "Nachvollziehbare Merkmale. Eine ehrliche Einordnung."
                    : view === "quality"
                      ? "Verstehen, was auffällt. Wissen, wo du anfangen kannst."
                      : "Erzählmuster erkennen. Texte nebeneinander betrachten. Mehr verstehen."}
              </p>
            </div>
            <div className="heading-actions">
              {view !== "method" &&
                view !== "quality" &&
                !(view === "compare" && comparisonMode !== "direct") && (
                  <button
                    className="button secondary"
                    disabled={!ready.length || comparing}
                    onClick={() => setModal("export")}
                  >
                    <ArrowDownToLine size={16} />
                    Bericht exportieren
                  </button>
                )}
              <button
                className="button primary"
                disabled={!data}
                onClick={() => setModal("upload")}
              >
                <Plus size={18} />
                Texte hinzufügen
              </button>
            </div>
          </div>
          {loadError && (
            <div className="notice error" role="alert">
              <p>{loadError}</p>
              <button
                className="button secondary"
                onClick={() => void refresh()}
              >
                Erneut verbinden
              </button>
            </div>
          )}
          {!data && !loadError && (
            <div className="loading">
              <LoaderCircle size={28} className="spin" />
              <h3>Dein Textlabor wird vorbereitet</h3>
              <p>Vorhandene Analysen und Referenzen werden geladen.</p>
            </div>
          )}
          {data && view === "library" && (
            <>
              <div className="library-toolbar">
                <div className="search">
                  <Search size={17} />
                  <input
                    placeholder="Texte durchsuchen …"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    aria-label="Texte durchsuchen"
                  />
                </div>
                <span>
                  {data.documents.length} Texte · {selected.length} ausgewählt
                </span>
                <button
                  className="button secondary"
                  disabled={!selected.length}
                  onClick={() => setView("compare")}
                >
                  <GitCompareArrows size={16} />
                  Auswahl vergleichen
                </button>
              </div>
              <div className="library-grid">
                {filtered.map((doc) => (
                  <article
                    key={doc.id}
                    className={
                      "library-card " +
                      (selected.includes(doc.id) ? "selected" : "")
                    }
                    style={{ "--doc-color": doc.color } as CSSProperties}
                  >
                    <div className="library-card-top">
                      <span className="document-glyph">
                        <FileText size={25} />
                      </span>
                      <label className="selection-check">
                        <input
                          type="checkbox"
                          checked={selected.includes(doc.id)}
                          onChange={() => toggle(doc.id)}
                          aria-label={doc.title + " auswählen"}
                        />
                      </label>
                    </div>
                    <small>
                      {doc.name.split(".").at(-1)?.toUpperCase()} ·{" "}
                      {doc.settings.language.toUpperCase()}
                    </small>
                    <h2>{doc.title}</h2>
                    <p>
                      {number(doc.wordCount)} Wörter · {doc.segmentCount}{" "}
                      Segmente
                    </p>
                    <Status doc={doc} />
                    {(doc.status === "ready" ||
                      (doc.status === "error" &&
                        doc.settings.mode === "codex")) &&
                      localActions(doc)}
                    {doc.status === "ready" && storyscopeAction(doc)}
                    {doc.progress && (
                      <div className="job-progress">
                        <progress
                          value={doc.progress.completed}
                          max={doc.progress.total}
                        />
                        <span>
                          {doc.progress.completed} / {doc.progress.total}{" "}
                          Dimensionen gespeichert
                        </span>
                      </div>
                    )}
                    <div className="card-divider" />
                    <div className="library-card-bottom">
                      <button
                        className="text-button"
                        onClick={() => setDetail(doc)}
                      >
                        Bericht ansehen
                        <ArrowRight size={15} />
                      </button>
                      <button
                        className="icon-button"
                        title="Aus Bibliothek ausblenden (Dateien bleiben gespeichert)"
                        aria-label={doc.title + " ausblenden"}
                        disabled={
                          doc.status === "queued" ||
                          doc.status === "analyzing" ||
                          storyscopePending(doc)
                        }
                        onClick={async () => {
                          try {
                            await call("remove", { id: doc.id });
                            setSelected((prev) =>
                              prev.filter((id) => id !== doc.id),
                            );
                            await refresh();
                            setMessage(
                              "Text ausgeblendet. Die gespeicherten Dateien bleiben erhalten.",
                            );
                          } catch (e) {
                            setMessage((e as Error).message);
                          }
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    {doc.status === "error" && (
                      <>
                        <p className="error-text">{doc.error}</p>
                        <button
                          className="button secondary"
                          onClick={async () => {
                            try {
                              await call("retry", { id: doc.id });
                              await refresh();
                            } catch (e) {
                              setMessage((e as Error).message);
                            }
                          }}
                        >
                          Analyse wiederholen
                        </button>
                      </>
                    )}
                  </article>
                ))}
                <button
                  className="library-add"
                  onClick={() => setModal("upload")}
                >
                  <Plus size={28} />
                  <strong>Ein neuer Text</strong>
                  <span>Hochladen und entdecken</span>
                </button>
              </div>
              {filtered.length === 0 && query && (
                <p className="muted">Keine Texte für diese Suche gefunden.</p>
              )}
            </>
          )}
          {data && (view === "overview" || view === "compare") && (
            <>
              <div className="quality-promo">
                <div>
                  <strong>Neu: das Qualitätslabor</strong>
                  <p>
                    51 lokale Kennzahlen für Lesbarkeit, Wortschatz, Rhythmus
                    und Stil. Mit Fundstellen und Kapitel-Baselines.
                  </p>
                </div>
                <button
                  className="button secondary"
                  onClick={() => setView("quality")}
                >
                  <Activity size={16} />
                  Qualitäten untersuchen
                </button>
              </div>
              <section className="selection-bar">
                <div className="selection-label">
                  <Layers3 size={18} />
                  <span>DEINE AUSWAHL</span>
                  <b>{selectedDocs.length.toString().padStart(2, "0")}</b>
                </div>
                <div className="selected-chips">
                  {selectedDocs.map((doc) => (
                    <button
                      key={doc.id}
                      className="text-chip"
                      style={{ "--doc-color": doc.color } as CSSProperties}
                      onClick={() => toggle(doc.id)}
                      aria-label={doc.title + " aus Vergleich entfernen"}
                    >
                      <Dot color={doc.color} />
                      {doc.title}
                      <X size={13} />
                    </button>
                  ))}
                  <button
                    className="add-chip"
                    onClick={() => setModal("select")}
                  >
                    <Plus size={14} />
                    Text wählen
                  </button>
                </div>
                <button
                  className="icon-button"
                  title="Standardeinstellungen"
                  onClick={() => {
                    setDraftSettings({ ...data.settings });
                    setModal("settings");
                  }}
                >
                  <Settings2 size={18} />
                </button>
              </section>
              {view === "compare" && (
                <div
                  className="comparison-tabs"
                  role="tablist"
                  aria-label="Vergleichsart"
                >
                  {[
                    ["direct", "Direkt vergleichen"],
                    ["baseline", "Gegen Baseline"],
                    ["chapters", "Kapitel vergleichen"],
                  ].map(([id, label]) => (
                    <button
                      key={id}
                      role="tab"
                      aria-selected={comparisonMode === id}
                      className={comparisonMode === id ? "active" : ""}
                      onClick={() => setComparisonMode(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
              {pending && (
                <div className="notice neutral">
                  <LoaderCircle size={17} className="spin" />
                  <p>
                    Analysen laufen. Die Diagramme erscheinen automatisch,
                    sobald ein Bericht fertig ist.
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setView("library")}
                  >
                    Zur Bibliothek
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
              {selectedDocs.some((d) => d.status === "error") && (
                <div className="notice error">
                  <p>
                    Eine Analyse konnte nicht abgeschlossen werden. In der
                    Bibliothek findest du die Ursache und kannst sie fortsetzen.
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setView("library")}
                  >
                    Details öffnen
                  </button>
                </div>
              )}
              {view === "compare" &&
              comparisonMode !== "direct" &&
              data.documents.some((d) => d.status === "ready") ? (
                <ComparisonWorkspace
                  mode={comparisonMode}
                  documents={ready}
                  data={data}
                  refresh={refresh}
                />
              ) : !ready.length ? (
                <section className="welcome-empty">
                  <div className="empty-illustration">
                    <FileText size={56} strokeWidth={1} />
                    <Activity size={70} strokeWidth={1.1} />
                  </div>
                  <h2>Jeder Text hat ein eigenes Profil.</h2>
                  <p>
                    Füge einen Text hinzu oder wähle eine vorhandene Analyse.
                    <br />
                    Diagramme machen Rhythmus, Erzählstruktur und Unterschiede
                    sichtbar.
                  </p>
                  <button
                    className="button primary"
                    onClick={() =>
                      setModal(data.documents.length ? "select" : "upload")
                    }
                  >
                    <Plus size={17} />
                    {data.documents.length
                      ? "Texte auswählen"
                      : "Ersten Text hinzufügen"}
                  </button>
                  <div className="empty-formats">
                    TXT <span>·</span> DOCX <span>·</span> EPUB <span>·</span>{" "}
                    PDF
                  </div>
                </section>
              ) : (
                <>
                  <div className="stat-grid">
                    <Stat
                      icon={<FileText size={19} />}
                      label="Wörter im Vergleich"
                      value={number(totalWords)}
                      note={
                        ready.length +
                        " " +
                        (ready.length === 1
                          ? "ausgewählter Text"
                          : "ausgewählte Texte")
                      }
                    />
                    <Stat
                      icon={<Layers3 size={19} />}
                      label="Analysierte Segmente"
                      value={number(totalSegments)}
                      note="Ohne Überlappung"
                    />
                    <Stat
                      icon={<Activity size={19} />}
                      label="Narrative Merkmale"
                      value={narrative.length ? "304" : "–"}
                      note={
                        narrative.length
                          ? "In zehn Dimensionen"
                          : "StoryScope noch nicht extrahiert"
                      }
                    />
                    <Stat
                      icon={<FlaskConical size={19} />}
                      label="Einordnung"
                      value="Explorativ"
                      note="Merkmale statt Herkunftsbeweis"
                      text
                    />
                  </div>
                  <div className="section-tabs">
                    <div>
                      {[
                        ["all", "Analyseübersicht"],
                        ["narrative", "Narrative Signale"],
                        ["language", "Sprachliches Profil"],
                      ].map(([id, label]) => (
                        <button
                          key={id}
                          className={tab === id ? "active" : ""}
                          onClick={() => setTab(id)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <span>
                      <span className="status-light" />
                      {comparing
                        ? "Vergleich wird berechnet"
                        : "Aus gespeicherten Analysen"}
                    </span>
                  </div>
                  {tab !== "language" && (
                    <>
                      {narrative.length < ready.length && (
                        <div className="coverage-note">
                          <Layers3 size={15} />
                          {narrative.length} von {ready.length} Texten mit
                          narrativer Analyse. Die übrigen Texte erscheinen im
                          sprachlichen Profil.
                        </div>
                      )}
                      {comparison?.languages &&
                        comparison.languages.length > 1 && (
                          <div className="coverage-note">
                            Mehrere Sprachen in der Auswahl: Sprachunterschiede
                            können auch die narrativen Abstände beeinflussen.
                          </div>
                        )}
                      <div className="chart-grid primary-charts">
                        <Panel
                          title="Wie erzählt dein Text?"
                          kicker="DAS NARRATIVE PROFIL"
                          action={<span className="tag">6 Merkmale</span>}
                        >
                          <p className="panel-description">
                            Erzählentscheidungen im Vergleich mit Mensch und KI.
                          </p>
                          {narrative.length ? (
                            <>
                              <div className="legend reference-legend">
                                <span>
                                  <i className="diamond human" />
                                  Mensch · Referenz
                                </span>
                                <span>
                                  <i className="diamond ai" />
                                  KI · Referenz
                                </span>
                                <span className="legend-hint">
                                  Band: mittlere 50 %
                                </span>
                              </div>
                              <ProfileChart
                                documents={ready}
                                reference={data.reference}
                              />
                              <Legend documents={narrative} />
                            </>
                          ) : (
                            <EmptyChart>
                              Das narrative Profil erscheint nach einer
                              StoryScope-Analyse. Du kannst sie für deine
                              vorhandenen Texte ergänzen:
                              {ready.map((doc) => (
                                <div key={doc.id}>
                                  <strong>{doc.title}</strong>
                                  {storyscopeAction(doc)}
                                </div>
                              ))}
                            </EmptyChart>
                          )}
                          <div className="panel-foot">
                            <span>
                              Merkmalsausprägung 0–100 · keine Qualitätsnote
                            </span>
                            <button
                              className="text-button"
                              onClick={() => setShowValues(!showValues)}
                            >
                              {showValues ? "Werte schließen" : "Werte ansehen"}
                              <ChevronRight size={13} />
                            </button>
                          </div>
                        </Panel>
                        <Panel
                          title="Wie ungewöhnlich ist die Erzählung?"
                          kicker="NARRATIVE SELTENHEIT"
                          className="rarity-panel"
                          action={<span className="tag lavender">Intern</span>}
                        >
                          <p className="panel-description">
                            Verteilung der Segmentabstände in deiner Auswahl.
                          </p>
                          {comparing ? (
                            <EmptyChart>
                              <LoaderCircle size={20} className="spin" />{" "}
                              Gemeinsamer Referenzraum wird berechnet.
                            </EmptyChart>
                          ) : comparison?.available ? (
                            <ViolinChart
                              documents={ready}
                              comparison={comparison}
                            />
                          ) : (
                            <EmptyChart>
                              {comparison?.reason ||
                                "Mindestens zwei StoryScope-Segmente werden benötigt."}
                            </EmptyChart>
                          )}
                          <div className="violin-key">
                            <span>
                              <i />
                              Mittelwert
                            </span>
                            <span>
                              <i className="dashed" />
                              Median
                            </span>
                            <span>
                              <i className="point" />
                              Segment
                            </span>
                          </div>
                          <div className="panel-foot">
                            <span>
                              {comparison?.available
                                ? "k = " +
                                  comparison.k +
                                  " · " +
                                  comparison.featureSet
                                : "Interne Distanz · kein Herkunftsscore"}
                            </span>
                          </div>
                        </Panel>
                      </div>
                      {showValues && (
                        <Panel
                          title="Merkmale nachvollziehen"
                          className="values-panel"
                        >
                          <div className="table-scroll">
                            <table>
                              <thead>
                                <tr>
                                  <th>Merkmal</th>
                                  <th>Mensch Ø (n)</th>
                                  <th>KI Ø (n)</th>
                                  {narrative.map((d) => (
                                    <th key={d.id}>{d.title}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {data.reference.profiles.map((axis) => (
                                  <tr key={axis.id}>
                                    <td>
                                      <strong>{axis.label}</strong>
                                      <small>
                                        {axis.id} · {axis.description}
                                      </small>
                                    </td>
                                    <td>
                                      {number(axis.human.mean, 1)}
                                      <small>
                                        {number(axis.human.n)} /{" "}
                                        {number(axis.human.total)}
                                      </small>
                                    </td>
                                    <td>
                                      {number(axis.ai.mean, 1)}
                                      <small>
                                        {number(axis.ai.n)} /{" "}
                                        {number(axis.ai.total)}
                                      </small>
                                    </td>
                                    {narrative.map((d) => {
                                      const p = d.narrative!.profiles.find(
                                        (p) => p.id === axis.id,
                                      );
                                      return (
                                        <td key={d.id}>
                                          {number(p?.mean, 1)}
                                          <small>
                                            {p?.n} / {p?.total} Segmente
                                          </small>
                                        </td>
                                      );
                                    })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <p className="field-hint">
                            {data.reference.policy} {data.reference.scope}.
                          </p>
                        </Panel>
                      )}
                      <div className="interpretation-note">
                        <span className="note-icon">
                          <FlaskConical size={18} />
                        </span>
                        <div>
                          <strong>
                            Muster erkennen, Herkunft vorsichtig einordnen.
                          </strong>
                          <p>
                            Referenznähe ist ein Anhaltspunkt, kein Beweis.
                            Deutsche Romansegmente und Codex-Extraktionen sind
                            eine Übertragung der englischen
                            Kurzgeschichtenstudie.
                          </p>
                        </div>
                        <button
                          className="text-button"
                          onClick={() => setView("method")}
                        >
                          Zur Methodik
                          <ArrowUpRight size={15} />
                        </button>
                      </div>
                    </>
                  )}
                  <Panel
                    title="Ein Text verändert sich. Hier wird es sichtbar."
                    kicker="VERLAUF ÜBER DIE SEGMENTE"
                    className="trend-panel"
                    action={
                      <select
                        className="chart-select"
                        aria-label="Metrik im Verlauf"
                        value={activeMetric}
                        onChange={(e) => setMetric(e.target.value)}
                      >
                        <option
                          value="rarity"
                          disabled={!comparison?.available}
                        >
                          Narrative Seltenheit
                        </option>
                        <option value="sentence">Mittlere Satzlänge</option>
                        <option value="vocabulary">Wortvielfalt</option>
                      </select>
                    }
                  >
                    <div className="trend-meta">
                      <p className="panel-description">
                        {activeMetric === "rarity"
                          ? "Interne Distanz"
                          : activeMetric === "sentence"
                            ? "Wörter pro Satz"
                            : "Verschiedene Wörter je 100-Wort-Fenster"}{" "}
                        · relative Segmentposition
                      </p>
                      <Legend
                        documents={
                          activeMetric === "rarity" ? narrative : ready
                        }
                      />
                    </div>
                    <TrendChart
                      documents={ready}
                      comparison={comparison}
                      metric={activeMetric}
                      onSegment={openSegment}
                    />
                    <div className="panel-foot">
                      <span>
                        <span className="tiny-circle" />
                        Punkt auswählen, um das zugehörige Textsegment zu lesen
                      </span>
                      <span>0 % → 100 % des Textverlaufs</span>
                    </div>
                  </Panel>
                  {tab !== "narrative" && (
                    <div className="chart-grid secondary-charts">
                      <Panel
                        title="Der Rhythmus deiner Sprache"
                        kicker="SATZLÄNGEN"
                      >
                        <Histogram documents={ready} />
                        <Legend documents={ready} />
                        <p className="field-hint">
                          Anteil der Sätze je Längenklasse. Regelbasierte
                          Satzgrenzen; Abkürzungen können die Zählung
                          beeinflussen.
                        </p>
                      </Panel>
                      <Panel
                        title="Was den Text ausmacht"
                        kicker="SPRACHLICHE MERKMALE"
                      >
                        <div className="metric-rows">
                          {ready.map((doc) => (
                            <div className="text-metrics" key={doc.id}>
                              <h3>
                                <Dot color={doc.color} />
                                {doc.title}
                              </h3>
                              <div>
                                <span>Ø Wörter pro Satz</span>
                                <strong>
                                  {number(doc.metrics!.sentenceMean, 1)}
                                </strong>
                              </div>
                              <div>
                                <span>
                                  Satzvariation <small>relative Streuung</small>
                                </span>
                                <strong>
                                  {number(doc.metrics!.sentenceVariation, 2)}
                                </strong>
                              </div>
                              <div>
                                <span>
                                  Wortvielfalt <small>je 100 Wörter</small>
                                </span>
                                <strong>
                                  {number(doc.metrics!.vocabulary, 1)}
                                </strong>
                              </div>
                              <div>
                                <span>
                                  Wörtliche Rede <small>heuristisch</small>
                                </span>
                                <strong>
                                  {number(doc.metrics!.dialogue, 1)} %
                                </strong>
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="field-hint">
                          Deskriptive Eigenschaften des Textes. Kein
                          Mensch-/KI-Klassifikator.
                        </p>
                      </Panel>
                    </div>
                  )}
                  {view === "compare" &&
                    comparison?.available &&
                    comparison.series.length > 1 && (
                      <Panel
                        title="Wie nah sind sich die Texte?"
                        kicker="NARRATIVE DISTANZMATRIX"
                      >
                        <DistanceMatrix
                          comparison={comparison}
                          documents={ready}
                        />
                        <p className="field-hint">
                          Euklidische Distanz zwischen den mittleren, gemeinsam
                          z-standardisierten Merkmalsvektoren. Kleinere Werte
                          bedeuten ähnlichere Profile. {comparison.note}
                        </p>
                      </Panel>
                    )}
                  <Panel
                    title="Deine Berichte"
                    kicker="AUTOMATISCH ZUSAMMENGEFASST"
                    className="reports-panel"
                  >
                    {ready.map((doc) => (
                      <button
                        key={doc.id}
                        className="report-row"
                        onClick={() => setDetail(doc)}
                      >
                        <span
                          className="report-icon"
                          style={{ color: doc.color }}
                        >
                          <FileText size={22} />
                        </span>
                        <span>
                          <strong>{doc.title}</strong>
                          <small>
                            {doc.narrative
                              ? "Narrative Analyse & Textprofil"
                              : "Lokales Textprofil"}{" "}
                            · {doc.segmentCount} Segmente
                          </small>
                        </span>
                        <span className="report-date">
                          {new Date(
                            doc.completedAt || doc.createdAt,
                          ).toLocaleDateString("de-DE")}
                        </span>
                        <ArrowUpRight size={18} />
                      </button>
                    ))}
                  </Panel>
                </>
              )}
            </>
          )}
          {data && view === "quality" && (
            <QualityLab
              data={data}
              initialIds={ready.map((d) => d.id)}
              onRefresh={refresh}
            />
          )}
          {data && view === "method" && <Method data={data} />}
          <footer className="page-footer">
            <span>
              Bookalyzer <b>·</b> Ein Werkzeug für aufmerksames Lesen.
            </span>
            <button onClick={() => setView("method")}>
              Basierend auf StoryScope
              <ArrowUpRight size={12} />
            </button>
          </footer>
        </div>
      </main>
      {message && (
        <div role="status" className="toast">
          <span>{message}</span>
          <button
            className="icon-button"
            aria-label="Meldung schließen"
            onClick={() => setMessage("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {data && modal === "upload" && (
        <UploadDialog
          defaults={data.settings}
          model={data.model}
          onClose={closeModal}
          onComplete={(ids) => {
            setSelected((prev) => [...prev, ...ids].slice(-6));
            setModal(null);
            setView("quality");
            void refresh();
          }}
        />
      )}
      {data && modal === "select" && (
        <Modal
          title="Texte für den Vergleich"
          subtitle="Bis zu sechs Texte. Alle Diagramme teilen sich dieselbe Auswahl."
          onClose={closeModal}
        >
          <div className="modal-content selection-list">
            {data.documents.map((doc) => (
              <label key={doc.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(doc.id)}
                  onChange={() => toggle(doc.id)}
                />
                <Dot color={doc.color} />
                <span>
                  <strong>{doc.title}</strong>
                  <small>
                    {number(doc.wordCount)} Wörter ·{" "}
                    {doc.narrative ? "StoryScope" : "Textprofil"}
                  </small>
                </span>
                <Status doc={doc} />
              </label>
            ))}
            {!data.documents.length && <p>Noch keine Texte vorhanden.</p>}
          </div>
          <footer className="modal-footer">
            <button
              className="button secondary"
              onClick={() => setModal("upload")}
            >
              <Plus size={16} />
              Neuer Upload
            </button>
            <button className="button primary" onClick={closeModal}>
              <Check size={16} />
              Auswahl übernehmen
            </button>
          </footer>
        </Modal>
      )}
      {data && modal === "library-transfer" && (
        <Modal
          title="Datenbestand sichern & laden"
          subtitle="Deine vollständige Bibliothek als ZIP mitnehmen oder wiederherstellen."
          onClose={closeTransfer}
          closeDisabled={transferBusy}
        >
          <LibraryTransferPanel
            pending={!!pending}
            onBusyChange={setTransferBusy}
            onImported={async () => {
              initialized.current = false;
              setSelected([]);
              setComparison(null);
              setDetail(null);
              setSegment(null);
              setQuery("");
              setView("library");
              await refresh();
            }}
          />
          <footer className="modal-footer">
            <span>ZIP bis 1 GB · entpackt bis 4 GB</span>
            <button
              className="button secondary"
              disabled={transferBusy}
              onClick={closeTransfer}
            >
              Schließen
            </button>
          </footer>
        </Modal>
      )}
      {data && modal === "settings" && draftSettings && (
        <Modal
          title="Deine Standardeinstellungen"
          subtitle="Diese Werte werden für neue Uploads übernommen. Bestehende Analysen behalten ihre Einstellungen."
          onClose={closeModal}
        >
          <div className="modal-content">
            <SettingsFields
              value={draftSettings}
              onChange={setDraftSettings}
              model={data.model}
            />
          </div>
          <footer className="modal-footer">
            <span>Für zukünftige Uploads</span>
            <button
              className="button primary"
              disabled={saving}
              onClick={async () => {
                setSaving(true);
                try {
                  await call("settings", { settings: draftSettings });
                  await refresh();
                  setModal(null);
                  setMessage("Standardeinstellungen gespeichert.");
                } catch (e) {
                  setMessage((e as Error).message);
                } finally {
                  setSaving(false);
                }
              }}
            >
              {saving ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Check size={16} />
              )}
              Einstellungen speichern
            </button>
          </footer>
        </Modal>
      )}
      {data && modal === "export" && (
        <Modal
          title="Deinen Bericht mitnehmen"
          subtitle="Alle ausgewählten Texte, mit den aktuellen Vergleichseinstellungen."
          onClose={closeModal}
        >
          <div className="modal-content">
            <div className="export-options">
              {[
                [
                  "html",
                  "Interaktives Format, statischer Bericht",
                  "HTML · Diagramme, Text & Methodik",
                ],
                ...(window.bookalyzer
                  ? [
                      [
                        "pdf",
                        "PDF-Dokument",
                        "PDF · bereit zum Teilen und Drucken",
                      ],
                    ]
                  : []),
                [
                  "csv",
                  "Messwerte als Tabelle",
                  "CSV · ein Datensatz pro Segment",
                ],
                [
                  "json",
                  "Vollständige Analysedaten",
                  "JSON · Merkmale, Einstellungen & Provenienz",
                ],
              ].map(([id, label, desc]) => (
                <label key={id} className={exportFormat === id ? "active" : ""}>
                  <input
                    type="radio"
                    name="format"
                    checked={exportFormat === id}
                    onChange={() => setExportFormat(id)}
                  />
                  <FileText size={22} />
                  <span>
                    <strong>{id === "html" ? "HTML-Bericht" : label}</strong>
                    <small>{desc}</small>
                  </span>
                  {exportFormat === id && <CheckCheck size={18} />}
                </label>
              ))}
            </div>
            <p className="field-hint">
              {ready.length} Texte · {number(totalSegments)} Segmente ·
              Diagramme und Werte beziehen sich auf diese Auswahl.
            </p>
          </div>
          <footer className="modal-footer">
            <span>Eigenständig lesbar</span>
            <button
              className="button primary"
              disabled={saving}
              onClick={exportReport}
            >
              {saving ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <ArrowDownToLine size={16} />
              )}
              Bericht speichern
            </button>
          </footer>
        </Modal>
      )}
      {segment && (
        <Modal
          title={
            "Segment " + (segment.index + 1) + " · " + segment.documentTitle
          }
          subtitle={segment.title + " · " + number(segment.words) + " Wörter"}
          onClose={closeSegment}
          wide
        >
          <div className="modal-content reader">
            <pre>{segment.text}</pre>
          </div>
        </Modal>
      )}
      {localDocument && (
        <Modal
          title="Lokale Analyse erweitern"
          subtitle={
            localDocument.title + " · Qualitätsmethoden für diesen Text"
          }
          onClose={closeLocal}
        >
          <LocalAnalysisForm
            document={localDocument}
            onUpdated={() => {
              setLocalDocument(null);
              setSelected([localDocument.id]);
              setView("quality");
              void refresh();
              setMessage(
                "Lokale Analyse aktualisiert. StoryScope bleibt verfügbar.",
              );
            }}
          />
        </Modal>
      )}
      {storyscopeDocument && data && (
        <Modal
          title="StoryScope mit Codex ergänzen"
          subtitle={storyscopeDocument.title + " · vorhandenes Dokument"}
          onClose={closeStoryscope}
          wide
        >
          <StoryScopeForm
            document={storyscopeDocument}
            model={data.model}
            onStarted={() => {
              setStoryscopeDocument(null);
              setSelected((prev) =>
                prev.includes(storyscopeDocument.id)
                  ? prev
                  : [storyscopeDocument.id, ...prev].slice(0, 6),
              );
              void refresh();
              setMessage(
                "StoryScope wird ergänzt. Das lokale Textprofil bleibt verfügbar.",
              );
            }}
          />
        </Modal>
      )}
      {detail && (
        <Modal
          title={detail.title}
          subtitle={detail.name + " · " + number(detail.wordCount) + " Wörter"}
          onClose={closeDetail}
          wide
        >
          <div className="modal-content">
            <Status doc={detail} />
            {(detail.status === "ready" ||
              (detail.status === "error" &&
                detail.settings.mode === "codex")) &&
              localActions(detail)}
            {detail.status === "ready" && storyscopeAction(detail)}
            {detail.error && <div className="notice error">{detail.error}</div>}
            <div className="report-prose">
              {detail.report?.map((p, i) => (
                <p key={i}>{p}</p>
              ))}
            </div>
            <h3>Einstellungen dieses Uploads</h3>
            <dl className="metadata">
              <dt>Sprache</dt>
              <dd>{detail.settings.language}</dd>
              <dt>Segmentierung</dt>
              <dd>
                {number(detail.settings.minWords)} /{" "}
                {number(detail.settings.targetWords)} /{" "}
                {number(detail.settings.maxWords)} Wörter
              </dd>
              <dt>Merkmalsraum</dt>
              <dd>{detail.settings.featureSet}</dd>
              <dt>Extraktionsmodell</dt>
              <dd>{detail.narrative?.model || "Keine externe Extraktion"}</dd>
              <dt>Reasoning-Level</dt>
              <dd>
                {detail.settings.mode === "codex"
                  ? detail.settings.reasoningEffort || "Modellstandard"
                  : "Keine externe Extraktion"}
              </dd>
              <dt>Dokument-ID</dt>
              <dd>{detail.id}</dd>
            </dl>
            <h3>Segmente entdecken</h3>
            <div className="detail-segments">
              {detail.segments.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setDetail(null);
                    void openSegment(detail.id, s.index);
                  }}
                >
                  <span>{String(s.index + 1).padStart(2, "0")}</span>
                  <strong>{s.title}</strong>
                  <small>{number(s.words)} Wörter</small>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function storyscopePending(doc: Document) {
  return (
    doc.storyscope?.status === "queued" ||
    doc.storyscope?.status === "analyzing"
  );
}

function Status({ doc }: { doc: Document }) {
  return (
    <span
      className={
        "status-badge " +
        (doc.status === "ready"
          ? "ready"
          : doc.status === "error"
            ? "failed"
            : "working")
      }
    >
      {doc.status === "ready" ? (
        <Check size={12} />
      ) : doc.status === "error" ? (
        <CircleHelp size={12} />
      ) : (
        <LoaderCircle size={12} className="spin" />
      )}
      {doc.status === "ready"
        ? doc.narrative
          ? "StoryScope · fertig"
          : "Textprofil · fertig"
        : doc.status === "error"
          ? "Analyse unterbrochen"
          : doc.status === "queued"
            ? "In der Warteschlange"
            : "Wird analysiert"}
    </span>
  );
}
function Stat({
  icon,
  label,
  value,
  note,
  text = false,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  note: string;
  text?: boolean;
}) {
  return (
    <div className="stat-card">
      <div>
        <span>{label}</span>
        {icon}
      </div>
      <strong className={text ? "text-value" : ""}>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
function Method({ data }: { data: Bootstrap }) {
  return (
    <div className="method-page">
      <div className="method-intro">
        <span className="method-icon">
          <FlaskConical size={34} strokeWidth={1.3} />
        </span>
        <div>
          <span className="eyebrow purple">
            STORYSCOPE · {data.method.version}
          </span>
          <h2>Die Erzählung hinter dem Schreibstil.</h2>
          <p>
            StoryScope untersucht Erzählentscheidungen in menschlichen und
            KI-generierten Geschichten. Bookalyzer nutzt die veröffentlichte
            Taxonomie und ergänzt transparente lokale Textstatistiken.
          </p>
          <a
            className="button secondary"
            href={data.method.url}
            target="_blank"
            rel="noreferrer"
          >
            Studie lesen
            <ArrowUpRight size={16} />
          </a>
        </div>
      </div>
      <div className="method-grid">
        <Panel title="01 · Textprofil">
          <p>
            Satzlänge, Satzvariation, Wortvielfalt und wörtliche Rede werden
            lokal berechnet. Wortvielfalt ist der Mittelwert verschiedener
            Wörter in vollständigen 100-Wort-Fenstern. Die Statistik nutzt
            regelbasierte Satzgrenzen und eine Heuristik für Anführungszeichen.
          </p>
        </Panel>
        <Panel title="02 · Narrative Merkmale">
          <p>
            StoryScope extrahiert 304 Merkmale aus zehn Dimensionen. Die
            Codex-Integration nutzt die Originalprompts dimensionsweise,
            validiert Antworten und speichert sie zur Wiederaufnahme. Sie
            verwendet ein anderes Modell als die Studie und ist explorativ.
          </p>
        </Panel>
        <Panel title="03 · Mensch-/KI-Referenzen">
          <p>
            Die sechs Profilachsen zeigen beobachtete Einzelmerkmalswerte aus
            dem veröffentlichten Korpus über alle Splits. Nur gültige Werte
            werden gemittelt; n und Gesamtzahl stehen unter „Werte ansehen“. Die
            Bänder zeigen das 25.–75. Perzentil. Referenznähe ist keine
            Wahrscheinlichkeit menschlicher Urheberschaft.
          </p>
        </Panel>
        <Panel title="04 · Gemeinsame Seltenheit">
          <p>
            Alle ausgewählten StoryScope-Segmente werden gemeinsam codiert und
            z-standardisiert. Die interne Seltenheit ist die mittlere
            euklidische Distanz zu bis zu 25 anderen Segmenten, ohne
            Selbsttreffer. Feature-Set und Referenzraum stehen am Diagramm.
            Auswahländerungen und Doppelimporte verändern die Werte.
          </p>
        </Panel>
      </div>
      <div className="notice amber">
        <CircleHelp size={22} />
        <div>
          <strong>Externe Rarity: derzeit nicht verfügbar</strong>
          <p>
            {data.method.externalReason} Interne Distanzen werden deshalb nicht
            als externe StoryScope-Perzentile ausgegeben.
          </p>
        </div>
      </div>
      <Panel title="Was die Diagramme sagen – und wo ihre Grenzen liegen">
        <p>
          Die Referenzen stammen aus englischen Kurzgeschichten. Deutsche Texte,
          ganze Romane, ihre Segmentierung und ein anderes Extraktionsmodell
          schränken die Übertragbarkeit ein. Kurze Texte unter 3.000 Wörtern
          können besonders instabile narrative Merkmale liefern.
        </p>
        <p>
          Hohe Merkmalswerte sind keine Qualitätsnote. Narrative Seltenheit
          beschreibt statistische Distanz, keine Originalität, kein Plagiat und
          keine gesicherte Urheberschaft. Ein Herkunfts-Klassifikator wird in
          dieser App nicht angewendet.
        </p>
        <p>
          Der Vergleich zeigt die vollständig nachvollziehbaren 265 narrativen
          Merkmale oder alle 304 Merkmale. Die exakte 257-Merkmalsvariante der
          Studie bleibt ohne die acht fehlenden offiziellen Ausschluss-IDs
          gesperrt.
        </p>
        <p className="field-hint">
          Bibliothek: {data.method.library}
          <br />
          Referenz SHA-256: {data.reference.sha256 || "nicht vorhanden"}
        </p>
      </Panel>
    </div>
  );
}
