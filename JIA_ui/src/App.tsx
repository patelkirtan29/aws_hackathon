import { useEffect, useMemo, useRef, useState } from "react";
import "./app.css";

type JobResearchResponse = {
  ok: boolean;
  company: string;
  role: string;
  output: string;
  saved_file?: string | null;
};

type ScanInboxResponse = {
  ok: boolean;
  dry_run: boolean;
  output: string;
};

const API_BASE = "http://127.0.0.1:8000";

/** Pieces of text that may include clickable links */
type LinkPart = string | { href: string; label: string };

function linkifyText(text: string): LinkPart[] {
  // Matches http(s) URLs + "www." URLs
  const urlRegex = /(https?:\/\/[^\s)]+)|(\bwww\.[^\s)]+)/g;

  const parts: LinkPart[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(urlRegex)) {
    const m = match[0];
    const start = match.index ?? 0;

    if (start > lastIndex) {
      parts.push(text.slice(lastIndex, start));
    }

    const href = m.startsWith("http") ? m : `https://${m}`;
    parts.push({ href, label: m });

    lastIndex = start + m.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

/**
 * Backend returns CLI transcript; UI should show only the brief.
 * Remove noisy CLI prompts / separators that look ugly in UI.
 */
function stripCliNoise(raw: string): string {
  if (!raw) return "";

  const lines = raw.replace(/\r\n/g, "\n").split("\n");

  const cleaned = lines.filter((line) => {
    const s = line.trim();

    // drop empty at start/end later; keep internal spacing
    // remove prompts
    if (s.startsWith("Choose mode:")) return false;
    if (s.startsWith("Company:")) return false;
    if (s.startsWith("Role:")) return false;

    // remove "complete" banners from CLI
    if (s === "JOB RESEARCH COMPLETE") return false;
    if (s.includes("JOB RESEARCH COMPLETE")) return false;
    if (s === "Bye 👋") return false;

    // remove heavy separator lines (==== and similar)
    if (/^=+$/.test(s)) return false;

    return true;
  });

  // Remove leading/trailing blank lines
  let out = cleaned.join("\n").trim();

  // If backend still includes the CLI header above the actual brief,
  // try to cut from "RECENT JOB BRIEF" onward when present.
  const idx = out.indexOf("RECENT JOB BRIEF");
  if (idx >= 0) out = out.slice(idx).trim();

  return out;
}

function Chip({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "ok" | "warn";
}) {
  return <span className={`chip chip-${tone}`}>{label}</span>;
}

function Tabs({
  active,
  setActive,
}: {
  active: "job" | "scan";
  setActive: (t: "job" | "scan") => void;
}) {
  return (
    <div className="tabs">
      <button
        className={active === "job" ? "tab active" : "tab"}
        onClick={() => setActive("job")}
        type="button"
      >
        Job Research
      </button>
      <button
        className={active === "scan" ? "tab active" : "tab"}
        onClick={() => setActive("scan")}
        type="button"
      >
        Inbox → Calendar
      </button>
    </div>
  );
}

function OutputPanel({
  title,
  output,
  downloadFile,
  rightActions,
}: {
  title: string;
  output: string;
  downloadFile?: string | null;
  rightActions?: React.ReactNode;
}) {
  const pretty = stripCliNoise(output || "");
  const show = pretty || "—";

  return (
    <div className="card card-big">
      <div className="cardHeader">
        <div className="cardHeaderLeft">
          <h2 className="cardTitle">{title}</h2>
          <span className="cardHint">Links become clickable automatically</span>
        </div>

        <div className="cardHeaderRight">
          {downloadFile ? (
            <a
              className="btn btn-ghost"
              href={`${API_BASE}/api/download?file=${encodeURIComponent(downloadFile)}`}
              target="_blank"
              rel="noreferrer"
            >
              Download
            </a>
          ) : null}

          {rightActions}
        </div>
      </div>

      <div className="terminal">
        {linkifyText(show).map((part, i) =>
          typeof part === "string" ? (
            <span key={i}>{part}</span>
          ) : (
            <a
              key={i}
              href={part.href}
              target="_blank"
              rel="noreferrer"
              className="linkOut"
            >
              {part.label}
            </a>
          )
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState<"job" | "scan">("job");

  // Job Research form
  const [company, setCompany] = useState("amazon");
  const [role, setRole] = useState("software engineer");
  const [autoRun, setAutoRun] = useState(false);

  const [jobLoading, setJobLoading] = useState(false);
  const [jobRes, setJobRes] = useState<JobResearchResponse | null>(null);
  const [jobErr, setJobErr] = useState<string | null>(null);

  // Scan form
  const [dryRun, setDryRun] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanRes, setScanRes] = useState<ScanInboxResponse | null>(null);
  const [scanErr, setScanErr] = useState<string | null>(null);

  const canRunJob = useMemo(
    () => company.trim().length > 0 && role.trim().length > 0,
    [company, role]
  );

  const status = useMemo(() => {
    if (jobLoading || scanLoading) return { label: "Running", tone: "warn" as const };
    if (jobErr || scanErr) return { label: "Error", tone: "warn" as const };
    return { label: "Ready", tone: "ok" as const };
  }, [jobLoading, scanLoading, jobErr, scanErr]);

  async function runJobResearch() {
    if (!canRunJob || jobLoading) return;

    setJobErr(null);
    setJobRes(null);
    setJobLoading(true);

    try {
      const r = await fetch(`${API_BASE}/api/job-research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company, role }),
      });

      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || `HTTP ${r.status}`);
      }

      const data = (await r.json()) as JobResearchResponse;
      setJobRes(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setJobErr(msg);
    } finally {
      setJobLoading(false);
    }
  }

  async function runScan() {
    if (scanLoading) return;

    setScanErr(null);
    setScanRes(null);
    setScanLoading(true);

    try {
      const r = await fetch(`${API_BASE}/api/scan-inbox`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dry_run: dryRun }),
      });

      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || `HTTP ${r.status}`);
      }

      const data = (await r.json()) as ScanInboxResponse;
      setScanRes(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setScanErr(msg);
    } finally {
      setScanLoading(false);
    }
  }

  function onEnterRun(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") runJobResearch();
  }

  // Optional auto-run: debounce after typing stops
  const debounceRef = useRef<number | null>(null);
  useEffect(() => {
    if (!autoRun) return;
    if (!canRunJob) return;

    // debounce 600ms
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      runJobResearch();
    }, 600);

    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun, company, role, canRunJob]);

  const jobOutput = jobRes?.output ?? "";
  const scanOutput = scanRes?.output ?? "";

  return (
    <div className="appShell">
      <div className="bgGlow" />

      <header className="topbar">
        <div className="brand brand-center">
          <div className="brandTitle">Job Intelligence Agent</div>
          <div className="brandSub">Research • interview prep • saved brief</div>
        </div>

        <div className="topbarRight">
          <Chip label={status.label} tone={status.tone} />
        </div>
      </header>

{/* <header className="topbar">
  <div className="topbarLeft" />
  <div className="brand-center">
    Job Intelligence Agent
  </div>
  <div className="topbarRight">
  Research • interview prep • saved brief
  </div>
</header> */}
      <div className="content">
        <Tabs active={active} setActive={setActive} />

        {active === "job" ? (
          <section className="layout">
            <div className="card">
              <div className="cardHeader compact">
                <div className="cardHeaderLeft">
                  <h2 className="cardTitle">Research</h2>
                  <span className="cardHint">Press Enter to run</span>
                </div>
              </div>

              <div className="form">
                <div className="fieldRow">
                  <label className="label">Company</label>
                  <input
                    className="input"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    onKeyDown={onEnterRun}
                    placeholder="amazon, netflix, expedia…"
                  />
                </div>

                <div className="fieldRow">
                  <label className="label">Role</label>
                  <input
                    className="input"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    onKeyDown={onEnterRun}
                    placeholder="software engineer, data engineer…"
                  />
                </div>

                <label className="toggleRow">
                  <input
                    type="checkbox"
                    checked={autoRun}
                    onChange={(e) => setAutoRun(e.target.checked)}
                  />
                  <span>Auto-run while typing</span>
                </label>

                <button
                  className="btn btn-primary"
                  disabled={!canRunJob || jobLoading}
                  onClick={runJobResearch}
                  type="button"
                >
                  {jobLoading ? "Running…" : "Run research"}
                </button>

                {jobErr ? <div className="errorBox">{jobErr}</div> : null}
              </div>
            </div>

            <OutputPanel
              title="Brief"
              output={jobOutput}
              downloadFile={jobRes?.saved_file ?? null}
              rightActions={
                <button
                  className="btn btn-ghost"
                  type="button"
                  onClick={() => setJobRes(null)}
                  disabled={!jobRes && !jobErr}
                >
                  Clear
                </button>
              }
            />
          </section>
        ) : (
          <section className="layout">
            <div className="card">
              <div className="cardHeader compact">
                <div className="cardHeaderLeft">
                  <h2 className="cardTitle">Inbox → Calendar</h2>
                  <span className="cardHint">Summarize interview emails</span>
                </div>
              </div>

              <div className="form">
                <label className="toggleRow">
                  <input
                    type="checkbox"
                    checked={dryRun}
                    onChange={(e) => setDryRun(e.target.checked)}
                  />
                  <span>Dry run (don’t create events)</span>
                </label>

                <button
                  className="btn btn-primary"
                  disabled={scanLoading}
                  onClick={runScan}
                  type="button"
                >
                  {scanLoading ? "Scanning…" : "Run scan"}
                </button>

                {scanErr ? <div className="errorBox">{scanErr}</div> : null}
              </div>
            </div>

            <OutputPanel
              title="Summary"
              output={scanOutput}
              rightActions={
                <button
                  className="btn btn-ghost"
                  type="button"
                  onClick={() => setScanRes(null)}
                  disabled={!scanRes && !scanErr}
                >
                  Clear
                </button>
              }
            />
          </section>
        )}
      </div>

      <footer className="footer">
        <span>Tip: Enter runs research • links are clickable • download saves the brief</span>
      </footer>
    </div>
  );
}
