import { createContext, useCallback, useContext, useRef, useState } from "react";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

interface ConfirmContextValue {
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue>({
  confirm: async () => false,
});

export function useConfirm() {
  return useContext(ConfirmContext).confirm;
}

interface PendingState {
  options: ConfirmOptions;
  resolve: (value: boolean) => void;
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingState | null>(null);
  const resolverRef = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
      setPending({ options, resolve });
    });
  }, []);

  const close = (value: boolean) => {
    if (pending) {
      pending.resolve(value);
      setPending(null);
    }
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending && (
        <div
          className="dialog-overlay"
          onClick={() => close(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            {pending.options.title && (
              <div className="dialog-title">{pending.options.title}</div>
            )}
            <div style={{ fontSize: 14, color: "var(--text-primary)", marginBottom: 20 }}>
              {pending.options.message}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => close(false)}
                autoFocus
              >
                {pending.options.cancelLabel ?? "Cancel"}
              </button>
              <button
                type="button"
                className={pending.options.destructive === false ? "btn-primary" : "btn-danger"}
                onClick={() => close(true)}
              >
                {pending.options.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}
