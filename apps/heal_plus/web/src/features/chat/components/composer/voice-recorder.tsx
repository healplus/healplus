import { useState, useEffect, useRef } from 'react';
import { Mic, Square, X, Check, AlertCircle, Loader2 } from 'lucide-react';

interface VoiceRecorderProps {
  onTranscriptComplete: (text: string) => void;
  disabled?: boolean;
}

type SpeechRecognitionType = any;

export function VoiceRecorder({ onTranscriptComplete, disabled }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionType | null>(null);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  const startRecording = () => {
    setErrorMsg(null);
    const windowWithSpeech = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionType;
      webkitSpeechRecognition?: new () => SpeechRecognitionType;
    };

    const SpeechRecClass = windowWithSpeech.SpeechRecognition || windowWithSpeech.webkitSpeechRecognition;

    if (!SpeechRecClass) {
      setErrorMsg('Reconhecimento de voz não suportado neste navegador.');
      return;
    }

    try {
      const recognition = new SpeechRecClass();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'pt-BR';

      let fullTranscript = '';

      recognition.onresult = (event: any) => {
        let currentText = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            fullTranscript += event.results[i][0].transcript + ' ';
          } else {
            currentText += event.results[i][0].transcript;
          }
        }
      };

      recognition.onerror = (err: any) => {
        if (err.error === 'not-allowed') {
          setErrorMsg('Permissão de microfone negada.');
        } else {
          setErrorMsg('Erro na captura de áudio.');
        }
        stopRecording(false);
      };

      recognition.onend = () => {
        if (isRecording) {
          setIsRecording(false);
          setIsTranscribing(false);
        }
      };

      recognition.start();
      recognitionRef.current = recognition;
      setIsRecording(true);
      setTimerSeconds(0);

      timerIntervalRef.current = setInterval(() => {
        setTimerSeconds((prev) => prev + 1);
      }, 1000);
    } catch (e) {
      setErrorMsg('Falha ao iniciar o microfone.');
    }
  };

  const stopRecording = (saveTranscript = true) => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        if (saveTranscript) {
          setIsTranscribing(true);
          recognitionRef.current.onend = () => {
            setIsRecording(false);
            setIsTranscribing(false);
          };
          recognitionRef.current.stop();
        } else {
          recognitionRef.current.abort();
          setIsRecording(false);
          setIsTranscribing(false);
        }
      } catch {
        setIsRecording(false);
        setIsTranscribing(false);
      }
    } else {
      setIsRecording(false);
      setIsTranscribing(false);
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (isRecording) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-blue-50/90 px-3 py-1.5 dark:bg-blue-950/80 border border-blue-200 dark:border-blue-800 animate-in fade-in">
        {/* Waveform bars */}
        <div className="flex items-center gap-0.5">
          <span className="h-3 w-1 animate-pulse rounded-full bg-blue-600 dark:bg-blue-400" style={{ animationDelay: '0ms' }} />
          <span className="h-4 w-1 animate-pulse rounded-full bg-blue-600 dark:bg-blue-400" style={{ animationDelay: '150ms' }} />
          <span className="h-2 w-1 animate-pulse rounded-full bg-blue-600 dark:bg-blue-400" style={{ animationDelay: '300ms' }} />
          <span className="h-4 w-1 animate-pulse rounded-full bg-blue-600 dark:bg-blue-400" style={{ animationDelay: '450ms' }} />
        </div>

        <span className="text-xs font-mono font-bold text-blue-700 dark:text-blue-300">
          {formatTimer(timerSeconds)}
        </span>
        <span className="text-xs text-blue-600 dark:text-blue-400 font-medium hidden sm:inline">Ouvindo...</span>

        <div className="flex items-center gap-1 ml-1">
          <button
            type="button"
            onClick={() => stopRecording(false)}
            className="rounded-lg p-1 text-slate-500 hover:bg-blue-100 hover:text-slate-700 dark:hover:bg-blue-900"
            title="Cancelar gravação"
            aria-label="Cancelar gravação"
          >
            <X size={15} />
          </button>
          <button
            type="button"
            onClick={() => stopRecording(true)}
            className="rounded-lg bg-blue-600 p-1 text-white hover:bg-blue-700"
            title="Concluir áudio"
            aria-label="Concluir áudio"
          >
            <Check size={15} />
          </button>
        </div>
      </div>
    );
  }

  if (isTranscribing) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-blue-50 px-3 py-1.5 text-xs text-blue-700 font-medium dark:bg-blue-950 dark:text-blue-300">
        <Loader2 size={14} className="animate-spin text-blue-600" />
        <span>Processando transcrição...</span>
      </div>
    );
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={startRecording}
        disabled={disabled}
        className="rounded-xl p-2 text-slate-500 hover:bg-slate-100 hover:text-blue-600 disabled:opacity-50 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-blue-400 transition-colors"
        title="Entrada por voz (AI Voice)"
        aria-label="Gravar áudio"
      >
        <Mic size={18} />
      </button>

      {errorMsg && (
        <div className="absolute bottom-full right-0 mb-2 w-48 rounded-xl border border-red-200 bg-red-50 p-2 text-[11px] font-semibold text-red-700 shadow-lg dark:border-red-900 dark:bg-red-950 dark:text-red-300 z-50">
          <div className="flex items-center gap-1.5">
            <AlertCircle size={14} className="shrink-0" />
            <span>{errorMsg}</span>
          </div>
        </div>
      )}
    </div>
  );
}
