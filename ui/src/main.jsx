import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, ArrowDownRight, Check, CheckCircle2, ChevronDown, Circle, ClipboardList, Code2, FileCheck2, FlaskConical, Layers2, RefreshCw, ShieldCheck, X, XCircle } from "lucide-react";
import "./style.css";

const statItems = [
  { key: "hypotheses", label: "Hypotheses", icon: Layers2, hint: "Identified for review" },
  { key: "verified", label: "Verified", icon: ShieldCheck, hint: "Evidence collected" },
  { key: "fixed", label: "Fixed", icon: FileCheck2, hint: "Patch prepared" },
  { key: "discarded", label: "Discarded", icon: XCircle, hint: "Not confirmed" },
];

function JsonBlock({ value }) {
  return <pre className="code-block">{typeof value === "string" ? value : JSON.stringify(value ?? {}, null, 2)}</pre>;
}

function Finding({ finding, index }) {
  const [open, setOpen] = useState(index === 0);
  const [tab, setTab] = useState("Evidence");
  const discarded = finding.verdict === "discarded";
  const diff = finding.patch?.diff || "No patch available.";
  return (
    <article className={`finding ${open ? "finding-open" : ""}`}>
      <button className="finding-header" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={`finding-icon ${discarded ? "muted-icon" : ""}`}>{discarded ? <X size={15} /> : <ShieldCheck size={16} />}</span>
        <span className="finding-title-wrap"><span className="finding-id">{finding.id}</span><span className="finding-title">{finding.title}</span></span>
        <span className={`badge ${discarded ? "badge-discarded" : "badge-confirmed"}`}><span className="badge-dot" />{discarded ? "Discarded" : finding.verdict || "Pending"}</span>
        <ChevronDown size={17} className={`chevron ${open ? "rotated" : ""}`} />
      </button>
      {open && <div className="finding-content">
        <div className="tab-bar" role="tablist" aria-label="Finding details">
          {[["Evidence", ClipboardList], ["Patch", Code2], ["Regression test", FlaskConical]].map(([name, Icon]) => <button key={name} role="tab" aria-selected={tab === name} className={`tab ${tab === name ? "active" : ""}`} onClick={() => setTab(name)}><Icon size={15} />{name}</button>)}
        </div>
        {tab === "Evidence" && <div className="evidence-grid"><div><div className="detail-label">REQUEST</div><JsonBlock value={finding.evidence?.request} /></div><div><div className="detail-label">RESPONSE</div><JsonBlock value={finding.evidence?.response} /></div></div>}
        {tab === "Patch" && <div className="tab-content"><div className="detail-heading"><span>{finding.patch?.file || "Patch"}</span><span>{finding.patch?.summary || "No patch available"}</span></div><pre className="code-block diff">{diff.split("\n").map((line, lineIndex) => <span className={line.startsWith("+") && !line.startsWith("+++") ? "diff-add" : line.startsWith("-") && !line.startsWith("---") ? "diff-remove" : ""} key={lineIndex}>{line}{"\n"}</span>)}</pre></div>}
        {tab === "Regression test" && <div className="tab-content"><div className="detail-label">REGRESSION TEST</div><JsonBlock value={finding.test || "No regression test available."} /></div>}
      </div>}
    </article>
  );
}

function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/state.json?t=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error("Unable to load state");
        const data = await response.json();
        if (active) { setState(data); setError(false); }
      } catch { if (active) setError(true); }
    }
    load();
    const timer = setInterval(load, 1000);
    return () => { active = false; clearInterval(timer); };
  }, [refresh]);
  const steps = state?.steps || [];
  const findings = state?.findings || [];
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark"><Activity size={21} strokeWidth={2.2} /></div><div><strong>verity<span>.</span></strong><small>SECURITY WORKSPACE</small></div></div><div className="sidebar-section">WORKSPACE</div><div className="side-item"><Layers2 size={17} />Run overview <span className="side-count">01</span></div><div className="sidebar-bottom"><span className="sidebar-status"><span /> Mock environment</span><small>LOCAL REVIEW</small></div></aside>
    <div className="main"><header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>Run overview</strong></div><div className="top-right"><span className="live-indicator"><span /> {error ? "State unavailable" : "Mock data"}</span><span className="avatar">V</span></div></header>
      <main className="content"><div className="page-heading"><div><div className="eyebrow"><span /> RUN OVERVIEW <span className="eyebrow-separator">/</span> {state?.run_id || "LOADING"}</div><h1>Security review<span>.</span></h1><p>A closer look at your latest run.</p></div><button className="refresh-button" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={15} /> Refresh mock</button></div>
        {error && <div className="error-banner" role="alert">Could not load mock state. Check that state.json is available.</div>}
        <section className="stats-grid" aria-label="Run statistics">{statItems.map(({ key, label, icon: Icon, hint }) => <div className="stat-card" key={key}><div className="stat-top"><span>{label}</span><Icon size={17} /></div><div className="stat-number">{state?.stats?.[key] ?? "--"}</div><div className="stat-hint"><span />{hint}</div></div>)}</section>
        <section className="timeline-section"><div className="section-heading"><div><div className="section-kicker">THE PROCESS</div><h2>Run timeline</h2></div><span className="run-status"><span /> {state?.status || "Waiting"}</span></div><div className="timeline">{[0, 1, 2, 3, 4].map(index => { const step = steps[index] || { name: ["Scan", "Verify", "Patch", "Replay", "Report"][index], status: "pending", detail: "Waiting" }; return <div className="timeline-step" key={index}><div className={`step-node ${step.status}`}>{step.status === "done" ? <Check size={15} /> : step.status === "failed" ? <X size={15} /> : <Circle size={9} />}</div><div className="step-name">{step.name}</div><div className="step-detail">{step.detail || step.status}</div></div>; })}</div></section>
        <section className="findings-section"><div className="section-heading"><div><div className="section-kicker">REVIEW QUEUE</div><h2>Findings <span className="heading-count">{String(findings.length).padStart(2, "0")}</span></h2></div><div className="section-aside"><ArrowDownRight size={15} /> Run details</div></div><div className="findings-list">{findings.map((finding, index) => <Finding key={finding.id || index} finding={finding} index={index} />)}{state && !findings.length && <div className="empty-state"><CheckCircle2 size={20} /> No findings in this run.</div>}</div></section>
        <footer><span>VERITY <span className="footer-dot">/</span> RUN REVIEW</span><span>Mock data <span className="footer-dot">/</span> Local workspace</span></footer>
      </main>
    </div>
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);