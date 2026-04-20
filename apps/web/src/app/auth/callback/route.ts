// OAuth / email-confirm callback: exchange code for session.
// Also forwards Supabase auth errors (otp_expired, access_denied, etc.) to
// /login with a readable message so users aren't stranded on a blank landing page.
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const errorCode = url.searchParams.get("error_code");
  const errorDesc = url.searchParams.get("error_description");
  const error = url.searchParams.get("error");
  const next = url.searchParams.get("next") || "/dashboard";

  // Supabase redirected back with an auth error — forward to /login with detail
  if (errorCode || error) {
    const login = new URL("/login", url.origin);
    const msg =
      errorCode === "otp_expired"
        ? "Your confirmation link expired. Sign in with your email and password, or request a new link."
        : errorDesc || error || "Authentication failed.";
    login.searchParams.set("error", msg);
    return NextResponse.redirect(login);
  }

  if (code) {
    const supabase = await createClient();
    const { error: exErr } = await supabase.auth.exchangeCodeForSession(code);
    if (exErr) {
      const login = new URL("/login", url.origin);
      login.searchParams.set("error", exErr.message);
      return NextResponse.redirect(login);
    }
  }
  return NextResponse.redirect(new URL(next, url.origin));
}
