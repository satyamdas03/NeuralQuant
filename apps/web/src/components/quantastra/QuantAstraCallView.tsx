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

class CallErrorBoundary extends Component<
  { children: React.ReactNode; onRetry: () => void },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode; onRetry: () => void }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
          <p className="text-sm text-on-surface-variant text-center">
            Connection interrupted. The agent may be restarting.
          </p>
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

type QuantAstraCallViewProps = {
  token: string;
  serverUrl: string;
  onDisconnected?: () => void;
};

function QuantAstraCallInner(_props: { onDisconnected?: () => void }) {
  const [agentState, setAgentState] = useState<AgentState>("initializing");
  const [transcriptLines, setTranscriptLines] = useState<TranscriptLine[]>([]);
  const [toolResults, setToolResults] = useState<ToolResult[]>([]);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [agentTimeout, setAgentTimeout] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Detect agent speaking from audio tracks
  const remoteParticipants = useRemoteParticipants();
  const localParticipant = useLocalParticipant();
  const agentParticipant = remoteParticipants[0];
  const isSpeaking = useIsSpeaking(agentParticipant);

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
              setToolResults((prev) => [...prev, ...data.data]);
            }
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    }, []),
  );

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcriptLines]);

  // Sync speaking state from audio
  useEffect(() => {
    if (isSpeaking) setAgentSpeaking(true);
  }, [isSpeaking]);

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
      </div>

      {/* Transcript + Data side-by-side */}
      <div className="flex flex-1 gap-0 overflow-hidden border-t border-ghost-border">
        <div className="flex-1 overflow-hidden">
          <QuantAstraTranscriptPanel
            lines={transcriptLines}
            endRef={transcriptEndRef}
          />
        </div>
        {toolResults.length > 0 && (
          <div className="w-72 shrink-0 border-l border-ghost-border">
            <QuantAstraDataPanel results={toolResults} />
          </div>
        )}
      </div>
    </div>
  );
}

export default function QuantAstraCallView({
  token,
  serverUrl,
  onDisconnected,
}: QuantAstraCallViewProps) {
  const handleDisconnected = useCallback(() => {
    onDisconnected?.();
  }, [onDisconnected]);

  if (!token) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-on-surface-variant">
          Unable to connect — LiveKit token is missing. Please try again.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg" style={{ height: 560 }}>
      <CallErrorBoundary onRetry={handleDisconnected}>
        <LiveKitRoom
          token={token}
          serverUrl={serverUrl}
          connect={true}
          video={false}
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
          <QuantAstraCallInner onDisconnected={onDisconnected} />
          <RoomAudioRenderer />
        </LiveKitRoom>
      </CallErrorBoundary>
    </div>
  );
}
