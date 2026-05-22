"use client";

import { useEffect, useRef, useState } from "react";
import { X, Maximize2, Minimize2 } from "lucide-react";

interface CalcStep {
  label: string;
  formula?: string;
  value?: string;
}

interface WhiteboardContent {
  title: string;
  description?: string;
  steps: CalcStep[];
  result: string;
  currency?: string;
  disclaimer?: string;
}

export default function QuantAstraWhiteboard({
  content,
  onToggle,
  isOpen,
}: {
  content: WhiteboardContent | null;
  onToggle: (open: boolean) => void;
  isOpen: boolean;
}) {
  const [fullscreen, setFullscreen] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const stepIndexRef = useRef(0);

  // Animate calculation steps appearing one by one
  useEffect(() => {
    if (!content || !isOpen) {
      stepIndexRef.current = 0;
      return;
    }
    stepIndexRef.current = 0;
    const total = content.steps.length;
    if (total === 0) return;

    const interval = setInterval(() => {
      stepIndexRef.current = Math.min(stepIndexRef.current + 1, total);
      if (stepIndexRef.current >= total) clearInterval(interval);
    }, 600);

    return () => clearInterval(interval);
  }, [content, isOpen]);

  // Draw whiteboard content on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !content || !isOpen) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const pad = 32;

    const draw = () => {
      // Whiteboard background — opaque off-white like a real whiteboard
      ctx.fillStyle = "#fafbfc";
      ctx.fillRect(0, 0, W, H);

      // Subtle dot grid — light gray, barely visible
      ctx.fillStyle = "rgba(209, 213, 219, 0.5)";
      const gridSize = 28;
      for (let x = pad; x < W - pad; x += gridSize) {
        for (let y = pad; y < H - pad; y += gridSize) {
          ctx.beginPath();
          ctx.arc(x, y, 1, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      let y = pad + 10;

      // Title — dark bold
      ctx.fillStyle = "#111827";
      ctx.font = "700 22px 'Inter', system-ui, sans-serif";
      ctx.fillText(content.title, pad, y);
      y += 36;

      // Description
      if (content.description) {
        ctx.fillStyle = "#4b5563";
        ctx.font = "14px 'Inter', system-ui, sans-serif";
        const words = content.description.split(" ");
        let line = "";
        for (const word of words) {
          const test = line + word + " ";
          if (ctx.measureText(test).width > W - pad * 2) {
            ctx.fillText(line, pad, y);
            y += 22;
            line = word + " ";
          } else {
            line = test;
          }
        }
        if (line) {
          ctx.fillText(line, pad, y);
          y += 22;
        }
        y += 16;
      }

      // Divider — light gray
      ctx.strokeStyle = "rgba(209, 213, 219, 0.8)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad, y);
      ctx.lineTo(W - pad, y);
      ctx.stroke();
      y += 26;

      // Steps — revealed one by one
      const visibleSteps = stepIndexRef.current;
      for (let i = 0; i < content.steps.length; i++) {
        const step = content.steps[i];
        const isVisible = i < visibleSteps;
        const alpha = isVisible ? 1 : 0.12;

        // Step background highlight — light gray
        if (isVisible) {
          ctx.fillStyle = "rgba(243, 244, 246, 0.9)";
          const stepH = 52;
          ctx.beginPath();
          ctx.roundRect(pad - 8, y - 8, W - pad * 2 + 16, stepH + 8, 8);
          ctx.fill();
        }

        // Step number — emerald accent
        ctx.fillStyle = `rgba(5, 150, 105, ${alpha * 0.8})`;
        ctx.font = "600 13px 'Inter', system-ui, sans-serif";
        ctx.fillText(`${i + 1}.`, pad, y + 4);

        // Step label — dark bold for visible, gray for hidden
        ctx.fillStyle = `rgba(17, 24, 39, ${alpha})`;
        ctx.font = `${isVisible ? "700" : "400"} 14px 'Inter', system-ui, sans-serif`;
        ctx.fillText(step.label, pad + 28, y + 4);

        // Formula — dark mono
        if (step.formula) {
          ctx.fillStyle = `rgba(55, 65, 81, ${alpha * 0.9})`;
          ctx.font = "13px 'JetBrains Mono', 'Fira Code', monospace";
          ctx.fillText(step.formula, pad + 28, y + 22);
        }

        // Value (right-aligned) — dark emerald bold
        if (step.value && isVisible) {
          ctx.fillStyle = "#059669";
          ctx.font = "700 15px 'JetBrains Mono', 'Fira Code', monospace";
          const valW = ctx.measureText(step.value).width;
          ctx.fillText(step.value, W - pad - valW, y + 12);
        }

        y += 56;
      }

      y += 8;

      // Result highlight box — light emerald background with dark text
      if (stepIndexRef.current >= content.steps.length) {
        ctx.fillStyle = "rgba(209, 250, 229, 0.7)";
        ctx.strokeStyle = "rgba(5, 150, 105, 0.4)";
        ctx.lineWidth = 1.5;
        const boxH = 52;
        ctx.beginPath();
        ctx.roundRect(pad - 4, y - 4, W - pad * 2 + 8, boxH + 8, 10);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#047857";
        ctx.font = "700 16px 'Inter', system-ui, sans-serif";
        ctx.fillText("Result", pad + 8, y + 18);

        ctx.fillStyle = "#111827";
        ctx.font = "800 18px 'JetBrains Mono', 'Fira Code', monospace";
        const resW = ctx.measureText(content.result).width;
        ctx.fillText(content.result, W - pad - resW - 8, y + 38);
      }

      // Disclaimer — medium gray
      if (content.disclaimer && stepIndexRef.current >= content.steps.length) {
        y += 70;
        ctx.fillStyle = "rgba(107, 114, 128, 0.7)";
        ctx.font = "11px 'Inter', system-ui, sans-serif";
        ctx.fillText(content.disclaimer, pad, y);
      }

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [content, isOpen, fullscreen]);

  if (!isOpen) return null;

  return (
    <div
      className={
        fullscreen
          ? "fixed inset-0 z-50 bg-background flex flex-col"
          : "flex flex-col h-full border-l border-gray-200 bg-white"
      }
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <span className="text-xs font-semibold text-gray-700 tracking-wide">
          QUANTASTRA WHITEBOARD
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setFullscreen(!fullscreen)}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {fullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button
            onClick={() => onToggle(false)}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            title="Close whiteboard"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full"
          style={{ imageRendering: "auto" }}
        />
        {!content && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-sm text-gray-400">
              Whiteboard ready — ask me to calculate something
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
