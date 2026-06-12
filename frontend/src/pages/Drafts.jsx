import { useState } from 'react';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { Badge, Button, Card, EmptyState, ErrorBanner, Modal, Spinner } from '../components/ui';
import { Header } from './Dashboard';
import { theme } from '../theme';
import { formatDate, relativeTime } from '../utils/format';

const t = theme;

const STATUS_TONE = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  published: 'info',
};

export default function Drafts() {
  const [limit, setLimit] = useState(50);
  const { data, error, loading, refetch } = useApi(() => api.listDrafts(limit, 0), [limit]);
  const [selected, setSelected] = useState(null);
  const [copied, setCopied] = useState(false);

  const copy = async (text) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Header
        title="Drafts"
        subtitle="LinkedIn-ready posts generated from monitored sources."
        actions={
          <>
            <Button variant="secondary" onClick={refetch}>
              ↻ Refresh
            </Button>
            <Button variant="secondary" onClick={() => setLimit((n) => n + 50)}>
              Load more
            </Button>
          </>
        }
      />

      <ErrorBanner error={error} onRetry={refetch} />

      {loading && !data ? (
        <Card style={{ display: 'flex', alignItems: 'center', gap: 12, color: t.colors.textMuted }}>
          <Spinner /> Loading drafts…
        </Card>
      ) : !data?.length ? (
        <EmptyState title="No drafts yet" hint="Once the pipeline processes content from your sources, drafts will appear here." />
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {data.map((d) => (
            <DraftCard key={d.id} draft={d} onOpen={() => setSelected(d)} />
          ))}
        </div>
      )}

      {selected && (
        <Modal
          open
          onClose={() => setSelected(null)}
          title={selected.title}
          footer={
            <>
              <Button variant="secondary" onClick={() => copy(selected.body)}>
                {copied ? '✓ Copied' : 'Copy body'}
              </Button>
              <Button onClick={() => window.open(selected.original_url, '_blank', 'noopener')}>
                View original ↗
              </Button>
            </>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Badge tone={STATUS_TONE[selected.status]}>{selected.status}</Badge>
              <Badge tone="accent">score {selected.evaluation_score.toFixed(2)}</Badge>
              <Badge>{formatDate(selected.created_at)}</Badge>
            </div>
            <Section label="Evaluation">
              <div style={{ color: t.colors.textMuted, fontSize: 13, lineHeight: 1.6 }}>
                {selected.evaluation_reason}
              </div>
            </Section>
            <Section label="Body">
              <div
                style={{
                  whiteSpace: 'pre-wrap',
                  fontSize: 14,
                  lineHeight: 1.65,
                  background: t.colors.bg,
                  padding: 14,
                  borderRadius: t.radius.md,
                  border: `1px solid ${t.colors.border}`,
                  maxHeight: 360,
                  overflow: 'auto',
                }}
              >
                {selected.body}
              </div>
            </Section>
            <Section label="Source URL">
              <a
                href={selected.original_url}
                target="_blank"
                rel="noopener"
                style={{ color: t.colors.accent, fontSize: 12, fontFamily: t.font.mono, wordBreak: 'break-all' }}
              >
                {selected.original_url}
              </a>
            </Section>
          </div>
        </Modal>
      )}
    </div>
  );
}

function DraftCard({ draft, onOpen }) {
  return (
    <Card
      onClick={onOpen}
      style={{
        padding: 18,
        cursor: 'pointer',
        transition: `border-color ${t.transition}, transform ${t.transition}`,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = t.colors.borderStrong;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = t.colors.border;
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, lineHeight: 1.4 }}>{draft.title}</h3>
          <p
            style={{
              margin: '8px 0 0',
              color: t.colors.textMuted,
              fontSize: 13,
              lineHeight: 1.55,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {draft.body}
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
          <Badge tone={STATUS_TONE[draft.status]}>{draft.status}</Badge>
          <span style={{ fontSize: 11, color: t.colors.textDim }}>{relativeTime(draft.created_at)}</span>
          <span style={{ fontSize: 11, color: t.colors.textDim, fontFamily: t.font.mono }}>
            {draft.evaluation_score.toFixed(2)}
          </span>
        </div>
      </div>
    </Card>
  );
}

function Section({ label, children }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          color: t.colors.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '.05em',
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}
