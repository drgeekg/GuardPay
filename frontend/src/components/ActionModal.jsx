import React, { useState } from 'react';
import { ShieldCheck, AlertTriangle, X, Check, Clock, Lock } from 'lucide-react';

export default function ActionModal({ isOpen, onClose, onConfirm, actionType, alert, isExecuting }) {
  const [acknowledged, setAcknowledged] = useState(false);

  if (!isOpen || !alert) return null;

  const isBlock = actionType === 'block_subnet';
  const title = isBlock ? 'Confirm Subnet Auto-Block' : 'Confirm Mandatory 3DS Step-up';
  const targetDesc = isBlock ? `Subnet ${alert.affected_subnet}` : `Card BIN ${alert.affected_bin}`;
  const blastRadius = isBlock
    ? `All future transaction attempts from IP range ${alert.affected_subnet} will be declined automatically.`
    : `All future transaction attempts using BIN ${alert.affected_bin} will require mandatory OTP / 3DS authentication.`;

  const handleConfirm = () => {
    if (!acknowledged) return;
    onConfirm(actionType);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-2.5">
            <div className={`p-2 rounded-lg ${isBlock ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-indigo-950 text-indigo-400 border border-indigo-800'}`}>
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">{title}</h3>
              <p className="text-xs text-slate-400">Bounded & Gated Risk Mitigation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4">
          {/* Target Box */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Mitigation Target</div>
            <div className="text-sm font-mono font-bold text-sky-400">{targetDesc}</div>
          </div>

          {/* Blast Radius & Effect */}
          <div className="space-y-2 text-xs text-slate-300">
            <div className="font-semibold text-slate-200">Blast Radius & Policy Impact:</div>
            <p className="text-slate-300 leading-relaxed bg-slate-800/40 p-3 rounded-lg border border-slate-800">
              {blastRadius}
            </p>
          </div>

          {/* Guarantees Box */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="bg-slate-950/60 border border-slate-800/80 p-2.5 rounded-lg flex items-center space-x-2 text-slate-300">
              <Clock className="w-4 h-4 text-amber-400 shrink-0" />
              <span>Bounded: 24h expiration</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800/80 p-2.5 rounded-lg flex items-center space-x-2 text-slate-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>100% Reversible via Audit Log</span>
            </div>
          </div>

          {/* Gating Acknowledgment Checkbox */}
          <label className="flex items-start space-x-3 p-3 rounded-xl bg-sky-950/20 border border-sky-900/40 cursor-pointer select-none hover:bg-sky-950/30 transition">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              className="mt-0.5 w-4 h-4 rounded text-sky-600 bg-slate-800 border-slate-700 focus:ring-sky-500"
            />
            <span className="text-xs text-slate-300 leading-normal">
              I acknowledge the blast radius of this action and authorize GuardPay to enforce this 24-hour mitigation policy.
            </span>
          </label>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-slate-950/80 border-t border-slate-800 flex items-center justify-end space-x-3">
          <button
            onClick={onClose}
            disabled={isExecuting}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!acknowledged || isExecuting}
            className={`flex items-center space-x-1.5 px-4 py-2 text-xs font-bold rounded-lg shadow-md transition disabled:opacity-40 ${
              isBlock
                ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/20'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/20'
            }`}
          >
            {isExecuting ? (
              <span>Executing...</span>
            ) : (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Confirm & Apply Mitigation</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
