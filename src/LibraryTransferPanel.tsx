import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  Archive,
  Check,
  FolderOpen,
  LoaderCircle,
} from "lucide-react";
import { call, exportLibrary, inspectLibrary } from "./api";
import { number } from "./charts";
import type { LibraryImportResult, LibraryPreview } from "./types";

export function LibraryTransferPanel({
  pending,
  onBusyChange,
  onImported,
}: {
  pending: boolean;
  onBusyChange: (busy: boolean) => void;
  onImported: () => Promise<void>;
}) {
  const [busy, setBusy] = useState<"export" | "inspect" | "import" | null>(
    null,
  );
  const [preview, setPreview] = useState<LibraryPreview | null>(null);
  const [result, setResult] = useState<LibraryImportResult | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const importId = useRef<string | null>(null);
  useEffect(
    () => () => {
      if (importId.current)
        void call("library_discard", { id: importId.current }).catch(() => {});
    },
    [],
  );
  const run = async (
    action: "export" | "inspect" | "import",
    task: () => Promise<void>,
  ) => {
    setBusy(action);
    onBusyChange(true);
    setError("");
    setSuccess("");
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
      onBusyChange(false);
    }
  };
  const inspect = (file?: File) =>
    run("inspect", async () => {
      setPreview(null);
      setResult(null);
      if (importId.current)
        await call("library_discard", { id: importId.current });
      importId.current = null;
      const next = file
        ? await inspectLibrary(file)
        : await window.bookalyzer!.pickLibrary();
      importId.current = next?.id || null;
      setPreview(next);
    });
  return (
    <div className="modal-content library-transfer" aria-busy={!!busy}>
      <p>
        Die ZIP enthält den vollständigen Datenbestand: Originaldateien,
        Analysen, Baselines, Standardeinstellungen und Markierungen. Auch
        ausgeblendete Texte und gespeicherte StoryScope-Antworten bleiben
        erhalten.
      </p>
      {pending && (
        <p className="notice neutral" role="status">
          Bitte laufende Analysen vor dem Sichern oder Laden abschließen.
        </p>
      )}
      <div className="library-transfer-actions">
        <button
          className="button secondary"
          disabled={pending || !!busy}
          onClick={() =>
            void run("export", async () => {
              if (await exportLibrary())
                setSuccess("Datenbestand als ZIP gesichert.");
            })
          }
        >
          {busy === "export" ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <ArrowDownToLine size={16} />
          )}
          ZIP sichern
        </button>
        <button
          className="button secondary"
          disabled={pending || !!busy}
          onClick={() =>
            window.bookalyzer ? void inspect() : input.current?.click()
          }
        >
          {busy === "inspect" ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <FolderOpen size={16} />
          )}
          ZIP zum Laden wählen
        </button>
        <input
          ref={input}
          type="file"
          accept=".zip,application/zip"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void inspect(file);
          }}
        />
      </div>
      {busy === "inspect" && (
        <p className="field-hint" role="status">
          Dateien und Prüfsummen werden geprüft. Der aktuelle Datenbestand
          bleibt bis zur Bestätigung erhalten.
        </p>
      )}
      {preview && (
        <section className="library-transfer-preview">
          <h3>
            <Archive size={18} /> Geprüfte Sicherung
          </h3>
          <p className="library-transfer-path">{preview.name}</p>
          <dl>
            <dt>Texte</dt>
            <dd>{number(preview.documentCount)}</dd>
            <dt>Baselines</dt>
            <dd>{number(preview.baselineCount)}</dd>
            <dt>Dateien</dt>
            <dd>{number(preview.fileCount)}</dd>
            <dt>Größe entpackt</dt>
            <dd>{number(preview.bytes / 1024 / 1024, 1)} MB</dd>
            {preview.createdAt && (
              <>
                <dt>Gesichert am</dt>
                <dd>{new Date(preview.createdAt).toLocaleString("de-DE")}</dd>
              </>
            )}
          </dl>
          <p>
            Beim Laden wird deine aktuelle Bibliothek vollständig durch diese
            Sicherung ersetzt. Vorher wird der bisherige Datenbestand
            automatisch als ZIP neben dem Bibliotheksordner gesichert.
          </p>
          <button
            className="button primary"
            disabled={pending || !!busy}
            onClick={() =>
              void run("import", async () => {
                const imported = await call<LibraryImportResult>(
                  "library_import",
                  {
                    id: preview.id,
                    replaceConfirmed: true,
                  },
                );
                importId.current = null;
                setPreview(null);
                setResult(imported);
                await onImported();
              })
            }
          >
            {busy === "import" ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Check size={16} />
            )}
            {busy === "import"
              ? "Datenbestand wird geladen …"
              : "Datenbestand ersetzen"}
          </button>
        </section>
      )}
      {result && (
        <div className="library-transfer-result" role="status">
          <strong>Datenbestand geladen.</strong>
          <p>
            {number(result.documentCount)} Texte und{" "}
            {number(result.baselineCount)} Baselines sind verfügbar.
          </p>
          <p>Der vorherige Stand wurde hier gesichert:</p>
          <p className="library-transfer-path">{result.backupPath}</p>
        </div>
      )}
      {success && (
        <p className="field-hint" role="status">
          {success}
        </p>
      )}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
