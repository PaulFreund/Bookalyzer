import { renderToStaticMarkup } from "react-dom/server";
import {
  Histogram,
  ProfileChart,
  TrendChart,
  ViolinChart,
  number,
} from "./charts";
import type { Bootstrap, Comparison, Document } from "./types";

export function exportContent(
  format: string,
  documents: Document[],
  data: Bootstrap,
  comparison: Comparison | null,
) {
  const report = {
    generatedAt: new Date().toISOString(),
    method: data.method,
    reference: data.reference,
    comparison,
    documents: documents.map(({ segments, ...doc }) => ({
      ...doc,
      segments: segments.map(({ preview, ...s }) => s),
    })),
  };
  if (format === "json") return JSON.stringify(report, null, 2);
  if (format === "csv") {
    const escape = (v: unknown) =>
      '"' +
      String(v ?? "")
        .replace(/^[=+\-@]/, "'$&")
        .replaceAll('"', '""') +
      '"';
    const rows: unknown[][] = [
      [
        "Text",
        "Dokument-ID",
        "Segment",
        "Wörter",
        "Mittlere Satzlänge",
        "Wortvielfalt je 100 Wörter",
        "Interne narrative Distanz",
        "Feature-Set",
        "k",
        "Referenzraum",
        "Modell",
      ],
    ];
    for (const doc of documents)
      doc.segments.forEach((s, i) =>
        rows.push([
          doc.title,
          doc.id,
          s.index + 1,
          s.words,
          doc.segmentMetrics?.[i]?.sentenceMean,
          doc.segmentMetrics?.[i]?.vocabulary,
          comparison?.series.find((v) => v.id === doc.id)?.values[i],
          comparison?.featureSet,
          comparison?.k,
          comparison?.scope,
          doc.narrative?.model,
        ]),
      );
    return "\uFEFF" + rows.map((row) => row.map(escape).join(";")).join("\r\n");
  }
  return (
    "<!doctype html>" +
    renderToStaticMarkup(
      <html lang="de">
        <head>
          <meta charSet="utf-8" />
          <title>Bookalyzer · Analysebericht</title>
          <meta
            httpEquiv="Content-Security-Policy"
            content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"
          />
          <style>{`
    *{box-sizing:border-box}body{font:14px/1.6 Arial,sans-serif;color:#2c3044;max-width:1080px;margin:40px auto;padding:0 30px}h1{font:38px Georgia,serif}h2{font-size:22px;margin:28px 0 8px}h3{font-size:16px}p{color:#636779}.chart{width:100%;max-height:340px}.grid{stroke:#e8e9ef;stroke-dasharray:3 4}.tick{fill:#6d7285;font-size:11px}.axis-label{fill:#454a60;font-size:12px}.value-label{font-size:14px}.row{display:flex;gap:30px}.row>section{flex:1;min-width:0}section{break-inside:avoid;border-top:1px solid #e8e9ef;padding-top:10px}.badge{display:inline-block;padding:4px 10px;border:1px solid #ddd;border-radius:20px;margin-right:8px}table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;padding:8px;border-bottom:1px solid #eee}.fine{font-size:11px;color:#707589}a{color:#7262c4}@page{size:A4;margin:16mm}@media print{body{margin:0;padding:0}.row{display:block}.chart{max-height:285px}h2{break-after:avoid}}
  `}</style>
        </head>
        <body>
          <p>BOOKALYZER / TEXTLABOR</p>
          <h1>Texte im Vergleich</h1>
          <p>Analysebericht · {new Date().toLocaleDateString("de-DE")}</p>
          <p>
            {documents.map((doc) => (
              <span key={doc.id} className="badge" style={{ color: doc.color }}>
                {doc.title}
              </span>
            ))}
          </p>
          <p>
            Deskriptive Textmerkmale und explorative StoryScope-Analyse. Keine
            kalibrierte Wahrscheinlichkeit menschlicher Urheberschaft und keine
            literarische Qualitätsnote.
          </p>
          {documents.some((d) => d.narrative) && (
            <section>
              <h2>Narratives Profil</h2>
              <p>
                Skalierte Merkmalsausprägung 0–100 · Türkis: Mensch · Ocker: KI
                · farbige Kreise: Texte. Referenzbänder: 25.–75. Perzentil
                gültiger Einzelmerkmalswerte.
              </p>
              <ProfileChart documents={documents} reference={data.reference} />
            </section>
          )}
          {comparison?.available && (
            <section>
              <h2>Interne narrative Seltenheit</h2>
              <p>
                {comparison.scope} · {comparison.featureSet} · k ={" "}
                {comparison.k}
              </p>
              <ViolinChart documents={documents} comparison={comparison} />
              <p className="fine">
                Linie: Mittelwert · gestrichelt: Median · Punkt: Segment. Dichte
                erst ab fünf Segmenten. {comparison.note}
              </p>
              <TrendChart
                documents={documents}
                comparison={comparison}
                metric="rarity"
              />
            </section>
          )}
          <section>
            <h2>Sprachliches Profil</h2>
            <Histogram documents={documents} />
            <p>
              Satzgrenzen werden regelbasiert erkannt; Abkürzungen können die
              Zählung beeinflussen.
            </p>
          </section>
          {documents.map((doc) => (
            <section key={doc.id}>
              <h2>{doc.title}</h2>
              {doc.report?.map((p, i) => (
                <p key={i}>{p}</p>
              ))}
              {doc.qualitySummary && (
                <>
                  <h3>Zusätzliche lokale Qualitätsmerkmale</h3>
                  <p>
                    Methodenversion {doc.qualitySummary.version}. Vollständige
                    51 Kennzahlen, Vergleichsdiagramme und Fundstellen im
                    eigenen Qualitätsbericht unter „Qualitätslabor“. Höhere
                    Werte sind keine besseren Noten.
                  </p>
                  <table>
                    <thead>
                      <tr>
                        <th>Kennzahl</th>
                        <th>Gesamttext</th>
                        <th>Einheit / Hinweis</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ["lix", "LIX", "Index"],
                        ["mattr", "MATTR · 100 Wörter", "%"],
                        ["hdd", "HD-D · 42 Wörter", "%"],
                        ["mtld", "MTLD · 0,72", "Wörter"],
                        ["sentenceCV", "Satzlängenvariation", "CV"],
                        ["trigramRepeat", "Wiederholte Dreierphrasen", "%"],
                        ["cohesion", "Lexikalischer Absatzanschluss", "%"],
                        ["passive", "Passivkandidaten", "% · Heuristik"],
                      ].map(([id, title, unit]) => (
                        <tr key={id}>
                          <th>{title}</th>
                          <td>{number(doc.qualitySummary!.values[id], 2)}</td>
                          <td>{doc.qualitySummary!.reasons[id] || unit}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              <p>
                Modell: {doc.narrative?.model || "Lokale Statistik"} · Sprache:{" "}
                {doc.settings.language} · Segmentziel:{" "}
                {number(doc.settings.targetWords)} Wörter.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Segment</th>
                    <th>Kapitel</th>
                    <th>Wörter</th>
                    <th>Ø Satzlänge</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.segments.map((s, i) => (
                    <tr key={s.id}>
                      <td>{s.index + 1}</td>
                      <td>{s.title}</td>
                      <td>{number(s.words)}</td>
                      <td>
                        {number(doc.segmentMetrics?.[i]?.sentenceMean, 1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
          <section>
            <h2>Methode & Einordnung</h2>
            <p>
              <a href={data.method.url}>
                StoryScope: Investigating idiosyncrasies in AI fiction
              </a>{" "}
              · {data.method.version}.
            </p>
            <p>{data.method.externalReason}</p>
            <p>
              {data.reference.scope}. {data.reference.policy}
            </p>
            <p>
              Codex-Extraktionen verwenden die veröffentlichte Taxonomie mit
              zehn Aufrufen je Segment, aber ein anderes Extraktionsmodell als
              die Studie. Romansegmente und nicht-englische Texte sind
              methodische Übertragungen. Die sechs Profilachsen sind keine
              vollständige Abbildung der 304 Merkmale.
            </p>
            <p>
              Wortvielfalt: mittlere Anzahl verschiedener Wörter in
              vollständigen, nicht überlappenden 100-Wort-Fenstern; kurze Reste
              ausgeschlossen. Satzvariation: Standardabweichung geteilt durch
              mittlere Satzlänge. Wörtliche Rede: heuristisch über
              Anführungszeichen gezählt.
            </p>
            <p className="fine">
              Referenz SHA-256: {data.reference.sha256 || "nicht verfügbar"}.
              Erstellt: {report.generatedAt}.
            </p>
          </section>
        </body>
      </html>,
    )
  );
}
