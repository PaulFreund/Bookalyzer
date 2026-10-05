import type { LibraryPreview, UploadFile } from "./types";
export async function call<T>(
  method: string,
  params: unknown = {},
): Promise<T> {
  if (window.bookalyzer) return window.bookalyzer.call<T>(method, params);
  const response = await fetch("/api/rpc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, params }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data.result as T;
}
export async function readFiles(files: File[]): Promise<UploadFile[]> {
  if (files.length > 12)
    throw new Error("Bitte maximal 12 Dateien gleichzeitig importieren.");
  return Promise.all(
    files.map(
      (file) =>
        new Promise<UploadFile>((resolve, reject) => {
          if (!/\.(txt|docx|epub|pdf)$/i.test(file.name)) {
            reject(new Error("Unterstützt werden TXT, DOCX, EPUB und PDF."));
            return;
          }
          if (file.size > 30 * 1024 * 1024) {
            reject(new Error("Datei zu groß (max. 30 MB)."));
            return;
          }
          const reader = new FileReader();
          reader.onload = () =>
            resolve({
              name: file.name,
              base64: String(reader.result).split(",")[1],
            });
          reader.onerror = () =>
            reject(new Error("Die Datei konnte nicht gelesen werden."));
          reader.readAsDataURL(file);
        }),
    ),
  );
}
export async function saveFile(
  name: string,
  content: string,
  format: string,
): Promise<boolean> {
  if (window.bookalyzer) return window.bookalyzer.save(name, content, format);
  const type =
    format === "html"
      ? "text/html"
      : format === "json"
        ? "application/json"
        : "text/csv";
  const url = URL.createObjectURL(
    new Blob([content], { type: type + ";charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

export async function exportLibrary(): Promise<boolean> {
  if (window.bookalyzer) return window.bookalyzer.exportLibrary();
  const response = await fetch("/api/library/export", {
    headers: { "X-Bookalyzer-Library": "1" },
  });
  if (!response.ok) throw new Error((await response.json()).error);
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `Bookalyzer-Datenbestand-${new Date().toISOString().slice(0, 10)}.zip`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

export async function inspectLibrary(file: File): Promise<LibraryPreview> {
  if (!/\.zip$/i.test(file.name))
    throw new Error("Bitte eine ZIP-Sicherung wählen.");
  if (file.size > 1024 * 1024 * 1024)
    throw new Error("ZIP-Datei zu groß (max. 1 GB).");
  const response = await fetch("/api/library/inspect", {
    method: "POST",
    headers: { "Content-Type": "application/zip", "X-Bookalyzer-Library": "1" },
    body: file,
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return { ...data.result, name: file.name };
}
