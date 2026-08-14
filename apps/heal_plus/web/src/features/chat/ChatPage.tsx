import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { subscribePatients } from '../patients/patientService';
import type { Patient } from '../../lib/types';
import type { PatientContext, ChatAttachment } from './types';
import { useAiChat } from './hooks/use-ai-chat';
import { ChatHeader } from './components/chat-header';
import { MessageList } from './components/message-list';
import { AIComposer } from './components/composer/ai-composer';
import { PatientSelectorDialog } from './components/dialogs/patient-selector-dialog';
import { PrivacyConfirmationDialog } from './components/dialogs/privacy-confirmation-dialog';
import { ExternalTransmissionDialog } from './components/dialogs/external-transmission-dialog';
import { AiProviderDialog } from './AiProviderDialog';
import {
  clearAiProviderConfig,
  createDefaultAiProviderConfig,
  saveAiProviderConfig,
  validateAiProviderConfig
} from './aiProvider';
import { ChatHistoryDrawer } from './components/chat-history-drawer';
import type { AppShellContext } from '../../components/layout/AppShell';

export function ChatPage() {
  const { user } = useAuth();
  const userId = user?.id || 'default-user';

  const outletContext = useOutletContext<AppShellContext>() || {
    isSidebarCollapsed: false,
    onToggleSidebar: () => {}
  };

  const [patients, setPatients] = useState<Patient[]>([]);

  // Modals state
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState(false);
  const [isPatientDialogOpen, setIsPatientDialogOpen] = useState(false);
  const [isProviderDialogOpen, setIsProviderDialogOpen] = useState(false);
  const [pendingPatient, setPendingPatient] = useState<PatientContext | null>(null);
  const [isPrivacyDialogOpen, setIsPrivacyDialogOpen] = useState(false);

  // Subscribe to real-time or memory patients
  useEffect(() => {
    if (!user?.id) return;
    const unsubscribe = subscribePatients(user.id, (list: Patient[]) => {
      setPatients(list);
    });
    return () => {
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  }, [user?.id]);

  const {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    activeMessages,
    stage,
    composerValue,
    setComposerValue,
    mode,
    setMode,
    internalSearchEnabled,
    setInternalSearchEnabled,
    externalSearchEnabled,
    setExternalSearchEnabled,
    attachments,
    setAttachments,
    patientContext,
    setPatientContext,
    providerConfig,
    setProviderConfig,
    pendingTransmission,
    pendingTransmissionHistoryCount,
    handleNewSession,
    handleRenameSession,
    handlePinSession,
    handleArchiveSession,
    handleDeleteSession,
    handleClearCurrentMessages,
    handleSendMessage,
    handleCancelGeneration,
    handleCancelTransmission,
    handleConfirmTransmission,
    handleEditUserMessage,
    handleRegenerateLastResponse,
    handleFeedbackMessage
  } = useAiChat(userId);

  useEffect(() => {
    if (validateAiProviderConfig(providerConfig)) {
      setIsProviderDialogOpen(true);
    }
    // A conexão é solicitada uma vez ao entrar; novos envios também validam a configuração.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestProviderReadyAction = (action: () => void) => {
    if (validateAiProviderConfig(providerConfig)) {
      setIsProviderDialogOpen(true);
      return;
    }
    action();
  };

  const requestSend = (text?: string) => {
    requestProviderReadyAction(() => handleSendMessage(text));
  };

  const requestEdit = (id: string, text: string) => {
    requestProviderReadyAction(() => handleEditUserMessage(id, text));
  };

  const requestRegeneration = () => {
    requestProviderReadyAction(handleRegenerateLastResponse);
  };

  const handleAddAttachment = (att: ChatAttachment) => {
    setAttachments((prev) => [...prev, att]);
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleSelectPatientIntent = (target: PatientContext) => {
    if (activeMessages.length > 0 && patientContext && patientContext.id !== target.id) {
      setPendingPatient(target);
      setIsPrivacyDialogOpen(true);
    } else {
      setPatientContext(target);
    }
  };

  const handleConfirmPatientSwitch = () => {
    if (pendingPatient) {
      setPatientContext(pendingPatient);
      setPendingPatient(null);
      setAttachments([]);
    }
  };

  const handleToggleInternalSearch = () => {
    setInternalSearchEnabled(!internalSearchEnabled);
  };

  const handleToggleExternalSearch = () => {
    setExternalSearchEnabled(!externalSearchEnabled);
  };

  return (
    <div className="relative flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-[#F8FAFC] font-sans text-slate-900 dark:bg-[#0B0F17] dark:text-slate-100">
      {/* Header with Sidebar Collapse Toggle */}
      <ChatHeader
        isSidebarCollapsed={outletContext.isSidebarCollapsed}
        onToggleSidebar={outletContext.onToggleSidebar}
        onOpenHistory={() => setIsHistoryDrawerOpen(true)}
        providerConfig={providerConfig}
        onOpenProviderDialog={() => setIsProviderDialogOpen(true)}
        onNewChat={handleNewSession}
      />

      {/* Messages Scroll Area */}
      <MessageList
        messages={activeMessages}
        stage={stage}
        onCancelProcessing={handleCancelGeneration}
        onSelectSuggestion={requestSend}
        patientContext={patientContext}
        onOpenPatientSelector={() => setIsPatientDialogOpen(true)}
        onEditUserMessage={requestEdit}
        onRegenerateLastResponse={requestRegeneration}
        onFeedbackMessage={handleFeedbackMessage}
      />

      {/* Region 3: Fixed Integrated KokonutUI Composer */}
      <div className="sticky bottom-0 z-20 shrink-0 bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC]/95 to-transparent pb-2 pt-3 dark:from-[#0B0F17] dark:via-[#0B0F17]/95 sm:pb-3">
        <AIComposer
          value={composerValue}
          onChange={setComposerValue}
          onSubmit={() => requestSend()}
          mode={mode}
          onSelectMode={setMode}
          internalSearchEnabled={internalSearchEnabled}
          externalSearchEnabled={externalSearchEnabled}
          onToggleInternalSearch={handleToggleInternalSearch}
          onToggleExternalSearch={handleToggleExternalSearch}
          attachments={attachments}
          onAddAttachment={handleAddAttachment}
          onRemoveAttachment={handleRemoveAttachment}
          patientContext={patientContext}
          onRemovePatientContext={() => setPatientContext(undefined)}
          onOpenPatientSelector={() => setIsPatientDialogOpen(true)}
          isSubmitting={stage === 'uploading' || stage === 'generating'}
          isGenerating={stage === 'streaming' || stage === 'analyzing' || stage === 'comparing'}
          onStopGeneration={handleCancelGeneration}
        />
      </div>

      {/* Original Restored History Drawer */}
      <ChatHistoryDrawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setIsHistoryDrawerOpen(false)}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={setCurrentSessionId}
        onPinSession={handlePinSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* Dialogs */}
      <PatientSelectorDialog
        isOpen={isPatientDialogOpen}
        onClose={() => setIsPatientDialogOpen(false)}
        patients={patients}
        currentPatientId={patientContext?.id}
        onSelectPatient={handleSelectPatientIntent}
      />

      <PrivacyConfirmationDialog
        isOpen={isPrivacyDialogOpen}
        onClose={() => setIsPrivacyDialogOpen(false)}
        targetPatient={pendingPatient}
        onConfirm={handleConfirmPatientSwitch}
      />

      <ExternalTransmissionDialog
        attachmentCount={pendingTransmission?.attachments.length ?? 0}
        config={providerConfig}
        historyMessageCount={pendingTransmissionHistoryCount}
        onCancel={handleCancelTransmission}
        onConfirm={handleConfirmTransmission}
        open={Boolean(pendingTransmission) && !validateAiProviderConfig(providerConfig)}
      />

      <AiProviderDialog
        open={isProviderDialogOpen}
        onClose={() => setIsProviderDialogOpen(false)}
        config={providerConfig}
        onSave={(cfg) => {
          saveAiProviderConfig(userId, cfg);
          setProviderConfig(cfg);
          setIsProviderDialogOpen(false);
        }}
        onRemove={() => {
          clearAiProviderConfig(userId);
          setProviderConfig(createDefaultAiProviderConfig('google'));
          setIsProviderDialogOpen(false);
        }}
      />
    </div>
  );
}

export default ChatPage;
