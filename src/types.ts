export type Settings = {
  language: "de" | "en" | "und";
  mode: "local" | "codex";
  targetWords: number;
  minWords: number;
  maxWords: number;
  excludeFrontmatter: boolean;
  excludeBackmatter: boolean;
  detectChapters: boolean;
  qualityGroups: string[];
  longSentenceWords: number;
  longSentenceShare: number;
  textProfile: "narrative" | "informative" | "technical";
  featureSet: "public_nonstyle_265" | "full_304";
  model: string;
  reasoningEffort: string;
  parallel: number;
};
export type Metrics = {
  words: number;
  sentences: number;
  sentenceMean: number;
  sentenceVariation: number;
  vocabulary: number | null;
  dialogue: number;
  paragraphs: number;
  histogram: number[];
};
export type Axis = {
  id: string;
  label: string;
  short: string;
  description: string;
};
export type Profile = Axis & {
  mean: number | null;
  values: (number | null)[];
  n: number;
  total: number;
};
export type Segment = {
  index: number;
  id: string;
  title: string;
  words: number;
  preview: string;
};
export type Document = {
  id: string;
  name: string;
  title: string;
  settings: Settings;
  createdAt: string;
  completedAt?: string;
  status: "draft" | "queued" | "analyzing" | "ready" | "error";
  error: string | null;
  color: string;
  wordCount: number;
  segmentCount: number;
  segments: Segment[];
  metrics?: Metrics;
  segmentMetrics?: Metrics[];
  source?: string;
  report?: string[];
  qualitySummary?: Pick<
    QualityProfile,
    "version" | "values" | "reasons" | "words" | "language"
  >;
  progress?: { completed: number; total: number };
  storyscope?: {
    status: "queued" | "analyzing" | "ready" | "error";
    error: string | null;
    startedAt: string;
    completedAt?: string;
  };
  provenance?: Record<string, string>;
  narrative?: {
    profiles: Profile[];
    featureCount: number;
    model: string;
    provider: string;
    exploratory: boolean;
    reasoningEffort?: string;
  } | null;
};
export type ReferenceValue = {
  mean: number | null;
  n: number;
  total: number;
  q25: number | null;
  q75: number | null;
};
export type Reference = {
  available: boolean;
  profiles: (Axis & { human: ReferenceValue; ai: ReferenceValue })[];
  scope?: string;
  policy?: string;
  sha256?: string;
  rows?: number;
};
export type Series = {
  id: string;
  title: string;
  values: number[];
  mean: number;
  median: number;
  indices: number[];
};
export type Comparison = {
  available: boolean;
  reason?: string;
  series: Series[];
  distance?: number[][];
  featureSet?: string;
  dimensions?: number;
  k?: number;
  segments?: number;
  scope?: string;
  note?: string;
  languages?: string[];
};
export type Bootstrap = {
  baselines: Baseline[];
  documents: Document[];
  settings: Settings;
  reference: Reference;
  model: string;
  method: {
    study: string;
    version: string;
    url: string;
    externalRarityAvailable: boolean;
    externalReason: string;
    library: string;
  };
};
export type UploadFile = { name: string; base64: string };
export type LibraryPreview = {
  id: string;
  name: string;
  createdAt: string | null;
  fileCount: number;
  bytes: number;
  documentCount: number;
  baselineCount: number;
};
export type LibraryImportResult = {
  documentCount: number;
  baselineCount: number;
  backupPath: string;
};
export type CodexModels = {
  available: boolean;
  configuredModel: string;
  reason: string | null;
  models: {
    id: string;
    name: string;
    description: string;
    reasoningEfforts: string[];
    defaultReasoningEffort: string | null;
    isDefault: boolean;
  }[];
};
export type Baseline = {
  id: string;
  name: string;
  documentId: string;
  documentTitle: string;
  createdAt: string;
  wordCount: number;
  segmentCount: number;
  narrative: boolean;
  hashes: Record<string, string>;
  textSha256: string;
};
export type BaselineInfo = Baseline & {
  metrics: Metrics;
  k: number | null;
  dimensions: number | null;
  note: string;
};
export type BaselineScore = {
  delta: Record<
    "sentenceMean" | "sentenceVariation" | "vocabulary" | "dialogue",
    number | null
  >;
  distance: number | null;
  values: number[];
  reason: string | null;
  warnings: string[];
};
export type BaselineComparison = {
  baseline: BaselineInfo;
  rows: (BaselineScore & { id: string; title: string; metrics: Metrics })[];
};
export type Chapter = {
  id: string;
  index: number;
  title: string;
  words: number;
  metrics: Metrics;
  profiles: Profile[];
  segmentIndices: number[];
  narrativeComplete: boolean;
  short: boolean;
  comparison?: BaselineScore;
};
export type Chapters = {
  documentId: string;
  title: string;
  chapters: Chapter[];
  distance: (number | null)[][] | null;
  baseline: BaselineInfo | null;
  note: string;
};
export type QualityMetric = {
  id: string;
  label: string;
  group: string;
  unit: string;
  formula: string;
  note: string;
  languages: string[];
  minWords: number;
  source: string | null;
  kind: string;
  displayRange: [number, number];
};
export type QualityEvidence = {
  key?: string;
  intentional?: boolean;
  metric: string;
  start: number;
  end: number;
  label: string;
  before: string;
  text: string;
  after: string;
  truncated: boolean;
};
export type QualityProfile = {
  version: string;
  textSha256: string;
  language: string;
  words: number;
  sentences: number;
  paragraphs: number;
  groups: string[];
  longSentenceWords: number;
  longSentenceShare: number;
  textProfile: Settings["textProfile"];
  basis?: { origin: string; note: string };
  values: Record<string, number | null>;
  reasons: Record<string, string>;
  evidence: QualityEvidence[];
  evidenceCounts: Record<string, number>;
  intentionalCounts?: Record<string, number>;
  cadence: {
    first: number;
    last: number;
    mean: number;
    low: number;
    high: number;
    start: number;
    end: number;
  }[];
  keywords: { word: string; count: number }[];
  phrases: { text: string; count: number }[];
};
export type QualityDelta = {
  values: Record<string, number | null>;
  reasons: Record<string, string>;
};
export type QualityPoint = {
  index: number;
  title: string;
  words: number;
  values: QualityProfile["values"];
  reasons: QualityProfile["reasons"];
  delta: QualityDelta | null;
  comparison?: QualityReference | null;
};
export type QualityBand = {
  low: number;
  median: number;
  high: number;
  n: number;
};
export type QualityReference = {
  basis: string;
  name: string;
  words: number;
  windows: number;
  values: Record<string, number | null>;
  bands: Record<string, QualityBand>;
  note: string;
};
export type QualityCard = {
  id: string;
  label: string;
  status: "fit" | "review" | "observe" | "unknown";
  title: string;
  detail: string;
  metric: string;
  value: number | null;
  target: number | null;
};
export type QualitySummary = {
  profile: string;
  note: string;
  intentional: number;
  cards: QualityCard[];
  deviations: QualityDeviation[];
  consistencyReference: {
    name: string;
    kind: "baseline" | "chapters";
    bands: Record<string, QualityBand>;
  };
  priorities: {
    metric: string;
    title: string;
    explanation: string;
    count: number;
    openCount: number;
    group: string;
    evidence: QualityEvidence[];
  }[];
};
export type QualityDeviation = {
  metric: string;
  label: string;
  direction: "lower" | "higher";
  title: string;
  explanation: string;
  detail: string;
  suggestion: string;
  value: number;
  band: QualityBand;
  unit: string;
  reference: string;
  referenceKind: "baseline" | "chapters";
};
export type QualityFindings = {
  total: number;
  offset: number;
  limit: number;
  textSha256: string;
  items: QualityEvidence[];
};
export type QualityRow = {
  id: string;
  documentId: string;
  chapterIndex: number | null;
  title: string;
  color: string;
  quality: QualityProfile;
  delta: QualityDelta | null;
  comparison: QualityReference | null;
  summary: QualitySummary;
};
export type QualityReport = {
  catalog: {
    version: string;
    groups: { id: string; label: string }[];
    metrics: QualityMetric[];
    sources: { id: string; label: string; url: string }[];
    lexicons: Record<string, Record<string, string>>;
    stopwords: Record<string, string[]>;
    note: string;
  };
  rows: QualityRow[];
  baseline: (Baseline & { quality: QualityProfile; derivation: string }) | null;
  scope: "chapters" | "documents";
};
declare global {
  interface Window {
    bookalyzer?: {
      call: <T>(method: string, params?: unknown) => Promise<T>;
      pickFiles: () => Promise<UploadFile[]>;
      exportLibrary: () => Promise<boolean>;
      pickLibrary: () => Promise<LibraryPreview | null>;
      save: (name: string, content: string, format: string) => Promise<boolean>;
    };
  }
}
