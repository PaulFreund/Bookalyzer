import { useEffect, useState } from "react";
import { LoaderCircle, RefreshCw } from "lucide-react";
import { call } from "./api";
import type { CodexModels, Settings } from "./types";

const effortLabels: Record<string, string> = {
  none: "Kein Reasoning",
  minimal: "Minimal",
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  xhigh: "Sehr hoch",
  max: "Maximum",
  ultra: "Ultra",
};
type Options = Pick<Settings, "model" | "reasoningEffort">;

export function CodexOptions({
  value,
  onChange,
  configuredModel,
}: {
  value: Options;
  onChange: (patch: Options) => void;
  configuredModel: string;
}) {
  const [catalog, setCatalog] = useState<CodexModels | null>(null);
  const [busy, setBusy] = useState(true);
  const [custom, setCustom] = useState(false);
  const load = async (refresh = false) => {
    setBusy(true);
    try {
      setCatalog(await call<CodexModels>("codex_models", { refresh }));
    } catch (e) {
      setCatalog({
        available: false,
        configuredModel,
        models: [],
        reason: (e as Error).message,
      });
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const resolvedModel =
    value.model || catalog?.configuredModel || configuredModel;
  const selected = catalog?.models.find((model) => model.id === resolvedModel);
  const manual = custom || (!!value.model && !!catalog && !selected);
  const efforts = selected?.reasoningEfforts.length
    ? selected.reasoningEfforts
    : Object.keys(effortLabels);
  const chooseModel = (model: string) => {
    const entry = catalog?.models.find(
      (entry) => entry.id === (model || catalog.configuredModel),
    );
    const reasoningEffort =
      value.reasoningEffort &&
      entry?.reasoningEfforts.length &&
      !entry.reasoningEfforts.includes(value.reasoningEffort)
        ? entry.defaultReasoningEffort || ""
        : value.reasoningEffort;
    onChange({ model, reasoningEffort });
  };
  return (
    <div className="codex-options">
      <div className="form-row">
        <label>
          Extraktionsmodell
          <select
            value={manual ? "__custom__" : value.model}
            onChange={(e) => {
              if (e.target.value === "__custom__") setCustom(true);
              else {
                setCustom(false);
                chooseModel(e.target.value);
              }
            }}
          >
            <option value="">
              Codex-Einstellung ({catalog?.configuredModel || configuredModel})
            </option>
            {catalog?.models.map((model) => (
              <option value={model.id} key={model.id}>
                {model.name} · {model.id}
              </option>
            ))}
            <option value="__custom__">Modell-ID selbst eingeben</option>
          </select>
        </label>
        <label>
          Reasoning-Level
          <select
            value={value.reasoningEffort}
            onChange={(e) =>
              onChange({ ...value, reasoningEffort: e.target.value })
            }
          >
            <option value="">
              Modellstandard
              {selected?.defaultReasoningEffort
                ? " (" +
                  (effortLabels[selected.defaultReasoningEffort] ||
                    selected.defaultReasoningEffort) +
                  ")"
                : ""}
            </option>
            {value.reasoningEffort &&
              !efforts.includes(value.reasoningEffort) && (
                <option value={value.reasoningEffort} disabled>
                  {value.reasoningEffort} · nicht unterstützt
                </option>
              )}
            {efforts.map((effort) => (
              <option value={effort} key={effort}>
                {effortLabels[effort] || effort} · {effort}
              </option>
            ))}
          </select>
        </label>
      </div>
      {manual && (
        <label>
          Modell-ID
          <input
            value={value.model}
            placeholder="Modell-ID aus deiner Codex-Konfiguration"
            onChange={(e) =>
              onChange({ ...value, model: e.target.value.trim() })
            }
          />
        </label>
      )}
      <div className="codex-catalog-status">
        <span>
          {busy ? (
            <>
              <LoaderCircle size={14} className="spin" /> Modelle werden aus
              Codex geladen …
            </>
          ) : catalog?.available ? (
            `${catalog.models.length} Modelle aus deiner Codex-Modellliste`
          ) : (
            catalog?.reason
          )}
        </span>
        <button
          type="button"
          className="text-button"
          disabled={busy}
          onClick={() => void load(true)}
        >
          <RefreshCw size={13} /> Aktualisieren
        </button>
      </div>
      <p className="field-hint">
        Mehr Reasoning kann die Laufzeit und den Verbrauch deines Kontingents
        erhöhen.
        {selected
          ? " Angezeigt werden die von diesem Modell unterstützten Stufen."
          : " Bei manueller Eingabe sind die Stufen nicht geprüft; Codex prüft sie beim Start."}
      </p>
    </div>
  );
}
