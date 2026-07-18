"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loader2, Sparkles, Search, Brain, Pencil, CheckCircle, Copy, Check } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type AgentStatus = { agent: string; message: string };
type ResearchData = {
  company_name: string;
  recent_news: string[];
  tech_stack: string[];
  pain_points: string[];
  key_urls: string[];
};
type EmailData = { subject_line: string; email_body: string; personalization_hook: string };
type Result = { research: ResearchData; email: EmailData };
type Phase = "idle" | "running" | "done" | "error";

const agentIcon = (name: string) => {
  if (name === "Researcher") return <Search className="h-4 w-4" />;
  if (name === "Analyst") return <Brain className="h-4 w-4" />;
  return <Pencil className="h-4 w-4" />;
};

export default function Home() {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [offering, setOffering] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [statuses, setStatuses] = useState<AgentStatus[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const isDone = useRef(false); // ref avoids stale closure in SSE handlers

  async function handleGenerate() {
    if (!company || !role || !offering) return;
    isDone.current = false;
    setPhase("running");
    setStatuses([]);
    setResult(null);
    setError("");

    // Step 1: start the crew job
    const res = await fetch(`${API}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, target_role: role, your_offering: offering }),
    });
    const { job_id } = await res.json();

    // Step 2: subscribe to SSE stream
    const es = new EventSource(`${API}/stream/${job_id}`);

    es.addEventListener("status", (e) => {
      const data: AgentStatus = JSON.parse(e.data);
      setStatuses((prev) => [...prev, data]);
    });

    es.addEventListener("result", (e) => {
      isDone.current = true;
      setResult(JSON.parse(e.data));
      setPhase("done");
      es.close();
    });

    es.addEventListener("error", (e) => {
      isDone.current = true;
      setError((e as MessageEvent).data ?? "Something went wrong.");
      setPhase("error");
      es.close();
    });

    // onerror fires on transient drops — only treat as fatal if we never got a result
    es.onerror = () => {
      if (!isDone.current) {
        setError("Connection lost. Please try again.");
        setPhase("error");
        es.close();
      }
    };
  }

  function copyEmail() {
    if (!result) return;
    navigator.clipboard.writeText(`Subject: ${result.email.subject_line}\n\n${result.email.email_body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-3">
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="font-semibold tracking-tight text-foreground">Outreach Engine</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* ── Left Column: Input Panel ── */}
        <div className="lg:col-span-1 space-y-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Cold Email Generator</h1>
            <p className="text-sm text-muted-foreground mt-1">
              AI agents research your prospect and write a hyper-personalized email.
            </p>
          </div>

          <Card className="border border-border shadow-sm">
            <CardContent className="pt-6 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="company">Target Company</Label>
                <Input
                  id="company"
                  placeholder="e.g. Stripe, Vercel, Linear"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  disabled={phase === "running"}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Target Role</Label>
                <Input
                  id="role"
                  placeholder="e.g. VP of Engineering"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  disabled={phase === "running"}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="offering">Your Offering</Label>
                <Input
                  id="offering"
                  placeholder="e.g. AI-powered code review tool"
                  value={offering}
                  onChange={(e) => setOffering(e.target.value)}
                  disabled={phase === "running"}
                />
              </div>
              <Button
                className="w-full"
                onClick={handleGenerate}
                disabled={phase === "running" || !company || !role || !offering}
              >
                {phase === "running" ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Agents working...</>
                ) : (
                  <><Sparkles className="mr-2 h-4 w-4" /> Generate Email</>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Agent Tracker */}
          {statuses.length > 0 && (
            <Card className="border border-border shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Live Agent Tracker
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {statuses.map((s, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="mt-0.5 text-primary">{agentIcon(s.agent)}</div>
                    <div>
                      <p className="text-xs font-semibold text-foreground">{s.agent}</p>
                      <p className="text-xs text-muted-foreground">{s.message}</p>
                    </div>
                    {i === statuses.length - 1 && phase === "running" && (
                      <Loader2 className="ml-auto h-3 w-3 animate-spin text-muted-foreground mt-1" />
                    )}
                    {phase === "done" && (
                      <CheckCircle className="ml-auto h-3 w-3 text-green-500 mt-1" />
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-md px-4 py-3 border border-destructive/20">
              {error}
            </p>
          )}
        </div>

        {/* ── Right Columns: Results ── */}
        {result && (
          <div className="lg:col-span-2 space-y-6">

            {/* Prospect Research Card */}
            <Card className="border border-border shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Prospect Research — {result.research.company_name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <Section label="Recent News">
                  <ul className="space-y-1.5">
                    {result.research.recent_news.map((n, i) => (
                      <li key={i} className="text-sm text-foreground flex gap-2">
                        <span className="text-muted-foreground mt-px">–</span> {n}
                      </li>
                    ))}
                  </ul>
                </Section>

                <Section label="Tech Stack">
                  <div className="flex flex-wrap gap-1.5">
                    {result.research.tech_stack.map((t) => (
                      <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                    ))}
                  </div>
                </Section>

                <Section label="Likely Pain Points">
                  <ul className="space-y-1.5">
                    {result.research.pain_points.map((p, i) => (
                      <li key={i} className="text-sm text-foreground flex gap-2">
                        <span className="text-primary mt-px">→</span> {p}
                      </li>
                    ))}
                  </ul>
                </Section>

                <Section label="Key Sources">
                  <div className="space-y-1">
                    {result.research.key_urls.map((url) => (
                      <a
                        key={url}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-xs text-primary hover:underline truncate"
                      >
                        {url}
                      </a>
                    ))}
                  </div>
                </Section>
              </CardContent>
            </Card>

            {/* Email Card */}
            <Card className="border border-border shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Generated Email
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={copyEmail} className="h-8 text-xs gap-1.5">
                  {copied ? <><Check className="h-3.5 w-3.5" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-md bg-muted/50 border border-border px-4 py-3">
                  <p className="text-xs text-muted-foreground mb-1">Subject</p>
                  <p className="text-sm font-semibold text-foreground">{result.email.subject_line}</p>
                </div>
                <div className="rounded-md bg-muted/50 border border-border px-4 py-4">
                  <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">
                    {result.email.email_body}
                  </p>
                </div>
                <div className="flex items-start gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Personalization hook:</span>
                  {result.email.personalization_hook}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Empty state */}
        {phase === "idle" && (
          <div className="lg:col-span-2 flex items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 min-h-64">
            <div className="text-center space-y-2 px-8">
              <Sparkles className="h-8 w-8 text-muted-foreground/40 mx-auto" />
              <p className="text-sm text-muted-foreground">Fill in the form and click Generate.</p>
              <p className="text-xs text-muted-foreground/60">
                Agents will research the company and craft a personalized email.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
      {children}
    </div>
  );
}
