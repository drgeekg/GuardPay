import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import SimulatorControls from './components/SimulatorControls';
import AlertFeed from './components/AlertFeed';
import IncidentDossier from './components/IncidentDossier';
import ActionModal from './components/ActionModal';
import AuditLogView from './components/AuditLogView';
import { fetchHealth, fetchAlerts, fetchAuditLog, blockSubnet, enable3DS } from './api';

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Action Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [modalActionType, setModalActionType] = useState(null);
  const [isExecutingAction, setIsExecutingAction] = useState(false);

  // Refresh all state
  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await fetchHealth();
      setIsConnected(true);
    } catch {
      setIsConnected(false);
    }

    try {
      const [fetchedAlerts, fetchedLogs] = await Promise.all([
        fetchAlerts(),
        fetchAuditLog(),
      ]);

      setAlerts(fetchedAlerts);
      setAuditLogs(fetchedLogs);

      // Preserve or set selected alert
      setSelectedAlert((prev) => {
        if (!prev && fetchedAlerts.length > 0) return fetchedAlerts[0];
        if (prev) {
          const updated = fetchedAlerts.find((a) => a.alert_id === prev.alert_id);
          return updated || fetchedAlerts[0] || null;
        }
        return null;
      });
    } catch (err) {
      console.error('Error loading data:', err);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Initial load + periodic polling (every 3s)
  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Action trigger handlers
  const handleTriggerAction = (actionType, alert) => {
    setSelectedAlert(alert);
    setModalActionType(actionType);
    setModalOpen(true);
  };

  const handleConfirmAction = async (actionType) => {
    if (!selectedAlert) return;
    setIsExecutingAction(true);

    try {
      if (actionType === 'block_subnet') {
        await blockSubnet(selectedAlert.alert_id, 'merchant_demo');
      } else if (actionType === 'enable_3ds') {
        await enable3DS(selectedAlert.alert_id, 'merchant_demo');
      }
      setModalOpen(false);
      await loadData();
    } catch (err) {
      alert(`Mitigation failed: ${err.message}`);
    } finally {
      setIsExecutingAction(false);
    }
  };

  const handleOverrideSuccess = async () => {
    await loadData();
  };

  const handleUndoSuccess = async () => {
    await loadData();
  };

  return (
    <div className="min-h-screen bg-[#0b1120] text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {/* Top Header */}
      <Header
        isConnected={isConnected}
        isRefreshing={isRefreshing}
        onRefresh={loadData}
        alertCount={alerts.length}
      />

      {/* Main Content Dashboard */}
      <main className="max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6 flex-1">
        {/* Interactive Simulator Banner */}
        <SimulatorControls onAttackComplete={loadData} />

        {/* Core Two-Column Triage Desk */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Live Incident Feed (5 cols) */}
          <div className="lg:col-span-5">
            <AlertFeed
              alerts={alerts}
              selectedAlert={selectedAlert}
              onSelectAlert={setSelectedAlert}
            />
          </div>

          {/* Right Column: AI Incident Dossier & Mitigations (7 cols) */}
          <div className="lg:col-span-7">
            <IncidentDossier
              alert={selectedAlert}
              onTriggerAction={handleTriggerAction}
              onOverrideSuccess={handleOverrideSuccess}
            />
          </div>
        </div>

        {/* Bottom Section: Immutable Audit Trail */}
        <div className="pt-2">
          <AuditLogView logs={auditLogs} onUndoSuccess={handleUndoSuccess} />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-4 px-6 text-center text-xs text-slate-500">
        GuardPay — AI Risk Manager for Razorpay Merchants • Bounded, Gated & Reversible Defense Desk
      </footer>

      {/* Gated Action Confirmation Modal */}
      <ActionModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={handleConfirmAction}
        actionType={modalActionType}
        alert={selectedAlert}
        isExecuting={isExecutingAction}
      />
    </div>
  );
}
