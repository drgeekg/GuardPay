import React, { useState } from 'react';
import { History, Undo2, CheckCircle2, Shield, User, Clock, AlertCircle } from 'lucide-react';
import { undoAction } from '../api';

export default function AuditLogView({ logs, onUndoSuccess }) {
  const [undoingId, setUndoingId] = useState(null);

  const handleUndo = async (actionId) => {
    if (!actionId) return;
    if (!window.confirm(`Reverse mitigation action ${actionId}? This will restore traffic immediately.`)) {
      return;
    }

    setUndoingId(actionId);
    try {
      await undoAction(actionId, 'merchant_admin');
      if (onUndoSuccess) onUndoSuccess();
    } catch (err) {
      alert(`Failed to undo action: ${err.message}`);
    } finally {
      setUndoingId(null);
    }
  };

  if (!logs || logs.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
        <History className="w-8 h-8 text-slate-700 mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-slate-400">Audit Trail is Empty</h3>
        <p className="text-xs text-slate-500 mt-1">
          Every mitigation action, undo operation, and merchant override will be immutably recorded here.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <div className="px-6 py-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center space-x-2">
          <History className="w-4 h-4 text-sky-400" />
          <h2 className="text-sm font-semibold text-slate-200">Immutable Audit Log</h2>
        </div>
        <span className="text-xs text-slate-500">
          Source of truth for explainable & reversible mitigations
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-semibold">
            <tr>
              <th className="py-3 px-4">Audit ID</th>
              <th className="py-3 px-4">Action Type</th>
              <th className="py-3 px-4">Actor</th>
              <th className="py-3 px-4">Reason / Blast Radius</th>
              <th className="py-3 px-4">Time</th>
              <th className="py-3 px-4">Status / Reversibility</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {logs.map((entry) => {
              const isUndoable = entry.action_id && !entry.undone && entry.action_type !== 'undo' && entry.action_type !== 'override';
              const isUndone = entry.undone;

              return (
                <tr key={entry.audit_log_id} className="hover:bg-slate-800/30 transition">
                  {/* Audit ID */}
                  <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                    {entry.audit_log_id}
                  </td>

                  {/* Action Type */}
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${
                        entry.action_type === 'block_subnet'
                          ? 'bg-rose-950 text-rose-300 border border-rose-800/60'
                          : entry.action_type === 'enable_3ds'
                          ? 'bg-indigo-950 text-indigo-300 border border-indigo-800/60'
                          : entry.action_type === 'undo'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800/60'
                          : 'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}
                    >
                      {entry.action_type.replace('_', ' ')}
                    </span>
                  </td>

                  {/* Actor */}
                  <td className="py-3 px-4 text-slate-400 flex items-center space-x-1.5 pt-3.5">
                    <User className="w-3 h-3 text-slate-500" />
                    <span>{entry.actor}</span>
                  </td>

                  {/* Reason */}
                  <td className="py-3 px-4 max-w-xs text-slate-200">
                    {entry.reason}
                  </td>

                  {/* Time */}
                  <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </td>

                  {/* Reversibility Status */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    {isUndone ? (
                      <span className="text-amber-400 text-[11px] font-medium">Reversed (Undone)</span>
                    ) : entry.reversible_until ? (
                      <span className="text-emerald-400 text-[11px] font-medium">Active (24h bounded)</span>
                    ) : (
                      <span className="text-slate-500 text-[11px]">—</span>
                    )}
                  </td>

                  {/* Undo Button */}
                  <td className="py-3 px-4 text-right">
                    {isUndoable ? (
                      <button
                        onClick={() => handleUndo(entry.action_id)}
                        disabled={undoingId === entry.action_id}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-amber-950/80 hover:bg-amber-900 text-amber-300 text-[11px] font-semibold border border-amber-800 transition disabled:opacity-50"
                      >
                        <Undo2 className="w-3 h-3" />
                        <span>{undoingId === entry.action_id ? 'Undoing...' : 'Undo Action'}</span>
                      </button>
                    ) : (
                      <span className="text-slate-600 text-[11px]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
