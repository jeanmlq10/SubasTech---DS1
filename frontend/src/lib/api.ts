export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: "client" | "technician" | "admin" | "arbiter";
  phone_number: string;
  whatsapp_id: string | null;
};

export type Category = {
  id: number;
  name: string;
  slug: string;
  description: string;
  is_active: boolean;
};

export type Zone = {
  id: number;
  name: string;
  slug: string;
  city: string;
  is_active: boolean;
};

export type TechnicianService = {
  id: number;
  category: Category;
  title: string;
  description: string;
  base_price: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TechnicianProfile = {
  id: number;
  bio: string;
  is_verified: boolean;
  availability_status: "available" | "busy" | "offline";
  response_time_minutes: number;
  completed_services: number;
  service_completion_rate: string;
  zones: Zone[];
};

export type OnboardingResponse = {
  onboarding_complete: boolean;
  profile: TechnicianProfile | null;
};


export type AdminMetrics = {
  total_technicians: number;
  verified_technicians: number;
  pending_verification: number;
  suspended_technicians: number;
  active_services: number;
  inactive_services: number;
  total_leads: number;
  new_leads: number;
  contacted_leads: number;
  accepted_leads: number;
  closed_leads: number;
  open_disputes: number;
  in_review_disputes: number;
  resolved_disputes: number;
  average_rating: number;
  average_reputation_score: number;
  recent_integration_errors: number;
  total_categories: number;
  total_zones: number;
};

export type AdminTechnicianSummary = {
  id: number;
  name: string;
  email: string;
  is_verified: boolean;
  user_is_active: boolean;
  availability_status: string;
  response_time_minutes: number;
  service_count: number;
  average_rating: number;
  zones: string[];
  created_at: string;
};

export type AdminServiceSummary = {
  id: number;
  title: string;
  category: string;
  technician: string;
  base_price: string;
  is_active: boolean;
  created_at: string;
};

export type AdminDisputeSummary = {
  id: number;
  title: string;
  status: string;
  priority: string;
  client: string;
  technician: string;
  service: string | null;
  created_at: string;
};

export type AdminAlert = {
  type: "warning" | "critical" | "info";
  title: string;
  message: string;
};

export type AdminAuditEvent = {
  id: number;
  event_type: string;
  status: string;
  source: string;
  entity_type: string;
  entity_id: string;
  message: string;
  created_at: string;
};

export type AdminSummary = {
  metrics: AdminMetrics;
  recent_technicians: AdminTechnicianSummary[];
  recent_services: AdminServiceSummary[];
  recent_disputes: AdminDisputeSummary[];
  lead_status_breakdown: Record<string, number>;
  recent_errors: AdminAuditEvent[];
  role_breakdown: Record<string, number>;
  alerts: AdminAlert[];
};


export type ArbiterAssistant = {
  summary: string;
  classification: string;
  suggested_priority: string;
  recommended_review_steps: string[];
};

export type ArbiterDispute = {
  id: number;
  client_name: string;
  technician_name: string;
  service_title: string | null;
  title: string;
  description: string;
  ai_summary: string;
  assistant: ArbiterAssistant;
  priority: string;
  status: string;
  decision: string;
  arbiter: number | null;
  arbiter_notes: string;
  evidence: Array<{ id: number; note: string; created_at: string }>;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type ArbiterQueue = {
  metrics: {
    open: number;
    in_review: number;
    resolved_by_me: number;
    high_priority: number;
  };
  by_status: Record<string, number>;
  disputes: ArbiterDispute[];
};


export type TechnicianLead = {
  id: number;
  service_title: string | null;
  client_name: string;
  client_phone: string;
  message: string;
  category: string;
  location: string;
  urgency: string;
  source: string;
  status: "new" | "contacted" | "accepted" | "closed";
  created_at: string;
  updated_at: string;
};
