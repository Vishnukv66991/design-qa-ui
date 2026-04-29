import React, { useState } from "react";
import UploadBox from "../components/UploadBox";
import RequirementsInput from "../components/RequirementsInput";
import ModelGuidance from "../components/ModelGuidance";
import ResultPanel from "../components/ResultPanel";

function Dashboard() {
  const [file, setFile] = useState(null);
  const [requirements, setRequirements] = useState("");
  const [guidance, setGuidance] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Keep a local preview URL so ResultPanel can show "original" side-by-side
  const [originalPreview, setOriginalPreview] = useState(null);

  const handleSetFile = (f) => {
    setFile(f);
    setOriginalPreview(f ? URL.createObjectURL(f) : null);
    // Clear previous result when a new file is chosen
    setResult(null);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError("Please upload a design image first.");
      return;
    }
    if (!requirements.trim()) {
      setError("Please enter the client requirements.");
      return;
    }

    setError(null);
    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("requirements", requirements);
    formData.append("guidance", guidance);

    try {
      // FIX: Use relative URL — CRA proxy in package.json routes this to localhost:8000
      const response = await fetch("/analyze", {
        method: "POST",
        body: formData,
      });

      // FIX: Read the actual error message from the backend response
      if (!response.ok) {
        let errorMessage = `Server error (${response.status})`;
        try {
          const errData = await response.json();
          if (errData.error) errorMessage = errData.error;
        } catch (_) {}
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const canAnalyze = file && requirements.trim() && !loading;

  return (
    <div className="tool-layout">

      {/* ── Top Bar ── */}
      <header className="tool-topbar">
        <div className="tool-topbar__logo">
          <div className="tool-topbar__icon">🔍</div>
          <span className="tool-topbar__name">Design QA Tool</span>
          <span className="tool-topbar__version">v1.0</span>
        </div>
        <div className="tool-topbar__status">
          <span className="status-dot" />
          Backend connected
        </div>
      </header>

      {/* ── Body ── */}
      <div className="tool-body">

        {/* ── LEFT: Input Sidebar ── */}
        <aside className="tool-sidebar">

          <UploadBox setFile={handleSetFile} />
          <RequirementsInput value={requirements} setValue={setRequirements} />
          <ModelGuidance value={guidance} setValue={setGuidance} />

          {/* Analyze button + error */}
          <div className="panel" style={{ border: "none", padding: "16px" }}>
            {error && (
              <div className="error-banner">
                ⚠ {error}
              </div>
            )}
            <button
              id="analyze-btn"
              className="btn-analyze"
              onClick={handleAnalyze}
              disabled={!canAnalyze}
              style={{ marginTop: error ? "10px" : "0" }}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Analyzing...
                </>
              ) : (
                <>🔍 Run Analysis</>
              )}
            </button>
          </div>

        </aside>

        {/* ── RIGHT: Results Panel ── */}
        <main className="tool-main">
          {result ? (
            <ResultPanel result={result} originalPreview={originalPreview} />
          ) : (
            <div className="tool-empty-state">
              <span className="tool-empty-state__icon">🎨</span>
              <span className="tool-empty-state__title">No Analysis Yet</span>
              <span className="tool-empty-state__sub">
                Upload a design image, enter the requirements, then click <strong>Run Analysis</strong>.
              </span>
            </div>
          )}
        </main>

      </div>
    </div>
  );
}

export default Dashboard;