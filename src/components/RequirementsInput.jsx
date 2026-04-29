import React from "react";

function RequirementsInput({ value, setValue }) {
  return (
    <div className="panel">
      <div className="panel__header">
        <span className="panel__header-icon">📋</span>
        Client Requirements
      </div>
      <div className="panel__body">
        <div className="form-field">
          <label className="form-label" htmlFor="requirements-input">
            Describe what the design should follow
          </label>
          <textarea
            id="requirements-input"
            className="form-textarea"
            rows={4}
            placeholder="e.g. Button should be blue, font size 16px, spacing 24px, neon dark theme..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}

export default RequirementsInput;