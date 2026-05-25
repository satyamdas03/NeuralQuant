"use client";

import { Component, useState, useEffect, useCallback, useRef } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useDataChannel,
  useIsSpeaking,
  useLocalParticipant,
  useRemoteParticipants,
  useTracks,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import "@livekit/components-styles";
import QuantAstraStatusBar from "./QuantAstraStatusBar";
import QuantAstraTranscriptPanel from "./QuantAstraTranscriptPanel";
import QuantAstraFace from "./QuantAstraFace";
import QuantAstraDataPanel from "./QuantAstraDataPanel";
import QuantAstraWhiteboard from "./QuantAstraWhiteboard";
import { useSessionTracker } from "@/lib/session-tracker";

class CallErrorBoundary extends Component<
  { children: React.ReactNode; onRetry: () => void },
  { hasError: boolean; errorMessage: string }
> {
  constructor(props: { children: React.ReactNode; onRetry: () => void }) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("QuantAstra CallErrorBoundary caught:", error.message, error.stack, errorInfo.componentStack);
    this.setState({ errorMessage: error.message });
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
          <p className="text-sm text-on-surface-variant text-center">
            Connection interrupted. The agent may be restarting.
          </p>
          {this.state.errorMessage && (
            <p className="max-w-xs text-xs text-error/70 text-center font-mono break-all">
              {this.state.errorMessage}
            </p>
          )}
          <button
            onClick={this.props.onRetry}
            className="rounded-full bg-primary-fixed px-4 py-2 text-sm font-semibold text-background"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

type AgentState = "initializing" | "idle" | "listening" | "thinking" | "speaking";

interface TranscriptLine {
  text: string;
  source: "agent" | "user";
  final: boolean;
  timestamp: number;
}

interface ToolResult {
  tool: string;
  result: Record<string, unknown>;
}

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

type QuantAstraCallViewProps = {
  token: string;
  serverUrl: string;
  onDisconnected?: () => void;
};

function QuantAstraCallInner() {
  const { logActivity } = useSessionTracker();
  const [agentState, setAgentState] = useState<AgentState>("initializing");
  const [transcriptLines, setTranscriptLines] = useState<TranscriptLine[]>([]);
  const [toolResults, setToolResults] = useState<ToolResult[]>([]);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [agentTimeout, setAgentTimeout] = useState(false);
  const [whiteboardOpen, setWhiteboardOpen] = useState(false);
  const [whiteboardContent, setWhiteboardContent] = useState<WhiteboardContent | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Detect agent speaking from audio tracks
  const remoteParticipants = useRemoteParticipants();
  const localParticipant = useLocalParticipant();
  const agentParticipant = remoteParticipants[0];
  // useIsSpeaking throws if passed undefined — fall back to local participant
  // (local won't report agent audio, so isSpeaking stays false until agent joins)
  const isSpeaking = useIsSpeaking(agentParticipant ?? localParticipant.localParticipant);

  // Clear agent timeout when remote participant appears
  useEffect(() => {
    if (agentParticipant && timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, [agentParticipant]);

  // Set agent join timeout — 15s
  useEffect(() => {
    timerRef.current = setTimeout(() => {
      if (!agentParticipant) {
        setAgentTimeout(true);
      }
    }, 15000);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const tracks = useTracks(
    [Track.Source.Microphone],
    { onlySubscribed: true }
  );
  const agentAudioTrack = tracks.find(
    (t) => t.participant.identity !== localParticipant.localParticipant?.identity
  );

  // Listen for data channel messages from agent
  useDataChannel(
    "quantastra",
    useCallback((msg: { payload: Uint8Array }) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(msg.payload));
        switch (data.type) {
          case "agent_state":
            setAgentState(data.state as AgentState);
            break;
          case "agent_transcript":
            setAgentSpeaking(true);
            setTranscriptLines((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.source === "agent" && !last.final && !data.final) {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  text: last.text + data.text,
                  source: "agent",
                  final: false,
                  timestamp: Date.now(),
                };
                return updated;
              }
              return [
                ...prev,
                {
                  text: data.text,
                  source: "agent",
                  final: data.final || false,
                  timestamp: Date.now(),
                },
              ];
            });
            if (data.final) {
              setTimeout(() => setAgentSpeaking(false), 2000);
            }
            break;
          case "user_transcript":
            logActivity("quantastra_user_speech", "conversation", data.text?.slice(0, 200), {
              text: data.text,
              is_final: data.is_final,
            });
            setTranscriptLines((prev) => [
              ...prev,
              {
                text: data.text,
                source: "user",
                final: data.is_final || true,
                timestamp: Date.now(),
              },
            ]);
            break;
          case "tool_results":
            if (Array.isArray(data.data)) {
              for (const tr of data.data) {
                logActivity("quantastra_tool_used", "analysis", `Agent used: ${tr.tool}`, {
                  tool: tr.tool,
                });
              }
              setToolResults((prev) => [...prev, ...data.data]);
            }
            break;
          case "whiteboard_update":
            if (data.action === "show") {
              logActivity("quantastra_whiteboard", "feature", data.content?.title || "Calculation shown", {
                title: data.content?.title,
                result: data.content?.result,
              });
              setWhiteboardContent(data.content as WhiteboardContent);
              setWhiteboardOpen(true);
            } else if (data.action === "close") {
              setWhiteboardOpen(false);
              setWhiteboardContent(null);
            }
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    }, [logActivity]),
  );

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcriptLines]);

  // Sync speaking state from audio
  useEffect(() => {
    if (isSpeaking) setAgentSpeaking(true);
  }, [isSpeaking]);

  // File upload handler — read file as base64 and send via data channel
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !localParticipant.localParticipant) return;
    setUploading(true);
    try {
      const bytes = await file.arrayBuffer();
      const chunkSize = 0x8000; // 32KB chunks to avoid stack overflow
      const uint8 = new Uint8Array(bytes);
      let base64 = "";
      for (let i = 0; i < uint8.length; i += chunkSize) {
        const chunk = uint8.subarray(i, i + chunkSize);
        base64 += String.fromCharCode.apply(null, Array.from(chunk));
      }
      base64 = btoa(base64);
      const payload = new TextEncoder().encode(JSON.stringify({
        type: "file_upload",
        file_name: file.name,
        mime_type: file.type || "application/octet-stream",
        data_b64: base64,
        size: file.size,
      }));
      await localParticipant.localParticipant.publishData(payload, {
        reliable: true,
        topic: "quantastra",
      });
      logActivity("quantastra_file_upload", "feature", `Uploaded: ${file.name}`, {
        file_name: file.name,
        mime_type: file.type,
        size: file.size,
      });
    } catch (err) {
      console.error("File upload failed:", err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [localParticipant.localParticipant, logActivity]);

  return (
    <div className="flex h-full flex-col">
      {/* Agent face + status area */}
      <div className="flex flex-col items-center py-6">
        <QuantAstraFace
          agentState={agentState}
          isSpeaking={agentSpeaking || isSpeaking}
          audioTrack={agentAudioTrack}
        />
        <div className="mt-4">
          <QuantAstraStatusBar state={agentTimeout && !agentParticipant ? "initializing" : agentState} />
        </div>
        {agentTimeout && !agentParticipant && (
          <p className="mt-3 max-w-xs text-center text-xs text-amber-400">
            Agent is taking longer than expected to join. The worker may be deploying — try again in a minute.
          </p>
        )}
        {/* Whiteboard + Upload toggles */}
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setWhiteboardOpen(!whiteboardOpen)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              whiteboardOpen
                ? "bg-primary-fixed/20 text-primary-fixed"
                : "bg-ghost-border/30 text-on-surface-variant hover:text-on-surface"
            }`}
            title="Toggle whiteboard for calculations"
          >
            {whiteboardOpen ? "Hide Whiteboard" : "Whiteboard"}
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="rounded-full bg-ghost-border/30 px-3 py-1 text-xs font-medium text-on-surface-variant transition-colors hover:text-on-surface disabled:opacity-50"
            title="Upload a file for QuantAstra to analyze"
          >
            {uploading ? "Uploading..." : "Upload File"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileUpload}
            className="hidden"
            accept="image/*,.pdf,.csv,.txt,.json,.html,.xml,.md"
          />
        </div>
      </div>

      {/* Whiteboard panel (when open, replaces transcript+data split) */}
      {whiteboardOpen ? (
        <div className="flex-1 overflow-hidden border-t border-ghost-border">
          <QuantAstraWhiteboard
            content={whiteboardContent}
            isOpen={whiteboardOpen}
            onToggle={setWhiteboardOpen}
          />
        </div>
      ) : (
        /* Transcript + Data side-by-side */
        <div className="flex flex-1 flex-col sm:flex-row gap-0 overflow-hidden border-t border-ghost-border">
          <div className="flex-1 overflow-hidden">
            <QuantAstraTranscriptPanel
              lines={transcriptLines}
              endRef={transcriptEndRef}
            />
          </div>
          {toolResults.length > 0 && (
            <div className="w-full sm:w-64 lg:w-72 shrink-0 border-t sm:border-t-0 sm:border-l border-ghost-border">
              <QuantAstraDataPanel results={toolResults} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function QuantAstraCallView({
  token,
  serverUrl,
  onDisconnected,
}: QuantAstraCallViewProps) {
  const [retryKey, setRetryKey] = useState(0);

  const handleDisconnected = useCallback(() => {
    onDisconnected?.();
  }, [onDisconnected]);

  const handleRetry = useCallback(() => {
    setRetryKey((k) => k + 1);
  }, []);

  if (!token) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-on-surface-variant">
          Unable to connect — LiveKit token is missing. Please try again.
        </p>
      </div>
    );
  }

  if (!serverUrl) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-on-surface-variant">
          Unable to connect — LiveKit server URL is missing. Please try again.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg h-[70vh] sm:h-[500px] lg:h-[560px]">
      <CallErrorBoundary key={retryKey} onRetry={handleRetry}>
        <LiveKitRoom
          token={token}
          serverUrl={serverUrl}
          connect={true}
          audio={true}
          onDisconnected={handleDisconnected}
          className="h-full w-full quantastra-call"
          style={
            {
              "--lk-control-bg": "rgba(13,20,37,0.85)",
              "--lk-control-fg": "#47ffb8",
              "--lk-control-hover-bg": "rgba(71,255,184,0.15)",
              "--lk-fg": "#e0e0e0",
              "--lk-bg": "rgba(13,20,37,0.95)",
              "--lk-border-color": "rgba(71,255,184,0.15)",
              "--lk-accent": "#47ffb8",
            } as React.CSSProperties
          }
        >
          <QuantAstraCallInner />
          <RoomAudioRenderer />
        </LiveKitRoom>
      </CallErrorBoundary>
    </div>
  );
}
