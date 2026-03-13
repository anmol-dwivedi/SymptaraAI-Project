import { useState, useRef, useCallback } from "react";
import { Mic, Send, Paperclip } from "lucide-react";

interface ConsultationInputProps {
  onSend: (message: string, inputMethod: "text" | "voice") => void;
  onUpload: (file: File) => void;
  isLoading: boolean;
  isPostConclusion: boolean;
}

const ConsultationInput = ({
  onSend,
  onUpload,
  isLoading,
  isPostConclusion,
}: ConsultationInputProps) => {
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [voiceUsed, setVoiceUsed] = useState(false);
  const recognitionRef = useRef<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed, voiceUsed ? "voice" : "text");
    setInput("");
    setVoiceUsed(false);
  }, [input, isLoading, onSend, voiceUsed]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleRecording = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser.");
      return;
    }

    if (isRecording && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsRecording(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript;
      setInput((prev) => prev + (prev ? " " : "") + transcript);
      setVoiceUsed(true);
      setIsRecording(false);
    };

    recognition.onerror = () => setIsRecording(false);
    recognition.onend = () => setIsRecording(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className={`border-t p-4 ${isPostConclusion ? "border-secondary/30 bg-secondary/5" : "border-border"}`}>
      <div className="flex items-end gap-2">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept=".pdf,.jpg,.jpeg,.png,.webp"
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/50 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
        >
          <Paperclip size={18} />
        </button>

        <div className="relative flex-1">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isPostConclusion ? "Ask follow-up questions..." : "Describe your symptoms..."}
            rows={1}
            className="w-full resize-none rounded-lg border border-border bg-muted/50 px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30 transition-colors"
            style={{ minHeight: "40px", maxHeight: "120px" }}
          />
        </div>

        <div className="relative">
          {isRecording && (
            <div className="absolute inset-0 rounded-full bg-destructive/30 animate-pulse-ring" />
          )}
          <button
            onClick={toggleRecording}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-all ${
              isRecording
                ? "bg-destructive text-destructive-foreground scale-110"
                : "border border-border bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            <Mic size={18} />
          </button>
          {isRecording && (
            <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] text-destructive">
              Listening...
            </span>
          )}
        </div>

        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-all hover:brightness-110 disabled:opacity-30 disabled:hover:brightness-100"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
};

export default ConsultationInput;
