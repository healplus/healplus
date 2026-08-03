export type AIMode =
  | 'assistant'
  | 'clinical-analysis'
  | 'evolution-comparison'
  | 'report-draft'
  | 'medical-record-search'
  | 'external-search';

export type ProcessingStage =
  | 'idle'
  | 'uploading'
  | 'retrieving-context'
  | 'analyzing'
  | 'comparing'
  | 'generating'
  | 'streaming'
  | 'completed'
  | 'cancelled'
  | 'error';

export interface PatientContext {
  id: string;
  displayName: string;
  maskedIdentifier?: string;
  lastAppointmentAt?: string;
}

export interface ChatAttachment {
  id: string;
  name: string;
  type: 'image' | 'pdf' | 'report' | 'assessment' | 'patient';
  status: 'uploading' | 'ready' | 'error';
  progress?: number;
  previewUrl?: string;
  size?: number;
  file?: File;
  patientId?: string;
}

export interface AIComposerState {
  value: string;
  mode: AIMode;
  internalSearchEnabled: boolean;
  externalSearchEnabled: boolean;
  attachments: ChatAttachment[];
  patientContext?: PatientContext;
  isRecording: boolean;
  isTranscribing: boolean;
  isSubmitting: boolean;
}

export interface PatientSummaryCardData {
  name: string;
  age?: number;
  maskedIdentifier?: string;
  lastAppointment?: string;
  evaluationsCount: number;
  status: string;
}

export interface WoundEvolutionCardData {
  initialDate: string;
  currentDate: string;
  dimensions: string;
  areaEstimate: string;
  healthScore: number;
  roiVariationPercentage: number;
  trend: 'improving' | 'stable' | 'deteriorating';
  requiresReview: boolean;
}

export interface ImageComparisonCardData {
  previousImageUrl: string;
  previousDate: string;
  currentImageUrl: string;
  currentDate: string;
  metricsSummary: string;
  caption?: string;
}

export interface ReportDraftCardData {
  title: string;
  content: string;
  draftId?: string;
}

export interface StructuredClinicalData {
  patientSummary?: PatientSummaryCardData;
  woundEvolution?: WoundEvolutionCardData;
  imageComparison?: ImageComparisonCardData;
  reportDraft?: ReportDraftCardData;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  error?: boolean;
  model?: string;
  provider?: string;
  attachments?: ChatAttachment[];
  patientContext?: PatientContext;
  clinicalData?: StructuredClinicalData;
  sources?: { title: string; url?: string; date?: string }[];
  timestamp?: number;
  feedback?: 'positive' | 'negative' | null;
  transmissionConsentId?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  isPinned?: boolean;
  isArchived?: boolean;
  patientContext?: PatientContext;
}
