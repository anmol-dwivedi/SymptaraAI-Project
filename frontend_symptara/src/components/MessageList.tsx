import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Heart } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { Message } from "@/types/consultation";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  isPostConclusion: boolean;
}

const TypingIndicator = () => (
  <div className="flex items-start gap-3 px-4 py-2">
    <div className="rounded-lg border-l-2 border-primary bg-card px-4 py-3">
      <div className="flex gap-1.5">
        <span className="h-2 w-2 rounded-full bg-primary animate-typing-1" />
        <span className="h-2 w-2 rounded-full bg-primary animate-typing-2" />
        <span className="h-2 w-2 rounded-full bg-primary animate-typing-3" />
      </div>
    </div>
  </div>
);

const WelcomeMessage = () => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3 }}
    className="flex justify-start"
  >
    <div className="max-w-[85%] rounded-lg border-l-2 border-primary bg-card px-4 py-3 text-sm text-foreground">
      <div className="mb-1.5 flex items-center gap-1.5">
        <Heart size={12} className="text-primary fill-primary" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">Symptara</span>
      </div>
      <p className="text-muted-foreground">
        Welcome to Symptara. Describe your symptoms to begin your consultation, or upload a medical document to get started.
      </p>
    </div>
  </motion.div>
);

const DISCLAIMER = "This is not a medical diagnosis. Please consult a qualified doctor.";

function splitDisclaimer(content: string): { body: string; hasDisclaimer: boolean } {
  const idx = content.indexOf(DISCLAIMER);
  if (idx === -1) return { body: content, hasDisclaimer: false };
  return { body: content.slice(0, idx).trimEnd(), hasDisclaimer: true };
}

const MessageList = ({ messages, isLoading }: MessageListProps) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.length === 0 && !isLoading && <WelcomeMessage />}
      <AnimatePresence initial={false}>
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "user" ? (
              <div className="max-w-[80%] rounded-lg bg-[hsl(270,46%,20%)] px-4 py-2.5 text-sm text-foreground">
                {msg.content}
              </div>
            ) : (
              <div
                className={`max-w-[85%] rounded-lg border-l-2 px-4 py-3 bg-card ${
                  msg.isPostConclusion ? "border-secondary" : "border-primary"
                }`}
              >
                {(() => {
                  const { body, hasDisclaimer } = splitDisclaimer(msg.content);
                  return (
                    <>
                      <div className="prose-symptara">
                        <ReactMarkdown>{body}</ReactMarkdown>
                      </div>
                      {hasDisclaimer && (
                        <span className="prose-symptara-disclaimer">
                          ⚕ {DISCLAIMER}
                        </span>
                      )}
                    </>
                  );
                })()}
              </div>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
      {isLoading && <TypingIndicator />}
      <div ref={endRef} />
    </div>
  );
};

export default MessageList;