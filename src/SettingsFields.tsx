import type { Settings } from "./types";
import { CodexOptions } from "./CodexOptions";
export function SettingsFields({
  value,
  onChange,
  model,
  localOnly = false,
}: {
  value: Settings;
  onChange: (s: Settings) => void;
  model: string;
  localOnly?: boolean;
}) {
  const set = <K extends keyof Settings>(key: K, v: Settings[K]) =>
    onChange({ ...value, [key]: v });
  return (
    <div className="settings-fields">
      {!localOnly && (
        <>
          <div className="form-row">
            <label>
              Analysemodus
              <select
                value={value.mode}
                onChange={(e) =>
                  set("mode", e.target.value as Settings["mode"])
                }
              >
                <option value="local">Textprofil · lokal & sofort</option>
                <option value="codex">StoryScope · mit Codex</option>
              </select>
            </label>
            <label>
              Textsprache
              <select
                value={value.language}
                onChange={(e) =>
                  set("language", e.target.value as Settings["language"])
                }
              >
                <option value="de">Deutsch</option>
                <option value="en">Englisch</option>
                <option value="und">Andere / unbekannt</option>
              </select>
            </label>
          </div>
          <p className="field-hint">
            {value.mode === "local"
              ? "Satzrhythmus, Wortvielfalt und Textverlauf werden auf diesem Gerät berechnet."
              : "304 narrative Merkmale in zehn Dimensionen. Die Segmenttexte werden über deinen Codex-Zugang an OpenAI gesendet. Die Freigabe erfolgt nach der Vorschau."}
          </p>
        </>
      )}
      <div className="field-heading">
        Qualitätslabor <span>Offline · zusätzlich zu StoryScope</span>
      </div>
      <label>
        Textprofil
        <select
          value={value.textProfile}
          onChange={(e) => {
            const profile = e.target.value as Settings["textProfile"];
            const goals = {
              narrative: [30, 10],
              informative: [25, 5],
              technical: [35, 15],
            }[profile];
            onChange({
              ...value,
              textProfile: profile,
              longSentenceWords: goals[0],
              longSentenceShare: goals[1],
            });
          }}
        >
          <option value="narrative">Erzähltext · Roman und Geschichten</option>
          <option value="informative">
            Sachtext · verständlich informieren
          </option>
          <option value="technical">Fachtext · für erfahrene Leser</option>
        </select>
      </label>
      <p className="field-hint">
        Das Profil schlägt ein bearbeitbares Ziel für Satzlängen vor. Es ist
        eine Schreibhilfe, keine wissenschaftliche Qualitätsnorm.
      </p>
      <div className="quality-settings">
        {[
          ["readability", "Lesbarkeit"],
          ["vocabulary", "Wortschatz"],
          ["rhythm", "Rhythmus"],
          ["repetition", "Wiederholungen"],
          ["cohesion", "Zusammenhang"],
          ["style", "Stilhinweise"],
        ].map(([id, label]) => (
          <label key={id}>
            <input
              type="checkbox"
              checked={value.qualityGroups.includes(id)}
              onChange={(e) =>
                set(
                  "qualityGroups",
                  e.target.checked
                    ? [...value.qualityGroups, id]
                    : value.qualityGroups.filter((g) => g !== id),
                )
              }
            />
            {label}
          </label>
        ))}
      </div>
      <label className="quality-threshold">
        Lange Sätze ab mehr als
        <div className="input-unit">
          <input
            type="number"
            min="15"
            max="80"
            value={value.longSentenceWords}
            onChange={(e) => set("longSentenceWords", Number(e.target.value))}
          />
          <span>Wörter</span>
        </div>
      </label>
      <label className="quality-threshold">
        Gewünschter Höchstanteil langer Sätze
        <div className="input-unit">
          <input
            type="number"
            min="0"
            max="100"
            value={value.longSentenceShare}
            onChange={(e) => set("longSentenceShare", Number(e.target.value))}
          />
          <span>%</span>
        </div>
      </label>
      <p className="field-hint">
        Formeln und Wortlisten sind im Qualitätslabor einsehbar. Heuristische
        Treffer sind Hinweise zum Nachlesen, keine Fehler oder Urhebernachweise.
      </p>
      {!localOnly && (
        <>
          <div className="field-heading">
            Segmentierung{" "}
            <span>Nicht überlappend · Kapitelgrenzen bevorzugt</span>
          </div>
          <div className="form-row three">
            {(
              [
                ["minWords", "Minimum"],
                ["targetWords", "Zielgröße"],
                ["maxWords", "Maximum"],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                {label}
                <div className="input-unit">
                  <input
                    type="number"
                    min="100"
                    max="20000"
                    step="100"
                    value={value[key]}
                    onChange={(e) => set(key, Number(e.target.value))}
                  />
                  <span>Wörter</span>
                </div>
              </label>
            ))}
          </div>
          <div className="checks">
            <label>
              <input
                type="checkbox"
                checked={value.detectChapters}
                onChange={(e) => set("detectChapters", e.target.checked)}
              />
              Kapitel erkennen und getrennt analysieren
            </label>
            <p className="field-hint">
              Aktiviert: Segmente überschreiten keine Kapitelgrenze. Kurze
              Kapitel bleiben erhalten, lange werden aufgeteilt. Die erkannten
              Überschriften kannst du vor dem Start prüfen.
            </p>
            <label>
              <input
                type="checkbox"
                checked={value.excludeFrontmatter}
                onChange={(e) => set("excludeFrontmatter", e.target.checked)}
              />
              Vorspann und Impressum ausschließen
            </label>
            <label>
              <input
                type="checkbox"
                checked={value.excludeBackmatter}
                onChange={(e) => set("excludeBackmatter", e.target.checked)}
              />
              Nachspann ausschließen
            </label>
          </div>
          {value.mode === "codex" && (
            <div className="external-fields">
              <div className="form-row">
                <label>
                  Merkmalsraum
                  <select
                    value={value.featureSet}
                    onChange={(e) =>
                      set(
                        "featureSet",
                        e.target.value as Settings["featureSet"],
                      )
                    }
                  >
                    <option value="public_nonstyle_265">
                      Narrativ · 265 Merkmale
                    </option>
                    <option value="full_304">
                      Narrativ + Stil · 304 Merkmale
                    </option>
                  </select>
                </label>
                <label>
                  Gleichzeitige Aufrufe
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={value.parallel}
                    onChange={(e) => set("parallel", Number(e.target.value))}
                  />
                </label>
              </div>
              <CodexOptions
                value={value}
                configuredModel={model}
                onChange={(patch) => onChange({ ...value, ...patch })}
              />
              <p className="field-hint">
                Explorative Auswertung. Ein anderes Modell verändert die
                Vergleichbarkeit mit der Studie.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
