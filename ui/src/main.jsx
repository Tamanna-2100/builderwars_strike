import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  ClipboardList,
  Code2,
  Copy,
  Download,
  ExternalLink,
  FileCheck2,
  FlaskConical,
  FolderCode,
  GitBranch,
  GitPullRequest,
  Layers2,
  Moon,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import logoImg from "./logo.jpeg";
import "./style.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const statItems = [
  { key: "hypotheses", label: "Hypotheses", icon: Layers2, hint: "Identified for review" },
  { key: "verified", label: "Verified", icon: ShieldCheck, hint: "Evidence collected" },
  { key: "fixed", label: "Fixed", icon: FileCheck2, hint: "Patch prepared" },
  { key: "discarded", label: "Discarded", icon: XCircle, hint: "Not confirmed" },
];

function JsonBlock({ value }) {
  return (
    <pre className="code-block">
      {typeof value === "string" ? value : JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}

function Finding({ finding, index, runId, isMock }) {
  const [open, setOpen] = useState(index === 0);
  const [viewMode, setViewMode] = useState("vibe"); // "vibe" (Vibe Coder / Plain English) or "tech" (Developer / Diffs)
  const [tab, setTab] = useState("Evidence");
  const [liveReplay, setLiveReplay] = useState(null);
  const [replaying, setReplaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);
  const [showFixedCode, setShowFixedCode] = useState(false);
  const [applyStatus, setApplyStatus] = useState(null);

  const discarded = finding.verdict === "discarded";
  const diff = finding.patch?.diff || "No patch available.";

  function copyCodeText(text) {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  }

  async function handleApplyFix() {
    if (!runId || isMock) return;
    setApplyStatus("Applying fix to your code...");
    try {
      const res = await fetch(`${API_BASE}/runs/${runId}/apply/${finding.id}`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setApplyStatus("✅ Fix applied directly to target/app.py!");
        setTimeout(() => setApplyStatus(null), 4000);
      } else {
        setApplyStatus(data.detail || "Could not apply fix automatically.");
      }
    } catch {
      setApplyStatus("Error applying fix.");
    }
  }

  const explainObj =
    typeof finding.explain === "object" && finding.explain !== null
      ? finding.explain
      : {
          story:
            finding.explain ||
            "Users could peek at other people's private data by changing the ID number in the link.",
          why_it_matters:
            "Any user who logs into your app can see private customer data and confidential files belonging to other accounts.",
          mistake_pattern:
            "The code fetched the record by number, but forgot to check whether the logged-in user actually owns it.",
          prevention_rule:
            "We added a security lock: if the record doesn't belong to the logged-in user, the app blocks it with an 'Access Denied' error.",
          ai_prompt:
            "When writing an endpoint that loads a user record by ID, always verify record['user_id'] == current_user()['id'] and return 403 Forbidden if not authorized.",
        };

  function copyPrompt(text) {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function triggerLiveReplay() {
    if (!runId || isMock) return;
    setReplaying(true);
    try {
      const res = await fetch(`${API_BASE}/runs/${runId}/replay/${finding.id}`);
      if (!res.ok) throw new Error("Replay failed");
      const data = await res.json();
      setLiveReplay(data);
    } catch {
      setLiveReplay({ error: "Could not run live replay. Check that backend is running." });
    } finally {
      setReplaying(false);
    }
  }

  return (
    <article className={`finding ${open ? "finding-open" : ""}`}>
      <button className="finding-header" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={`finding-icon ${discarded ? "muted-icon" : ""}`}>
          {discarded ? <X size={15} /> : <ShieldCheck size={16} />}
        </span>
        <span className="finding-title-wrap">
          <span className="finding-id">{finding.id}</span>
          <span className="finding-title">{finding.title}</span>
        </span>
        {finding.severity && (
          <span
            className="badge"
            style={{
              marginRight: "8px",
              textTransform: "uppercase",
              fontSize: "11px",
              opacity: 0.85,
            }}
          >
            {finding.severity}
          </span>
        )}
        <span className={`badge ${discarded ? "badge-discarded" : "badge-confirmed"}`}>
          <span className="badge-dot" />
          {discarded ? "Discarded" : finding.verdict || "Confirmed"}
        </span>
        <ChevronDown size={17} className={`chevron ${open ? "rotated" : ""}`} />
      </button>

      {open && (
        <div className="finding-content">
          <div className="view-toggle" style={{ margin: "14px 19px 10px" }}>
            <button
              type="button"
              aria-pressed={viewMode === "vibe"}
              onClick={() => setViewMode("vibe")}
            >
              <Sparkles size={13} style={{ display: "inline", marginRight: "6px" }} />
              Vibe Coder / Plain English
            </button>
            <button
              type="button"
              aria-pressed={viewMode === "tech"}
              onClick={() => setViewMode("tech")}
            >
              <Code2 size={13} style={{ display: "inline", marginRight: "6px" }} />
              Developer / Technical (Diffs & Pytest)
            </button>
          </div>

          {!discarded && (
            <div
              style={{
                display: "flex",
                gap: "10px",
                alignItems: "center",
                flexWrap: "wrap",
                margin: "10px 19px 4px",
                padding: "12px 14px",
                borderRadius: "6px",
                background: "var(--bg-pill)",
                border: "1px solid var(--border-pill)",
              }}
            >
              <span style={{ color: "var(--brand-pill-text)", fontSize: "12px", fontWeight: "600", marginRight: "4px" }}>
                📦 Fixed Code Ready:
              </span>
              <a
                href={`${API_BASE}/runs/${runId}/fixed/${finding.id}/file`}
                className="refresh-button"
                style={{ textDecoration: "none", padding: "6px 12px", fontSize: "11.5px", background: "var(--action-bg)", color: "var(--action-text)" }}
                download="app.py"
              >
                <Download size={13} /> Download Fixed app.py
              </a>
              <button
                type="button"
                className="refresh-button"
                style={{ padding: "6px 12px", fontSize: "11.5px", background: "var(--brand-pill-bg)", color: "var(--brand-pill-text)" }}
                onClick={handleApplyFix}
              >
                <Check size={13} /> Apply Fix to Codebase (1-Click)
              </button>
              <button
                type="button"
                className="refresh-button"
                style={{ padding: "6px 12px", fontSize: "11.5px", background: "transparent", border: "1px solid var(--border-card)", color: "var(--text-muted)" }}
                onClick={() => setShowFixedCode(!showFixedCode)}
              >
                <Code2 size={13} /> {showFixedCode ? "Hide Fixed Code" : "Inspect Fixed Code"}
              </button>
              {applyStatus && (
                <span style={{ color: "var(--brand-primary)", fontSize: "12px", fontWeight: "600", marginLeft: "4px" }}>{applyStatus}</span>
              )}
            </div>
          )}

          {showFixedCode && !discarded && (
            <div
              style={{
                margin: "8px 19px 12px",
                padding: "14px",
                background: "var(--bg-flow)",
                border: "1px solid var(--border-flow)",
                borderRadius: "6px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ color: "var(--brand-pill-text)", fontSize: "12px", fontWeight: "600" }}>
                  📄 Patched <code>app.py</code> — Tested & Verified in Live Sandbox
                </span>
                <button
                  type="button"
                  className="copy-button"
                  onClick={() => copyCodeText(finding.patch?.fixed_code || finding.patch?.diff)}
                >
                  <Copy size={12} /> {codeCopied ? "Copied!" : "Copy Full Code"}
                </button>
              </div>
              <pre
                style={{
                  margin: 0,
                  maxHeight: "260px",
                  overflow: "auto",
                  fontSize: "11.5px",
                  color: "var(--text-code)",
                  background: "var(--code-bg)",
                  border: "1px solid var(--code-border)",
                  padding: "10px",
                  borderRadius: "4px",
                  fontFamily: "monospace",
                  lineHeight: "1.4",
                }}
              >
                {finding.patch?.fixed_code || finding.patch?.diff || "Fixed code loaded."}
              </pre>
            </div>
          )}

          {viewMode === "vibe" ? (
            <div className="simple-view">
              <div className="simple-summary">
                <div>
                  <h3 className="simple-verdict">
                    {discarded
                      ? "False Alarm Discarded"
                      : "Privacy Leak Detected & Fully Remediated"}
                  </h3>
                  <p style={{ margin: "6px 0 0", color: "#8fa087", fontSize: "12.5px" }}>
                    {finding.title}
                  </p>
                </div>
                {finding.severity && (
                  <span className="severity-badge">{finding.severity} risk</span>
                )}
              </div>

              <div className="explain-grid">
                <div>
                  <div className="detail-label">{discarded ? "1. WHAT WE TESTED" : "1. WHAT BUTTON / CONNECTION BROKE"}</div>
                  <p>{explainObj.story}</p>
                </div>
                <div>
                  <div className="detail-label">{discarded ? "2. WHY IT IS SAFE" : "2. WHY IT IS DANGEROUS"}</div>
                  <p>{explainObj.why_it_matters}</p>
                </div>
                <div>
                  <div className="detail-label">{discarded ? "3. VERITY VERDICT" : "3. HOW VERITY FIXED & TESTED IT"}</div>
                  <p>{explainObj.prevention_rule}</p>
                </div>
              </div>

              {!discarded && (
                <div className="evidence-flow">
                  <div className="flow-panel">
                    <div className="flow-step">1. USER ALICE TRIES TO ACCESS BOB'S NOTE</div>
                    <pre className="code-block" style={{ minHeight: "125px" }}>
                      {`GET /notes/2\nX-Token: alice-token\n\n# Alice asks for Bob's private note #2`}
                    </pre>
                  </div>
                  <div className="flow-panel">
                    <div className="flow-step">2. BEFORE FIX (BOB'S SECRET LEAKED - 200 OK)</div>
                    <pre className="code-block" style={{ minHeight: "125px", color: "var(--flow-fail-text)" }}>
                      {`HTTP/1.1 200 OK\n{\n  "id": 2,\n  "body": "BOB_SECRET_123"\n}\n# Bob's private data leaked!`}
                    </pre>
                  </div>
                  <div className="flow-panel">
                    <div className="flow-step">3. AFTER FIX (ACCESS BLOCKED - 403 FORBIDDEN)</div>
                    <pre className="code-block" style={{ minHeight: "125px", color: "var(--flow-success-text)" }}>
                      {`HTTP/1.1 403 Forbidden\n{\n  "error": "Forbidden"\n}\n# Unauthorized access blocked!`}
                    </pre>
                  </div>
                </div>
              )}

              <div
                className="prompt-row"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "12px",
                  background: "var(--bg-card-alt)",
                  padding: "12px 16px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-card)",
                  marginTop: "18px",
                }}
              >
                <div style={{ flex: 1, minWidth: "220px" }}>
                  <strong style={{ display: "block", color: "var(--text-heading)", marginBottom: "4px" }}>
                    🤖 Copy Prompt for your AI Assistant (Cursor, Claude, Copilot):
                  </strong>
                  <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                    {explainObj.ai_prompt}
                  </span>
                </div>
                <button
                  className="copy-button"
                  type="button"
                  onClick={() => copyPrompt(explainObj.ai_prompt)}
                >
                  <Copy size={13} />
                  {copied ? "Copied!" : "Copy AI Prompt"}
                </button>
              </div>

              <div className="glossary">
                <span className="detail-label">JARGON BUSTER:</span>
                <span className="glossary-term">
                  IDOR
                  <span className="glossary-tooltip">
                    Insecure Direct Object Reference: When an app lets you access someone else's file just by changing the ID number in the link.
                  </span>
                </span>
                <span className="glossary-term">
                  Sandbox
                  <span className="glossary-tooltip">
                    A secure, isolated throwaway copy of your app where Verity tests the exploit without touching your production database.
                  </span>
                </span>
                <span className="glossary-term">
                  Replay
                  <span className="glossary-tooltip">
                    Firing the exact same exploit a second time against the patched code to guarantee the fix works.
                  </span>
                </span>
              </div>
            </div>
          ) : (
            <div>
              <div className="tab-bar" role="tablist" aria-label="Finding details">
                {[
                  ["Evidence", ClipboardList],
                  ["Patch", Code2],
                  ["Replay", ShieldCheck],
                  ["Regression test", FlaskConical],
                ].map(([name, Icon]) => (
                  <button
                    key={name}
                    role="tab"
                    aria-selected={tab === name}
                    className={`tab ${tab === name ? "active" : ""}`}
                    onClick={() => setTab(name)}
                  >
                    <Icon size={15} />
                    {name}
                  </button>
                ))}
              </div>

              {tab === "Evidence" && (
                <div className="evidence-grid">
                  <div>
                    <div className="detail-label">EXPLOIT REQUEST (SANDBOX)</div>
                    <JsonBlock value={finding.evidence?.request} />
                  </div>
                  <div>
                    <div className="detail-label">EXPLOIT RESPONSE (BEFORE PATCH)</div>
                    <JsonBlock value={finding.evidence?.response} />
                  </div>
                </div>
              )}

              {tab === "Patch" && (
                <div className="tab-content">
                  <div className="detail-heading">
                    <span>{finding.patch?.file || "Patch"}</span>
                    <span style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span>{finding.patch?.summary || "No patch available"}</span>
                      {!discarded && runId && !isMock && (
                        <a
                          href={`${API_BASE}/runs/${runId}/patch`}
                          className="refresh-button"
                          style={{ textDecoration: "none", padding: "4px 10px", fontSize: "12px" }}
                          download={`${runId}.patch`}
                        >
                          <Download size={13} /> Download .patch
                        </a>
                      )}
                    </span>
                  </div>
                  <pre className="code-block diff">
                    {diff.split("\n").map((line, lineIndex) => (
                      <span
                        className={
                          line.startsWith("+") && !line.startsWith("+++")
                            ? "diff-add"
                            : line.startsWith("-") && !line.startsWith("---")
                            ? "diff-remove"
                            : ""
                        }
                        key={lineIndex}
                      >
                        {line}
                        {"\n"}
                      </span>
                    ))}
                  </pre>
                </div>
              )}

              {tab === "Replay" && (
                <div className="tab-content">
                  {!discarded && !isMock && runId && (
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "12px",
                      }}
                    >
                      <span className="detail-label" style={{ margin: 0 }}>
                        LIVE SANDBOX VERIFICATION (BEFORE VS. AFTER PATCH)
                      </span>
                      <button
                        className="refresh-button"
                        onClick={triggerLiveReplay}
                        disabled={replaying}
                        style={{ padding: "6px 12px", fontSize: "12px" }}
                      >
                        <Play size={13} />
                        {replaying ? " Spinning up sandboxes..." : " Try it yourself (Live Replay)"}
                      </button>
                    </div>
                  )}

                  {liveReplay ? (
                    <div className="evidence-grid">
                      <div>
                        <div className="detail-label">
                          BEFORE PATCH (EXPOSED — HTTP {liveReplay.before?.response?.status ?? 200})
                        </div>
                        <JsonBlock value={liveReplay.before || liveReplay} />
                      </div>
                      <div>
                        <div className="detail-label">
                          AFTER PATCH (BLOCKED — HTTP {liveReplay.after?.response?.status ?? 403})
                        </div>
                        <JsonBlock value={liveReplay.after || {}} />
                      </div>
                    </div>
                  ) : (
                    <div className="evidence-grid">
                      <div>
                        <div className="detail-label">REPLAYED REQUEST</div>
                        <JsonBlock
                          value={
                            typeof finding.replay === "object"
                              ? finding.replay?.request
                              : finding.evidence?.request
                          }
                        />
                      </div>
                      <div>
                        <div className="detail-label">PATCHED RESPONSE (AFTER FIX)</div>
                        <JsonBlock
                          value={
                            typeof finding.replay === "object"
                              ? finding.replay?.response
                              : finding.replay || "No replay recorded"
                          }
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {tab === "Regression test" && (
                <div className="tab-content">
                  <div className="detail-label">GENERATED PYTEST SUITE</div>
                  <JsonBlock value={finding.test || "No regression test available."} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function App() {
  const params = new URLSearchParams(window.location.search);
  const isMock = params.get("demo") === "mock";

  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem("verity-theme");
      if (saved === "light" || saved === "dark") return saved;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    } catch {
      return "dark";
    }
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("verity-theme", theme);
      const meta = document.querySelector('meta[name="color-scheme"]');
      if (meta) meta.content = theme;
      const metaTheme = document.getElementById("theme-color-meta");
      if (metaTheme) metaTheme.content = theme === "dark" ? "#101210" : "#f6f8f4";
    } catch {}
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const [currentView, setCurrentView] = useState("overview"); // "overview" | "codebase" | "github"
  const [repoInput, setRepoInput] = useState("");
  const [runId, setRunId] = useState(params.get("run_id") || null);
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [prStatus, setPrStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [workspaceFiles, setWorkspaceFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileEditorContent, setFileEditorContent] = useState("");
  const [saveStatus, setSaveStatus] = useState(null);

  useEffect(() => {
    async function fetchConfig() {
      try {
        const res = await fetch(`${API_BASE}/config`);
        if (res.ok) {
          const data = await res.json();
          setConfig(data);
        }
      } catch {}
      try {
        const res = await fetch(`${API_BASE}/workspace/files`);
        if (res.ok) {
          const data = await res.json();
          setWorkspaceFiles(data.files || []);
          if (data.files && data.files.length > 0) {
            setSelectedFile(data.files[0]);
            setFileEditorContent(data.files[0].content);
          }
        }
      } catch {}
    }
    if (!isMock) {
      fetchConfig();
    }
  }, [isMock]);

  async function startNewScan(overrideRepo) {
    if (isMock) return;
    setScanning(true);
    setError(null);
    setPrStatus(null);
    try {
      const targetRepo =
        typeof overrideRepo === "string" ? overrideRepo.trim() : repoInput.trim();
      const res = await fetch(`${API_BASE}/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: targetRepo || undefined }),
      });
      if (!res.ok) throw new Error(`Scan request failed (${res.status})`);
      const data = await res.json();
      setRunId(data.run_id);
    } catch {
      setError("Could not reach backend API at " + API_BASE + ". Make sure uvicorn api:app is running.");
      setScanning(false);
    }
  }

  async function handleOpenPr() {
    if (!state?.run_id || isMock) return;
    setPrStatus("Opening draft PR on GitHub...");
    try {
      const res = await fetch(`${API_BASE}/runs/${state.run_id}/pr`, { method: "POST" });
      const data = await res.json();
      if (data.pr_url) {
        setPrStatus(`Draft PR opened: ${data.pr_url}`);
        window.open(data.pr_url, "_blank");
      } else {
        setPrStatus(`${data.error || "GitHub token not set in .env"} — downloading .patch instead.`);
        window.location.href = `${API_BASE}/runs/${state.run_id}/patch`;
      }
    } catch {
      setPrStatus("Could not open PR; use Download .patch.");
    }
  }

  async function handleWipeRun() {
    if (!runId || isMock) return;
    if (!window.confirm("Permanently wipe this security run and delete all artifacts from S3 and local storage?")) return;
    try {
      await fetch(`${API_BASE}/runs/${runId}`, { method: "DELETE" });
      setState(null);
      setRunId(null);
      window.history.replaceState({}, document.title, window.location.pathname);
    } catch {
      alert("Error deleting run data.");
    }
  }

  async function handleSaveFile() {
    if (!selectedFile) return;
    setSaveStatus("Saving file...");
    try {
      const res = await fetch(`${API_BASE}/workspace/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: selectedFile.name, content: fileEditorContent }),
      });
      if (res.ok) {
        setSaveStatus("Saved! Triggering test run...");
        setTimeout(() => setSaveStatus(null), 3000);
        setCurrentView("overview");
        startNewScan("");
      } else {
        setSaveStatus("Failed to save file.");
      }
    } catch {
      setSaveStatus("Error uploading file.");
    }
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result;
      if (typeof text === "string") {
        setFileEditorContent(text);
        if (selectedFile) {
          selectedFile.content = text;
        }
      }
    };
    reader.readAsText(file);
  }

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const url = isMock
          ? `/state.json?t=${Date.now()}`
          : runId
          ? `${API_BASE}/runs/${runId}`
          : `${API_BASE}/runs/latest`;

        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) {
          if (response.status === 404 && !runId && !isMock) {
            if (active) setError(null);
            return;
          }
          throw new Error("Unable to load state");
        }
        const data = await response.json();
        if (active) {
          setState(data);
          if (!runId && data.run_id && !isMock) {
            setRunId(data.run_id);
          }
          if (data.status === "done" || data.status === "failed") {
            setScanning(false);
          } else if (data.status === "running" || data.status === "pending") {
            setScanning(true);
          }
          setError(null);
        }
      } catch {
        if (active) {
          setError(
            isMock
              ? "Could not load mock state.json."
              : `Backend unreachable at ${API_BASE}. Run: uvicorn api:app --reload --port 8000`
          );
        }
      }
    }

    load();
    const timer = setInterval(load, 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [runId, isMock]);

  const steps = state?.steps || [];
  const findings = state?.findings || [];
  const defaultStepNames = ["scan", "verify", "patch", "replay", "test"];
  const displayRepo = state?.repo_url || config?.repository || "Tamanna-2100/builderwars_strike";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" style={{ overflow: "hidden", padding: 0 }}>
            <img
              src={logoImg}
              alt="Verity Logo"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
              }}
            />
          </div>
          <div>
            <strong>
              verity<span>.</span>
            </strong>
            <small>SECURITY WORKSPACE</small>
          </div>
        </div>

        <div className="sidebar-section">WORKSPACE</div>
        <button
          type="button"
          onClick={() => setCurrentView("overview")}
          className="side-item"
          style={{
            width: "100%",
            border: 0,
            cursor: "pointer",
            background: currentView === "overview" ? "var(--brand-pill-bg)" : "transparent",
            color: currentView === "overview" ? "var(--brand-pill-text)" : "var(--text-muted)",
            marginBottom: "4px",
            textAlign: "left",
          }}
        >
          <Layers2 size={17} />
          Run overview <span className="side-count">01</span>
        </button>

        <button
          type="button"
          onClick={() => setCurrentView("codebase")}
          className="side-item"
          style={{
            width: "100%",
            border: 0,
            cursor: "pointer",
            background: currentView === "codebase" ? "var(--brand-pill-bg)" : "transparent",
            color: currentView === "codebase" ? "var(--brand-pill-text)" : "var(--text-muted)",
            marginBottom: "4px",
            textAlign: "left",
          }}
        >
          <FolderCode size={17} />
          Target Codebase / Files
        </button>

        <button
          type="button"
          onClick={() => setCurrentView("github")}
          className="side-item"
          style={{
            width: "100%",
            border: 0,
            cursor: "pointer",
            background: currentView === "github" ? "var(--brand-pill-bg)" : "transparent",
            color: currentView === "github" ? "var(--brand-pill-text)" : "var(--text-muted)",
            textAlign: "left",
          }}
        >
          <GitPullRequest size={17} />
          GitHub & PRs
        </button>

        <div className="sidebar-bottom">
          <span className="sidebar-status">
            <span /> {isMock ? "Mock environment" : "Live sandbox"}
          </span>
          <small>{isMock ? "SAMPLE DATA" : "AWS BEDROCK + S3"}</small>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              type="button"
              onClick={() => setCurrentView("overview")}
              style={{
                background: "none",
                border: "0",
                color: "#7e867a",
                cursor: "pointer",
                padding: 0,
                font: "inherit",
              }}
            >
              Workspace
            </button>
            <span>/</span>
            <strong>
              {currentView === "overview"
                ? "Run overview"
                : currentView === "codebase"
                ? "Target Codebase"
                : "GitHub & Settings"}
            </strong>
          </div>

          <div className="top-right" style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <button
              type="button"
              onClick={toggleTheme}
              className="theme-toggle-button"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? <Sun size={13} /> : <Moon size={13} />}
              <span>{theme === "dark" ? "Light" : "Dark"}</span>
            </button>

            {runId && !isMock && (
              <button
                type="button"
                onClick={handleWipeRun}
                className="theme-toggle-button"
                style={{
                  color: "#e06c75",
                  borderColor: "rgba(224, 108, 117, 0.35)",
                }}
                title="Wipe this run session and permanently delete all uploaded artifacts from S3"
              >
                <Trash2 size={13} />
                <span>Wipe S3 & Session</span>
              </button>
            )}

            {state?.saved_to_s3 && (
              <span className="badge badge-confirmed" title={(state.s3_keys || []).join("\n")}>
                <span className="badge-dot" /> Saved to S3
              </span>
            )}
            <span className="live-indicator">
              <span />{" "}
              {error
                ? "API offline"
                : isMock
                ? "Sample data"
                : scanning
                ? "Scan running..."
                : "Live connected"}
            </span>
            <span className="avatar">V</span>
          </div>
        </header>

        <main className="content">
          {currentView === "codebase" ? (
            <div>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span /> WORKSPACE FILES <span className="eyebrow-separator">/</span> TARGET
                  </div>
                  <h1>
                    Target codebase<span>.</span>
                  </h1>
                  <p>View, edit, or upload Python files to test custom code directly in Verity sandboxes.</p>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <label
                    className="refresh-button"
                    style={{ cursor: "pointer", background: "rgba(255,255,255,0.08)", color: "#e7eae3" }}
                  >
                    <Upload size={14} /> Upload Custom .py File
                    <input type="file" accept=".py,.txt" onChange={handleFileUpload} style={{ display: "none" }} />
                  </label>
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={handleSaveFile}
                  >
                    <Play size={14} /> Save & Test This Code
                  </button>
                </div>
              </div>

              {saveStatus && (
                <div style={{ padding: "10px 14px", marginBottom: "16px", borderRadius: "6px", background: "rgba(197,232,127,0.1)", color: "#d7edb4", fontSize: "13px" }}>
                  {saveStatus}
                </div>
              )}

              <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "18px" }}>
                <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-card)", borderRadius: "6px", padding: "12px", boxShadow: "var(--shadow-card)" }}>
                  <div className="detail-label" style={{ marginBottom: "10px" }}>WORKSPACE FILES</div>
                  {workspaceFiles.map((f) => (
                    <button
                      key={f.name}
                      type="button"
                      onClick={() => {
                        setSelectedFile(f);
                        setFileEditorContent(f.content);
                      }}
                      style={{
                        width: "100%",
                        textAlign: "left",
                        padding: "8px 10px",
                        borderRadius: "4px",
                        border: 0,
                        background: selectedFile?.name === f.name ? "var(--brand-pill-bg)" : "transparent",
                        color: selectedFile?.name === f.name ? "var(--brand-pill-text)" : "var(--text-muted)",
                        fontSize: "12px",
                        fontFamily: "'DM Mono', monospace",
                        marginBottom: "4px",
                        cursor: "pointer",
                      }}
                    >
                      {f.name}
                    </button>
                  ))}
                  {workspaceFiles.length === 0 && (
                    <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>target/app.py</div>
                  )}
                </div>

                <div>
                  <div className="detail-heading">
                    <span>{selectedFile?.name || "target/app.py"} (Live Editable)</span>
                    <span>EDIT OR PASTE SOURCE CODE BELOW</span>
                  </div>
                  <textarea
                    value={fileEditorContent}
                    onChange={(e) => setFileEditorContent(e.target.value)}
                    style={{
                      width: "100%",
                      minHeight: "450px",
                      padding: "15px",
                      background: "var(--code-bg)",
                      border: "1px solid var(--code-border)",
                      borderRadius: "4px",
                      color: "var(--code-text)",
                      fontFamily: "'DM Mono', monospace",
                      fontSize: "12px",
                      lineHeight: "1.7",
                      outline: "none",
                      resize: "vertical",
                    }}
                  />
                </div>
              </div>
            </div>
          ) : currentView === "github" ? (
            <div>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span /> INTEGRATIONS <span className="eyebrow-separator">/</span> GITHUB
                  </div>
                  <h1>
                    GitHub integration<span>.</span>
                  </h1>
                  <p>Test any repository and automatically create draft review PRs with evidence.</p>
                </div>
                <button
                  type="button"
                  className="refresh-button"
                  onClick={() => setCurrentView("overview")}
                >
                  <Layers2 size={15} /> Back to Run overview
                </button>
              </div>

              <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-card)", borderRadius: "8px", padding: "24px", maxWidth: "800px", boxShadow: "var(--shadow-card)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
                  <GitBranch size={24} style={{ color: "var(--brand-primary)" }} />
                  <div>
                    <h3 style={{ margin: 0, fontSize: "18px", color: "var(--text-heading)" }}>
                      {displayRepo}
                    </h3>
                    <small style={{ color: "var(--text-muted)" }}>Branch: {config?.branch || "main"}</small>
                  </div>
                </div>

                <p style={{ color: "var(--text-muted)", fontSize: "13.5px", lineHeight: 1.6 }}>
                  You can point Verity to <strong>any public GitHub repository</strong> to clone and verify it in isolated sandboxes. When a vulnerability is proven and patched:
                </p>

                <ul style={{ color: "var(--text-muted)", fontSize: "13px", lineHeight: 1.8, paddingLeft: "20px" }}>
                  <li>Verity creates a dedicated review branch: <code>verity-review/{`{run_id}`}</code></li>
                  <li>Commits the verified unified diff: <code>verity-reviews/{`{run_id}`}/changes.patch</code></li>
                  <li>Uploads captured HTTP exploit proof: <code>verity-reviews/{`{run_id}`}/evidence.md</code></li>
                  <li>Includes generated pytest regression suite: <code>verity-reviews/{`{run_id}`}/tests/test_security_*.py</code></li>
                  <li>Opens a draft Pull Request on GitHub ready for human review</li>
                </ul>

                <div style={{ marginTop: "24px", display: "flex", gap: "12px" }}>
                  <a
                    href={
                      displayRepo.startsWith("http")
                        ? displayRepo
                        : `https://github.com/${displayRepo}`
                    }
                    target="_blank"
                    rel="noreferrer"
                    className="refresh-button"
                    style={{ textDecoration: "none" }}
                  >
                    <ExternalLink size={14} /> Open Repository on GitHub
                  </a>
                </div>
              </div>
            </div>
          ) : (
            <div>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span /> RUN OVERVIEW <span className="eyebrow-separator">/</span>{" "}
                    {state?.run_id || "READY"}
                  </div>
                  <h1>
                    Security review<span>.</span>
                  </h1>
                  <p>Automated exploit verification, patching, and regression testing.</p>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                  {state?.run_id && !isMock && state?.stats?.fixed > 0 && (
                    <>
                      <a
                        href={`${API_BASE}/runs/${state.run_id}/patch`}
                        className="refresh-button"
                        style={{ textDecoration: "none" }}
                        download={`${state.run_id}.patch`}
                      >
                        <Download size={15} /> Download .patch
                      </a>
                      <button className="refresh-button" onClick={handleOpenPr}>
                        <GitPullRequest size={15} /> Open draft PR on GitHub
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* REPOSITORY INPUT BAR */}
              <div
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-card)",
                  borderRadius: "8px",
                  padding: "18px 22px",
                  marginBottom: "28px",
                  boxShadow: "var(--shadow-card)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "10px",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <label
                    style={{
                      color: "var(--text-muted)",
                      fontSize: "11px",
                      fontFamily: "'DM Mono', monospace",
                    }}
                  >
                    TEST ANY GITHUB REPOSITORY OR ENTER A REPO URL:
                  </label>
                  <span style={{ color: "var(--text-subtle)", fontSize: "11px" }}>
                    Active Target:{" "}
                    <strong style={{ color: "var(--brand-primary)" }}>
                      {state?.repo_url || (repoInput || "Sample Vulnerable Target (Local)")}
                    </strong>
                  </span>
                </div>

                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <input
                    type="text"
                    placeholder="https://github.com/owner/repo or owner/repo"
                    value={repoInput}
                    onChange={(e) => setRepoInput(e.target.value)}
                    style={{
                      flex: 1,
                      minWidth: "260px",
                      padding: "11px 14px",
                      background: "var(--bg-input)",
                      border: "1px solid var(--border-card)",
                      borderRadius: "5px",
                      color: "var(--text-main)",
                      fontSize: "13px",
                      fontFamily: "'DM Mono', monospace",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={() => startNewScan(repoInput)}
                    disabled={scanning || isMock}
                  >
                    {scanning ? <RefreshCw size={15} /> : <Play size={15} />}
                    {scanning ? " Running scan & sandbox..." : " Scan & Test Repo"}
                  </button>
                </div>
              </div>

              {prStatus && (
                <div
                  style={{
                    padding: "10px 14px",
                    marginBottom: "16px",
                    borderRadius: "8px",
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    fontSize: "13px",
                  }}
                >
                  {prStatus}
                </div>
              )}

              {error && (
                <div className="error-banner" role="alert">
                  {error}
                </div>
              )}

              <section className="stats-grid" aria-label="Run statistics">
                {statItems.map(({ key, label, icon: Icon, hint }) => (
                  <div className="stat-card" key={key}>
                    <div className="stat-top">
                      <span>{label}</span>
                      <Icon size={17} />
                    </div>
                    <div className="stat-number">{state?.stats?.[key] ?? 0}</div>
                    <div className="stat-hint">
                      <span />
                      {hint}
                    </div>
                  </div>
                ))}
              </section>

              <section className="timeline-section">
                <div className="section-heading">
                  <div>
                    <div className="section-kicker">THE PROCESS</div>
                    <h2>Run timeline</h2>
                  </div>
                  <span className="run-status">
                    <span /> {state?.status || "Ready"}
                  </span>
                </div>
                <div className="timeline">
                  {[0, 1, 2, 3, 4].map((index) => {
                    const step = steps[index] || {
                      name: defaultStepNames[index],
                      status: "pending",
                      detail: "Waiting",
                    };
                    return (
                      <div className="timeline-step" key={index}>
                        <div className={`step-node ${step.status}`}>
                          {step.status === "done" ? (
                            <Check size={15} />
                          ) : step.status === "failed" ? (
                            <X size={15} />
                          ) : (
                            <Circle size={9} />
                          )}
                        </div>
                        <div className="step-name" style={{ textTransform: "capitalize" }}>
                          {step.name}
                        </div>
                        <div className="step-detail">{step.detail || step.status}</div>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="findings-section">
                <div className="section-heading">
                  <div>
                    <div className="section-kicker">REVIEW QUEUE</div>
                    <h2>
                      Findings{" "}
                      <span className="heading-count">
                        {String(findings.length).padStart(2, "0")}
                      </span>
                    </h2>
                  </div>
                  <div className="section-aside">
                    <ArrowDownRight size={15} /> Run details
                  </div>
                </div>
                <div className="findings-list">
                  {findings.map((finding, index) => (
                    <Finding
                      key={finding.id || index}
                      finding={finding}
                      index={index}
                      runId={state?.run_id}
                      isMock={isMock}
                    />
                  ))}
                  {(!state || !findings.length) && (
                    <div className="empty-state">
                      <CheckCircle2 size={20} />{" "}
                      {scanning
                        ? "Pipeline is running sandbox verification and generating patches..."
                        : "Enter a GitHub repo URL above or click 'Scan & Test Repo' to start a verification run."}
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}

          <footer>
            <span>
              VERITY <span className="footer-dot">/</span> RUN REVIEW
            </span>
            <span>
              {state?.saved_to_s3 ? "Saved to S3" : isMock ? "Mock data" : "Live API"}{" "}
              <span className="footer-dot">/</span> Local workspace
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
