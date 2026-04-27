import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

    const url = new URL(req.url);
    let query = supabase.from("team_tasks").select("*", { count: "exact" }).order("created_at", { ascending: false });

    const status = url.searchParams.get("status");
    const assignee = url.searchParams.get("assignee");
    const priority = url.searchParams.get("priority");

    if (status) query = query.eq("status", status);
    if (assignee) query = query.eq("assignee", assignee);
    if (priority) query = query.eq("priority", priority);

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
    const { title, description, assignee, created_by, priority, category, reference_url } = body;

    if (!title || !assignee) {
      return NextResponse.json({ error: "title and assignee required" }, { status: 400 });
    }

    const { data, error } = await supabase
      .from("team_tasks")
      .insert({
        title,
        description: description ?? null,
        assignee,
        created_by: created_by ?? user.id,
        priority: priority ?? "medium",
        category: category ?? "general",
        reference_url: reference_url ?? null,
        status: "pending",
      })
      .select()
      .single();

    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json(data, { status: 201 });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}