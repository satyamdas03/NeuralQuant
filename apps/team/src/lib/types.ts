export interface TeamTask {
  id: string;
  title: string;
  description: string | null;
  assignee: string;
  created_by: string;
  status: "pending" | "in_progress" | "in_review" | "done" | "blocked";
  priority: "low" | "medium" | "high" | "critical";
  category: string;
  output: string | null;
  review_notes: string | null;
  reference_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeamStandup {
  id: string;
  agent_role: string;
  summary: string;
  blockers: string | null;
  next_actions: string | null;
  created_at: string;
}