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
import { BatchProcessingPage } from "./pages/BatchProcessingPage";
import { BatchResultsPage } from "./pages/BatchResultsPage";
import { BatchHistoryPage } from "./pages/BatchHistoryPage";
import { CellMapperPage } from "./pages/CellMapperPage";
import { UsersPage } from "./pages/UsersPage";
import { ServicersPage } from "./pages/ServicersPage";
import { GlobalExportPage } from "./pages/GlobalExportPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/deals" element={<DealListPage />} />
          <Route path="/deals/:dealId" element={<DealDetailPage />} />
          <Route path="/deals/:dealId/dag" element={<DagEditorPage />} />
          <Route path="/deals/:dealId/export" element={<ExportBuilderPage />} />
          <Route path="/deals/:dealId/mappings/cells" element={<CellMapperPage />} />
          <Route path="/deals/:dealId/runs/:runId/trace" element={<ExecutionTracePage />} />
          <Route path="/deals/:dealId/runs/:runId/lineage/:nodeKey" element={<LineagePage />} />
          <Route path="/variables" element={<VariableLibraryPage />} />
          <Route path="/variable-map" element={<VariableMapPage />} />
          <Route path="/processing" element={<ProcessingPage />} />
          <Route path="/batch" element={<BatchProcessingPage />} />
          <Route path="/batches" element={<BatchHistoryPage />} />
          <Route path="/batches/:batchId" element={<BatchResultsPage />} />
          <Route path="/audit" element={<AuditLogPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/servicers" element={<ServicersPage />} />
          <Route path="/export-templates" element={<GlobalExportPage />} />
          <Route path="/" element={<Navigate to="/deals" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
