import { Heart } from "lucide-react";

const SymptaraLogo = ({ size = "default" }: { size?: "default" | "small" }) => {
  const iconSize = size === "small" ? 20 : 28;
  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <Heart
          size={iconSize}
          className="text-primary fill-primary animate-heartbeat"
        />
      </div>
      <span className={`font-display font-bold tracking-tight ${size === "small" ? "text-lg" : "text-2xl"}`}>
        <span className="text-foreground">Symp</span>
        <span className="gradient-text">tara</span>
      </span>
    </div>
  );
};

export default SymptaraLogo;
