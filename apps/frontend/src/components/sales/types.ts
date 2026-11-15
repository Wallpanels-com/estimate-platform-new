export interface GhlRecord {
  _latest_comment?: GhlRecord | null;
  _id: string;
  id?: string;
  _synced_at: string;
  _changed_at: string;
  _active: boolean;
  name?: string;
  fullName?: string;
  firstName?: string;
  lastName?: string;
  contactName?: string;
  contactId?: string;
  assignedTo?: string;
  userId?: string;
  source?: string;
  status?: string;
  pipelineId?: string;
  pipelineStageId?: string;
  monetaryValue?: number;
  createdAt?: string;
  updatedAt?: string;
  dateAdded?: string;
  dateUpdated?: string;
  contact?: { name?: string; email?: string; phone?: string };
  phone?: string;
  email?: string;
  tags?: string[];
  body?: string;
  lastMessageBody?: string;
  lastMessageDate?: string | number;
  lastMessageType?: string;
  direction?: string;
  messageType?: string;
  conversationId?: string;
  lastCallStatus?: string;
  lastMessageDirection?: string;
  unreadCount?: number;
  phoneNumber?: string;
  friendlyName?: string;
  linkedUser?: string;
  linkedRingAllUsers?: string[];
  inboundCallService?: { type?: string; value?: string };
  forwardingNumber?: string;
  isDefaultNumber?: boolean;
  capabilities?: { sms?: boolean; voice?: boolean };
  agentId?: string;
  transcript?: string;
  summary?: string;
  duration?: number;
  messageId?: string;
  fromNumber?: string;
  availability?: string;
  segments?: {
    transcript?: string;
    text?: string;
    startTime?: number;
    mediaChannel?: number;
  }[];
  attributionSource?: Record<string, unknown>;
  lastAttributionSource?: Record<string, unknown>;
  customFields?: { id: string; value?: unknown }[];
  title?: string;
  completed?: boolean;
}
export interface Lookups {
  users: { id: string; name: string; deleted: boolean }[];
  pipelines: {
    id: string;
    name: string;
    stages: { id: string; name: string }[];
  }[];
  agents: { id: string; name: string }[];
}
export interface Review {
  contact_name?: string;
  id: string;
  contact_id?: string;
  created_at: string;
  summary: string;
  outcome: string;
  source_kind: string;
  source_id: string;
  findings: {
    kind: string;
    severity: string;
    source_id: string;
    quote: string;
    explanation: string;
    recommendation: string;
    confidence: string;
  }[];
  sources: {
    id: string;
    text: string;
    actor: string;
    start_ms?: number;
    date?: string;
  }[];
  next_steps: string[];
  limitations: string[];
  lead_reasons: string[];
}
export interface SalesStatus {
  configured: boolean;
  enabled: boolean;
  counts: Record<string, number>;
  analyses: number;
  concerns: number;
  jobs: Record<string, number>;
  job_errors: { kind: string; error: string; count: number }[];
  resources: {
    name: string;
    last_success: string | null;
    error: string | null;
    state: {
      complete?: boolean;
      total?: number;
      loaded?: number;
      completed_at?: string;
    };
  }[];
  history_days: number;
  ai_daily_limit: number;
  location_id: string;
}
export interface ContactDetail {
  contact: GhlRecord | null;
  conversations: GhlRecord[];
  opportunities: GhlRecord[];
  messages: GhlRecord[];
  notes: GhlRecord[];
  tasks: GhlRecord[];
  calls: GhlRecord[];
  transcripts: GhlRecord[];
  analyses: Review[];
  pending: number;
  history_days: number;
  message_limit: number;
  warning: string | null;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}
export interface Report {
  count: number;
  value: string;
  statuses: Record<string, number>;
  groups: {
    pipeline_id: string;
    stage_id: string;
    owner_id: string;
    status: string;
    count: number;
    value: string;
  }[];
}
