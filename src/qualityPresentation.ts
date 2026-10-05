import type { QualityCard, QualityRow } from "./types";

export const STATUS = {
  fit: "Ziel eingehalten",
  review: "Prüfen",
  observe: "Beobachtung",
  unknown: "Wenig Grundlage",
};

export function withConsistencyReference(row: QualityRow): QualityRow {
  const reference = row.summary.consistencyReference;
  if (row.comparison || !Object.keys(reference.bands).length) return row;
  return {
    ...row,
    comparison: {
      basis: "chapters",
      name: reference.name,
      words: 0,
      windows: 0,
      values: Object.fromEntries(
        Object.entries(reference.bands).map(([key, b]) => [key, b.median]),
      ),
      bands: reference.bands,
      note: "Vergleich mit den übrigen Kapiteln; das aktuelle Kapitel ist ausgeschlossen.",
    },
  };
}

// The screen and brief report must describe book-wide chapter variation alike.
export function overviewCards(
  row: QualityRow,
  chapters: QualityRow[],
): (QualityCard & { note?: string })[] {
  const own = chapters.filter((c) => c.documentId === row.documentId);
  if (row.chapterIndex !== null || own.length < 2) return row.summary.cards;
  const statuses = own.map(
    (c) => c.summary.cards.find((card) => card.id === "consistency")?.status,
  );
  const assessed = statuses.filter(
    (status) => status === "observe" || status === "review",
  ).length;
  const anomalies = statuses.filter((status) => status === "review").length;
  const note = `${assessed} von ${own.length} Kapiteln eingeordnet`;
  return row.summary.cards.map((card) =>
    card.id !== "consistency"
      ? card
      : {
          ...card,
          status: anomalies ? "review" : assessed ? "observe" : "unknown",
          title: anomalies
            ? `${anomalies} Kapitel ${anomalies === 1 ? "weicht" : "weichen"} ab`
            : assessed
              ? "Kapitel ohne starke Ausreißer"
              : "Vergleichsbasis ergänzen",
          detail: `${note}. ${row.comparison ? `Vergleich mit ${row.comparison.name}.` : "Jedes Kapitel wird mit den übrigen Kapiteln verglichen."} Öffne ein auffälliges Kapitel für Ursache, Messwerte und Diagramm. Eine Stilabweichung ist kein Qualitätsurteil.`,
          note,
        },
  );
}
