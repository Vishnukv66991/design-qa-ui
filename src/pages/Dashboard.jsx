import React, { useEffect, useState } from "react";
import UploadBox from "../components/UploadBox";
import RequirementsInput from "../components/RequirementsInput";
import ModelGuidance from "../components/ModelGuidance";
import ResultPanel from "../components/ResultPanel";

function Dashboard() {
  const [file, setFile] = useState(null);
  const [requirements, setRequirements] = useState("");
  const [guidance, setGuidance] = useState("");
  const [selectedModule, setSelectedModule] = useState("all");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [originalPreview, setOriginalPreview] = useState(null);

  useEffect(() => {
    return () => {
      if (originalPreview) {
        URL.revokeObjectURL(originalPreview);
      }
    };
  }, [originalPreview]);

  const handleSetFile = (f) => {
    if (originalPreview) {
      URL.revokeObjectURL(originalPreview);
    }
    setFile(f);
    const previewable = f && (f.type.startsWith("image/") || f.type.startsWith("video/"));
    setOriginalPreview(previewable ? URL.createObjectURL(f) : null);
    setResult(null);
    setError(null);
  };

  const API_BASE = process.env.REACT_APP_API_BASE_URL || "";

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
      const url = `${API_BASE}/analyze`;
      const response = await fetch(url, {
        method: "POST",
        body: formData,
      });

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
          <div className="panel">
            <div className="panel__header">
              <span className="panel__header-icon">🧪</span>
              Module Scope
            </div>
            <div className="panel__body">
              <div className="form-field">
                <label className="form-label" htmlFor="module-select">
                  Choose module(s) to test
                </label>
                <select
                  id="module-select"
                  className="form-select"
                  value={selectedModule}
                  onChange={(e) => setSelectedModule(e.target.value)}
                >
                  <option value="all">All Modules</option>
                  <option value="image_quality">Image Quality</option>
                  <option value="layout">Layout & Alignment</option>
                  <option value="color_contrast">Color & Contrast</option>
                  <option value="typography_ocr">Typography + OCR</option>
                  <option value="density">Spacing & Density</option>
                  <option value="image_forensics">Image Forensics</option>
                  <option value="color_palette">Color Palette</option>
                  <option value="edge_precision">Edge Precision</option>
                  <option value="duplicates_overlaps">Duplicates & Overlaps</option>
                  <option value="exposure_analysis">Exposure</option>
                  <option value="cta_detection">CTA Detection</option>
                  <option value="visual_hierarchy">Visual Hierarchy</option>
                  <option value="spelling_locale">Spelling & Locale</option>
                </select>
              </div>
            </div>
          </div>

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
                Upload an image/video/PDF, enter the requirements, choose module scope, then click <strong>Run Analysis</strong>.
              </span>
            </div>
          )}
        </main>

      </div>
    </div>
  );
}

export default Dashboard;