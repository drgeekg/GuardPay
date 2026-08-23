import React, { useState } from 'react';
import { Play, Flame, ShieldAlert, Sparkles, CheckCircle } from 'lucide-react';
import { sendTransaction } from '../api';

const ATTACK_BINS = ['411111', '411112', '411113', '411114', '411115'];
const NORMAL_BINS = ['457173', '542418', '601200', '411082', '543210'];
const NORMAL_SUBNETS = ['49.207', '117.96', '223.196', '45.119'];

export default function SimulatorControls({ onAttackComplete }) {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState('');

  const runBurst = async (type = 'card_testing') => {
    setIsRunning(true);
    setProgress(0);
    const count = type === 'normal' ? 10 : 15;
    setStatusMsg(`Firing ${count} transactions (${type})...`);

    try {
      for (let i = 0; i < count; i++) {
        let txn;
        const now = new Date().toISOString();
        const randId = `txn_ui_${Math.random().toString(36).substring(2, 9)}`;

        if (type === 'card_testing') {
          txn = {
            transaction_id: randId,
            card_bin: '411111',
            amount_paise: 300,
            ip_address: `103.21.58.${(i % 15) + 1}`,
            timestamp: now,
          };
        } else if (type === 'bin_clustering') {
          txn = {
            transaction_id: randId,
            card_bin: ATTACK_BINS[i % ATTACK_BINS.length],
            amount_paise: 500,
            ip_address: `103.21.58.${(i % 10) + 1}`,
            timestamp: now,
          };
        } else {
          const subnet = NORMAL_SUBNETS[i % NORMAL_SUBNETS.length];
          txn = {
            transaction_id: randId,
            card_bin: NORMAL_BINS[i % NORMAL_BINS.length],
            amount_paise: Math.floor(Math.random() * 200000) + 5000,
            ip_address: `${subnet}.${Math.floor(Math.random() * 250) + 1}.${Math.floor(Math.random() * 250) + 1}`,
            timestamp: now,
          };
        }

        await sendTransaction(txn);
        setProgress(Math.round(((i + 1) / count) * 100));
        await new Promise((r) => setTimeout(r, 60)); // 60ms delay
      }

      setStatusMsg(`Complete! ${count} transactions processed.`);
      if (onAttackComplete) onAttackComplete();
    } catch (err) {
      setStatusMsg(`Error: ${err.message}`);
    } finally {
      setIsRunning(false);
      setTimeout(() => setStatusMsg(''), 4000);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-sky-400" />
            <h2 className="text-sm font-semibold text-slate-200">Interactive Attack Simulator</h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Trigger live synthetic fraud bursts to evaluate detection rules, LLM dossiers, and bounded actions.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => runBurst('card_testing')}
            disabled={isRunning}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 border border-rose-800 text-rose-300 text-xs font-medium transition disabled:opacity-50"
          >
            <Flame className="w-3.5 h-3.5" />
            <span>Card-Testing Burst (15 txn)</span>
          </button>

          <button
            onClick={() => runBurst('bin_clustering')}
            disabled={isRunning}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-amber-950/80 hover:bg-amber-900 border border-amber-800 text-amber-300 text-xs font-medium transition disabled:opacity-50"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>BIN Rotation Attack (15 txn)</span>
          </button>

          <button
            onClick={() => runBurst('normal')}
            disabled={isRunning}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-medium transition disabled:opacity-50"
          >
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
            <span>Normal Traffic (10 txn)</span>
          </button>
        </div>
      </div>

      {/* Progress & status feedback */}
      {(isRunning || statusMsg) && (
        <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
          <span>{statusMsg}</span>
          {isRunning && (
            <div className="w-32 bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-sky-500 h-full transition-all duration-100"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
