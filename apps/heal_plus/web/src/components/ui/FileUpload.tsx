"use client";

import { UploadCloud } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { DragEvent, ChangeEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../../lib/utils";

type FileStatus = "idle" | "dragging" | "uploading" | "error";

export interface FileError {
  message: string;
  code: string;
}

export interface FileUploadProps {
  onUploadSuccess?: (file: File) => void;
  onUploadError?: (error: FileError) => void;
  acceptedFileTypes?: string[];
  maxFileSize?: number;
  currentFile?: File | null;
  onFileRemove?: () => void;
  /** Duration in milliseconds for the upload simulation. Defaults to 1200ms, 0 for no simulation */
  uploadDelay?: number;
  validateFile?: (file: File) => FileError | null;
  className?: string;
  title?: string;
  description?: string;
}

const DEFAULT_MAX_FILE_SIZE = 15 * 1024 * 1024; // 15MB
const UPLOAD_STEP_SIZE = 10;
const FILE_SIZES = ["Bytes", "KB", "MB", "GB"] as const;

const formatBytes = (bytes: number, decimals = 1): string => {
  if (!+bytes) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const unit = FILE_SIZES[i] || FILE_SIZES[FILE_SIZES.length - 1];
  return `${Number.parseFloat((bytes / k ** i).toFixed(dm))} ${unit}`;
};

const UploadIllustration = () => (
  <div className="relative h-16 w-16 select-none">
    <svg
      aria-label="Upload illustration"
      className="h-full w-full"
      fill="none"
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>Upload File Illustration</title>
      <circle
        className="stroke-heal-blue/30 dark:stroke-blue-500/20"
        cx="50"
        cy="50"
        r="45"
        strokeDasharray="4 4"
        strokeWidth="2"
      >
        <animateTransform
          attributeName="transform"
          dur="40s"
          from="0 50 50"
          repeatCount="indefinite"
          to="360 50 50"
          type="rotate"
        />
      </circle>

      <path
        className="fill-heal-softBlue stroke-heal-blue dark:fill-blue-950/40 dark:stroke-blue-400"
        d="M30 35H70C75 35 75 40 75 40V65C75 70 70 70 70 70H30C25 70 25 65 25 65V40C25 35 30 35 30 35Z"
        strokeWidth="2"
      >
        <animate
          attributeName="d"
          dur="2.5s"
          repeatCount="indefinite"
          values="
                        M30 35H70C75 35 75 40 75 40V65C75 70 70 70 70 70H30C25 70 25 65 25 65V40C25 35 30 35 30 35Z;
                        M30 38H70C75 38 75 43 75 43V68C75 73 70 73 70 73H30C25 73 25 68 25 68V43C25 38 30 38 30 38Z;
                        M30 35H70C75 35 75 40 75 40V65C75 70 70 70 70 70H30C25 70 25 65 25 65V40C25 35 30 35 30 35Z"
        />
      </path>

      <path
        className="stroke-heal-blue dark:stroke-blue-400"
        d="M30 35C30 35 35 35 40 35C45 35 45 30 50 30C55 30 55 35 60 35C65 35 70 35 70 35"
        fill="none"
        strokeWidth="2"
      />

      <g className="translate-y-2 transform">
        <line
          className="stroke-heal-blue dark:stroke-blue-400"
          strokeLinecap="round"
          strokeWidth="2"
          x1="50"
          x2="50"
          y1="45"
          y2="60"
        >
          <animate
            attributeName="y2"
            dur="2s"
            repeatCount="indefinite"
            values="60;55;60"
          />
        </line>
        <polyline
          className="stroke-heal-blue dark:stroke-blue-400"
          fill="none"
          points="42,52 50,45 58,52"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
        >
          <animate
            attributeName="points"
            dur="2s"
            repeatCount="indefinite"
            values="42,52 50,45 58,52;42,47 50,40 58,47;42,52 50,45 58,52"
          />
        </polyline>
      </g>
    </svg>
  </div>
);

const UploadingAnimation = ({ progress }: { progress: number }) => (
  <div className="relative h-16 w-16 select-none">
    <svg
      aria-label={`Progresso do upload: ${Math.round(progress)}%`}
      className="h-full w-full"
      fill="none"
      viewBox="0 0 240 240"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>Progresso do Upload</title>
      <defs>
        <mask id="progress-mask-heal">
          <rect fill="black" height="240" width="240" />
          <circle
            cx="120"
            cy="120"
            fill="white"
            r="120"
            strokeDasharray={`${(progress / 100) * 754}, 754`}
            transform="rotate(-90 120 120)"
          />
        </mask>
      </defs>

      <style>
        {`
          @keyframes rotate-cw-heal {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes rotate-ccw-heal {
            from { transform: rotate(360deg); }
            to { transform: rotate(0deg); }
          }
          .g-spin-heal circle {
            transform-origin: 120px 120px;
          }
          .g-spin-heal circle:nth-child(1) { animation: rotate-cw-heal 8s linear infinite; }
          .g-spin-heal circle:nth-child(2) { animation: rotate-ccw-heal 8s linear infinite; }
          .g-spin-heal circle:nth-child(3) { animation: rotate-cw-heal 8s linear infinite; }
          .g-spin-heal circle:nth-child(4) { animation: rotate-ccw-heal 8s linear infinite; }
        `}
      </style>

      <g
        className="g-spin-heal"
        mask="url(#progress-mask-heal)"
        strokeDasharray="18% 40%"
        strokeWidth="10"
      >
        <circle cx="120" cy="120" opacity="0.95" r="140" stroke="#41B6E6" />
        <circle cx="120" cy="120" opacity="0.95" r="110" stroke="#10B981" />
        <circle cx="120" cy="120" opacity="0.95" r="80" stroke="#299DC4" />
        <circle cx="120" cy="120" opacity="0.95" r="50" stroke="#6CD6FF" />
      </g>
    </svg>
  </div>
);

export function FileUpload({
  onUploadSuccess = () => {},
  onUploadError = () => {},
  acceptedFileTypes = ["image/*"],
  maxFileSize = DEFAULT_MAX_FILE_SIZE,
  currentFile: initialFile = null,
  onFileRemove = () => {},
  uploadDelay = 1200,
  validateFile = () => null,
  className,
  title = "Arraste e solte a imagem da ferida",
  description = "Suporta PNG, JPG, WEBP ou HEIC",
}: FileUploadProps) {
  const [file, setFile] = useState<File | null>(initialFile);
  const [status, setStatus] = useState<FileStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<FileError | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      if (uploadIntervalRef.current) {
        clearInterval(uploadIntervalRef.current);
      }
    },
    []
  );

  const validateFileSize = useCallback(
    (file: File): FileError | null => {
      if (file.size > maxFileSize) {
        return {
          message: `Arquivo excede o tamanho máximo de ${formatBytes(maxFileSize)}`,
          code: "FILE_TOO_LARGE",
        };
      }
      return null;
    },
    [maxFileSize]
  );

  const validateFileType = useCallback(
    (file: File): FileError | null => {
      if (!acceptedFileTypes?.length) return null;

      const fileType = file.type.toLowerCase();
      const isAccepted = acceptedFileTypes.some((type) => {
        const cleanType = type.toLowerCase().trim();
        if (cleanType === "image/*") return fileType.startsWith("image/");
        return fileType.includes(cleanType.replace("*", ""));
      });

      if (!isAccepted) {
        return {
          message: `Formato de arquivo inválido. Formatos aceitos: ${acceptedFileTypes.join(", ")}`,
          code: "INVALID_FILE_TYPE",
        };
      }
      return null;
    },
    [acceptedFileTypes]
  );

  const handleError = useCallback(
    (err: FileError) => {
      setError(err);
      setStatus("error");
      onUploadError?.(err);

      setTimeout(() => {
        setError(null);
        setStatus("idle");
      }, 3500);
    },
    [onUploadError]
  );

  const simulateUpload = useCallback(
    (uploadingFile: File) => {
      let currentProgress = 0;

      if (uploadIntervalRef.current) {
        clearInterval(uploadIntervalRef.current);
      }

      if (uploadDelay <= 0) {
        setStatus("idle");
        onUploadSuccess?.(uploadingFile);
        return;
      }

      uploadIntervalRef.current = setInterval(
        () => {
          currentProgress += UPLOAD_STEP_SIZE;
          if (currentProgress >= 100) {
            if (uploadIntervalRef.current) {
              clearInterval(uploadIntervalRef.current);
            }
            setProgress(0);
            setStatus("idle");
            setFile(null);
            onUploadSuccess?.(uploadingFile);
          } else {
            setStatus((prevStatus) => {
              if (prevStatus === "uploading") {
                setProgress(currentProgress);
                return "uploading";
              }
              if (uploadIntervalRef.current) {
                clearInterval(uploadIntervalRef.current);
              }
              return prevStatus;
            });
          }
        },
        uploadDelay / (100 / UPLOAD_STEP_SIZE)
      );
    },
    [onUploadSuccess, uploadDelay]
  );

  const handleFileSelect = useCallback(
    (selectedFile: File | null) => {
      if (!selectedFile) return;

      setError(null);

      const sizeError = validateFileSize(selectedFile);
      if (sizeError) {
        handleError(sizeError);
        return;
      }

      const typeError = validateFileType(selectedFile);
      if (typeError) {
        handleError(typeError);
        return;
      }

      const customError = validateFile?.(selectedFile);
      if (customError) {
        handleError(customError);
        return;
      }

      setFile(selectedFile);
      setStatus("uploading");
      setProgress(0);
      simulateUpload(selectedFile);
    },
    [
      simulateUpload,
      validateFileSize,
      validateFileType,
      validateFile,
      handleError,
    ]
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setStatus((prev) => (prev !== "uploading" ? "dragging" : prev));
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setStatus((prev) => (prev === "dragging" ? "idle" : prev));
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (status === "uploading") return;
      setStatus("idle");
      const droppedFile = e.dataTransfer.files?.[0];
      if (droppedFile) handleFileSelect(droppedFile);
    },
    [status, handleFileSelect]
  );

  const handleFileInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      handleFileSelect(selectedFile || null);
      if (e.target) e.target.value = "";
    },
    [handleFileSelect]
  );

  const triggerFileInput = useCallback(() => {
    if (status === "uploading") return;
    fileInputRef.current?.click();
  }, [status]);

  const resetState = useCallback(() => {
    setFile(null);
    setStatus("idle");
    setProgress(0);
    if (onFileRemove) onFileRemove();
  }, [onFileRemove]);

  return (
    <div
      aria-label="Upload de imagem da ferida"
      className={cn("relative mx-auto w-full max-w-md", className || "")}
    >
      <div className="group relative w-full rounded-2xl bg-white p-0.5 ring-1 ring-heal-line dark:bg-[#0c0c0e] dark:ring-zinc-800 shadow-soft">
        <div className="absolute inset-x-0 -top-px h-px w-full bg-gradient-to-r from-transparent via-heal-blue/40 to-transparent" />

        <div className="relative w-full rounded-[14px] bg-slate-50/70 p-2 dark:bg-zinc-950/40">
          <div
            className={cn(
              "relative mx-auto w-full overflow-hidden rounded-xl border border-heal-line/80 bg-white transition-all duration-200 dark:border-zinc-800 dark:bg-[#0c0c0e]",
              error ? "border-red-500/50" : "",
              status === "dragging" ? "border-heal-blue ring-2 ring-heal-blue/20" : ""
            )}
          >
            <div
              className={cn(
                "absolute inset-0 transition-opacity duration-300 pointer-events-none",
                status === "dragging" ? "opacity-100" : "opacity-0"
              )}
            >
              <div className="absolute inset-0 bg-heal-blue/5 animate-pulse rounded-lg" />
            </div>

            <div className="relative h-[220px]">
              <AnimatePresence mode="wait">
                {status === "idle" || status === "dragging" ? (
                  <motion.div
                    animate={{
                      opacity: status === "dragging" ? 0.85 : 1,
                      y: 0,
                      scale: status === "dragging" ? 0.98 : 1,
                    }}
                    className="absolute inset-0 flex flex-col items-center justify-center p-5 cursor-pointer"
                    exit={{ opacity: 0, y: -10 }}
                    initial={{ opacity: 0, y: 10 }}
                    key="dropzone"
                    onClick={triggerFileInput}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="mb-3">
                      <UploadIllustration />
                    </div>

                    <div className="mb-3 space-y-1 text-center">
                      <h3 className="font-bold text-heal-ink text-sm tracking-tight dark:text-white">
                        {title}
                      </h3>
                      <p className="text-heal-muted text-xs dark:text-zinc-400">
                        {description} {maxFileSize && `(até ${formatBytes(maxFileSize)})`}
                      </p>
                    </div>

                    <button
                      className="group flex items-center justify-center gap-2 rounded-xl bg-heal-blue px-4 py-2 font-bold text-white text-xs shadow-sm transition-all duration-200 hover:bg-heal-blueDark active:scale-95 border-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        triggerFileInput();
                      }}
                      type="button"
                    >
                      <span>Carregar imagem</span>
                      <UploadCloud className="h-3.5 w-3.5 transition-transform duration-200 group-hover:scale-110" />
                    </button>

                    <input
                      accept={acceptedFileTypes?.join(",")}
                      aria-label="Input de arquivo"
                      className="sr-only"
                      onChange={handleFileInputChange}
                      ref={fileInputRef}
                      type="file"
                    />
                  </motion.div>
                ) : status === "uploading" ? (
                  <motion.div
                    animate={{ opacity: 1, scale: 1 }}
                    className="absolute inset-0 flex flex-col items-center justify-center p-5"
                    exit={{ opacity: 0, scale: 0.95 }}
                    initial={{ opacity: 0, scale: 0.95 }}
                    key="uploading"
                  >
                    <div className="mb-3">
                      <UploadingAnimation progress={progress} />
                    </div>

                    <div className="mb-3 space-y-1 text-center max-w-[85%]">
                      <h3 className="truncate font-bold text-heal-ink text-xs dark:text-white">
                        {file?.name}
                      </h3>
                      <div className="flex items-center justify-center gap-2 text-[11px]">
                        <span className="text-heal-muted dark:text-zinc-400">
                          {formatBytes(file?.size || 0)}
                        </span>
                        <span className="font-bold text-heal-blue">
                          {Math.round(progress)}%
                        </span>
                      </div>
                    </div>

                    <button
                      className="flex items-center justify-center gap-2 rounded-lg bg-slate-100 px-3 py-1.5 font-bold text-heal-ink text-xs transition-all duration-200 hover:bg-slate-200 dark:bg-zinc-800 dark:text-white dark:hover:bg-zinc-700 border-0"
                      onClick={resetState}
                      type="button"
                    >
                      Cancelar
                    </button>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>

            <AnimatePresence>
              {error && (
                <motion.div
                  animate={{ opacity: 1, y: 0 }}
                  className="absolute bottom-3 left-1/2 -translate-x-1/2 transform rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-center max-w-[90%]"
                  exit={{ opacity: 0, y: -10 }}
                  initial={{ opacity: 0, y: 10 }}
                >
                  <p className="text-red-600 text-xs font-semibold dark:text-red-400">
                    {error.message}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

FileUpload.displayName = "FileUpload";
