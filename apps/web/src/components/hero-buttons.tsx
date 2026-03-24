"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function HeroButtons() {
  return (
    <div className="flex gap-4">
      <Link
        href="/screener"
        className={cn(buttonVariants({ size: "lg" }), "bg-violet-600 hover:bg-violet-700")}
      >
        View Top Picks
      </Link>
      <Link
        href="/query"
        className={cn(buttonVariants({ size: "lg", variant: "outline" }), "border-gray-700 hover:bg-gray-800")}
      >
        Ask the AI
      </Link>
    </div>
  );
}
