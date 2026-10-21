/**
 * Demo Mode Factory Data Import Handler (CSV & Static Limitations)
 * Governed by DATA_AND_API.md Section 4.3, SPECIFICATION.md Section 9, and PROJECT_RULES.md.
 * Zero external libraries, pure client-side parsing with explicit validation.
 */

import { ApiClientError } from '../api/client';
import {
  ImportConfirmResponse,
  ImportPreviewResponse,
  ImportRowError,
  ImportStagedData,
  ImportSummary,
  MachineResponse,
  OrderResponse,
  DowntimeResponse,
} from '../types/api';
import { getMutableDemoFactory, getDemoFactory } from './demoService';

// In-memory staging store for demo imports: jobId -> ImportStagedData
const demoStagedImports = new Map<string, ImportStagedData>();

export function clearDemoStagedImports(): void {
  demoStagedImports.clear();
}

/**
 * Robust CSV line tokenizer supporting quoted fields with embedded commas and escaped quotes.
 */
function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

/**
 * Download sample template.
 * For CSV: downloads a schema-compliant sample CSV with machines, orders, operations, and downtimes.
 * For XLSX: binary Excel cannot be generated in client without external binary libraries; throws informative error.
 */
export function downloadDemoTemplate(format: 'csv' | 'xlsx'): void {
  if (format === 'xlsx') {
    throw new ApiClientError(
      'UNSUPPORTED_FORMAT',
      'Static Demo Notice: Binary Excel (.xlsx) templates require the Opwise Python backend server. Please download the Starter CSV template for static browser demo mode.',
      400
    );
  }

  const sampleCsv = [
    '# ====================================================================',
    '# Opwise Manufacturing Factory Template (Sample CSV)',
    '# Lines starting with # are comments and ignored during parsing.',
    '# ====================================================================',
    '',
    '# Section: Machines',
    '# Format: machine_id,name',
    'M1,CNC Milling Station Alpha',
    'M2,Precision Turning Lathe Beta',
    'M3,Surface Grinder Gamma',
    'M4,Assembly & Inspection Delta',
    '',
    '# Section: Orders',
    '# Format: order_id,name,release_minute,due_minute,tardiness_weight',
    'ORD-101,Titanium Rotor Shaft,0,180,2',
    'ORD-102,Precision Drive Gear,30,240,1',
    '',
    '# Section: Operations',
    '# Format: order_id,sequence_index,machine_id,processing_minutes',
    'ORD-101,1,M1,30',
    'ORD-101,2,M2,45',
    'ORD-101,3,M4,20',
    'ORD-102,1,M2,25',
    'ORD-102,2,M3,35',
    'ORD-102,3,M4,15',
    '',
    '# Section: Downtimes (Optional)',
    '# Format: machine_id,start_minute,end_minute,reason',
    'M1,60,90,Scheduled Spindle Inspection',
    '',
  ].join('\n');

  if (typeof window !== 'undefined' && window.URL && typeof window.URL.createObjectURL === 'function') {
    const blob = new Blob([sampleCsv], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'opwise_factory_template.csv';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }
}

/**
 * Preview and validate uploaded import file in demo mode.
 * - Binary .xlsx and .zip archives are honestly rejected with an explicit limitation notice.
 * - CSV files are parsed line-by-line and validated against schema invariants.
 */
export async function previewDemoImport(_workspaceId: string, file: File): Promise<ImportPreviewResponse> {
  const fileName = file.name.toLowerCase();

  // 1. Explicit limitation for binary files in static browser demo mode
  if (fileName.endsWith('.xlsx') || fileName.endsWith('.zip')) {
    const formatName = fileName.endsWith('.xlsx') ? 'Excel Workbook (.xlsx)' : 'ZIP Archive (.zip)';
    const errors: ImportRowError[] = [
      {
        sheet: formatName,
        row: 0,
        column: 'File Format',
        value: file.name,
        issue:
          'Static Demo Limitation: Binary Excel (.xlsx) and ZIP archives require the Opwise Python backend server. To test factory import in standalone browser mode, please upload a plain CSV file or use the Starter CSV template.',
      },
    ];

    return {
      job_id: '',
      filename: file.name,
      status: 'FAILED',
      is_valid: false,
      summary: {
        machine_count: 0,
        order_count: 0,
        operation_count: 0,
        downtime_count: 0,
      },
      warnings: [],
      staged_data: {
        machines: [],
        orders: [],
        downtimes: [],
      },
      errors,
    };
  }

  // 2. Read CSV text
  let content: string;
  try {
    content = await file.text();
  } catch (err: unknown) {
    return {
      job_id: '',
      filename: file.name,
      status: 'FAILED',
      is_valid: false,
      summary: { machine_count: 0, order_count: 0, operation_count: 0, downtime_count: 0 },
      warnings: [],
      staged_data: { machines: [], orders: [], downtimes: [] },
      errors: [
        {
          sheet: 'CSV',
          row: 0,
          column: 'File Read',
          value: file.name,
          issue: `Failed to read file content: ${err instanceof Error ? err.message : 'Unknown read error'}`,
        },
      ],
    };
  }

  const lines = content.split(/\r?\n/).map((l) => l.trim());
  const nonCommentLines = lines.filter((l) => l.length > 0 && !l.startsWith('#'));

  if (nonCommentLines.length === 0) {
    return {
      job_id: '',
      filename: file.name,
      status: 'FAILED',
      is_valid: false,
      summary: { machine_count: 0, order_count: 0, operation_count: 0, downtime_count: 0 },
      warnings: [],
      staged_data: { machines: [], orders: [], downtimes: [] },
      errors: [
        {
          sheet: 'CSV',
          row: 1,
          column: 'File Content',
          value: '',
          issue: 'File is empty or contains only comments/whitespace. No factory configuration rows found.',
        },
      ],
    };
  }

  // 3. Parse CSV sections
  type Section = 'UNKNOWN' | 'MACHINES' | 'ORDERS' | 'OPERATIONS' | 'DOWNTIMES';
  let currentSection: Section = 'UNKNOWN';

  const machines: Array<{ id: string; name: string }> = [];
  const ordersMap = new Map<
    string,
    {
      id: string;
      name: string;
      release_minute: number;
      due_minute: number;
      tardiness_weight: number;
      operations: Array<{
        id: string;
        order_id: string;
        sequence_index: number;
        machine_id: string;
        processing_minutes: number;
      }>;
    }
  >();
  const downtimes: Array<{
    id: string;
    machine_id: string;
    start_minute: number;
    end_minute: number;
    reason: string;
  }> = [];

  const errors: ImportRowError[] = [];
  const warnings: string[] = [];

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const rawLine = lines[lineIdx];
    const lineNum = lineIdx + 1;

    if (!rawLine || rawLine.trim().length === 0) continue;

    // Section detection via header comment or keyword
    const lower = rawLine.toLowerCase();
    if (lower.includes('section: machines') || lower.includes('# machines') || lower === 'machines') {
      currentSection = 'MACHINES';
      continue;
    }
    if (lower.includes('section: orders') || lower.includes('# orders') || lower === 'orders') {
      currentSection = 'ORDERS';
      continue;
    }
    if (lower.includes('section: operations') || lower.includes('# operations') || lower === 'operations') {
      currentSection = 'OPERATIONS';
      continue;
    }
    if (lower.includes('section: downtimes') || lower.includes('# downtimes') || lower === 'downtimes') {
      currentSection = 'DOWNTIMES';
      continue;
    }

    if (rawLine.startsWith('#')) continue;

    const cols = parseCsvLine(rawLine);

    // Skip column header rows if present
    if (
      cols[0]?.toLowerCase() === 'machine_id' ||
      cols[0]?.toLowerCase() === 'order_id' ||
      cols[0]?.toLowerCase() === 'format:'
    ) {
      continue;
    }

    // Auto-detect section if not explicitly declared
    let sec = currentSection;
    if (sec === 'UNKNOWN') {
      if (cols.length === 2) sec = 'MACHINES';
      else if (cols.length === 5) sec = 'ORDERS';
      else if (cols.length === 4) {
        // Can be Operations (order_id, seq, machine_id, proc) or Downtime (machine_id, start, end, reason)
        const secondNum = Number(cols[1]);
        const thirdNum = Number(cols[2]);
        if (!isNaN(secondNum) && !isNaN(thirdNum)) {
          sec = 'DOWNTIMES';
        } else {
          sec = 'OPERATIONS';
        }
      }
    }

    if (sec === 'MACHINES') {
      const [mId, mName] = cols;
      if (!mId) {
        errors.push({ sheet: 'Machines', row: lineNum, column: 'machine_id', value: '', issue: 'Missing machine ID.' });
        continue;
      }
      if (machines.some((m) => m.id === mId)) {
        errors.push({ sheet: 'Machines', row: lineNum, column: 'machine_id', value: mId, issue: `Duplicate machine ID '${mId}'.` });
        continue;
      }
      machines.push({ id: mId, name: mName || `Machine ${mId}` });
    } else if (sec === 'ORDERS') {
      const [oId, oName, rMin, dMin, w] = cols;
      if (!oId) {
        errors.push({ sheet: 'Orders', row: lineNum, column: 'order_id', value: '', issue: 'Missing order ID.' });
        continue;
      }
      if (ordersMap.has(oId)) {
        errors.push({ sheet: 'Orders', row: lineNum, column: 'order_id', value: oId, issue: `Duplicate order ID '${oId}'.` });
        continue;
      }
      const release = Number(rMin ?? 0);
      const due = Number(dMin ?? 100);
      const weight = Number(w ?? 1);

      if (isNaN(release) || release < 0) {
        errors.push({ sheet: 'Orders', row: lineNum, column: 'release_minute', value: rMin, issue: 'Release minute must be non-negative integer.' });
      }
      if (isNaN(due) || due <= 0) {
        errors.push({ sheet: 'Orders', row: lineNum, column: 'due_minute', value: dMin, issue: 'Due minute must be strictly positive integer.' });
      }
      if (isNaN(weight) || weight <= 0) {
        errors.push({ sheet: 'Orders', row: lineNum, column: 'tardiness_weight', value: w, issue: 'Tardiness weight must be strictly positive integer.' });
      }

      ordersMap.set(oId, {
        id: oId,
        name: oName || `Order ${oId}`,
        release_minute: Math.max(0, isNaN(release) ? 0 : release),
        due_minute: Math.max(1, isNaN(due) ? 100 : due),
        tardiness_weight: Math.max(1, isNaN(weight) ? 1 : weight),
        operations: [],
      });
    } else if (sec === 'OPERATIONS') {
      const [oId, seqIdx, mId, procMin] = cols;
      if (!oId || !seqIdx || !mId || !procMin) {
        errors.push({ sheet: 'Operations', row: lineNum, column: 'row', value: rawLine, issue: 'Operation row requires order_id, sequence_index, machine_id, and processing_minutes.' });
        continue;
      }
      const seq = Number(seqIdx);
      const proc = Number(procMin);

      if (isNaN(seq) || seq < 1) {
        errors.push({ sheet: 'Operations', row: lineNum, column: 'sequence_index', value: seqIdx, issue: 'Sequence index must be integer >= 1.' });
      }
      if (isNaN(proc) || proc < 1) {
        errors.push({ sheet: 'Operations', row: lineNum, column: 'processing_minutes', value: procMin, issue: 'Processing minutes must be integer >= 1.' });
      }

      const order = ordersMap.get(oId);
      if (!order) {
        errors.push({ sheet: 'Operations', row: lineNum, column: 'order_id', value: oId, issue: `Operation references unknown order '${oId}'.` });
      } else {
        order.operations.push({
          id: `${oId}-OP${seq}`,
          order_id: oId,
          sequence_index: seq,
          machine_id: mId,
          processing_minutes: proc,
        });
      }
    } else if (sec === 'DOWNTIMES') {
      const [mId, sMin, eMin, reason] = cols;
      const start = Number(sMin);
      const end = Number(eMin);

      if (isNaN(start) || start < 0) {
        errors.push({ sheet: 'Downtimes', row: lineNum, column: 'start_minute', value: sMin, issue: 'Downtime start minute must be >= 0.' });
      }
      if (isNaN(end) || end <= start) {
        errors.push({ sheet: 'Downtimes', row: lineNum, column: 'end_minute', value: eMin, issue: 'Downtime end minute must be strictly greater than start minute.' });
      }

      downtimes.push({
        id: `dt-import-${downtimes.length + 1}`,
        machine_id: mId,
        start_minute: start,
        end_minute: end,
        reason: reason || 'Scheduled maintenance',
      });
    }
  }

  // Cross-table referential integrity validation
  const machineIds = new Set(machines.map((m) => m.id));

  for (const order of ordersMap.values()) {
    if (order.operations.length === 0) {
      warnings.push(`Order '${order.id}' has no operations defined.`);
    }
    const seqSet = new Set<number>();
    for (const op of order.operations) {
      if (!machineIds.has(op.machine_id)) {
        errors.push({
          sheet: 'Operations',
          row: 0,
          column: 'machine_id',
          value: op.machine_id,
          issue: `Operation '${op.id}' references unknown machine '${op.machine_id}'.`,
        });
      }
      if (seqSet.has(op.sequence_index)) {
        errors.push({
          sheet: 'Operations',
          row: 0,
          column: 'sequence_index',
          value: String(op.sequence_index),
          issue: `Order '${order.id}' contains duplicate sequence index ${op.sequence_index}.`,
        });
      }
      seqSet.add(op.sequence_index);
    }
  }

  for (const dt of downtimes) {
    if (!machineIds.has(dt.machine_id)) {
      errors.push({
        sheet: 'Downtimes',
        row: 0,
        column: 'machine_id',
        value: dt.machine_id,
        issue: `Downtime on machine '${dt.machine_id}' references unknown machine.`,
      });
    }
  }

  const isValid = errors.length === 0 && machines.length > 0;
  const jobId = isValid ? `job-demo-${Date.now()}` : '';

  const stagedOrders: OrderResponse[] = Array.from(ordersMap.values()).map((o) => ({
    id: o.id,
    external_id: o.id,
    name: o.name,
    release_minute: o.release_minute,
    due_minute: o.due_minute,
    tardiness_weight: o.tardiness_weight,
    operations: o.operations.map((op) => ({
      id: op.id,
      order_id: op.order_id,
      sequence_index: op.sequence_index,
      machine_id: op.machine_id,
      processing_minutes: op.processing_minutes,
      status: 'PLANNED',
      actual_start_minute: null,
      actual_end_minute: null,
      remaining_duration_minutes: null,
    })),
  }));

  const stagedMachines: MachineResponse[] = machines.map((m) => ({
    id: m.id,
    external_id: m.id,
    name: m.name,
    created_at: new Date().toISOString(),
  }));

  const stagedDowntimes: DowntimeResponse[] = downtimes.map((dt) => ({
    id: dt.id,
    machine_id: dt.machine_id,
    start_minute: dt.start_minute,
    end_minute: dt.end_minute,
    reason: dt.reason,
  }));

  const totalOps = stagedOrders.reduce((sum, o) => sum + o.operations.length, 0);

  const summary: ImportSummary = {
    machine_count: stagedMachines.length,
    order_count: stagedOrders.length,
    operation_count: totalOps,
    downtime_count: stagedDowntimes.length,
  };

  const stagedData: ImportStagedData = {
    machines: stagedMachines.map((m) => ({ external_id: m.external_id, name: m.name })),
    orders: stagedOrders.map((o) => ({
      external_id: o.external_id,
      name: o.name,
      release_minute: o.release_minute,
      due_minute: o.due_minute,
      tardiness_weight: o.tardiness_weight,
      operations: o.operations.map((op) => ({
        sequence_index: op.sequence_index,
        machine_id: op.machine_id,
        processing_minutes: op.processing_minutes,
      })),
    })),
    downtimes: stagedDowntimes.map((dt) => ({
      machine_id: dt.machine_id,
      start_minute: dt.start_minute,
      end_minute: dt.end_minute,
      reason: dt.reason,
    })),
  };

  if (isValid) {
    // Store staged data keyed by jobId
    demoStagedImports.set(jobId, stagedData);
  }

  return {
    job_id: jobId,
    filename: file.name,
    status: isValid ? 'VALIDATED' : 'FAILED',
    is_valid: isValid,
    summary,
    warnings,
    staged_data: stagedData,
    errors,
  };
}

/**
 * Confirm and atomically commit staged import job into the demo factory.
 */
export function confirmDemoImport(workspaceId: string, jobId: string): ImportConfirmResponse {
  const staged = demoStagedImports.get(jobId);
  if (!staged) {
    throw new ApiClientError(
      'RESOURCE_NOT_FOUND',
      `Staged import job '${jobId}' not found or already committed.`,
      404
    );
  }

  const factory = getMutableDemoFactory(workspaceId);

  // Atomically replace factory entities
  factory.machines = staged.machines.map((m) => ({
    id: m.external_id,
    external_id: m.external_id,
    name: m.name,
    created_at: new Date().toISOString(),
  }));

  factory.orders = staged.orders.map((o) => ({
    id: o.external_id,
    external_id: o.external_id,
    name: o.name,
    release_minute: o.release_minute,
    due_minute: o.due_minute,
    tardiness_weight: o.tardiness_weight,
    operations: (o.operations || []).map((op, i: number) => ({
      id: `${o.external_id}-OP${op.sequence_index || i + 1}`,
      order_id: o.external_id,
      sequence_index: op.sequence_index || i + 1,
      machine_id: op.machine_id,
      processing_minutes: op.processing_minutes,
      status: 'PLANNED' as const,
      actual_start_minute: null,
      actual_end_minute: null,
      remaining_duration_minutes: null,
    })),
  }));

  factory.downtimes = staged.downtimes.map((dt, idx) => ({
    id: `dt-imported-${idx + 1}`,
    machine_id: dt.machine_id,
    start_minute: dt.start_minute,
    end_minute: dt.end_minute,
    reason: dt.reason || 'Scheduled downtime',
  }));

  // Clean up staged import
  demoStagedImports.delete(jobId);

  return {
    job_id: jobId,
    status: 'COMMITTED',
    message: 'Demo import confirmed and committed to in-memory factory configuration.',
    factory: getDemoFactory(workspaceId),
  };
}
