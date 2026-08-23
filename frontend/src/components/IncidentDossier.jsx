import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  AlertOctagon, 
  IndianRupee, 
  Target, 
  Gauge, 
  ShieldCheck, 
  ShieldX, 
  Check, 
  HelpCircle,
  FileText,
  Lock,
  ArrowRight
} from 'lucide-react';
import { fetchDossier, overrideAlert } from '../api';

export default function IncidentDossier({ alert, onTriggerAction, onOverrideSuccess }) {
  const [dossier, setDossier] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isOverriding, setIsOverriding] = useState(false);

  useEffect(() => {
    if (!alert) {
      setDossier(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    fetchDossier(alert.alert_id)
      .then((data) => {
        if (isMounted) setDossier(data);
      })
      .catch((err) => {
        if (isMounted) setError(err.message);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [alert?.alert_id]);

  if (!alert) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center h-full flex flex-col items-center justify-center">
        <FileText className="w-10 h-10 text-slate-700 mb-3" />
        <h3 className="text-sm font-semibold text-slate-400">No Incident Selected</h3>
        <p className="text-xs text-slate-600 mt-1 max-w-sm">
          Select an incident from the live feed on the left to inspect its AI-generated root cause, financial blast radius, and one-click mitigations.
        </p>
      </div>
    );
  }

  const handleOverride = async () => {
    if (!window.confirm(`Mark ${alert.alert_id} as a false positive? This will be recorded in the audit log.`)) {
      return;
    }
    setIsOverriding(true);
    try {
      await overrideAlert(alert.alert_id, 'merchant_demo');
      if (onOverrideSuccess) onOverrideSuccess(alert.alert_id);
    } catch (err) {
      alert(`Override failed: ${err.message}`);
    } finally {
      setIsOverriding(false);
    }
  };

  const formattedFeeInr = dossier?.estimated_fee_damage_paise
    ? `₹ ${(dossier.estimated_fee_damage_paise / 100).toLocaleString('en-IN')}`
    : 'Calculating...';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm flex flex-col h-full">
      {/* Dossier Header */}
      <div className="px-6 py-4 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-sky-950 text-sky-400 border border-sky-800 rounded-lg">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-white">Incident Dossier</h2>
              <span className="font-mono text-xs text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-900">
                {alert.alert_id}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Synthesized by AI Risk Agent • Zero Latency on Ingestion</p>
          </div>
        </div>

        {/* Override Button */}
        {!alert.overridden ? (
          <button
            onClick={handleOverride}
            disabled={isOverriding}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
          >
            <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
            <span>Mark False Positive</span>
          </button>
        ) : (
          <span className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800 rounded-lg">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Overridden (Logged)</span>
          </span>
        )}
      </div>

      {/* Dossier Content */}
      <div className="p-6 space-y-6 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-6 h-6 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-xs text-slate-400">Generating AI incident dossier narrative...</p>
          </div>
        ) : error ? (
          <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-xs text-rose-300">
            Error loading dossier: {error}
          </div>
        ) : dossier ? (
          <>
            {/* Top Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Fee Damage */}
              <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-1">
                <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                  <IndianRupee className="w-3.5 h-3.5 text-amber-400" />
                  <span>Estimated Gateway Loss</span>
                </div>
                <div className="text-lg font-bold text-amber-400 font-mono">
                  {formattedFeeInr}
                </div>
                <div className="text-[10px] text-slate-500">Auth fees & fraud risk</div>
              </div>

              {/* Blast Radius */}
              <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-1">
                <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                  <Target className="w-3.5 h-3.5 text-rose-400" />
                  <span>Attack Blast Radius</span>
                </div>
                <div className="text-xs font-semibold text-slate-200 truncate" title={dossier.blast_radius}>
                  {dossier.blast_radius}
                </div>
                <div className="text-[10px] text-slate-500">Subnets & cards involved</div>
              </div>

              {/* Confidence */}
              <div className="bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-1">
                <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                  <Gauge className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Detection Confidence</span>
                </div>
                <div className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                  {dossier.confidence}
                </div>
                <div className="text-[10px] text-slate-500">Deterministic rule verified</div>
              </div>
            </div>

            {/* Root Cause Technical Narrative */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <AlertOctagon className="w-3.5 h-3.5 text-sky-400" />
                <span>Threat Root Cause</span>
              </h3>
              <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs text-slate-200 leading-relaxed font-sans">
                {dossier.root_cause}
              </div>
            </div>

            {/* Plain-Language Merchant Summary */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                <span>Executive Summary & Recommendation</span>
              </h3>
              <div className="bg-gradient-to-br from-indigo-950/30 to-slate-950/80 border border-indigo-900/40 p-4 rounded-xl text-xs text-indigo-200 leading-relaxed">
                {dossier.summary}
              </div>
            </div>
          </>
        ) : null}
      </div>

      {/* Bounded Mitigation Action Bar */}
      <div className="px-6 py-4 bg-slate-950/90 border-t border-slate-800">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-slate-400 flex items-center space-x-1.5">
            <Lock className="w-3.5 h-3.5 text-slate-500" />
            <span>Every action is bounded, gated, and reversible.</span>
          </div>

          <div className="flex items-center space-x-2.5 w-full sm:w-auto">
            <button
              onClick={() => onTriggerAction('block_subnet', alert)}
              className="flex-1 sm:flex-none flex items-center justify-center space-x-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-600/20 transition"
            >
              <ShieldX className="w-3.5 h-3.5" />
              <span>Auto-Block Subnet</span>
            </button>

            <button
              onClick={() => onTriggerAction('enable_3ds', alert)}
              className="flex-1 sm:flex-none flex items-center justify-center space-x-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-lg shadow-indigo-600/20 transition"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Enable 3DS Step-up</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
