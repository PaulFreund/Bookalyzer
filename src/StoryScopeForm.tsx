import { useState } from "react";
import {
  ArrowUpRight,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { call } from "./api";
import { number } from "./charts";
import type { Document, Settings } from "./types";
import { CodexOptions } from "./CodexOptions";

export function StoryScopeForm({
  document,
  model,
  onStarted,
}: {
  document: Document;
  model: string;
  onStarted: () => void;
}) {
  const [options, setOptions] = useState({
    model: document.settings.model,
    reasoningEffort: document.settings.reasoningEffort,
    parallel: document.settings.parallel,
    featureSet: document.settings.featureSet,
  });
  const [consent, setConsent] = useState(false);
  const [checked, setChecked] = useState(false);
  const [approver, setApprover] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{
    text: string;
    title: string;
  } | null>(null);
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await call("storyscope_start", {
        id: document.id,
        ...options,
        consent,
        previewConfirmed: checked,
        approver,
      });
      onStarted();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <>
      <div className="modal-content">
        <fieldset className="wizard-fieldset" disabled={busy}>
          <div className="notice neutral">
            <ShieldCheck size={19} />
            <p>
              StoryScope ergänzt 304 narrative Merkmale. Dein lokales Textprofil
              bleibt währenddessen verfügbar. Anschließend findest du beide
              Auswertungen beim selben Dokument.
            </p>
          </div>
          <h3>Einstellungen für StoryScope</h3>
          <div className="settings-fields">
            <CodexOptions
              value={options}
              configuredModel={model}
              onChange={(patch) => setOptions({ ...options, ...patch })}
            />
            <div className="form-row">
              <label>
                Gleichzeitige Aufrufe
                <input
                  type="number"
                  min="1"
                  max="6"
                  value={options.parallel}
                  onChange={(e) =>
                    setOptions({ ...options, parallel: Number(e.target.value) })
                  }
                />
              </label>
            </div>
            <label>
              Merkmalsraum für Vergleiche
              <select
                value={options.featureSet}
                onChange={(e) =>
                  setOptions({
                    ...options,
                    featureSet: e.target.value as Settings["featureSet"],
                  })
                }
              >
                <option value="public_nonstyle_265">
                  Narrativ · 265 Merkmale
                </option>
                <option value="full_304">Narrativ + Stil · 304 Merkmale</option>
              </select>
            </label>
            <p className="field-hint">
              {number(document.wordCount)} Wörter · {document.segmentCount}{" "}
              vorhandene Segmente · {number(document.segmentCount * 10)}{" "}
              Dimensionsaufrufe. Die Analyse nutzt dein Codex-Kontingent. Bei
              Büchern kann sie länger dauern. Voraussetzung ist eine
              installierte und angemeldete Codex CLI.
            </p>
          </div>
          <h3>Diese Segmente werden analysiert</h3>
          <p className="field-hint">
            Die Sprache, Textauswahl und Kapitelaufteilung deiner lokalen
            Analyse werden übernommen. Prüfe die Vorschau vor der Übertragung an
            OpenAI.
          </p>
          <div className="segment-preview-list">
            {document.segments.map((s) => (
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
                          id: document.id,
                          index: s.index,
                        }),
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Vollständiges Segment lesen <ArrowUpRight size={14} />
                </button>
              </details>
            ))}
          </div>
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
              Übertragung dieser StoryScope-Segmente an OpenAI über meinen
              Codex-Zugang frei.
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
          {error && (
            <div role="alert" className="notice error">
              {error}
            </div>
          )}
        </fieldset>
      </div>
      <footer className="modal-footer">
        <span>Ergänzt die vorhandene Analyse</span>
        <button
          className="button primary"
          disabled={busy || !consent || !checked || !approver.trim()}
          onClick={start}
        >
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Sparkles size={16} />
          )}
          {busy
            ? "StoryScope wird gestartet …"
            : "StoryScope mit Codex starten"}
        </button>
      </footer>
    </>
  );
}
