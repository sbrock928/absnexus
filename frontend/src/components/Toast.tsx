import { createContext, useCallback, useContext, useState } from "react";

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

interface ToastContextValue {
  toast: (message: string, type?: Toast["type"]) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: Toast["type"] = "success") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        zIndex: 1000,
        pointerEvents: "none",
      }}>
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => dismiss(t.id)}
            style={{
              pointerEvents: "auto",
              padding: "10px 16px",
              borderRadius: "var(--radius)",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              maxWidth: 360,
              animation: "toast-in 0.2s ease-out",
              background:
                t.type === "success" ? "rgba(74, 222, 128, 0.15)"
                : t.type === "error" ? "rgba(248, 113, 113, 0.15)"
                : "rgba(74, 158, 255, 0.15)",
              border: `1px solid ${
                t.type === "success" ? "rgba(74, 222, 128, 0.3)"
                : t.type === "error" ? "rgba(248, 113, 113, 0.3)"
                : "rgba(74, 158, 255, 0.3)"
              }`,
              color:
                t.type === "success" ? "var(--accent-green)"
                : t.type === "error" ? "var(--accent-red)"
                : "var(--accent-blue)",
            }}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
