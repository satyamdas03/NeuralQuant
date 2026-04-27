import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

    const url = new URL(req.url);
    const agentRole = url.searchParams.get("agent_role");
    const limit = parseInt(url.searchParams.get("limit") ?? "20", 10);

    let query = supabase
      .from("team_standups")
      .select("*", { count: "exact" })
      .order("created_at", { ascending: false })
      .limit(limit);

    if (agentRole) query = query.eq("agent_role", agentRole);

    const { data, count, error } = await query;
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });

    return NextResponse.json({ items: data ?? [], count: count ?? 0 });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

    const body = await req.json();
    const { agent_role, summary, blockers, next_actions } = body;

    if (!agent_role || !summary) {
      return NextResponse.json({ error: "agent_role and summary required" }, { status: 400 });
    }

    const { data, error } = await supabase
      .from("team_standups")
      .insert({
        agent_role,
        summary,
        blockers: blockers ?? null,
        next_actions: next_actions ?? null,
      })
      .select()
      .single();

    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json(data, { status: 201 });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}