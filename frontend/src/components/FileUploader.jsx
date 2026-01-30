import React, { useState } from 'react';
import { Upload, X, FileText, Video, Music, Loader2 } from 'lucide-react';
import { useFileUpload } from '../hooks/useChat';
import { uploadFile, uploadMultipleFiles } from '../services/api';
import './FileUploader.css';

const FileUploader = ({ onUploadSuccess }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const { uploading, progress, error, upload } = useFileUpload();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles(files);
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles(files);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    try {
      let result;
      if (selectedFiles.length === 1) {
        result = await upload(selectedFiles[0], uploadFile);
      } else {
        result = await upload(selectedFiles, uploadMultipleFiles);
      }

      setSelectedFiles([]);
      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };

  const removeFile = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const getFileIcon = (file) => {
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext === 'pdf') return <FileText size={20} />;
    if (['mp4', 'avi', 'mov'].includes(ext)) return <Video size={20} />;
    if (['mp3', 'wav', 'm4a'].includes(ext)) return <Music size={20} />;
    return <FileText size={20} />;
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="file-uploader">
      <div
        className={`drop-zone ${dragActive ? 'active' : ''} ${uploading ? 'uploading' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload size={48} />
        <h3>Drag & Drop files here</h3>
        <p>or</p>
        <label className="file-select-button">
          Choose Files
          <input
            type="file"
            multiple
            accept=".pdf,.mp3,.wav,.mp4,.avi,.mov,.m4a"
            onChange={handleFileSelect}
            disabled={uploading}
          />
        </label>
        <p className="supported-formats">
          Supported: PDF, Audio (MP3, WAV, M4A), Video (MP4, AVI, MOV)
        </p>
      </div>

      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <h4>Selected Files ({selectedFiles.length})</h4>
          <div className="files-list">
            {selectedFiles.map((file, index) => (
              <div key={index} className="file-item">
                <div className="file-info">
                  <div className="file-icon">{getFileIcon(file)}</div>
                  <div className="file-details">
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">{formatFileSize(file.size)}</div>
                  </div>
                </div>
                {!uploading && (
                  <button
                    className="remove-button"
                    onClick={() => removeFile(index)}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            ))}
          </div>

          {!uploading ? (
            <button className="upload-button" onClick={handleUpload}>
              <Upload size={18} />
              Upload {selectedFiles.length} {selectedFiles.length === 1 ? 'File' : 'Files'}
            </button>
          ) : (
            <div className="upload-progress">
              <Loader2 className="spinner" size={20} />
              <span>Uploading... {progress}%</span>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {error && (
            <div className="upload-error">
              <p>❌ {error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FileUploader;
