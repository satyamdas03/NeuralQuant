"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { authedApi } from "@/lib/api";
import type { TeamTask, TeamStandup } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GradientButton from "@/components/ui/GradientButton";
import {
  Users, Loader2, LogIn, Plus, CheckCircle2, Clock,
  AlertTriangle, ChevronDown, Eye, ArrowRight, X,
  Bot, MessageSquare, RefreshCw,
} from "lucide-react";

// ─── Agent metadata ────────────────────────────────────────────────────────────

const AGENTS = [
  { role: "NQ-Engineer", label: "Engineer", icon: "🔧", desc: "Code, deploy, CI/CD" },
  { role: "NQ-Guardian", label: "Guardian", icon: "🛡️", desc: "Security, perf, testing" },
  { role: "NQ-Content", label: "Content", icon: "📝", desc: "SEO, social, newsletter" },
  { role: "NQ-Analyst-Ops", label: "Analyst-Ops", icon: "📊", desc: "Scoring pipeline, data quality" },
  { role: "NQ-Quant", label: "Quant", icon: "🧮", desc: "Research, new models" },
  { role: "NQ-Biz", label: "Biz", icon: "💼", desc: "Billing, metrics, analytics" },
  { role: "NQ-Intel", label: "Intel", icon: "🔍", desc: "Market scanning, competitor watch" },
  { role: "NQ-Support", label: "Support", icon: "🤝", desc: "User feedback, onboarding" },
  { role: "Satyam", label: "Satyam", icon: "👤", desc: "Human orchestrator" },
] as const;

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: "Pending", color: "text-on-surface-variant bg-surface-container", icon: <Clock size={14} /> },
  in_progress: { label: "In Progress", color: "text-blue-400 bg-blue-400/10", icon: <RefreshCw size={14} /> },
  in_review: { label: "In Review", color: "text-amber-400 bg-amber-400/10", icon: <Eye size={14} /> },
  done: { label: "Done", color: "text-emerald-400 bg-emerald-400/10", icon: <CheckCircle2 size={14} /> },
  blocked: { label: "Blocked", color: "text-red-400 bg-red-400/10", icon: <AlertTriangle size={14} /> },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: "Low", color: "text-on-surface-variant" },
  medium: { label: "Med", color: "text-blue-400" },
  high: { label: "High", color: "text-amber-400" },
  critical: { label: "Critical", color: "text-red-400" },
};

// ─── Task card ─────────────────────────────────────────────────────────────────

function TaskCard({ task, onAction }: { task: TeamTask; onAction: (id: string, status: string) => void }) {
  const statusCfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;
  const priCfg = PRIORITY_CONFIG[task.priority] ?? PRIORITY_CONFIG.medium;
  const agent = AGENTS.find((a) => a.role === task.assignee);
  const createdDate = new Date(task.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <GhostBorderCard className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-on-surface leading-tight">{task.title}</h4>
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${statusCfg.color}`}>
          {statusCfg.icon}
          {statusCfg.label}
        </span>
      </div>
      {task.description && (
        <p className="text-xs text-on-surface-variant line-clamp-2">{task.description}</p>
      )}
      <div className="flex items-center justify-between text-[10px]">
        <span className="flex items-center gap-1 text-on-surface-variant">
          <span>{agent?.icon ?? "🤖"}</span>
          <span>{agent?.label ?? task.assignee}</span>
        </span>
        <span className={`font-medium ${priCfg.color}`}>{priCfg.label}</span>
      </div>
      {task.status === "in_review" && (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => onAction(task.id, "done")}
            className="flex-1 text-[11px] font-medium text-emerald-400 bg-emerald-400/10 rounded-md py-1 hover:bg-emerald-400/20 transition-colors"
          >
            Approve
          </button>
          <button
            onClick={() => onAction(task.id, "blocked")}
            className="flex-1 text-[11px] font-medium text-red-400 bg-red-400/10 rounded-md py-1 hover:bg-red-400/20 transition-colors"
          >
            Block
          </button>
        </div>
      )}
      <span className="text-[10px] text-on-surface-variant">{createdDate}</span>
    </GhostBorderCard>
  );
}

// ─── Standup card ──────────────────────────────────────────────────────────────

function StandupCard({ standup }: { standup: TeamStandup }) {
  const agent = AGENTS.find((a) => a.role === standup.agent_role);
  const date = new Date(standup.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  return (
    <GhostBorderCard className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-base">{agent?.icon ?? "🤖"}</span>
        <span className="text-sm font-medium text-on-surface">{agent?.label ?? standup.agent_role}</span>
        <span className="text-[10px] text-on-surface-variant ml-auto">{date}</span>
      </div>
      <p className="text-xs text-on-surface">{standup.summary}</p>
      {standup.blockers && (
        <p className="text-xs text-red-400/80">Blocked: {standup.blockers}</p>
      )}
      {standup.next_actions && (
        <p className="text-xs text-on-surface-variant">Next: {standup.next_actions}</p>
      )}
    </GhostBorderCard>
  );
}

// ─── Skeletons ─────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6 p-4 lg:p-6 animate-pulse">
      <div className="h-8 w-40 bg-surface-container rounded-lg" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 bg-surface-container rounded-xl" />
        ))}
      </div>
      <div className="h-64 bg-surface-container rounded-2xl" />
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function TeamPage() {
  const [tasks, setTasks] = useState<TeamTask[]>([]);
  const [standups, setStandups] = useState<TeamStandup[]>([]);
  const [stats, setStats] = useState<{ by_status: Record<string, number>; by_assignee: Record<string, number>; total: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterAssignee, setFilterAssignee] = useState<string>("");

  const checkAuth = async () => {
    try {
      const { createClient } = await import("@/lib/supabase/client");
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const loggedIn = !!data.session?.access_token;
      setIsLoggedIn(loggedIn);
      return loggedIn;
    } catch {
      setIsLoggedIn(false);
      return false;
    }
  };

  const fetchAll = useCallback(async () => {
    try {
      setError(null);
      const params: Record<string, string> = {};
      if (filterStatus) params.status = filterStatus;
      if (filterAssignee) params.assignee = filterAssignee;
      const [taskRes, standupRes, statsRes] = await Promise.all([
        authedApi.listTeamTasks(params),
        authedApi.listStandups(undefined, 20),
        authedApi.getTaskStats(),
      ]);
      setTasks(taskRes.items);
      setStandups(standupRes.items);
      setStats(statsRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load team hub");
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterAssignee]);

  useEffect(() => {
    checkAuth().then((loggedIn) => {
      if (loggedIn) fetchAll();
      else setLoading(false);
    });
  }, [fetchAll]);

  const handleAction = async (taskId: string, newStatus: string) => {
    try {
      await authedApi.updateTeamTask(taskId, { status: newStatus as TeamTask["status"] });
      setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status: newStatus as TeamTask["status"] } : t)));
    } catch { /* non-critical */ }
  };

  if (loading) return <PageSkeleton />;

  if (isLoggedIn === false) {
    return (
      <div className="space-y-6 p-4 lg:p-6">
        <h1 className="font-headline text-2xl font-bold text-on-surface">Team Hub</h1>
        <GhostBorderCard>
          <div className="text-center py-8">
            <LogIn size={24} className="mx-auto text-on-surface-variant mb-2" />
            <p className="text-sm text-on-surface-variant">Sign in to access the team hub</p>
            <Link
              href="/login"
              className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-on-surface text-sm font-medium hover:bg-primary/80 transition-colors"
            >
              <LogIn size={14} /> Sign in
            </Link>
          </div>
        </GhostBorderCard>
      </div>
    );
  }

  // Group tasks by status for kanban
  const grouped = {
    pending: tasks.filter((t) => t.status === "pending"),
    in_progress: tasks.filter((t) => t.status === "in_progress"),
    in_review: tasks.filter((t) => t.status === "in_review"),
    done: tasks.filter((t) => t.status === "done"),
    blocked: tasks.filter((t) => t.status === "blocked"),
  };

  const reviewCount = grouped.in_review.length;

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users size={24} className="text-primary" />
          <h1 className="font-headline text-2xl font-bold text-on-surface">Team Hub</h1>
          {reviewCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-400/10 px-2.5 py-0.5 text-xs font-medium text-amber-400">
              <Eye size={12} /> {reviewCount} review{reviewCount !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <button
          onClick={fetchAll}
          className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-high hover:text-on-surface transition-colors"
          title="Refresh"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      {error && (
        <GhostBorderCard className="text-sm text-red-400">{error}</GhostBorderCard>
      )}

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
          {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
            <div key={key} className={`rounded-xl p-3 ${cfg.color}`}>
              <div className="flex items-center gap-1.5">
                {cfg.icon}
                <span className="text-xs font-medium">{cfg.label}</span>
              </div>
              <span className="text-xl font-bold">{stats.by_status[key] ?? 0}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="bg-surface-container ghost-border rounded-lg px-3 py-1.5 text-sm text-on-surface"
        >
          <option value="">All Status</option>
          {Object.entries(STATUS_CONFIG).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <select
          value={filterAssignee}
          onChange={(e) => setFilterAssignee(e.target.value)}
          className="bg-surface-container ghost-border rounded-lg px-3 py-1.5 text-sm text-on-surface"
        >
          <option value="">All Agents</option>
          {AGENTS.map((a) => (
            <option key={a.role} value={a.role}>{a.icon} {a.label}</option>
          ))}
        </select>
      </div>

      {/* Kanban board */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        {(Object.entries(grouped) as [string, TeamTask[]][]).map(([status, items]) => {
          const cfg = STATUS_CONFIG[status];
          return (
            <div key={status} className="space-y-2">
              <div className="flex items-center gap-2 px-1">
                <div className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${cfg.color}`}>
                  {cfg.icon} {cfg.label}
                </div>
                <span className="text-xs text-on-surface-variant">{items.length}</span>
              </div>
              <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                {items.length === 0 ? (
                  <div className="rounded-xl bg-surface-container/50 border border-dashed border-ghost-border p-4 text-center text-xs text-on-surface-variant">
                    No tasks
                  </div>
                ) : (
                  items.map((task) => (
                    <TaskCard key={task.id} task={task} onAction={handleAction} />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Agent activity + standups */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Agent roster */}
        <GlassPanel className="space-y-3">
          <h2 className="text-sm font-semibold text-on-surface flex items-center gap-2">
            <Bot size={16} className="text-primary" /> Agent Roster
          </h2>
          <div className="space-y-2">
            {AGENTS.map((a) => {
              const taskCount = stats?.by_assignee?.[a.role] ?? 0;
              return (
                <div key={a.role} className="flex items-center gap-2 text-xs">
                  <span className="text-base">{a.icon}</span>
                  <span className="font-medium text-on-surface flex-1">{a.label}</span>
                  <span className="text-on-surface-variant">{taskCount} task{taskCount !== 1 ? "s" : ""}</span>
                </div>
              );
            })}
          </div>
        </GlassPanel>

        {/* Recent standups */}
        <GlassPanel className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-semibold text-on-surface flex items-center gap-2">
            <MessageSquare size={16} className="text-primary" /> Recent Standups
          </h2>
          {standups.length === 0 ? (
            <p className="text-xs text-on-surface-variant py-4 text-center">No standups yet. Agents will post updates as they work.</p>
          ) : (
            <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
              {standups.map((s) => (
                <StandupCard key={s.id} standup={s} />
              ))}
            </div>
          )}
        </GlassPanel>
      </div>
    </div>
  );
}