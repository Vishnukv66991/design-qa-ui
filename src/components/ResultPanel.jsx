import React from "react";

// Map severity → CSS class
const SEVERITY_CLASS = {
  high:   "issue-item--fail",
  medium: "issue-item--warn",
  low:    "issue-item--pass",
};

const SEVERITY_LABEL = {
  high:   "HIGH",
  medium: "MED",
  low:    "LOW",
};

// Score gauge colour
function scoreColor(s) {
  if (s >= 80) return "var(--pass)";
  if (s >= 55) return "var(--warn)";
  return "var(--fail)";
}

function ResultPanel({ result, originalPreview }) {
  if (!result) return null;

  const {
    score,
    summary,
    issues = [],
    strengths = [],
    quick_fixes = [],
    meta = {},
    module_status = {},
    requirements_coverage = {},
    content_type = "",
  } = result;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>

      {/* ── Score header ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        {/* Circular score */}
        <div style={{
          width: 80, height: 80, borderRadius: "50%",
          border: `4px solid ${scoreColor(score)}`,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          flexShrink: 0,
          boxShadow: `0 0 16px ${scoreColor(score)}44`,
        }}>
          <span style={{ fontSize: 22, fontWeight: 700, color: scoreColor(score), lineHeight: 1 }}>
            {score}
          </span>
          <span style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 1 }}>
            /100
          </span>
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span className="result-title">QA Report</span>
            <span className={`result-badge ${score >= 80 ? "result-badge--pass" : "result-badge--warn"}`}>
              {issues.filter(i => i.severity === "high").length} Critical
            </span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
            {summary}
          </p>
        </div>
      </div>

      {/* ── Score bar ── */}
      <div style={{ height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${score}%`,
          background: scoreColor(score),
          borderRadius: 2,
          transition: "width 0.8s ease",
        }} />
      </div>

      {/* ── Quick Fixes ── */}
      {quick_fixes.length > 0 && (
        <div className="result-section">
          <div className="result-section__title">⚡ Top Quick Fixes</div>
          <div className="result-section__body">
            <ol style={{ paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
              {quick_fixes.map((fix, i) => (
                <li key={i} style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  {fix}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {/* ── Requirement Coverage ── */}
      {requirements_coverage && (
        <div className="result-section">
          <div className="result-section__title">📌 Requirements Coverage</div>
          <div className="result-section__body">
            <div className="meta-row">
              <span className="meta-row__key">Covered modules</span>
              <span className="meta-row__val">
                {(requirements_coverage.covered_modules || []).join(", ") || "None matched"}
              </span>
            </div>
            <div className="meta-row">
              <span className="meta-row__key">Missing requested modules</span>
              <span className="meta-row__val">
                {(requirements_coverage.missing_modules || []).join(", ") || "None"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Module Status ── */}
      {module_status && Object.keys(module_status).length > 0 && (
        <div className="result-section">
          <div className="result-section__title">🧩 Module Run Status</div>
          <div className="result-section__body">
            {Object.entries(module_status).map(([key, val]) => (
              <div className="meta-row" key={key}>
                <span className="meta-row__key">{key.replace(/_/g, " ")}</span>
                <span className="meta-row__val">
                  {val.status}{val.reason ? ` (${val.reason})` : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Issues ── */}
      <div className="result-section">
        <div className="result-section__title">
          🔍 Issues Found ({issues.length})
        </div>
        <div className="result-section__body">
          {issues.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--pass)" }}>✅ No issues detected.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {issues.map((issue, i) => (
                <div key={i} className={`issue-item ${SEVERITY_CLASS[issue.severity] || "issue-item--pass"}`}
                  style={{ flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
                  {/* Header row */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                    <span style={{
                      fontSize: 9, fontWeight: 700, letterSpacing: 1,
                      padding: "2px 6px", borderRadius: 4,
                      background: "rgba(0,0,0,0.2)",
                    }}>
                      {SEVERITY_LABEL[issue.severity]}
                    </span>
                    <span style={{ fontSize: 10, opacity: 0.7, textTransform: "uppercase", letterSpacing: 0.5 }}>
                      {issue.category}
                    </span>
                    <span style={{ marginLeft: "auto", fontSize: 10, opacity: 0.6 }}>
                      {issue.confidence ? `${Math.round(issue.confidence * 100)}% conf.` : ""}
                    </span>
                  </div>
                  {/* Problem */}
                  <p style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>{issue.problem}</p>
                  {/* Impact */}
                  <p style={{ fontSize: 12, opacity: 0.8, margin: 0 }}>
                    <strong>Impact:</strong> {issue.impact}
                  </p>
                  {/* Suggestion */}
                  <p style={{ fontSize: 12, opacity: 0.8, margin: 0 }}>
                    <strong>Fix:</strong> {issue.suggestion}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Strengths ── */}
      {strengths.length > 0 && (
        <div className="result-section">
          <div className="result-section__title">✅ Strengths</div>
          <div className="result-section__body">
            <ul className="issue-list">
              {strengths.map((s, i) => (
                <li key={i} className="issue-item issue-item--pass">{s}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ── Image Comparison ── */}
      {result.processed_file && content_type.startsWith("image/") && (
        <div className="result-section">
          <div className="result-section__title">🖼 Image Comparison</div>
          <div className="result-section__body">
            <div className="image-grid">
              {originalPreview && (
                <div className="image-card">
                  <div className="image-card__label">Original</div>
                  <img src={originalPreview} alt="Original design" />
                </div>
              )}
              <div className="image-card">
                <div className="image-card__label">Grayscale QA View</div>
                <img src={`/uploads/${result.processed_file}`} alt="Grayscale" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Meta / Debug ── */}
      {meta && Object.keys(meta).length > 0 && (
        <div className="result-section">
          <div className="result-section__title">📊 Analysis Metadata</div>
          <div className="result-section__body">
            {Object.entries(meta).map(([k, v]) => (
              <div className="meta-row" key={k}>
                <span className="meta-row__key">{k.replace(/_/g, " ")}</span>
                <span className="meta-row__val">
                  {Array.isArray(v) ? (v.length ? v.join(", ") : "—") : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ResultPanel;
