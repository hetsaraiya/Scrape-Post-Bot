import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { theme } from '../theme';
import { hasApiKey, setApiKey } from '../api/client';
import { Button, Input, Modal } from './ui';

const t = theme;

const navItems = [
  { to: '/', label: 'Dashboard', icon: '◆' },
  { to: '/sources', label: 'Sources', icon: '◈' },
  { to: '/drafts', label: 'Drafts', icon: '◇' },
];

function NavItem({ to, label, icon }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
        borderRadius: t.radius.md,
        textDecoration: 'none',
        color: isActive ? t.colors.text : t.colors.textMuted,
        background: isActive ? t.colors.surfaceAlt : 'transparent',
        fontSize: 13,
        fontWeight: 500,
        transition: `all ${t.transition}`,
        borderLeft: isActive ? `2px solid ${t.colors.accent}` : '2px solid transparent',
      })}
    >
      <span style={{ color: t.colors.accent, fontSize: 11 }}>{icon}</span>
      {label}
    </NavLink>
  );
}

export default function Layout() {
  const [keyOpen, setKeyOpen] = useState(false);
  const [keyInput, setKeyInput] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (!hasApiKey()) setKeyOpen(true);
  }, []);

  const saveKey = () => {
    setApiKey(keyInput.trim());
    setKeyOpen(false);
    setKeyInput('');
    navigate(0);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: t.colors.bg, color: t.colors.text, fontFamily: t.font.body }}>
      <aside
        style={{
          width: 240,
          borderRight: `1px solid ${t.colors.border}`,
          padding: '20px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          position: 'sticky',
          top: 0,
          height: '100vh',
        }}
      >
        <div style={{ padding: '8px 14px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: `linear-gradient(135deg, ${t.colors.accent}, #ff6bcc)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            N
          </div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>News Post</div>
        </div>

        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}

        <div style={{ marginTop: 'auto', padding: '12px 4px', borderTop: `1px solid ${t.colors.border}` }}>
          <Button variant="ghost" size="sm" onClick={() => setKeyOpen(true)} style={{ width: '100%', justifyContent: 'flex-start' }}>
            ⚙ API Key
          </Button>
        </div>
      </aside>

      <main style={{ flex: 1, padding: '28px 36px', maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </main>

      <Modal
        open={keyOpen}
        onClose={() => hasApiKey() && setKeyOpen(false)}
        title="API Key"
        footer={
          <>
            {hasApiKey() && (
              <Button variant="secondary" onClick={() => setKeyOpen(false)}>
                Cancel
              </Button>
            )}
            <Button onClick={saveKey} disabled={!keyInput.trim()}>
              Save
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ color: t.colors.textMuted, fontSize: 13, margin: 0 }}>
            Enter your <code style={{ background: t.colors.surfaceAlt, padding: '2px 6px', borderRadius: 4 }}>X-API-Key</code> to authenticate requests.
            It is stored locally in your browser.
          </p>
          <Input
            label="API key"
            type="password"
            autoFocus
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && keyInput.trim() && saveKey()}
            placeholder="paste key here"
          />
        </div>
      </Modal>
    </div>
  );
}
