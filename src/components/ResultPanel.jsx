import React from "react";

function ResultPanel({ result }) {
  if (!result) return null;

  return (
    <div style={styles.box}>
      <h3>Analysis Result</h3>

      {result.status === "success" && (
        <div style={styles.success}>
          ✅ Submit Successfully!
          <div style={styles.subMessage}>{result.message}</div>
        </div>
      )}

      <div style={styles.section}>
        <strong>File:</strong> {result.original_name}
      </div>

      <div style={styles.section}>
        <strong>Requirements:</strong>
        <p style={styles.text}>{result.requirements}</p>
      </div>

      {result.guidance && (
        <div style={styles.section}>
          <strong>Guidance:</strong>
          <p style={styles.text}>{result.guidance}</p>
        </div>
      )}

      <div style={styles.section}>
        <strong>Image Issues:</strong>
        <ul style={styles.list}>
          {result.issues &&
            result.issues.map((issue, index) => (
              <li key={index} style={styles.issueItem}>
                {issue}
              </li>
            ))}
        </ul>
      </div>

      {result.processed_file && (
        <div style={styles.section}>
          <strong>Processed Image (Grayscale):</strong>
          <div style={styles.imageBox}>
            <img
              src={`http://127.0.0.1:8000/uploads/${result.processed_file}`}
              alt="Processed"
              style={styles.image}
            />
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  box: {
    border: "1px solid #4CAF50",
    padding: "20px",
    marginTop: "20px",
    background: "#f0f8f0",
    borderRadius: "8px",
  },
  success: {
    color: "#2e7d32",
    fontWeight: "bold",
    fontSize: "16px",
    marginBottom: "15px",
    padding: "10px",
    background: "#c8e6c9",
    borderRadius: "4px",
  },
  section: {
    marginTop: "15px",
  },
  text: {
    margin: "5px 0",
    padding: "8px",
    background: "#fff",
    borderRadius: "4px",
  },
  list: {
    margin: "5px 0",
    paddingLeft: "20px",
  },
  issueItem: {
    margin: "5px 0",
    color: "#d32f2f",
  },
  imageBox: {
    marginTop: "10px",
  },
  image: {
    maxWidth: "100%",
    maxHeight: "300px",
    border: "1px solid #ccc",
    borderRadius: "4px",
  },
};

export default ResultPanel;
