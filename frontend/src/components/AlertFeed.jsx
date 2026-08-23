import React from 'react';
import { AlertCircle, ShieldAlert, CheckCircle, Clock, ChevronRight, Layers } from 'lucide-react';

export default function AlertFeed({ alerts, selectedAlert, onSelectAlert }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center mx-auto mb-3 text-slate-500">
          <Layers className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-300">No Fraud Alerts</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
          The transaction stream is currently clean. Use the attack simulator above to fire a test burst.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-sky-400" />
          <h2 className="text-sm font-semibold text-slate-200">Incident Feed</h2>
        </div>
        <span className="px-2 py-0.5 text-xs font-semibold bg-slate-800 text-slate-400 rounded-full">
          {alerts.length} {alerts.length === 1 ? 'Incident' : 'Incidents'}
        </span>
      </div>

      <div className="divide-y divide-slate-800/80 max-h-[580px] overflow-y-auto">
        {alerts.map((alert) => {
          const isSelected = selectedAlert && selectedAlert.alert_id === alert.alert_id;
          const isHigh = alert.severity === 'high';

          return (
            <button
              key={alert.alert_id}
              onClick={() => onSelectAlert(alert)}
              className={`w-full text-left p-4 transition flex items-start justify-between group ${
                isSelected
                  ? 'bg-sky-950/40 border-l-4 border-sky-500 pl-3'
                  : 'hover:bg-slate-800/40 border-l-4 border-transparent'
              }`}
            >
              <div className="space-y-1.5 flex-1 pr-2">
                {/* Header line: ID + Badges */}
                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                  <span className="text-xs font-mono font-bold text-slate-300">
                    {alert.alert_id}
                  </span>

                  {/* Severity Badge */}
                  <span
                    className={`px-2 py-0.5 text-[11px] font-semibold rounded-md uppercase tracking-wider ${
                      isHigh
                        ? 'bg-rose-950 text-rose-300 border border-rose-800/80'
                        : 'bg-amber-950 text-amber-300 border border-amber-800/80'
                    }`}
                  >
                    {alert.severity}
                  </span>

                  {/* Pattern Badge */}
                  <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-slate-800 text-slate-300 border border-slate-700">
                    {alert.pattern_type.replace('_', ' ')}
                  </span>

                  {/* Overridden Badge */}
                  {alert.overridden && (
                    <span className="flex items-center space-x-1 px-1.5 py-0.5 text-[10px] font-medium bg-emerald-950 text-emerald-400 border border-emerald-800 rounded">
                      <CheckCircle className="w-3 h-3" />
                      <span>Overridden</span>
                    </span>
                  )}
                </div>

                {/* Subnet & BIN info */}
                <div className="text-xs text-slate-400">
                  <span>Subnet: </span>
                  <span className="font-mono text-slate-300">{alert.affected_subnet}</span>
                  <span className="mx-1.5">•</span>
                  <span>BIN: </span>
                  <span className="font-mono text-slate-300">{alert.affected_bin}</span>
                </div>

                {/* Meta footer: Txn count + relative time */}
                <div className="flex items-center space-x-3 text-[11px] text-slate-500 pt-0.5">
                  <span>{alert.transaction_ids?.length || 0} transactions</span>
                  <span>•</span>
                  <span className="flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>{new Date(alert.created_at).toLocaleTimeString()}</span>
                  </span>
                </div>
              </div>

              <ChevronRight
                className={`w-4 h-4 mt-2 transition ${
                  isSelected ? 'text-sky-400 translate-x-0.5' : 'text-slate-600 group-hover:text-slate-400'
                }`}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
