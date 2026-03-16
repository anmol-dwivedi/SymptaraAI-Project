import { useState, useRef, useCallback } from "react";
import { Upload, FileText, X, Paperclip } from "lucide-react";

interface FileDropZoneProps {
  onUpload: (file: File) => void;
  onRemoveFile: () => void;
  isUploading: boolean;
  uploadedFileName: string | null;
}

const ACCEPT_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"];
const ACCEPT_EXT = ".pdf,.jpg,.jpeg,.png,.webp";

const FileDropZone = ({ onUpload, onRemoveFile, isUploading, uploadedFileName }: FileDropZoneProps) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file && ACCEPT_TYPES.includes(file.type)) {
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="border-b border-border px-4 py-3">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept={ACCEPT_EXT}
        className="hidden"
      />

      {/* Uploaded file badge */}
      {uploadedFileName && (
        <div className="mb-2 flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs text-primary">
            <FileText size={12} />
            {uploadedFileName}
            <button onClick={onRemoveFile} className="ml-1 hover:text-destructive transition-colors">
              <X size={12} />
            </button>
          </span>
        </div>
      )}

      {/* Upload progress */}
      {isUploading && (
        <div className="mb-2">
          <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-primary" />
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">Analyzing file...</p>
        </div>
      )}

      {/* Drop zone */}
      {!uploadedFileName && !isUploading && (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`group flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed p-4 transition-all ${
            isDragOver
              ? "border-primary bg-primary/5"
              : "border-border hover:border-muted-foreground/40 hover:bg-muted/20"
          }`}
        >
          <Upload
            size={20}
            className={`mb-2 transition-colors ${
              isDragOver ? "text-primary" : "text-muted-foreground group-hover:text-foreground/60"
            }`}
          />
          <p className="text-xs text-muted-foreground">
            <span className="font-medium">Drag & Drop Files</span> — PDFs, Reports, X-Rays, Images
          </p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            className="mt-1.5 text-[11px] font-medium text-primary hover:underline"
          >
            Browse Files
          </button>
        </div>
      )}
    </div>
  );
};

export default FileDropZone;
