import React from "react";

function RequirementsInput({ value, setValue }) {
  return (
    <div style={styles.box}>
      <h3>Client Requirements</h3>
      <textarea
        rows="4"
        style={{ width: "100%" }}
        placeholder="e.g. Button should be blue, spacing 16px"
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

export default RequirementsInput;