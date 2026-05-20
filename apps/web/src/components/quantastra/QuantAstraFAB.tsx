"use client";

import { useState } from "react";
import { Mic } from "lucide-react";
import QuantAstraModal from "./QuantAstraModal";

export default function QuantAstraFAB() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        aria-label="Talk to QuantAstra"
        title="Talk to QuantAstra — AI Portfolio Manager"
        className="fixed bottom-6 right-6 z-[60] flex items-center gap-2 rounded-full bg-primary-fixed px-5 py-3 text-background shadow-[0_0_30px_rgba(0,255,178,0.3)] transition-all duration-300 hover:scale-105 hover:shadow-[0_0_45px_rgba(0,255,178,0.45)]"
      >
        <Mic className="size-5 animate-pulse" />
        <span className="hidden text-sm font-semibold sm:inline">
          Talk to QuantAstra
        </span>
      </button>

      {modalOpen && <QuantAstraModal onClose={() => setModalOpen(false)} />}
    </>
  );
}
