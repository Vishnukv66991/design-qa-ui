import React from "react";

function ModelGuidance({ value, setValue }) {
  return (
    <div style={styles.box}>
      <h3>Model Guidance (Optional)</h3>
      <textarea
        rows="4"
        style={{ width: "100%" }}
        placeholder="e.g. Focus more on typography and spacing consistency"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
    </div>
  );
}

const styles = {
  box: {
    border: "1px solid #ccc",
    padding: "15px",
    marginTop: "15px",
  },
};

export default ModelGuidance;