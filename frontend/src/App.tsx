import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth";
import { AppShell } from "./components/layout/AppShell";
import { DealListPage } from "./pages/DealListPage";
import { DealDetailPage } from "./pages/DealDetailPage";
import { DagEditorPage } from "./pages/DagEditorPage";
import { VariableLibraryPage } from "./pages/VariableLibraryPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ExecutionTracePage } from "./pages/ExecutionTracePage";
import { LineagePage } from "./pages/LineagePage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { ExportBuilderPage } from "./pages/ExportBuilderPage";
import { VariableMapPage } from "./pages/VariableMapPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/deals" element={<DealListPage />} />
          <Route path="/deals/:dealId" element={<DealDetailPage />} />
          <Route path="/deals/:dealId/dag" element={<DagEditorPage />} />
          <Route path="/deals/:dealId/export" element={<ExportBuilderPage />} />
          <Route path="/deals/:dealId/runs/:runId/trace" element={<ExecutionTracePage />} />
          <Route path="/deals/:dealId/runs/:runId/lineage/:nodeKey" element={<LineagePage />} />
          <Route path="/variables" element={<VariableLibraryPage />} />
          <Route path="/variable-map" element={<VariableMapPage />} />
          <Route path="/processing" element={<ProcessingPage />} />
          <Route path="/audit" element={<AuditLogPage />} />
          <Route path="/" element={<Navigate to="/deals" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
