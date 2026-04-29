import React from "react";

function ModelGuidance({ value, setValue }) {
  return (
    <div className="panel">
      <div className="panel__header">
        <span className="panel__header-icon">🧭</span>
        Model Guidance
        <span style={{ marginLeft: "auto" }}>
          <span className="form-label__badge">Optional</span>
        </span>
      </div>
      <div className="panel__body">
        <div className="form-field">
          <label className="form-label" htmlFor="guidance-input">
            Focus hints for analysis
          </label>
          <textarea
            id="guidance-input"
            className="form-textarea"
            rows={3}
            placeholder="e.g. Focus on typography consistency and spacing rhythm..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}

export default ModelGuidance;