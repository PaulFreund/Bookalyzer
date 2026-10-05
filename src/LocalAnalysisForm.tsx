import { useState } from "react";
import { Check, LoaderCircle, ShieldCheck } from "lucide-react";
import { call } from "./api";
import { SettingsFields } from "./SettingsFields";
import type { Document } from "./types";

export function LocalAnalysisForm({
  document,
  onUpdated,
}: {
  document: Document;
  onUpdated: () => void;
}) {
  const [settings, setSettings] = useState({ ...document.settings });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <>
      <div className="modal-content">
        <fieldset className="wizard-fieldset" disabled={busy}>
          <div className="notice neutral">
            <ShieldCheck size={19} />
            <p>
              Wähle die Qualitätsbereiche und das Zielprofil für diesen Text.
              Die lokale Analyse berechnet sie auf deinem Gerät. Vorhandene
              StoryScope-Ergebnisse bleiben beim selben Dokument verfügbar.
            </p>
          </div>
          <SettingsFields
            value={settings}
            onChange={setSettings}
            model=""
            localOnly
          />
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
        </fieldset>
      </div>
      <footer className="modal-footer">
        <span>Für dieses Dokument · lokal auf deinem Gerät</span>
        <button
          className="button primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              const {
                qualityGroups,
                longSentenceWords,
                longSentenceShare,
                textProfile,
              } = settings;
              await call("local_update", {
                id: document.id,
                settings: {
                  qualityGroups,
                  longSentenceWords,
                  longSentenceShare,
                  textProfile,
                },
              });
              onUpdated();
            } catch (e) {
              setError((e as Error).message);
              setBusy(false);
            }
          }}
        >
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Check size={16} />
          )}
          {busy ? "Wird lokal berechnet …" : "Lokale Analyse aktualisieren"}
        </button>
      </footer>
    </>
  );
}
