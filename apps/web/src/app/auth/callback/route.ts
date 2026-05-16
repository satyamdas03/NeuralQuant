// OAuth / email-confirm callback: exchange code for session.
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const errorCode = url.searchParams.get("error_code");
  const errorDesc = url.searchParams.get("error_description");
  const error = url.searchParams.get("error");
  const next = url.searchParams.get("next") || "/dashboard";

  console.log("[auth/callback] params:", {
    hasCode: !!code,
    errorCode,
    error,
    errorDesc,
    next,
    origin: url.origin,
  });

  if (errorCode || error) {
    console.error("[auth/callback] Supabase auth error:", errorCode || error, errorDesc);
    const login = new URL("/login", url.origin);
    const msg =
      errorCode === "otp_expired"
        ? "Your confirmation link expired. Sign in with your email and password, or request a new link."
        : errorDesc || error || "Authentication failed.";
    login.searchParams.set("error", msg);
    return NextResponse.redirect(login);
  }

  if (!code) {
    console.error("[auth/callback] No code in callback, redirecting to login");
    const login = new URL("/login", url.origin);
    login.searchParams.set("error", "No authentication code received. Please try again.");
    return NextResponse.redirect(login);
  }

  const supabase = await createClient();
  const { data, error: exErr } = await supabase.auth.exchangeCodeForSession(code);

  if (exErr) {
    console.error("[auth/callback] exchangeCodeForSession failed:", exErr.message);
    const login = new URL("/login", url.origin);
    login.searchParams.set("error", exErr.message);
    return NextResponse.redirect(login);
  }

  console.log("[auth/callback] Session created for:", data?.user?.email || "unknown");
  return NextResponse.redirect(new URL(next, url.origin));
}
