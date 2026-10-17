import React, { useState } from 'react';
import { Button } from '../../components/common/Button';
import { apiEndpoints } from '../../api/endpoints';

export interface ExportActionButtonsProps {
  workspaceId: string;
  scheduleId: string;
}

export function ExportActionButtons({
  workspaceId,
  scheduleId,
}: ExportActionButtonsProps): React.ReactElement {
  const [downloadingFormat, setDownloadingFormat] = useState<'csv' | 'json' | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      setDownloadingFormat(format);
      setDownloadError(null);
      await apiEndpoints.downloadScheduleExport(workspaceId, scheduleId, format);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setDownloadError(msg);
    } finally {
      setDownloadingFormat(null);
    }
  };

  return (
    <div className="export-action-buttons flex flex-wrap items-center gap-3">
      <Button
        variant="secondary"
        onClick={() => handleExport('csv')}
        disabled={downloadingFormat !== null}
        className="text-xs font-medium border-slate-700 hover:border-slate-500"
      >
        {downloadingFormat === 'csv' ? (
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
            Generating CSV...
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            <span className="font-mono text-emerald-400 font-bold">CSV</span>
            Export (Sanitized)
          </span>
        )}
      </Button>

      <Button
        variant="secondary"
        onClick={() => handleExport('json')}
        disabled={downloadingFormat !== null}
        className="text-xs font-medium border-slate-700 hover:border-slate-500"
      >
        {downloadingFormat === 'json' ? (
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
            Generating JSON...
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            <span className="font-mono text-cyan-400 font-bold">JSON</span>
            Export (Full Audit)
          </span>
        )}
      </Button>

      {downloadError && (
        <span className="text-xs text-rose-400 font-mono">
          {downloadError}
        </span>
      )}
    </div>
  );
}
