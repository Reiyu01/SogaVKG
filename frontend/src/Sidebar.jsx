import { NavLink } from 'react-router-dom';

const linkStyle = ({ isActive }) => ({
  display: 'block',
  padding: '10px 16px',
  borderRadius: 6,
  textDecoration: 'none',
  color: isActive ? '#185fa5' : '#444',
  background: isActive ? '#e6f1fb' : 'transparent',
  fontWeight: isActive ? 600 : 400,
  fontSize: '14px',
  marginBottom: '4px',
});

export default function Sidebar() {
  return (
    <div
      style={{
        width: '200px',
        height: '100vh',
        borderRight: '1px solid #eee',
        padding: '20px 12px',
        boxSizing: 'border-box',
        flexShrink: 0,
      }}
    >
      <div style={{ fontWeight: 700, fontSize: '15px', padding: '0 4px 20px' }}>
        語義查詢系統
      </div>

      <NavLink to="/" end style={linkStyle}>
        知識圖譜
      </NavLink>

      <NavLink to="/ask" style={linkStyle}>
        AI 檢索
      </NavLink>
    </div>
  );
}