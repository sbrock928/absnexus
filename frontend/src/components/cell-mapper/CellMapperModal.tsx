import { CellMapper } from "./CellMapper";
import styles from "./CellMapperModal.module.css";

interface Props {
  dealId: number;
  runId: number;
  variableId: number;
  variableName: string;
  onClose: () => void;
  onSaved: () => void;
}

export function CellMapperModal({
  dealId,
  runId,
  variableId,
  variableName,
  onClose,
  onSaved,
}: Props) {
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div>
            <div className={styles.title}>Remap: {variableName}</div>
            <div className={styles.subtitle}>
              Select a new cell, then click "Bind cell" to update the mapping.
            </div>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={styles.body}>
          <CellMapper
            dealId={dealId}
            runId={runId}
            focusVariableId={variableId}
            onMappingSaved={() => {
              onSaved();
              onClose();
            }}
          />
        </div>
      </div>
    </div>
  );
}
