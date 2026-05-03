"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff } from "lucide-react";

type Props = {
  onSubmit: (text: string) => void;
  placeholder?: string;
  disabled?: boolean;
};

export default function ChatInputArea({
  onSubmit,
  placeholder = "Ask about any stock...",
  disabled = false,
}: Props) {
  const [text, setText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setVoiceSupported(!!SR);
  }, []);

  const startListening = () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setText(transcript);
      setIsListening(false);
      setTimeout(() => {
        if (transcript.trim()) onSubmit(transcript.trim());
      }, 300);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSubmit(text.trim());
    setText("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2 flex-1">
      <div className="flex-1 rounded-xl bg-surface-high ghost-border px-4 py-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="w-full resize-none bg-transparent text-sm text-on-surface outline-none placeholder:text-on-surface-variant"
        />
      </div>
      {voiceSupported && (
        <button
          type="button"
          onClick={isListening ? stopListening : startListening}
          disabled={disabled}
          className={`press-scale flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
            isListening
              ? "bg-red-500/20 text-red-400 animate-pulse ghost-border"
              : "bg-surface-high text-on-surface-variant hover:text-on-surface ghost-border"
          }`}
          title={isListening ? "Stop listening" : "Voice input"}
        >
          {isListening ? <MicOff size={16} /> : <Mic size={16} />}
        </button>
      )}
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="gradient-cta press-scale flex h-10 w-10 items-center justify-center rounded-xl disabled:opacity-40"
      >
        <Send size={16} className="text-on-primary-container" />
      </button>
    </form>
  );
}