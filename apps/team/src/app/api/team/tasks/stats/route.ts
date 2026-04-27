import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

    const { data, error } = await supabase.from("team_tasks").select("status, assignee");
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });

    const by_status: Record<string, number> = {};
    const by_assignee: Record<string, number> = {};

    for (const row of data ?? []) {
      by_status[row.status] = (by_status[row.status] ?? 0) + 1;
      by_assignee[row.assignee] = (by_assignee[row.assignee] ?? 0) + 1;
    }

    return NextResponse.json({ by_status, by_assignee, total: data?.length ?? 0 });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}