"use client";

import { useState, useEffect, useCallback } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoConference,
} from "@livekit/components-react";
import "@livekit/components-styles";

type QuantAstraCallViewProps = {
  token: string;
  serverUrl: string;
  onDisconnected?: () => void;
};

export default function QuantAstraCallView({
  token,
  serverUrl,
  onDisconnected,
}: QuantAstraCallViewProps) {
  const [videoEnabled, setVideoEnabled] = useState(true);

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
    <div className="overflow-hidden rounded-lg" style={{ height: 480 }}>
      <LiveKitRoom
        token={token}
        serverUrl={serverUrl}
        connect={true}
        video={videoEnabled}
        audio={true}
        onDisconnected={handleDisconnected}
        className="h-full w-full"
      >
        <VideoConference />
        <RoomAudioRenderer />
      </LiveKitRoom>
    </div>
  );
}
