import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchTapeGrid,
  fetchMappings,
  createMapping,
  updateMapping,
  type TapeGridSheet,
  type Mapping,
} from "../../api/mappings";
import { api } from "../../api/client";
import type { Variable } from "../../types";
import styles from "./CellMapper.module.css";

interface SelectedCell {
  sheet: string;
  column: string;
  row: number;
  value: string | number | null;
}

interface Props {
  dealId: number;
  /** Optional run_id to load a specific tape */
  runId?: number;
  /** If set, the mapper pre-selects this variable and highlights its current cell */
  focusVariableId?: number;
  /** Called when a mapping is saved — used to trigger re-extraction in the processing flow */
  onMappingSaved?: (variableId: number) => void;
}

export function CellMapper({ dealId, runId, focusVariableId, onMappingSaved }: Props) {
  const qc = useQueryClient();
  const gridScrollRef = useRef<HTMLDivElement>(null);

  const [activeSheet, setActiveSheet] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelectedCell | null>(null);
  const [variableSearch, setVariableSearch] = useState("");
  const [selectedVariableId, setSelectedVariableId] = useState<number | null>(
    focusVariableId ?? null,
  );

  // Fetch initial grid (all sheets)
  const { data: gridData, isLoading: loadingGrid } = useQuery({
    queryKey: ["tape-grid", dealId, runId],
    queryFn: () => fetchTapeGrid(dealId, runId),
  });

  // Fetch mappings
  const { data: mappings = [] } = useQuery({
    queryKey: ["mappings", dealId],
    queryFn: () => fetchMappings(dealId),
  });

  // Fetch variables
  const { data: variables = [] } = useQuery({
    queryKey: ["variables-all"],
    queryFn: () => api.get<Variable[]>("/variables/"),
  });

  // Helper: look up a cell value from grid data
  const lookupCellValue = useCallback(
    (sheetName: string, col: string, row: number): string | number | null => {
      if (!gridData) return null;
      const sheet = gridData.sheets
        ? gridData.sheets.find((s) => s.sheet_name === sheetName)
        : gridData.sheet?.sheet_name === sheetName ? gridData.sheet : null;
      if (!sheet) return null;
      const colIdx = sheet.column_letters.indexOf(col);
      if (colIdx < 0) return null;
      const r = sheet.rows.find((r) => r.row_number === row);
      return r ? r.cells[colIdx] ?? null : null;
    },
    [gridData],
  );

  // Set default active sheet — runs once when grid data first loads
  const initializedRef = useRef(false);
  useEffect(() => {
    if (initializedRef.current || !gridData || gridData.sheet_names.length === 0) return;
    if (focusVariableId && mappings.length > 0) {
      const m = mappings.find((m) => m.variable_id === focusVariableId);
      if (m) {
        setActiveSheet(m.sheet_name);
        setSelected({
          sheet: m.sheet_name,
          column: m.column_letter,
          row: m.row_number,
          value: lookupCellValue(m.sheet_name, m.column_letter, m.row_number),
        });
        initializedRef.current = true;
        return;
      }
    }
    setActiveSheet(gridData.sheet_names[0]);
    initializedRef.current = true;
  }, [gridData, focusVariableId, mappings, lookupCellValue]);

  // Lookup: cell coordinate → variable mapping
  const cellToMapping = useMemo(() => {
    const map: Record<string, Mapping> = {};
    for (const m of mappings) {
      const key = `${m.sheet_name}|${m.column_letter}${m.row_number}`;
      map[key] = m;
    }
    return map;
  }, [mappings]);

  // Currently active sheet's grid
  const activeSheetData = useMemo(() => {
    if (!gridData || !activeSheet) return null;
    if (gridData.sheets) {
      return gridData.sheets.find((s) => s.sheet_name === activeSheet) ?? null;
    }
    return gridData.sheet?.sheet_name === activeSheet ? gridData.sheet : null;
  }, [gridData, activeSheet]);

  // Mutations
  const saveMut = useMutation({
    mutationFn: async () => {
      if (!selected || !selectedVariableId) return;
      const existing = mappings.find((m) => m.variable_id === selectedVariableId);
      if (existing) {
        return await updateMapping(dealId, existing.id, {
          sheet_name: selected.sheet,
          column_letter: selected.column,
          row_number: selected.row,
        });
      }
      return await createMapping(dealId, {
        variable_id: selectedVariableId,
        sheet_name: selected.sheet,
        column_letter: selected.column,
        row_number: selected.row,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mappings", dealId] });
      if (selectedVariableId && onMappingSaved) {
        onMappingSaved(selectedVariableId);
      }
    },
  });

  const filteredVariables = variables.filter((v) =>
    v.name.toLowerCase().includes(variableSearch.toLowerCase()) ||
    (v.display_name ?? "").toLowerCase().includes(variableSearch.toLowerCase()),
  );

  const selectedMapping = selectedVariableId
    ? mappings.find((m) => m.variable_id === selectedVariableId)
    : null;

  const scrollToCell = useCallback((col: string, row: number) => {
    requestAnimationFrame(() => {
      const container = gridScrollRef.current;
      if (!container) return;
      const cell = container.querySelector(`[data-cell="${col}${row}"]`);
      if (cell) cell.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    });
  }, []);

  if (loadingGrid) return <div className={styles.loading}>Loading tape...</div>;
  if (!gridData) return <div className={styles.error}>Failed to load tape data.</div>;

  return (
    <div className={styles.layout}>
      {/* LEFT: Spreadsheet grid */}
      <div className={styles.gridSection}>
        {/* Sheet tabs */}
        <div className={styles.sheetTabs}>
          {gridData.sheet_names.map((name) => (
            <button
              key={name}
              className={`${styles.sheetTab} ${activeSheet === name ? styles.sheetTabActive : ""}`}
              onClick={() => setActiveSheet(name)}
            >
              {name}
            </button>
          ))}
        </div>

        {/* Grid */}
        <div className={styles.gridScroll} ref={gridScrollRef}>
          {activeSheetData ? (
            <table className={styles.grid}>
              <thead>
                <tr>
                  <th className={styles.rowHeader}></th>
                  {activeSheetData.column_letters.map((col) => (
                    <th key={col} className={styles.colHeader}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {activeSheetData.rows.map((row) => (
                  <tr key={row.row_number}>
                    <td className={styles.rowHeader}>{row.row_number}</td>
                    {activeSheetData.column_letters.map((col, colIdx) => {
                      const cellKey = `${activeSheet}|${col}${row.row_number}`;
                      const isMapped = !!cellToMapping[cellKey];
                      const isSelected =
                        selected?.sheet === activeSheet &&
                        selected?.column === col &&
                        selected?.row === row.row_number;
                      const mappedVar = cellToMapping[cellKey];
                      const mappedVarName = mappedVar
                        ? variables.find((v) => v.id === mappedVar.variable_id)?.name
                        : null;
                      const value = row.cells[colIdx];
                      return (
                        <td
                          key={col}
                          data-cell={`${col}${row.row_number}`}
                          className={`${styles.cell} ${isMapped ? styles.cellMapped : ""} ${isSelected ? styles.cellSelected : ""}`}
                          title={mappedVarName ? `Mapped to: ${mappedVarName}` : undefined}
                          onClick={() =>
                            setSelected({
                              sheet: activeSheet!,
                              column: col,
                              row: row.row_number,
                              value: value,
                            })
                          }
                        >
                          {value === null
                            ? ""
                            : typeof value === "number"
                            ? value.toLocaleString("en-US", { maximumFractionDigits: 2 })
                            : String(value)}
                          {isMapped && <span className={styles.mappedDot} />}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className={styles.loading}>Select a sheet tab above.</div>
          )}
        </div>
      </div>

      {/* RIGHT: Binding panel */}
      <div className={styles.bindingPanel}>
        <div className={styles.bindingTitle} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          Cell → variable binding
          {selected && (
            <button
              className={styles.closeBtn}
              onClick={() => { setSelected(null); setSelectedVariableId(focusVariableId ?? null); }}
              title="Close binding"
            >✕</button>
          )}
        </div>
        {selected ? (
          <div className={styles.selectedInfo}>
            Selected:{" "}
            <span className={styles.mono}>
              {selected.sheet} · {selected.column}{selected.row}
            </span>
          </div>
        ) : (
          <div className={styles.muted}>Click a cell to select it.</div>
        )}

        {selected && (
          <>
            <div className={styles.field}>
              <label className={styles.label}>Selected cell</label>
              <div className={styles.cellInfo}>
                <div>
                  <span className={styles.smallLabel}>Sheet</span>
                  <div className={styles.mono}>{selected.sheet}</div>
                </div>
                <div>
                  <span className={styles.smallLabel}>Column</span>
                  <div className={styles.mono}>{selected.column}</div>
                </div>
                <div>
                  <span className={styles.smallLabel}>Row</span>
                  <div className={styles.mono}>{selected.row}</div>
                </div>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Preview value</label>
              <div className={styles.previewValue}>
                {selected.value === null ? (
                  <span className={styles.muted}>(empty)</span>
                ) : typeof selected.value === "number" ? (
                  selected.value.toLocaleString("en-US", {
                    maximumFractionDigits: 4,
                  })
                ) : (
                  String(selected.value)
                )}
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Bind to variable</label>
              <input
                className={styles.input}
                placeholder="Search variables..."
                value={variableSearch}
                onChange={(e) => setVariableSearch(e.target.value)}
              />
              <div className={styles.variableList}>
                {filteredVariables.slice(0, 10).map((v) => (
                  <button
                    key={v.id}
                    className={`${styles.variableItem} ${
                      selectedVariableId === v.id
                        ? styles.variableItemSelected
                        : ""
                    }`}
                    onClick={() => setSelectedVariableId(selectedVariableId === v.id ? null : v.id)}
                  >
                    <div>
                      <div className={styles.mono} style={{ fontSize: 12 }}>
                        {v.name}
                      </div>
                      <div className={styles.smallLabel}>
                        {v.display_name || v.description || ""}
                      </div>
                    </div>
                    <span
                      className={`${styles.scopeBadge} ${
                        styles[`scope_${v.scope}`] || ""
                      }`}
                    >
                      {v.scope}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Save button */}
            <button
              className={styles.saveBtn}
              disabled={!selectedVariableId || saveMut.isPending}
              onClick={() => saveMut.mutate()}
            >
              {saveMut.isPending
                ? "Saving..."
                : selectedMapping
                ? `Update mapping for ${variables.find((v) => v.id === selectedVariableId)?.name}`
                : "Bind cell"}
            </button>

            {saveMut.isSuccess && (
              <div className={styles.successMsg}>✓ Mapping saved</div>
            )}
          </>
        )}

        {/* Mapped variables list */}
        <div className={styles.divider} />
        <div className={styles.mappedList}>
          <div className={styles.bindingTitle}>
            Mapped variables
            <span className={styles.count}>
              {mappings.length} / {variables.length}
            </span>
          </div>
          {mappings.map((m) => {
            const v = variables.find((v) => v.id === m.variable_id);
            return (
              <div
                key={m.id}
                className={styles.mappedItem}
                onClick={() => {
                  setActiveSheet(m.sheet_name);
                  setSelected({
                    sheet: m.sheet_name,
                    column: m.column_letter,
                    row: m.row_number,
                    value: lookupCellValue(m.sheet_name, m.column_letter, m.row_number),
                  });
                  setSelectedVariableId(m.variable_id);
                  scrollToCell(m.column_letter, m.row_number);
                }}
              >
                <div className={styles.mono} style={{ fontSize: 11 }}>
                  {v?.name ?? "?"}
                </div>
                <div className={styles.mappedCell}>
                  {m.column_letter}
                  {m.row_number}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
