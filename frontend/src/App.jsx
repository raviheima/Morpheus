import { useCallback, useEffect, useMemo, useState } from "react";
import { api, downloadBlob } from "./lib/api";
import { DEMO_PATH, pickReport } from "./lib/format";
import Modal from "./components/Modal";
import Toast from "./components/Toast";
import ProgressBar from "./components/ProgressBar";
import TopBar from "./components/TopBar";
import FindingsReport from "./components/FindingsReport";

export default function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem("mz_token") || ""
  );
  const [user, setUser] = useState(
    () => localStorage.getItem("mz_user") || ""
  );
  const [userRole, setUserRole] = useState(
    () => localStorage.getItem("mz_role") || ""
  );
  const [screen, setScreen] = useState(() => (token ? "hub" : "landing"));
  const [view, setView] = useState("overview");

  const [cases, setCases] = useState([]);
  const [active, setActive] = useState(null);
  const [dataSources, setDataSources] = useState([]);
  const [integrity, setIntegrity] = useState(null);
  const [custody, setCustody] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [extractionLog, setExtractionLog] = useState([]);
  const [analysisBySource, setAnalysisBySource] = useState({});
  const [activeAnalysis, setActiveAnalysis] = useState(null);
  const [activeJobUi, setActiveJobUi] = useState(null);

  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [imagePreviewName, setImagePreviewName] = useState("");

  const [busy, setBusy] = useState(false);
  const [hashing, setHashing] = useState(false);
  const [hashStartedAt, setHashStartedAt] = useState(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);
  const [aiSummary, setAiSummary] = useState(null);
  const [aiConfigured, setAiConfigured] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [evidenceList, setEvidenceList] = useState([]);
  const [addEvOpen, setAddEvOpen] = useState(false);
  const [evForm, setEvForm] = useState({ file_path: "", notes: "" });

  const [loginOpen, setLoginOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [addSrcOpen, setAddSrcOpen] = useState(false);
  const [pathFixOpen, setPathFixOpen] = useState(false);
  const [pathFixItem, setPathFixItem] = useState(null); // integrity item
  const [pathFixValue, setPathFixValue] = useState("");

  const [loginForm, setLoginForm] = useState({
    username: "admin",
    password: "admin123",
  });
  const [caseForm, setCaseForm] = useState({
    case_name: "",
    examiner_name: "",
    examiner_email: "",
    organisation: "",
    description: "",
  });
  const [srcForm, setSrcForm] = useState({
    file_path: "",
    label: "",
    collected_by: "",
    fileName: "",
  });

  const notify = useCallback((title, detail) => {
    setToast({ title, detail });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const saveSession = (t, u) => {
    localStorage.setItem("mz_token", t);
    localStorage.setItem("mz_user", u);
    setToken(t);
    setUser(u);
  };

  const loadCurrentUser = useCallback(async (t = token) => {
    if (!t) return;
    const current = await api("/auth/me", { token: t });
    setUser(current.username);
    setUserRole(current.role);
    localStorage.setItem("mz_user", current.username);
    localStorage.setItem("mz_role", current.role);
  }, [token]);

  const logout = () => {
    localStorage.removeItem("mz_token");
    localStorage.removeItem("mz_user");
    localStorage.removeItem("mz_role");
    setToken("");
    setUser("");
    setUserRole("");
    setActive(null);
    setActiveAnalysis(null);
    setScreen("landing");
  };

  const loadCases = useCallback(
    async (t = token) => {
      if (!t) return;
      const data = await api("/cases/", { token: t });
      setCases(Array.isArray(data) ? data : data.cases || []);
    },
    [token]
  );

  useEffect(() => {
    if (token) {
      loadCurrentUser().catch(() => logout());
      loadCases().catch(() => {});
    }
  }, [token, loadCases, loadCurrentUser]);

  useEffect(() => {
    return () => {
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    };
  }, [imagePreviewUrl]);

  const refreshCaseFiles = async (caseNumber, t = token) => {
    try {
      const ds = await api(`/data-sources/${caseNumber}`, { token: t });
      setDataSources(Array.isArray(ds) ? ds : []);
    } catch {
      setDataSources([]);
    }
  };

  const loadCustody = async (caseNumber) => {
    try {
      const data = await api(`/data-sources/${caseNumber}/custody-report`, {
        token,
      });
      setCustody(data);
    } catch {
      setCustody(null);
    }
  };

  const loadAuditLog = async () => {
    try {
      const data = await api("/auth/audit", { token });
      setAuditLog(
        (Array.isArray(data) ? data : []).sort(
          (a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime() ||
            b.id - a.id
        )
      );
    } catch {
      setAuditLog([]);
    }
  };

  const loadExtractionLog = async (caseNumber) => {
    try {
      const data = await api(`/data-sources/${caseNumber}/extractions`, { token });
      setExtractionLog(Array.isArray(data) ? data : []);
    } catch {
      setExtractionLog([]);
    }
  };

  const login = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api("/auth/token", {
        method: "POST",
        form: loginForm,
      });
      saveSession(data.access_token, loginForm.username);
      const current = await api("/auth/me", { token: data.access_token });
      setUserRole(current.role);
      localStorage.setItem("mz_role", current.role);
      setLoginOpen(false);
      setScreen("hub");
      await loadCases(data.access_token);
      notify("Signed in", loginForm.username);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const canEditCase = userRole === "admin" || userRole === "examiner";
  const canDeleteCase = userRole === "admin";

  const createCase = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api("/cases/", {
        token,
        method: "POST",
        body: caseForm,
      });
      const c = {
        case_number: created.case_number,
        case_name: created.case_name || caseForm.case_name,
        examiner_name: created.examiner_name || caseForm.examiner_name,
        organisation: created.organisation || caseForm.organisation,
        status: created.status || "open",
      };
      setCreateOpen(false);
      await loadCases();
      await openCase(c);
      notify("Case created", c.case_number);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const openCase = async (c) => {
    setActive(c);
    setView("overview");
    setIntegrity(null);
    setActiveAnalysis(null);
    setActiveJobUi(null);
    setAnalysisBySource({});
    setImagePreviewUrl(null);
    setScreen("workspace");
    await api(`/cases/${c.case_number}`, { token }).catch(() => {});
    await refreshCaseFiles(c.case_number);
    await loadCustody(c.case_number);
    await loadExtractionLog(c.case_number);
    await loadAuditLog(c.case_number);
    try {
      const ev = await api(`/evidence/${c.case_number}`, { token });
      setEvidenceList(Array.isArray(ev) ? ev : []);
    } catch {
      setEvidenceList([]);
    }
    setAiSummary(null);
    try {
      const aiStatus = await api("/analysis/ai-status", { token });
      setAiConfigured(Boolean(aiStatus?.ai_configured));
    } catch {
      setAiConfigured(false);
    }
    // Load last stored analysis — no need to run again
    try {
      const latest = await api(`/analysis/case/${c.case_number}/latest`, { token });
      if (latest && latest.status === "completed" && latest.result) {
        setActiveAnalysis(latest);
        setActiveJobUi(latest);
      }
    } catch {
      /* no prior analysis */
    }
  };

  const closeCase = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const action = active.status === "closed" ? "reopen" : "close";
      await api(`/cases/${active.case_number}/${action}`, {
        token,
        method: "POST",
      });
      const nextStatus = action === "reopen" ? "open" : "closed";
      setActive((current) =>
        current ? { ...current, status: nextStatus } : current
      );
      notify(action === "reopen" ? "Case reopened" : "Case closed", active.case_number);
      await loadCases();
      if (action === "close") setScreen("hub");
    } catch (e) {
      notify(action === "reopen" ? "Reopen failed" : "Close failed", e.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteCase = async () => {
    if (!active) return;
    if (
      !window.confirm(
        `Delete case ${active.case_number}? This cannot be undone.`
      )
    )
      return;
    setBusy(true);
    try {
      await api(`/cases/${active.case_number}`, { token, method: "DELETE" });
      notify("Case deleted", active.case_number);
      setActive(null);
      await loadCases();
      setScreen("hub");
    } catch (e) {
      notify("Delete failed", e.message);
    } finally {
      setBusy(false);
    }
  };

  const addDataSource = async (e) => {
    e.preventDefault();
    if (!active) return;
    if (!srcForm.file_path.trim()) {
      setError("Enter the full path on the Morpheus analysis machine.");
      return;
    }
    setBusy(true);
    setHashing(true);
    setHashStartedAt(Date.now());
    setError("");
    try {
      await api("/data-sources/", {
        token,
        method: "POST",
        body: {
          case_number: active.case_number,
          file_path: srcForm.file_path.trim(),
          label: srcForm.label || srcForm.fileName || undefined,
          collected_by: srcForm.collected_by || user,
        },
      });
      setAddSrcOpen(false);
      setSrcForm({ file_path: "", label: "", collected_by: user, fileName: "" });
      await refreshCaseFiles(active.case_number);
      await loadCustody(active.case_number);
      notify("Data source registered", "Fingerprint stored");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setHashing(false);
      setHashStartedAt(null);
    }
  };

  const runIntegrity = async () => {
    if (!active) return;
    if (dataSources.length === 0) {
      notify("Nothing to verify", "Add a disk image data source first");
      return;
    }
    setBusy(true);
    try {
      const data = await api(
        `/data-sources/${active.case_number}/integrity-check`,
        { token, method: "POST" }
      );
      setIntegrity(data);
      await loadCustody(active.case_number);
      await refreshCaseFiles(active.case_number);

      const items = data.items || [];
      const missing = items.filter((i) => i.status === "missing");
      const mismatch = items.filter((i) => i.status === "hash_mismatch");

      if (data.warnings === 0) {
        notify("Integrity verified", `${data.ok ?? 0} file(s) match registered fingerprints`);
      } else if (mismatch.length) {
        notify(
          "Integrity compromised",
          `${mismatch.length} file(s) no longer match SHA-256 — content may have been modified or replaced`
        );
      } else if (missing.length) {
        notify(
          "File(s) missing",
          `${missing.length} path(s) not found — update the path if the file moved`
        );
        // Open fix dialog for first missing data_source
        const first = missing.find((i) => i.kind === "data_source") || missing[0];
        if (first) {
          setPathFixItem(first);
          setPathFixValue(first.stored_path || "");
          setPathFixOpen(true);
        }
      } else {
        notify("Integrity problems", `${data.ok ?? 0} ok · ${data.warnings ?? 0} warning(s)`);
      }
    } catch (err) {
      notify("Integrity failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const submitPathFix = async (e) => {
    e?.preventDefault?.();
    if (!pathFixItem || !pathFixValue.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api(`/data-sources/by-id/${pathFixItem.id}/path`, {
        token,
        method: "PATCH",
        body: { new_path: pathFixValue.trim() },
      });
      setPathFixOpen(false);
      setPathFixItem(null);
      notify("Path updated", "Fingerprint confirmed — location saved");
      if (active) {
        await refreshCaseFiles(active.case_number);
        await loadCustody(active.case_number);
        // re-run integrity quietly
        const data = await api(
          `/data-sources/${active.case_number}/integrity-check`,
          { token, method: "POST" }
        );
        setIntegrity(data);
      }
    } catch (err) {
      setError(err.message);
      notify("Path update failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadReport = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const blob = await api(
        `/data-sources/${active.case_number}/report.pdf`,
        { token }
      );
      downloadBlob(blob, `morpheus_report_${active.case_number}.pdf`);
      notify("Report downloaded", "Findings, integrity, and chain of custody");
      await loadCustody(active.case_number);
    } catch (err) {
      notify("Report download failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const startAnalysisFor = async (ds) => {
    if (!ds?.stored_path) {
      notify("Missing path", "Data source has no stored path");
      return;
    }
    setBusy(true);
    try {
      const res = await api("/analysis/run", {
        token,
        method: "POST",
        body: {
          evidence_path: ds.stored_path, case_number: active?.case_number, data_source_id: ds.id,
          export_artifacts: true,
          build_timeline: false,
        },
      });
      setAnalysisBySource((prev) => ({
        ...prev,
        [ds.id]: { status: res.status || "queued", jobId: res.job_id },
      }));
      setActiveJobUi({
        sourceId: ds.id,
        jobId: res.job_id,
        status: res.status || "queued",
        progress: 0,
        phase: "queued",
      });
      notify("Analysis started", ds.label || ds.original_filename);
      pollJob(ds.id, res.job_id);
    } catch (err) {
      notify("Analyze failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const pollJob = async (sourceId, jobId) => {
    const tick = async () => {
      try {
        const job = await api(`/analysis/jobs/${jobId}`, { token });
        setAnalysisBySource((prev) => ({
          ...prev,
          [sourceId]: {
            status: job.status,
            jobId,
            result: job.result || null,
            error: job.error,
          },
        }));
        setActiveJobUi({
          sourceId,
          jobId,
          status: job.status,
          progress: job.progress,
          phase: job.phase || job.status,
          eta_seconds: job.eta_seconds,
        });
        if (job.status === "completed") {
          setActiveAnalysis(job.result || job);
          setView("findings");
          notify("Analysis complete", "Report ready");
          if (active?.case_number) await loadCustody(active.case_number);
          return;
        }
        if (job.status === "failed") {
          notify("Analysis failed", job.error || "Error");
          return;
        }
        setTimeout(tick, 2000);
      } catch (err) {
        notify("Job poll error", err.message);
      }
    };
    tick();
  };

  const report = useMemo(() => pickReport(activeAnalysis), [activeAnalysis]);

  const extractArtifact = async (art) => {
    const path = art.path || art.file_path;
    const ds = dataSources.find((d) => d.stored_path) || dataSources[0];
    if (!ds?.stored_path || !path) {
      notify("Extract unavailable", "Need data source and path");
      return;
    }
    setBusy(true);
    try {
      const blob = await api("/analysis/export-file", {
        token,
        method: "POST",
        body: {
          evidence_path: ds.stored_path,
          file_path: path,
          case_number: active.case_number,
        },
      });
      const name =
        art.name || String(path).split(/[/\\]/).pop() || "artifact.bin";
      downloadBlob(blob, name);
      notify("Extracted", name);
    } catch (err) {
      notify("Extract failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const previewImage = async (art) => {
    const path = art.path || art.file_path;
    const ds = dataSources.find((d) => d.stored_path) || dataSources[0];
    if (!ds?.stored_path || !path) {
      notify("Preview unavailable", "Need data source and image path");
      return;
    }
    setBusy(true);
    try {
      const blob = await api("/analysis/export-file", {
        token,
        method: "POST",
        body: {
          evidence_path: ds.stored_path,
          file_path: path,
          case_number: active.case_number,
        },
      });
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
      const url = URL.createObjectURL(blob);
      setImagePreviewUrl(url);
      setImagePreviewName(art.name || path);
      setView("findings");
      notify("Image loaded", art.name || path);
    } catch (err) {
      notify("Image preview failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const requestAiSummary = async () => {
    if (!active) return;
    setAiBusy(true);
    try {
      const data = await api("/analysis/ai-summary", {
        token,
        method: "POST",
        body: { case_number: active.case_number },
      });
      if (!data.ok) {
        setAiConfigured(Boolean(data.ai_configured));
        notify("AI summary unavailable", data.error || "Set MORPHEUS_AI_API_KEY on the server");
        setAiSummary(null);
      } else {
        setAiConfigured(true);
        setAiSummary(data.summary);
        notify("AI summary ready", "Plain-language overview for the court");
        await loadCustody(active.case_number);
      }
    } catch (err) {
      notify("AI summary failed", err.message);
    } finally {
      setAiBusy(false);
    }
  };

  const addEvidenceArtifact = async (e) => {
    e.preventDefault();
    if (!active || !evForm.file_path.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api("/evidence/", {
        token,
        method: "POST",
        body: {
          case_number: active.case_number,
          file_path: evForm.file_path.trim(),
          collected_by: user,
          notes: evForm.notes || null,
        },
      });
      setAddEvOpen(false);
      setEvForm({ file_path: "", notes: "" });
      const ev = await api(`/evidence/${active.case_number}`, { token });
      setEvidenceList(Array.isArray(ev) ? ev : []);
      await loadCustody(active.case_number);
      notify("Evidence added", "Fingerprint stored in chain of custody");
    } catch (err) {
      setError(err.message);
      notify("Add evidence failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const hasFiles = dataSources.length > 0;
  const hashElapsed = hashStartedAt
    ? Math.round((Date.now() - hashStartedAt) / 1000)
    : 0;

  /* ───── LANDING ───── */
  if (screen === "landing") {
    return (
      <div className="landing premium-land">
        <header className="land-header">
          <span className="topbar-brand">MORPHEUS</span>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              className="btn"
              onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}
            >
              Features
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
            >
              {token ? "Open workspace" : "Sign in"}
            </button>
          </div>
        </header>

        <section className="land-hero">
          <p className="land-kicker">Digital forensics for investigators and courts</p>
          <h1>Know that your evidence still matches the original</h1>
          <p className="land-lead">
            Morpheus helps you register disk images, check file fingerprints,
            keep a clear chain of custody, and review what the disk analysis found —
            in one calm workspace.
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
            >
              Start examining
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => document.getElementById("why")?.scrollIntoView({ behavior: "smooth" })}
            >
              Why integrity matters
            </button>
          </div>
        </section>

        <section className="land-grid" id="features">
          <div className="land-card">
            <h3>Integrity checks</h3>
            <p>
              When you register a file, Morpheus stores its SHA-256 fingerprint.
              Later you can verify that the file is still the same — or see a clear
              warning if it is missing or changed.
            </p>
          </div>
          <div className="land-card">
            <h3>Chain of custody</h3>
            <p>
              Every important action is logged: who did it, when, and what changed.
              The log is kept even if a case is closed or marked deleted.
            </p>
          </div>
          <div className="land-card">
            <h3>Disk analysis, stored once</h3>
            <p>
              Run analysis on a disk image. Results are saved. Open the case later
              and the findings are still there — you do not need to run analysis again.
            </p>
          </div>
          <div className="land-card">
            <h3>Court-ready reports</h3>
            <p>
              Download a case report with integrity status, key findings, and the
              full custody timeline. Optional AI summary explains findings in simple language.
            </p>
          </div>
          <div className="land-card">
            <h3>Evidence artifacts</h3>
            <p>
              Add other files (exports, photos, notes) with the same fingerprint and
              custody rules — not only disk images.
            </p>
          </div>
          <div className="land-card">
            <h3>Items to review</h3>
            <p>
              Highlight signs of encryption, deleted material, and suspicious text
              so judges and reviewers can focus on what matters.
            </p>
          </div>
        </section>

        <section className="land-why" id="why">
          <h2>Why file integrity is the heart of Morpheus</h2>
          <p>
            Courts care whether evidence is still the same as when it was collected.
            A fingerprint is a short value made from the whole file. If even one byte
            changes, the fingerprint changes. Matching fingerprints mean the content
            is unchanged. The file path only tells the tool where to read the file.
          </p>
        </section>

        <section className="land-soon">
          <h2>Coming soon</h2>
          <ul>
            <li>
              <strong>Multi-machine sync</strong> — share cases between lab computers
              without breaking custody. This needs careful design so logs stay trusted;
              it is planned, not available yet.
            </li>
            <li>
              <strong>Mobile device acquisition</strong> — Android and iOS collection
              and analysis in the same workflow.
            </li>
            <li>
              <strong>Deeper cloud artifacts</strong> — more sources beyond local disk images.
            </li>
          </ul>
        </section>

        <footer className="land-footer">
          <span>Morpheus — integrity-first digital forensics</span>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
          >
            Get started
          </button>
        </footer>

        {loginOpen && (
          <Modal title="Sign in" onClose={() => setLoginOpen(false)}>
            <form onSubmit={login} className="signin-form">
              <label htmlFor="signin-username">Username</label>
              <input
                id="signin-username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={loginForm.username}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, username: e.target.value })
                }
              />
              <label htmlFor="signin-password">Password</label>
              <input
                id="signin-password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
              />
              {error ? (
                <p className="err-text" role="alert">
                  {error}
                </p>
              ) : null}
              <button type="submit" className="btn btn-primary" disabled={busy}>
                Sign in
              </button>
            </form>
          </Modal>
        )}
      </div>
    );
  }

  if (screen === "hub") {
    return (
      <div className="app-root">
        <TopBar user={user} onLogout={logout} />
        <div className="main-scroll">
          <div className="hub">
            <h1 className="page-title">Cases</h1>
            <p className="page-sub">
              Create an investigation or open an existing case.
            </p>
            <div className="hub-tiles">
              <button
                type="button"
                className="hub-tile"
                disabled={!canEditCase}
                title={!canEditCase ? "Viewers have read-only access" : undefined}
                onClick={() => {
                  setCaseForm((f) => ({ ...f, examiner_name: user }));
                  setError("");
                  setCreateOpen(true);
                }}
              >
                <strong>Create case</strong>
                <span>Start a new investigation with custody from the first action.</span>
              </button>
              <button
                type="button"
                className="hub-tile"
                onClick={() =>
                  loadCases().catch((e) => notify("Refresh failed", e.message))
                }
              >
                <strong>Refresh list</strong>
                <span>Reload cases from the Morpheus API.</span>
              </button>
              <button
                type="button"
                className="hub-tile"
                onClick={() => {
                  setView("audit");
                  loadAuditLog().catch(() =>
                    notify("Audit log unavailable", "Could not load the general audit log")
                  );
                }}
              >
                <strong>General audit log</strong>
                <span>Review application-wide activity across the shared demo organization.</span>
              </button>
            </div>
            <div className="panel">
              <div className="panel-title">Registered cases</div>
              <div className="panel-body" style={{ padding: 0 }}>
                {cases.length === 0 ? (
                  <div className="empty">No cases yet. Create one to begin.</div>
                ) : (
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Case number</th>
                        <th>Name</th>
                        <th>Examiner</th>
                        <th>Status</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {cases.map((c) => (
                        <tr key={c.case_number}>
                          <td className="mono">{c.case_number}</td>
                          <td>{c.case_name}</td>
                          <td>{c.examiner_name}</td>
                          <td>{c.status}</td>
                          <td>
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() => openCase(c)}
                            >
                              Open
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              {view === "audit" && (
                <div className="panel" style={{ marginTop: 14 }}>
                  <div className="panel-title">General audit log</div>
                  <div className="panel-body audit-log-scroll">
                    {!auditLog.length ? (
                      <div className="empty">No audit events recorded yet.</div>
                    ) : (
                      auditLog.map((entry) => (
                        <div key={entry.id} className="finding">
                          <span className="dot" />
                          <div>
                            <strong>{entry.action} — {entry.actor}</strong>
                            <small>
                              {new Date(entry.timestamp).toLocaleString()}
                              {entry.case_id ? ` · Case ${entry.case_id}` : ""}
                            </small>
                            {entry.details ? (
                              <small className="mono">{entry.details}</small>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
        {createOpen && (
          <Modal title="Create case" onClose={() => setCreateOpen(false)}>
            <form onSubmit={createCase}>
              <label>Case name</label>
              <input
                required
                value={caseForm.case_name}
                onChange={(e) =>
                  setCaseForm({ ...caseForm, case_name: e.target.value })
                }
              />
              <div className="row-2">
                <div>
                  <label>Examiner</label>
                  <input
                    required
                    value={caseForm.examiner_name}
                    onChange={(e) =>
                      setCaseForm({
                        ...caseForm,
                        examiner_name: e.target.value,
                      })
                    }
                  />
                </div>
                <div>
                  <label>Organisation</label>
                  <input
                    value={caseForm.organisation}
                    onChange={(e) =>
                      setCaseForm({
                        ...caseForm,
                        organisation: e.target.value,
                      })
                    }
                  />
                </div>
              </div>
              <label>Email</label>
              <input
                type="email"
                value={caseForm.examiner_email}
                onChange={(e) =>
                  setCaseForm({ ...caseForm, examiner_email: e.target.value })
                }
              />
              <label>Description</label>
              <textarea
                value={caseForm.description}
                onChange={(e) =>
                  setCaseForm({ ...caseForm, description: e.target.value })
                }
              />
              {error && <p className="err-text">{error}</p>}
              <footer>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setCreateOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={busy}
                >
                  {busy ? "Creating…" : "Create & open"}
                </button>
              </footer>
            </form>
          </Modal>
        )}
        {toast && <Toast {...toast} />}
      </div>
    );
  }

  /* ───── WORKSPACE ───── */
  return (
    <div className="app-root">
      <TopBar
        user={user}
        caseLabel={
          active ? `${active.case_number} — ${active.case_name}` : ""
        }
        onLogout={logout}
        onCases={() => setScreen("hub")}
      />
      <div className="shell">
        <aside className="sidebar">
          <div className="sidebar-section">Investigation</div>
          {[
            ["overview", "Case overview"],
            ["sources", "Data sources"],
            ["findings", "Key findings"],
            ["custody", "Chain of custody"],
            ["extracted", "Extracted files"],
            ["reports", "Reports"],
            ["about", "About & roadmap"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`nav-item ${view === id ? "active" : ""}`}
              onClick={() => setView(id)}
            >
              {label}
            </button>
          ))}
          <div className="sidebar-section">Roadmap</div>
          <button type="button" className="nav-item" disabled>
            Evidence collection <span className="badge">Soon</span>
          </button>
          <button type="button" className="nav-item" disabled>
            Android / iOS <span className="badge">Soon</span>
          </button>
          <div className="sidebar-foot">
            Signed in as <strong>{user}</strong>
          </div>
        </aside>

        <div className="main">
          <div className="main-scroll">
            {hashing && (
              <div className="panel">
                <div className="panel-body">
                  <ProgressBar
                    value={null}
                    label="Computing SHA-256 fingerprint…"
                    sub={`Elapsed ${hashElapsed}s · Large images can take several minutes.`}
                  />
                </div>
              </div>
            )}
            {activeJobUi &&
              !["completed", "failed"].includes(activeJobUi.status) && (
                <div className="panel">
                  <div className="panel-body">
                    <ProgressBar
                      value={activeJobUi.progress}
                      label={`Analysis · ${activeJobUi.phase || activeJobUi.status}`}
                      sub="Status updates every few seconds"
                    />
                  </div>
                </div>
              )}

            {view === "overview" && (
              <>
                <h1 className="page-title">Case overview</h1>
                <p className="page-sub">
                  {active?.case_number} · Integrity, custody, and disk-image
                  analysis
                </p>
                {userRole === "viewer" && (
                  <div className="access-note" role="status">
                    You are signed in as a viewer. Case data, integrity checks,
                    findings, custody, and reports are available read-only.
                    Evidence changes, analysis, and case status changes are
                    restricted to examiners and admins.
                  </div>
                )}
                <div
                  className={`banner ${
                    integrity
                      ? integrity.warnings === 0
                        ? "ok"
                        : "warn"
                      : ""
                  }`}
                >
                  <div>
                    <strong>
                      {integrity
                        ? integrity.warnings === 0
                          ? "Integrity check passed"
                          : "Integrity problems detected"
                        : "Integrity has not been run yet"}
                    </strong>
                    <span>
                      {integrity
                        ? `${integrity.ok ?? 0} file(s) ok · ${integrity.warnings ?? 0} warning(s)`
                        : "Register a disk image, then verify fingerprints."}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || !hasFiles}
                    onClick={runIntegrity}
                  >
                    Verify integrity
                  </button>
                </div>
                {integrity?.items?.length > 0 && (
                  <div className="panel" style={{ marginBottom: 12 }}>
                    <div className="panel-title">Integrity results</div>
                    <div className="panel-body">
                      {(integrity.items || []).map((it) => {
                        const bad = it.status !== "ok";
                        const compromised = it.status === "hash_mismatch";
                        const missing = it.status === "missing";
                        return (
                          <div
                            key={`${it.kind}-${it.id}`}
                            className="finding integrity-finding"
                            style={{
                              borderLeft: compromised
                                ? "3px solid #c44"
                                : missing
                                  ? "3px solid #c90"
                                  : "3px solid #2a7",
                              paddingLeft: 10,
                              marginBottom: 10,
                            }}
                          >
                            <div>
                              <strong>
                                {it.filename || it.stored_path || `#${it.id}`}
                              </strong>
                              <small style={{ display: "block" }}>
                                {it.kind} ·{" "}
                                {compromised
                                  ? "COMPROMISED (hash mismatch)"
                                  : missing
                                    ? "MISSING (path not found)"
                                    : "OK"}
                              </small>
                              <small style={{ display: "block", color: "var(--text-2)" }}>
                                {it.message}
                              </small>
                              {it.stored_path ? (
                                <small className="mono" style={{ display: "block" }}>
                                  {it.stored_path}
                                </small>
                              ) : null}
                              {compromised && (
                                <small style={{ display: "block", marginTop: 4 }}>
                                  Expected {it.expected_sha256?.slice?.(0, 16)}… ·
                                  Actual {it.actual_sha256?.slice?.(0, 16)}…
                                  <br />
                                  Do not treat this file as original evidence without
                                  investigation. Path update is blocked unless the
                                  fingerprint matches.
                                </small>
                              )}
                              {missing && it.kind === "data_source" && (
                                <button
                                  type="button"
                                  className="btn btn-sm"
                                  style={{ marginTop: 6 }}
                                  disabled={!canEditCase}
                                  title={!canEditCase ? "Viewers cannot update evidence paths" : undefined}
                                  onClick={() => {
                                    setPathFixItem(it);
                                    setPathFixValue(it.stored_path || "");
                                    setPathFixOpen(true);
                                    setError("");
                                  }}
                                >
                                  Update path…
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                <div className="panel-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canEditCase}
                    title={!canEditCase ? "Viewers cannot add data sources" : undefined}
                    onClick={() => {
                      setError("");
                      setSrcForm({
                        file_path: "",
                        label: "",
                        collected_by: user,
                        fileName: "",
                      });
                      setAddSrcOpen(true);
                    }}
                  >
                    Add data source
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || !hasFiles}
                    onClick={runIntegrity}
                  >
                    Verify integrity
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={downloadReport}
                  >
                    Download report
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={!canEditCase || busy}
                    title={!canEditCase ? "Viewers cannot close or reopen cases" : undefined}
                    onClick={closeCase}
                  >
                    {active?.status === "closed" ? "Reopen case" : "Close case"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={!canDeleteCase || busy}
                    title={!canDeleteCase ? "Only admins can delete cases" : undefined}
                    onClick={deleteCase}
                  >
                    Delete case
                  </button>
                </div>
                <div className="stats">
                  <div className="stat">
                    <label>Data sources</label>
                    <b>{dataSources.length}</b>
                    <small>Disk images</small>
                  </div>
                  <div className="stat">
                    <label>Files (last report)</label>
                    <b>
                      {report?.case_summary?.total_files_scanned ?? "—"}
                    </b>
                    <small>From analysis</small>
                  </div>
                  <div className="stat">
                    <label>Deleted</label>
                    <b>
                      {report?.case_summary?.total_deleted_recovered ?? "—"}
                    </b>
                    <small>Engine total</small>
                  </div>
                  <div className="stat">
                    <label>Integrity</label>
                    <b>
                      {integrity
                        ? integrity.warnings === 0
                          ? "OK"
                          : "Warn"
                        : "—"}
                    </b>
                    <small>Hash vs collection</small>
                  </div>
                </div>
                <div className="grid-2">
                  <div className="panel">
                    <div className="panel-title">Data sources</div>
                    <div className="panel-body">
                      {dataSources.length === 0 ? (
                        <div className="empty">
                          Add a forensic disk image to begin analysis.
                        </div>
                      ) : (
                        dataSources.map((ds) => (
                          <div key={ds.id} style={{ marginBottom: 14 }}>
                            <strong>
                              {ds.label || ds.original_filename}
                            </strong>
                            <div
                              className="mono"
                              style={{ color: "var(--muted)" }}
                            >
                              {ds.stored_path}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              <button
                                type="button"
                                className="btn btn-sm btn-primary"
                                disabled={!canEditCase || busy}
                                title={!canEditCase ? "Viewers cannot analyze data sources" : undefined}
                                onClick={() => startAnalysisFor(ds)}
                              >
                                Analyze
                              </button>{" "}
                              {analysisBySource[ds.id]?.status && (
                                <span className="tag">
                                  {analysisBySource[ds.id].status}
                                </span>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="panel">
                    <div className="panel-title">Recent custody</div>
                    <div className="panel-body">
                      {!(custody?.custody_timeline || []).length ? (
                        <div className="empty">No custody events yet.</div>
                      ) : (
                        (custody.custody_timeline || [])
                          .filter((e) => e.action !== "file_extracted")
                          .slice(0, 8)
                          .map((e, i) => (
                            <div key={i} className="finding">
                              <span className="dot" />
                              <div>
                                <strong>
                                  {e.what} — {e.who}
                                </strong>
                                <small>{e.when}</small>
                              </div>
                            </div>
                          ))
                      )}
                      <button
                        type="button"
                        className="btn btn-sm"
                        style={{ marginTop: 10 }}
                        onClick={() => setView("custody")}
                      >
                        Full custody log
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}

            {view === "sources" && (
              <>
                <h1 className="page-title">Data sources</h1>
                <p className="page-sub">
                  Forensic disk images for this case. Analyze each source
                  independently.
                </p>
                <div className="panel-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canEditCase}
                    title={!canEditCase ? "Viewers cannot add data sources" : undefined}
                    onClick={() => setAddSrcOpen(true)}
                  >
                    Add data source
                  </button>
                </div>
                <div className="panel">
                  <div className="panel-body">
                    {dataSources.length === 0 ? (
                      <div className="empty">None registered.</div>
                    ) : (
                      dataSources.map((ds) => (
                        <div key={ds.id} style={{ marginBottom: 14 }}>
                          <strong>{ds.label || ds.original_filename}</strong>
                          <div className="mono">{ds.stored_path}</div>
                          <div className="mono" style={{ marginTop: 4 }}>
                            {ds.sha256_hash
                              ? `${ds.sha256_hash.slice(0, 32)}…`
                              : ""}
                          </div>
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            style={{ marginTop: 10 }}
                            disabled={!canEditCase || busy}
                            title={!canEditCase ? "Viewers cannot analyze data sources" : undefined}
                            onClick={() => startAnalysisFor(ds)}
                          >
                            Analyze
                          </button>{" "}
                          {analysisBySource[ds.id]?.status && (
                            <span className="tag">
                              {analysisBySource[ds.id].status}
                            </span>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "findings" && (
              <>
                <h1 className="page-title">Key findings</h1>
                <p className="page-sub">
                  Saved analysis results. You only need to run analysis once per
                  image; reopen the case to see them again.
                </p>
                {!report ? (
                  <div className="empty">
                    Run <strong>Analyze</strong> on a data source first. Results
                    are stored automatically.
                  </div>
                ) : (
                  <>
                    <div className="panel review-panel">
                      <div className="panel-title">Items for human review</div>
                      <div className="panel-body">
                        <p style={{ color: "var(--text-2)", fontSize: 14 }}>
                          These items may matter in court. Open a path to extract
                          or preview when the disk image is still available.
                        </p>
                        {(report.suspicious_files || report.suspicious || []).length ? (
                          <div style={{ marginBottom: 12 }}>
                            <strong>Suspicious / notable files</strong>
                            {(report.suspicious_files || report.suspicious || [])
                              .slice(0, 12)
                              .map((d, i) => (
                                <div key={i} className="finding">
                                  <div>
                                    <strong>{d.name || d.path}</strong>
                                    <small className="mono">{d.path}</small>
                                    <div style={{ marginTop: 4 }}>
                                      <button type="button" className="btn btn-sm" disabled={busy} onClick={() => extractArtifact(d)}>Extract</button>
                                      {/\.(jpg|jpeg|png|gif|bmp|webp)$/i.test(String(d.path || d.name || "")) && (
                                        <button type="button" className="btn btn-sm" style={{ marginLeft: 6 }} disabled={busy} onClick={() => previewImage(d)}>Preview</button>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                          </div>
                        ) : null}
                        {(report.documents_of_interest || []).length ? (
                          <div style={{ marginBottom: 12 }}>
                            <strong>Documents of interest (incl. possible encryption)</strong>
                            {(report.documents_of_interest || []).slice(0, 12).map((d, i) => (
                              <div key={i} className="finding">
                                <div>
                                  <strong>{d.name || d.path}</strong>
                                  <small className="mono">{d.path}</small>
                                  <div style={{ marginTop: 4 }}>
                                    <button type="button" className="btn btn-sm" disabled={busy} onClick={() => extractArtifact(d)}>Extract</button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {(report.deleted_files || []).length ? (
                          <div>
                            <strong>Deleted / recovered paths (sample)</strong>
                            {(report.deleted_files || []).slice(0, 8).map((d, i) => (
                              <div key={i} className="finding">
                                <div>
                                  <strong>{d.name || d.path}</strong>
                                  <small className="mono">{d.path}</small>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {!(report.suspicious_files || report.suspicious || []).length &&
                          !(report.documents_of_interest || []).length &&
                          !(report.deleted_files || []).length && (
                            <div className="empty">No high-priority review items in this presentation.</div>
                          )}
                      </div>
                    </div>

                    <div className="panel" style={{ marginTop: 14 }}>
                      <div className="panel-title">AI summary for the court</div>
                      <div className="panel-body">
                        <p style={{ color: "var(--text-2)", fontSize: 14 }}>
                          Creates a simple-language summary from the stored findings.
                          {aiConfigured === false && (
                            <>
                              {" "}
                              Set <code>MORPHEUS_AI_API_KEY</code> on the API server
                              (OpenAI-compatible) to enable it.
                            </>
                          )}
                        </p>
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={aiBusy || busy}
                          onClick={requestAiSummary}
                        >
                          {aiBusy ? "Writing summary…" : "Generate AI summary"}
                        </button>
                        {aiSummary ? (
                          <pre className="ai-summary-box">{aiSummary}</pre>
                        ) : null}
                      </div>
                    </div>

                    <FindingsReport
                      report={report}
                      busy={busy}
                      onExtract={extractArtifact}
                      onPreviewImage={previewImage}
                      imagePreviewUrl={imagePreviewUrl}
                      imagePreviewName={imagePreviewName}
                    />
                  </>
                )}
              </>
            )}

            {view === "custody" && (
              <>
                <h1 className="page-title">Chain of custody</h1>
                <p className="page-sub">
                  Actions recorded for this case. This log is kept even when a case is closed or marked deleted.
                </p>
                <div className="panel">
                  <div className="panel-body">
                    {!(custody?.custody_timeline || []).length ? (
                      <div className="empty">No events.</div>
                    ) : (
                      (custody.custody_timeline || []).map((e, i) => (
                        <div key={i} className="finding">
                          <span className="dot" />
                          <div>
                            <strong>
                              {e.what} — {e.who}
                            </strong>
                            <small>{e.when}</small>
                            {e.detail ? (
                              <small style={{ display: "block" }}>
                                {e.detail}
                              </small>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}

                  </div>
                </div>
              </>
            )}

            {view === "extracted" && (
              <>
                <h1 className="page-title">Extracted files</h1>
                <p className="page-sub">
                  Files extracted from this case during artifact review. Each extraction is recorded in the chain of custody.
                </p>
                <div className="panel">
                  <div className="panel-title">Extraction history · {extractionLog.length}</div>
                  <div className="panel-body" style={{ padding: 0 }}>
                    {!extractionLog.length ? (
                      <div className="empty">No files have been extracted from this case.</div>
                    ) : (
                      <table className="data">
                        <thead>
                          <tr>
                            <th>Extracted file</th>
                            <th>Source path</th>
                            <th>Extracted by</th>
                            <th>Time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {extractionLog.map((entry) => (
                            <tr key={entry.id}>
                              <td className="mono">{entry.file_path?.split(/[\\\\/]/).pop() || "Unknown file"}</td>
                              <td className="mono" style={{ wordBreak: "break-all" }}>{entry.file_path || "—"}</td>
                              <td>{entry.actor || "—"}</td>
                              <td>{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "reports" && (
              <>
                <h1 className="page-title">Reports</h1>
                <p className="page-sub">
                  Download a case PDF (findings + integrity + custody), or review
                  the full analysis presentation below.
                </p>
                <div className="panel">
                  <div className="panel-title">Case report (PDF)</div>
                  <div className="panel-body">
                    <p style={{ color: "var(--text-2)", fontSize: 14 }}>
                      Includes integrity status, key analysis findings from the
                      last completed run, and the full chain of custody.
                    </p>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={downloadReport}
                    >
                      Download report
                    </button>
                  </div>
                </div>
                <div className="panel" style={{ marginTop: 16 }}>
                  <div className="panel-title">Full analysis report</div>
                  <div className="panel-body">
                    {!report ? (
                      <div className="empty">
                        No analysis yet. Open Evidence / Key findings and run
                        Analyze on a data source.
                      </div>
                    ) : (
                      <>
                        <div className="stats" style={{ marginBottom: 12 }}>
                          <div className="stat">
                            <label>Files scanned</label>
                            <b>{report?.case_summary?.total_files_scanned ?? "—"}</b>
                          </div>
                          <div className="stat">
                            <label>Deleted</label>
                            <b>
                              {report?.case_summary?.total_deleted_recovered ??
                                report?.case_summary?.total_deleted_found ??
                                "—"}
                            </b>
                          </div>
                          <div className="stat">
                            <label>Emails</label>
                            <b>{report?.case_summary?.total_emails_parsed ?? "—"}</b>
                          </div>
                          <div className="stat">
                            <label>Browser history</label>
                            <b>
                              {report?.case_summary?.total_browser_history_entries ??
                                "—"}
                            </b>
                          </div>
                        </div>
                        <p style={{ color: "var(--text-2)", fontSize: 14 }}>
                          Detailed tabs (documents, emails, web, images) are on{" "}
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => setView("findings")}
                          >
                            Key findings
                          </button>
                          . Use <strong>Download report</strong> above for a
                          PDF that also includes chain of custody.
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "about" && (
              <>
                <h1 className="page-title">About &amp; roadmap</h1>
                <div className="panel">
                  <div className="panel-body">
                    <div className="note-card" style={{ marginTop: 0 }}>
                      <h4>Disk images</h4>
                      <p style={{ margin: 0 }}>
                        Analysis targets forensic images on the Morpheus host.
                        Paste the full path when registering a data source.
                      </p>
                    </div>
                    <div className="note-card">
                      <h4>Evidence collection</h4>
                      <p style={{ margin: 0 }}>
                        Non-image case files — coming soon. Integrity already
                        applies to disk images you register.
                      </p>
                    </div>
                    <div className="note-card">
                      <h4>Mobile</h4>
                      <p style={{ margin: 0 }}>
                        Android and iOS acquisition and analysis — coming soon.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {addSrcOpen && (
        <Modal title="Add data source" onClose={() => setAddSrcOpen(false)}>
          <form onSubmit={addDataSource}>
            <div className="note-card" style={{ marginTop: 0 }}>
              <h4>How to add a disk image</h4>
              <p style={{ margin: 0 }}>
                Copy the image into a Morpheus Evidence folder on this
                workstation when possible. In the desktop app use{" "}
                <strong>Browse…</strong> to pick the file (full path is filled
                automatically), or paste the path below.
              </p>
            </div>
            <label>Full path on Morpheus host</label>
            <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
              <input
                required
                placeholder="/path/to/image.E01"
                value={srcForm.file_path}
                onChange={(e) =>
                  setSrcForm({ ...srcForm, file_path: e.target.value })
                }
                style={{ flex: 1 }}
              />
              {typeof window !== "undefined" && window.electronAPI?.openFile && (
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={async () => {
                    const selected = await window.electronAPI.openFile({
                      title: "Select evidence disk image",
                    });
                    if (!selected) return;
                    const filePath = Array.isArray(selected)
                      ? selected[0]
                      : selected;
                    const base =
                      String(filePath).split(/[/\\]/).pop() || "";
                    setSrcForm((s) => ({
                      ...s,
                      file_path: filePath,
                      label: s.label || base,
                      fileName: base,
                    }));
                  }}
                >
                  Browse…
                </button>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() =>
                  setSrcForm((s) => ({
                    ...s,
                    file_path: DEMO_PATH,
                    label: s.label || "2020JimmyWilson.E01",
                  }))
                }
              >
                Fill demo path
              </button>
            </div>
            <label>Label</label>
            <input
              value={srcForm.label}
              onChange={(e) =>
                setSrcForm({ ...srcForm, label: e.target.value })
              }
            />
            <label>Collected by</label>
            <input
              value={srcForm.collected_by || user}
              onChange={(e) =>
                setSrcForm({ ...srcForm, collected_by: e.target.value })
              }
            />
            {hashing && (
              <ProgressBar
                value={null}
                label="Hashing…"
                sub={`Elapsed ${hashElapsed}s`}
              />
            )}
            {error && <p className="err-text">{error}</p>}
            <footer>
              <button
                type="button"
                className="btn"
                onClick={() => setAddSrcOpen(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy}
              >
                {hashing ? "Hashing…" : "Register"}
              </button>
            </footer>
          </form>
        </Modal>
      )}
      {toast && <Toast {...toast} />}
      {addEvOpen && (
        <Modal title="Add evidence artifact" onClose={() => setAddEvOpen(false)}>
          <form onSubmit={addEvidenceArtifact}>
            <div className="note-card" style={{ marginTop: 0 }}>
              <h4>Non-image files</h4>
              <p style={{ margin: 0 }}>
                Photos, exports, notes, or other files. They get a fingerprint and
                a custody entry, the same idea as disk images.
              </p>
            </div>
            <label>Full path on this machine</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                required
                className="mono"
                style={{ flex: 1 }}
                value={evForm.file_path}
                onChange={(e) => setEvForm({ ...evForm, file_path: e.target.value })}
                placeholder="/path/to/file"
              />
              {typeof window !== "undefined" && window.electronAPI?.openFile && (
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={async () => {
                    const selected = await window.electronAPI.openFile({
                      title: "Select evidence file",
                      filters: [{ name: "All files", extensions: ["*"] }],
                    });
                    if (!selected) return;
                    const filePath = Array.isArray(selected) ? selected[0] : selected;
                    setEvForm((s) => ({ ...s, file_path: filePath }));
                  }}
                >
                  Browse…
                </button>
              )}
            </div>
            <label>Notes</label>
            <input
              value={evForm.notes}
              onChange={(e) => setEvForm({ ...evForm, notes: e.target.value })}
            />
            {error ? <p style={{ color: "#c44" }}>{error}</p> : null}
            <button type="submit" className="btn btn-primary" disabled={busy}>
              Register evidence
            </button>
          </form>
        </Modal>
      )}

      {pathFixOpen && pathFixItem && (
        <Modal
          title="Update evidence path"
          onClose={() => {
            setPathFixOpen(false);
            setPathFixItem(null);
            setError("");
          }}
        >
          <form onSubmit={submitPathFix}>
            <div className="note-card" style={{ marginTop: 0 }}>
              <h4>File not found at registered path</h4>
              <p style={{ margin: 0 }}>
                Provide the new absolute path on this machine. The file must still
                match the original SHA-256 fingerprint or the update will be
                rejected.
              </p>
            </div>
            <label>Previous path</label>
            <input
              readOnly
              className="mono"
              value={pathFixItem.stored_path || ""}
            />
            <label>New path</label>
            <input
              required
              className="mono"
              placeholder="/path/to/image.E01"
              value={pathFixValue}
              onChange={(e) => setPathFixValue(e.target.value)}
            />
            {error ? (
              <p style={{ color: "#c44", fontSize: 13 }}>{error}</p>
            ) : null}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                Verify &amp; save path
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setPathFixOpen(false);
                  setPathFixItem(null);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

    </div>
  );
}
