import { useApi } from '../hooks/useApi';
import { api } from '../api/client';
import { Badge, Button, Card, EmptyState, ErrorBanner, Spinner, Stat } from '../components/ui';
import { theme } from '../theme';
import { relativeTime } from '../utils/format';
import { useState } from 'react';

const t = theme;

export default function Dashboard() {
  const status = useApi(api.pipelineStatus, [], { pollMs: 5000 });
  const metrics = useApi(api.pipelineMetrics, [], { pollMs: 5000 });
  const [running, setRunning] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const runPipeline = async () => {
    setRunning(true);
    try {
      const res = await api.pipelineRun();
      showToast(res?.message || 'Pipeline triggered');
    } catch (e) {
      showToast(e.message);
    } finally {
      setRunning(false);
      status.refetch();
    }
  };

  const resetMetrics = async () => {
    if (!confirm('Reset all pipeline metrics to zero?')) return;
    setResetting(true);
    try {
      await api.pipelineMetricsReset();
      showToast('Metrics reset');
      metrics.refetch();
    } catch (e) {
      showToast(e.message);
    } finally {
      setResetting(false);
    }
  };

  const evalTotal = (metrics.data?.eval_passed || 0) + (metrics.data?.eval_failed || 0);
  const passRate = evalTotal ? Math.round((metrics.data.eval_passed / evalTotal) * 100) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Header
        title="Dashboard"
        subtitle="Real-time pipeline status and processing metrics."
        actions={
          <>
            <Button variant="secondary" onClick={resetMetrics} loading={resetting}>
              Reset metrics
            </Button>
            <Button onClick={runPipeline} loading={running}>
              ▶ Run pipeline
            </Button>
          </>
        }
      />

      <ErrorBanner error={status.error} onRetry={status.refetch} />

      <section>
        <SectionTitle>Pipeline status</SectionTitle>
        {status.loading && !status.data ? (
          <CardSkeleton />
        ) : status.data ? (
          <Card>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 20 }}>
              <StatusItem
                label="Worker"
                value={
                  <Badge tone={status.data.worker_running ? 'success' : 'danger'}>
                    {status.data.worker_running ? 'Running' : 'Stopped'}
                  </Badge>
                }
              />
              <StatusItem label="State" value={<code style={codeStyle}>{status.data.worker_state}</code>} />
              <StatusItem label="Queue depth" value={status.data.queue_depth} />
              <StatusItem label="Active sources" value={status.data.active_sources} />
              <StatusItem
                label="Enabled"
                value={<Badge tone={status.data.pipeline_enabled ? 'success' : 'warning'}>{status.data.pipeline_enabled ? 'Yes' : 'No'}</Badge>}
              />
              <StatusItem label="Last heartbeat" value={relativeTime(status.data.last_heartbeat)} />
            </div>
          </Card>
        ) : null}
      </section>

      <section>
        <SectionTitle>Processing metrics</SectionTitle>
        {metrics.loading && !metrics.data ? (
          <CardSkeleton />
        ) : metrics.data ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <Stat label="Items processed" value={metrics.data.items_processed} />
            <Stat label="Dedup hits" value={metrics.data.dedup_hits} tone="accent" />
            <Stat label="Eval passed" value={metrics.data.eval_passed} tone="success" />
            <Stat label="Eval failed" value={metrics.data.eval_failed} tone="danger" />
            <Stat label="Gen success" value={metrics.data.gen_success} tone="success" />
            <Stat label="Gen errors" value={metrics.data.gen_errors} tone="danger" />
            <Stat label="Pass rate" value={`${passRate}%`} />
          </div>
        ) : (
          <EmptyState title="No metrics yet" hint="Run the pipeline to start collecting metrics." />
        )}
      </section>

      {toast && <Toast>{toast}</Toast>}
    </div>
  );
}

function StatusItem({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: t.colors.textMuted, textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ marginTop: 6, fontSize: 14, fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <Card style={{ display: 'flex', alignItems: 'center', gap: 12, color: t.colors.textMuted }}>
      <Spinner /> Loading…
    </Card>
  );
}

export function Header({ title, subtitle, actions }) {
  return (
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-.01em' }}>{title}</h1>
        {subtitle && <p style={{ margin: '6px 0 0', color: t.colors.textMuted, fontSize: 13 }}>{subtitle}</p>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>{actions}</div>
    </header>
  );
}

export function SectionTitle({ children }) {
  return (
    <h2 style={{ fontSize: 12, fontWeight: 600, color: t.colors.textMuted, textTransform: 'uppercase', letterSpacing: '.08em', margin: '0 0 12px' }}>
      {children}
    </h2>
  );
}

const codeStyle = {
  background: t.colors.surfaceAlt,
  padding: '3px 8px',
  borderRadius: 4,
  fontSize: 12,
  fontFamily: t.font.mono,
};

function Toast({ children }) {
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        background: t.colors.surface,
        border: `1px solid ${t.colors.border}`,
        padding: '10px 16px',
        borderRadius: t.radius.md,
        boxShadow: t.shadow.md,
        fontSize: 13,
        zIndex: 100,
        animation: 'slideUp .2s ease',
      }}
    >
      {children}
    </div>
  );
}
