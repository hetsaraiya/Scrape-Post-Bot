import { useEffect } from 'react';
import { theme } from '../theme';

const t = theme;

export function Button({ variant = 'primary', size = 'md', loading, children, style, disabled, ...rest }) {
  const variants = {
    primary: { background: t.colors.accent, color: '#fff', border: `1px solid ${t.colors.accent}` },
    secondary: { background: t.colors.surfaceAlt, color: t.colors.text, border: `1px solid ${t.colors.border}` },
    ghost: { background: 'transparent', color: t.colors.textMuted, border: `1px solid transparent` },
    danger: { background: 'transparent', color: t.colors.danger, border: `1px solid ${t.colors.border}` },
  };
  const sizes = {
    sm: { padding: '6px 10px', fontSize: 12 },
    md: { padding: '9px 14px', fontSize: 13 },
    lg: { padding: '12px 18px', fontSize: 14 },
  };
  return (
    <button
      disabled={disabled || loading}
      style={{
        ...variants[variant],
        ...sizes[size],
        borderRadius: t.radius.md,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        fontWeight: 500,
        fontFamily: t.font.body,
        transition: `all ${t.transition}`,
        opacity: disabled || loading ? 0.6 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        ...style,
      }}
      {...rest}
    >
      {loading && <Spinner size={12} />}
      {children}
    </button>
  );
}

export function Input({ label, error, style, ...rest }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {label && (
        <span style={{ fontSize: 12, color: t.colors.textMuted, fontWeight: 500 }}>{label}</span>
      )}
      <input
        style={{
          background: t.colors.bg,
          color: t.colors.text,
          border: `1px solid ${error ? t.colors.danger : t.colors.border}`,
          borderRadius: t.radius.md,
          padding: '10px 12px',
          fontSize: 13,
          fontFamily: t.font.body,
          outline: 'none',
          transition: `border-color ${t.transition}`,
          ...style,
        }}
        onFocus={(e) => (e.target.style.borderColor = t.colors.accent)}
        onBlur={(e) => (e.target.style.borderColor = error ? t.colors.danger : t.colors.border)}
        {...rest}
      />
      {error && <span style={{ fontSize: 11, color: t.colors.danger }}>{error}</span>}
    </label>
  );
}

export function Select({ label, children, ...rest }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {label && (
        <span style={{ fontSize: 12, color: t.colors.textMuted, fontWeight: 500 }}>{label}</span>
      )}
      <select
        style={{
          background: t.colors.bg,
          color: t.colors.text,
          border: `1px solid ${t.colors.border}`,
          borderRadius: t.radius.md,
          padding: '10px 12px',
          fontSize: 13,
          fontFamily: t.font.body,
          outline: 'none',
        }}
        {...rest}
      >
        {children}
      </select>
    </label>
  );
}

export function Card({ children, style, ...rest }) {
  return (
    <div
      style={{
        background: t.colors.surface,
        border: `1px solid ${t.colors.border}`,
        borderRadius: t.radius.lg,
        padding: 20,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Badge({ tone = 'neutral', children }) {
  const tones = {
    neutral: { bg: t.colors.surfaceAlt, fg: t.colors.textMuted },
    success: { bg: 'rgba(61,220,151,.12)', fg: t.colors.success },
    warning: { bg: 'rgba(255,180,84,.12)', fg: t.colors.warning },
    danger: { bg: 'rgba(255,107,107,.12)', fg: t.colors.danger },
    info: { bg: 'rgba(92,184,255,.12)', fg: t.colors.info },
    accent: { bg: 'rgba(124,92,255,.15)', fg: t.colors.accent },
  };
  const c = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        padding: '3px 9px',
        borderRadius: t.radius.pill,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '.02em',
        textTransform: 'uppercase',
        display: 'inline-block',
      }}
    >
      {children}
    </span>
  );
}

export function Spinner({ size = 16 }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        border: `2px solid ${t.colors.border}`,
        borderTopColor: t.colors.accent,
        borderRadius: '50%',
        display: 'inline-block',
        animation: 'spin .8s linear infinite',
      }}
    />
  );
}

export function EmptyState({ title, hint, action }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 20px',
        textAlign: 'center',
        gap: 8,
      }}
    >
      <div style={{ fontSize: 15, fontWeight: 600, color: t.colors.text }}>{title}</div>
      {hint && <div style={{ fontSize: 13, color: t.colors.textMuted, maxWidth: 360 }}>{hint}</div>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  return (
    <div
      style={{
        background: 'rgba(255,107,107,.08)',
        border: `1px solid rgba(255,107,107,.3)`,
        color: t.colors.danger,
        padding: '10px 14px',
        borderRadius: t.radius.md,
        fontSize: 13,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <span>{error.message || String(error)}</span>
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,.6)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: 20,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: t.colors.surface,
          border: `1px solid ${t.colors.border}`,
          borderRadius: t.radius.lg,
          width: 'min(520px, 100%)',
          maxHeight: '85vh',
          overflow: 'auto',
          boxShadow: t.shadow.lg,
        }}
      >
        <div
          style={{
            padding: '16px 20px',
            borderBottom: `1px solid ${t.colors.border}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</h3>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: t.colors.textMuted,
              cursor: 'pointer',
              fontSize: 20,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: 20 }}>{children}</div>
        {footer && (
          <div
            style={{
              padding: '12px 20px',
              borderTop: `1px solid ${t.colors.border}`,
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function Stat({ label, value, tone }) {
  const tones = { success: t.colors.success, danger: t.colors.danger, accent: t.colors.accent };
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ fontSize: 11, color: t.colors.textMuted, textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, marginTop: 6, color: tones[tone] || t.colors.text, fontFamily: t.font.mono }}>
        {value}
      </div>
    </Card>
  );
}
