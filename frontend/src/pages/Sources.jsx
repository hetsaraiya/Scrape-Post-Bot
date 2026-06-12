import { useState } from 'react';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Modal, Select, Spinner } from '../components/ui';
import { Header, SectionTitle } from './Dashboard';
import { theme } from '../theme';
import { formatInterval, relativeTime } from '../utils/format';

const t = theme;

const SOURCE_TYPES = ['rss', 'blog', 'twitter', 'reddit', 'youtube', 'arxiv'];

export default function Sources() {
  const { data, error, loading, refetch } = useApi(api.listSources, []);
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (m) => {
    setToast(m);
    setTimeout(() => setToast(null), 2500);
  };

  const handleDelete = async (s) => {
    if (!confirm(`Delete "${s.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteSource(s.id);
      showToast('Source deleted');
      refetch();
    } catch (e) {
      showToast(e.message);
    }
  };

  const handlePoll = async (s) => {
    try {
      await api.pollSource(s.id);
      showToast(`Polling "${s.name}"`);
    } catch (e) {
      showToast(e.message);
    }
  };

  const handleToggle = async (s) => {
    try {
      await api.updateSource(s.id, { is_active: !s.is_active });
      refetch();
    } catch (e) {
      showToast(e.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Header
        title="Sources"
        subtitle="The feeds and pages the pipeline watches."
        actions={<Button onClick={() => setCreating(true)}>Add source</Button>}
      />

      <ErrorBanner error={error} onRetry={refetch} />

      {loading && !data ? (
        <Card style={{ display: 'flex', alignItems: 'center', gap: 12, color: t.colors.textMuted }}>
          <Spinner /> Loading sources…
        </Card>
      ) : !data?.length ? (
        <EmptyState
          title="No sources yet"
          hint="Add a feed or page and the pipeline will start watching it."
          action={<Button onClick={() => setCreating(true)}>Add source</Button>}
        />
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {data.map((s) => (
            <SourceRow
              key={s.id}
              source={s}
              onEdit={() => setEditing(s)}
              onDelete={() => handleDelete(s)}
              onPoll={() => handlePoll(s)}
              onToggle={() => handleToggle(s)}
            />
          ))}
        </div>
      )}

      {(creating || editing) && (
        <SourceForm
          source={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={(msg) => {
            showToast(msg);
            refetch();
            setCreating(false);
            setEditing(null);
          }}
        />
      )}

      {toast && (
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
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

function SourceRow({ source: s, onEdit, onDelete, onPoll, onToggle }) {
  return (
    <Card style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>{s.name}</span>
          <Badge tone="accent">{s.type}</Badge>
          <Badge tone={s.is_active ? 'success' : 'neutral'}>{s.is_active ? 'Active' : 'Paused'}</Badge>
          {s.error_count > 0 && <Badge tone="danger">{s.error_count} errors</Badge>}
        </div>
        <div
          style={{
            color: t.colors.textMuted,
            fontSize: 12,
            fontFamily: t.font.mono,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {s.url}
        </div>
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12, color: t.colors.textDim }}>
          <span>Checks every {formatInterval(s.poll_interval)}</span>
          <span>Last checked {relativeTime(s.last_poll_at)}</span>
          {s.last_error && <span style={{ color: t.colors.danger }}>{s.last_error}</span>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <Button variant="ghost" size="sm" onClick={onPoll} title="Check this source now">
          Check now
        </Button>
        <Button variant="ghost" size="sm" onClick={onToggle}>
          {s.is_active ? 'Pause' : 'Resume'}
        </Button>
        <Button variant="secondary" size="sm" onClick={onEdit}>
          Edit
        </Button>
        <Button variant="danger" size="sm" onClick={onDelete}>
          Delete
        </Button>
      </div>
    </Card>
  );
}

function SourceForm({ source, onClose, onSaved }) {
  const isEdit = !!source;
  const [form, setForm] = useState({
    name: source?.name || '',
    url: source?.url || '',
    type: source?.type || 'rss',
    poll_interval: source?.poll_interval || 900,
    is_active: source?.is_active ?? true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setErr(null);
    setSubmitting(true);
    try {
      if (isEdit) {
        await api.updateSource(source.id, {
          name: form.name,
          url: form.url,
          poll_interval: Number(form.poll_interval),
          is_active: form.is_active,
        });
        onSaved('Source updated');
      } else {
        await api.createSource({
          name: form.name,
          url: form.url,
          type: form.type,
          poll_interval: Number(form.poll_interval),
        });
        onSaved('Source created');
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? 'Edit source' : 'New source'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={submitting} disabled={!form.name || !form.url}>
            {isEdit ? 'Save changes' : 'Create source'}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {err && <ErrorBanner error={{ message: err }} />}
        <Input label="Name" value={form.name} onChange={(e) => update('name', e.target.value)} placeholder="e.g. OpenAI Blog" />
        <Input label="URL" value={form.url} onChange={(e) => update('url', e.target.value)} placeholder="https://…" />
        {!isEdit && (
          <Select label="Type" value={form.type} onChange={(e) => update('type', e.target.value)}>
            {SOURCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        )}
        <Input
          label="Poll interval (seconds)"
          type="number"
          min={60}
          max={86400}
          value={form.poll_interval}
          onChange={(e) => update('poll_interval', e.target.value)}
        />
        {isEdit && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: t.colors.textMuted }}>
            <input type="checkbox" checked={form.is_active} onChange={(e) => update('is_active', e.target.checked)} />
            Active
          </label>
        )}
      </div>
    </Modal>
  );
}
