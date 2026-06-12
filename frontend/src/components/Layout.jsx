import { NavLink, Outlet } from 'react-router-dom';
import { theme } from '../theme';

const t = theme;

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/sources', label: 'Sources' },
  { to: '/drafts', label: 'Drafts' },
];

function NavItem({ to, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className="nav-item"
      style={({ isActive }) => ({
        display: 'block',
        padding: '7px 12px',
        borderRadius: t.radius.md,
        textDecoration: 'none',
        color: isActive ? t.colors.text : t.colors.textMuted,
        background: isActive ? t.colors.surfaceAlt : 'transparent',
        fontSize: 14,
        fontWeight: isActive ? 600 : 400,
        transition: `all ${t.transition}`,
      })}
    >
      {label}
    </NavLink>
  );
}

export default function Layout() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: t.colors.bg, color: t.colors.text, fontFamily: t.font.body }}>
      <aside
        style={{
          width: 220,
          borderRight: `1px solid ${t.colors.border}`,
          padding: '24px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          position: 'sticky',
          top: 0,
          height: '100vh',
          flexShrink: 0,
        }}
      >
        <div style={{ padding: '0 12px 24px', fontWeight: 600, fontSize: 15, letterSpacing: '-.01em' }}>
          News Post
        </div>

        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </aside>

      <main style={{ flex: 1, padding: '40px 48px', maxWidth: 1100, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </main>
    </div>
  );
}
