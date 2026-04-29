import React, { useState, useEffect, useRef } from "react";

function UploadBox({ setFile }) {
  const [preview, setPreview] = useState(null);
  const [fileName, setFileName] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const previewUrlRef = useRef(null);

  // FIX: Revoke old object URLs to prevent memory leaks
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  const processFile = (file) => {
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Only image files are allowed.");
      return;
    }

    // Revoke previous URL before creating a new one
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }

    const imageUrl = URL.createObjectURL(file);
    previewUrlRef.current = imageUrl;

    setFile(file);
    setPreview(imageUrl);
    setFileName(file.name);
  };

  const handleChange = (e) => processFile(e.target.files[0]);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    processFile(e.dataTransfer.files[0]);
  };

  return (
    <div className="panel">
      <div className="panel__header">
        <span className="panel__header-icon">🖼</span>
        Design File
      </div>
      <div className="panel__body">
        <div
          className={`upload-zone ${isDragOver ? "dragover" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
        >
          <input
            id="file-input"
            type="file"
            accept="image/*"
            onChange={handleChange}
          />
          <span className="upload-zone__icon">📂</span>
          <span className="upload-zone__label">
            {fileName ? "Click to change file" : "Drop image here or click to browse"}
          </span>
          <span className="upload-zone__sub">PNG, JPG, WEBP · Max 10 MB</span>
        </div>

        {preview && (
          <div className="upload-preview">
            <img src={preview} alt="preview" />
            <div className="upload-preview__info">
              <span className="upload-preview__dot" />
              {fileName}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadBox;