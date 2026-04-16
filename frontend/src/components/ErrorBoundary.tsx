import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: "var(--bg-primary)",
          color: "var(--text-primary)",
          padding: 40,
        }}>
          <div style={{ fontSize: 24, fontWeight: 600, marginBottom: 12 }}>Something went wrong</div>
          <div style={{ color: "var(--text-secondary)", fontSize: 14, marginBottom: 24, maxWidth: 500, textAlign: "center" }}>
            An unexpected error occurred. Try refreshing the page. If the problem persists, contact the analytics team.
          </div>
          <div style={{
            background: "var(--bg-tertiary)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 16,
            fontSize: 12,
            fontFamily: "monospace",
            color: "var(--accent-red)",
            maxWidth: 600,
            overflow: "auto",
            marginBottom: 24,
          }}>
            {this.state.error?.message}
          </div>
          <button
            className="btn btn-primary"
            onClick={() => window.location.reload()}
          >
            Refresh page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
