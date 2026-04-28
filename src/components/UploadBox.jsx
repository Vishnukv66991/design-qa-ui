import React, { useState } from "react";

function UploadBox({ setFile }) {
  const [preview, setPreview] = useState(null);

  const handleFile = (e) => {
    const file = e.target.files[0];

    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Only image files allowed");
      return;
    }

    setFile(file);

    // Create preview
    const imageUrl = URL.createObjectURL(file);
    setPreview(imageUrl);
  };

  return (
    <div style={styles.box}>
      <h3>Upload Design</h3>

      <input type="file" onChange={handleFile} />

      {/* Show preview */}
      {preview && (
        <div style={styles.previewContainer}>
          <p>Preview:</p>
          <img src={preview} alt="preview" style={styles.image} />
        </div>
      )}
    </div>
  );
}

const styles = {
  box: {
    border: "2px dashed #aaa",
    padding: "20px",
    textAlign: "center",
  },
  previewContainer: {
    marginTop: "15px",
  },
  image: {
    maxWidth: "100%",
    height: "200px",
    objectFit: "contain",
    border: "1px solid #ddd",
    padding: "5px",
  },
};

export default UploadBox;