/**
 * Client-Side CSV & JSON Data Export for Standalone Demo Mode
 * Governed by SPECIFICATION.md Section 5.2 and Milestone 11 standards.
 */

import { ScheduleDetailResponse } from '../types/api';
import { ScheduleReportResponse } from '../types/reports';

export function downloadClientBlob(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export function exportDemoScheduleCsv(schedule: ScheduleDetailResponse): void {
  const headers = [
    'operation_id',
    'order_id',
    'sequence_index',
    'machine_id',
    'start_minute',
    'end_minute',
    'duration_minutes',
    'slack_minutes',
  ];

  const rows = schedule.scheduled_operations.map((op) => [
    op.operation_id,
    op.order_id,
    op.sequence_index,
    op.machine_id,
    op.start_minute,
    op.end_minute,
    op.duration,
    op.slack_minutes,
  ]);

  const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\r\n');
  downloadClientBlob(csvContent, `schedule_${schedule.id}_export.csv`, 'text/csv;charset=utf-8;');
}

export function exportDemoScheduleJson(report: ScheduleReportResponse): void {
  const jsonContent = JSON.stringify(report, null, 2);
  downloadClientBlob(jsonContent, `schedule_${report.schedule_id}_report.json`, 'application/json;charset=utf-8;');
}
