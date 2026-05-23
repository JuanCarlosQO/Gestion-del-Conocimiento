/* app-ui.js — utilidades de interfaz compartidas */
function showPanel(panelId) {
  document.querySelectorAll('.panel').forEach(p => {
    p.style.display = 'none';
  });
  const el = document.getElementById(panelId);
  if (!el) return;
  if (panelId === 'panel_dashboard') {
    el.style.display = 'flex';
    el.style.padding  = '0';
    el.style.alignItems = 'stretch';
  } else {
    el.style.display        = 'flex';
    el.style.flexDirection  = 'column';
    el.style.alignItems     = 'center';
    el.style.justifyContent = 'center';
    el.style.padding        = '36px 48px';
  }
}
