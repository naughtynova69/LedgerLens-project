import React from "react";
import { Modal } from "../components/Modal";
import { ProofTrailInspector } from "../components/ProofTrailInspector";

export function FindingDetailModal({
  isOpen,
  onClose,
  finding,
  onMakeDecision,
  isSubmitting,
  onToast,
}) {
  if (!finding) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Proof Trail Inspector — ${finding.finding_id}`}
      maxWidth="max-w-5xl"
    >
      <ProofTrailInspector
        finding={finding}
        onMakeDecision={onMakeDecision}
        isSubmitting={isSubmitting}
        onToast={onToast}
      />
    </Modal>
  );
}
