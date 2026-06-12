import { useEffect } from 'react';
import { theme } from '../theme';

const t = theme;

export function Button({ variant = 'primary', size = 'md', loading, children, style, disabled, ...rest }) {
  const variants = {
    primary: { background: t.colors.accent, color: '#0e0e10', border: `1px solid ${t.colors.accent}` },
    secondary: { background: t.colors.surfaceAlt, color: t.colors.text, border: `1px solid ${t.colors.border}` },
    ghost: { background: 'transparent', color: t.colors.textMuted, border: '1px solid transparent' },
    danger: { background: 'transparent', color: t.colors.danger, border: `1px solid ${t.colors.border}` },
  };
  const sizes = {
    sm: { padding: '5px 10px', fontSize: 13 },
    md: { padding: '8px 14px', fontSize: 13 },
    lg: { padding: '10px 18px', fontSize: 14 },
  };
  return (
    <button
      className={`btn btn-${variant}`}
      disabled={disabled || loading}
      style={{
        ...variants[variant],
        ...sizes[size],
        borderRadius: t.radius.md,
        cursor: disabled || loading ? 'default' : 'pointer',
        fontWeight: 500,
        fontFamily: t.font.body,
        opacity: disabled || loading ? 0.5 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
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
        <span style={{ fontSize: 13, color: t.colors.text, fontWeight: 500 }}>{label}</span>
      )}
      <input
        style={{
          background: t.colors.bg,
          color: t.colors.text,
          border: `1px solid ${error ? t.colors.danger : t.colors.border}`,
          borderRadius: t.radius.md,
          padding: '8px 12px',
          fontSize: 14,
          fontFamily: t.font.body,
          outline: 'none',
          transition: `border-color ${t.transition}, box-shadow ${t.transition}`,
          ...style,
        }}
        onFocus={(e) => {
          e.target.style.borderColor = t.colors.borderStrong;
          e.target.style.boxShadow = '0 0 0 3px rgba(237,237,239,.06)';
        }}
        onBlur={(e) => {
          e.target.style.borderColor = error ? t.colors.danger : t.colors.border;
          e.target.style.boxShadow = 'none';
        }}
        {...rest}
      />
      {error && <span style={{ fontSize: 12, color: t.colors.danger }}>{error}</span>}
    </label>
  );
}

export function Select({ label, children, ...rest }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {label && (
        <span style={{ fontSize: 13, color: t.colors.text, fontWeight: 500 }}>{label}</span>
      )}
      <select
        style={{
          background: t.colors.bg,
          color: t.colors.text,
          border: `1px solid ${t.colors.border}`,
          borderRadius: t.radius.md,
          padding: '8px 12px',
          fontSize: 14,
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
    neutral: { bg: t.colors.surfaceAlt, fg: t.colors.textMuted, dot: t.colors.textDim },
    success: { bg: 'rgba(74,222,128,.1)', fg: t.colors.success, dot: t.colors.success },
    warning: { bg: 'rgba(251,191,36,.1)', fg: t.colors.warning, dot: t.colors.warning },
    danger: { bg: 'rgba(248,113,113,.1)', fg: t.colors.danger, dot: t.colors.danger },
    info: { bg: 'rgba(96,165,250,.1)', fg: t.colors.info, dot: t.colors.info },
    accent: { bg: t.colors.surfaceAlt, fg: t.colors.text, dot: t.colors.textDim },
  };
  const c = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        padding: '2px 8px',
        borderRadius: t.radius.pill,
        fontSize: 12,
        fontWeight: 500,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
      }}
    >
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.dot, flexShrink: 0 }} />
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
        borderTopColor: t.colors.text,
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
        padding: '64px 20px',
        textAlign: 'center',
        gap: 6,
        border: `1px dashed ${t.colors.borderStrong}`,
        borderRadius: t.radius.lg,
      }}
    >
      <div style={{ fontSize: 15, fontWeight: 600, color: t.colors.text }}>{title}</div>
      {hint && <div style={{ fontSize: 13, color: t.colors.textMuted, maxWidth: 380 }}>{hint}</div>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  return (
    <div
      style={{
        background: 'rgba(248,113,113,.08)',
        border: '1px solid rgba(248,113,113,.3)',
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
        <Button variant="ghost" size="sm" onClick={onRetry} style={{ color: t.colors.danger }}>
          Try again
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
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: 20,
        animation: 'fadeIn .12s ease',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: t.colors.surface,
          border: `1px solid ${t.colors.border}`,
          borderRadius: t.radius.lg,
          width: 'min(540px, 100%)',
          maxHeight: '85vh',
          overflow: 'auto',
          boxShadow: t.shadow.lg,
          animation: 'slideUp .15s ease',
        }}
      >
        <div
          style={{
            padding: '18px 24px 0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 12,
          }}
        >
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, lineHeight: 1.4 }}>{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: t.colors.textDim,
              cursor: 'pointer',
              fontSize: 20,
              lineHeight: 1,
              padding: 2,
            }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: '16px 24px 24px' }}>{children}</div>
        {footer && (
          <div
            style={{
              padding: '14px 24px',
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
  const tones = { success: t.colors.success, danger: t.colors.danger, accent: t.colors.text };
  return (
    <Card style={{ padding: '16px 18px' }}>
      <div style={{ fontSize: 13, color: t.colors.textMuted }}>{label}</div>
      <div
        style={{
          fontSize: 26,
          fontWeight: 600,
          marginTop: 4,
          letterSpacing: '-.01em',
          fontVariantNumeric: 'tabular-nums',
          color: tones[tone] || t.colors.text,
        }}
      >
        {value}
      </div>
    </Card>
  );
}
