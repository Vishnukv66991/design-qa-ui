import React, { useState, useEffect, useRef } from "react";

function UploadBox({ setFile }) {
  const [preview, setPreview] = useState(null);
  const [fileName, setFileName] = useState(null);
  const [fileType, setFileType] = useState(null);
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

    const isImage = file.type.startsWith("image/");
    const isVideo = file.type.startsWith("video/");
    const isPdf = file.type === "application/pdf";
    if (!isImage && !isVideo && !isPdf) {
      alert("Only image, video, or PDF files are allowed.");
      return;
    }

    // Revoke previous URL before creating a new one
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }

    const previewUrl = (isImage || isVideo) ? URL.createObjectURL(file) : null;
    previewUrlRef.current = previewUrl;

    setFile(file);
    setPreview(previewUrl);
    setFileName(file.name);
    setFileType(file.type);
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
            accept="image/*,video/*,application/pdf"
            onChange={handleChange}
          />
          <span className="upload-zone__icon">📂</span>
          <span className="upload-zone__label">
            {fileName ? "Click to change file" : "Drop image here or click to browse"}
          </span>
          <span className="upload-zone__sub">Image / Video / PDF · Up to configured limits</span>
        </div>

        {preview && (
          <div className="upload-preview">
            {fileType && fileType.startsWith("video/") ? (
              <video src={preview} controls />
            ) : (
              <img src={preview} alt="preview" />
            )}
            <div className="upload-preview__info">
              <span className="upload-preview__dot" />
              {fileName}
            </div>
          </div>
        )}
        {!preview && fileName && (
          <div className="upload-preview" style={{ padding: 12 }}>
            <div className="upload-preview__info" style={{ borderTop: "none", padding: 0 }}>
              <span className="upload-preview__dot" />
              {fileName} (preview not available for this file type)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadBox;