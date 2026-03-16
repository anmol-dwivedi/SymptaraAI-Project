import { motion } from "framer-motion";
import { Star, ExternalLink, ChevronDown, ChevronUp, FileText, AlertTriangle, BookOpen, Stethoscope, Pill, FlaskConical, MapPin, TestTubes } from "lucide-react";
import { useState } from "react";
import type { ResultsData } from "@/types/consultation";

const sectionAnim = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4 },
};

const Section = ({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) => (
  <motion.div {...sectionAnim} className="mb-6">
    <h3 className="mb-3 flex items-center gap-2 font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
      {icon}
      {title}
    </h3>
    {children}
  </motion.div>
);

const ConfidenceBadge = ({ level }: { level: string }) => {
  const colors: Record<string, string> = {
    High: "bg-success/15 text-success border-success/30",
    Medium: "bg-warning/15 text-warning border-warning/30",
    Low: "bg-destructive/15 text-destructive border-destructive/30",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${colors[level] || colors.Low}`}>
      {level}
    </span>
  );
};

const PriorityBadge = ({ priority }: { priority: string }) => {
  const colors: Record<string, string> = {
    STAT: "bg-destructive/15 text-destructive border-destructive/30",
    Urgent: "bg-warning/15 text-warning border-warning/30",
    Routine: "bg-primary/15 text-primary border-primary/30",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${colors[priority] || colors.Routine}`}>
      {priority}
    </span>
  );
};

const SeverityBadge = ({ severity }: { severity: string }) => {
  const colors: Record<string, string> = {
    high: "bg-destructive/15 text-destructive border-destructive/30",
    moderate: "bg-warning/15 text-warning border-warning/30",
    low: "bg-warning/10 text-yellow-400 border-yellow-400/30",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${colors[severity] || colors.low}`}>
      {severity}
    </span>
  );
};

const ResultsDashboard = ({ results }: { results: ResultsData }) => {
  const [guidelineOpen, setGuidelineOpen] = useState<number | null>(null);
  const hasAny = results.diagnoses.length || results.tests.length || results.medications.length ||
    results.interactions.length || results.doctors.length || results.pubmed.length ||
    results.guidelines.length || results.fileAnalysis;

  if (!hasAny) return null;

  return (
    <div className="space-y-2">
      {/* Diagnoses */}
      {results.diagnoses.length > 0 && (
        <Section title="Differential Diagnoses" icon={<Stethoscope size={14} />}>
          <div className="grid gap-2">
            {results.diagnoses.map((d, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-border bg-card p-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{d.disease}</p>
                  {d.description && <p className="mt-0.5 text-xs text-muted-foreground">{d.description}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{typeof d.match_score === "number" ? `${(d.match_score * 100).toFixed(0)}%` : ""}</span>
                  <ConfidenceBadge level={d.confidence} />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Tests */}
      {results.tests.length > 0 && (
        <Section title="Confirmatory Tests" icon={<TestTubes size={14} />}>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Priority</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Test</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Purpose</th>
                </tr>
              </thead>
              <tbody>
                {results.tests.map((t, i) => (
                  <tr key={i} className="border-b border-border/50 last:border-0">
                    <td className="px-3 py-2"><PriorityBadge priority={t.priority} /></td>
                    <td className="px-3 py-2 text-foreground">{t.test_name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{t.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Medications */}
      {results.medications.length > 0 && (
        <Section title="Medications" icon={<Pill size={14} />}>
          <div className="grid gap-2">
            {results.medications.map((m, i) => (
              <div key={i} className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-foreground">{m.drug_name}</p>
                  {m.source && (
                    <span className="rounded-full bg-primary/10 border border-primary/20 px-2 py-0.5 text-[10px] text-primary">{m.source}</span>
                  )}
                </div>
                {m.indication && <p className="mt-1 text-xs text-muted-foreground">{m.indication}</p>}
                {m.warnings && m.warnings.length > 0 && (
                  <div className="mt-2 rounded-md bg-warning/5 border border-warning/20 p-2">
                    {m.warnings.map((w, j) => (
                      <p key={j} className="text-xs text-warning flex items-start gap-1">
                        <AlertTriangle size={10} className="mt-0.5 shrink-0" />
                        {w}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Drug Interactions */}
      {results.interactions.length > 0 && (
        <Section title="Drug Interactions" icon={<AlertTriangle size={14} />}>
          <div className="grid gap-2">
            {results.interactions.map((inter, i) => (
              <div key={i} className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-medium text-foreground">{inter.drug1} ↔ {inter.drug2}</p>
                  <SeverityBadge severity={inter.severity} />
                </div>
                <p className="text-xs text-muted-foreground">{inter.description}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Doctors */}
      {results.doctors.length > 0 && (
        <Section title={`Nearby ${results.specialistType || "Doctors"}`} icon={<MapPin size={14} />}>
          <div className="grid gap-2">
            {results.doctors.map((doc, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-border bg-card p-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">{doc.address}</p>
                  <div className="mt-1 flex items-center gap-0.5">
                    {Array.from({ length: 5 }).map((_, s) => (
                      <Star key={s} size={12} className={s < Math.round(doc.rating) ? "fill-warning text-warning" : "text-border"} />
                    ))}
                    <span className="ml-1 text-xs text-muted-foreground">{doc.rating}</span>
                  </div>
                </div>
                {doc.maps_link && (
                  <a href={doc.maps_link} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1 rounded-md bg-primary/10 px-3 py-1.5 text-xs text-primary hover:bg-primary/20 transition-colors">
                    <MapPin size={12} /> Map
                    <ExternalLink size={10} />
                  </a>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* PubMed */}
      {results.pubmed.length > 0 && (
        <Section title="PubMed References" icon={<BookOpen size={14} />}>
          <div className="space-y-2">
            {results.pubmed.map((p, i) => (
              <div key={i} className="rounded-lg border border-border bg-card p-3">
                <a href={p.link} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-primary hover:underline">
                  {p.title}
                </a>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {p.authors?.slice(0, 3).join(", ")}{p.authors?.length > 3 ? " et al." : ""} — {p.journal} ({p.year})
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Guidelines */}
      {results.guidelines.length > 0 && (
        <Section title="Clinical Guidelines" icon={<FlaskConical size={14} />}>
          <div className="space-y-2">
            {results.guidelines.map((g, i) => (
              <div key={i} className="rounded-lg border border-border bg-card">
                <button
                  onClick={() => setGuidelineOpen(guidelineOpen === i ? null : i)}
                  className="flex w-full items-center justify-between p-3 text-left"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{g.title}</p>
                    <span className="mt-0.5 inline-flex rounded-full bg-secondary/10 border border-secondary/20 px-2 py-0.5 text-[10px] text-secondary">
                      {g.source}
                    </span>
                  </div>
                  {guidelineOpen === i ? <ChevronUp size={14} className="text-muted-foreground" /> : <ChevronDown size={14} className="text-muted-foreground" />}
                </button>
                {guidelineOpen === i && (
                  <div className="border-t border-border px-3 py-3 text-xs text-muted-foreground whitespace-pre-wrap">
                    {g.content}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* File Analysis */}
      {results.fileAnalysis && (
        <Section title="Uploaded File Analysis" icon={<FileText size={14} />}>
          <div className="rounded-lg border border-border bg-card p-3 text-sm text-muted-foreground whitespace-pre-wrap">
            {results.fileAnalysis}
          </div>
        </Section>
      )}
    </div>
  );
};

export default ResultsDashboard;
