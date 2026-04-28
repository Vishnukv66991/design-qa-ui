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

  const handleAnalyze = async () => {
    if (!file || !requirements) {
      alert("Upload file and add requirements");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("requirements", requirements);
    formData.append("guidance", guidance);

    try {
      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to analyze");
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      alert("Error: " + error.message);
    }
  };

  return (
    <div style={styles.container}>
      <h1>Design QA Tool</h1>

      <UploadBox setFile={setFile} />

      <RequirementsInput
        value={requirements}
        setValue={setRequirements}
      />

      <ModelGuidance
        value={guidance}
        setValue={setGuidance}
      />

      <button style={styles.button} onClick={handleAnalyze}>
        Analyze
      </button>

      <ResultPanel result={result} />
    </div>
  );
}

const styles = {
  container: {
    maxWidth: "700px",
    margin: "auto",
    padding: "20px",
  },
  button: {
    marginTop: "20px",
    padding: "10px",
    cursor: "pointer",
  },
};

export default Dashboard;