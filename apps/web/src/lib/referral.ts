const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";

export interface ReferralInfo {
  code: string;
  link: string;
  total_referred: number;
  bonus_queries: number;
}

export async function getReferralCode(token: string): Promise<ReferralInfo> {
  const res = await fetch(`${API_URL}/referrals/my-code`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch referral code");
  return res.json();
}

export function getReferralLink(code: string): string {
  const site = process.env.NEXT_PUBLIC_SITE_URL || "https://neuralquant.vercel.app";
  return `${site}/signup?ref=${code}`;
}