/* ============================================================
   SIGIC-IA — Widget flotante de chatbot
   Inserta automáticamente la burbuja en cualquier página
   ============================================================ */
(function () {
  // ── Estilos ─────────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    /* Burbuja flotante */
    #sigic-bubble {
      position: fixed;
      bottom: 28px;
      right: 28px;
      width: 58px;
      height: 58px;
      border-radius: 50%;
      background: linear-gradient(135deg, #059669 0%, #064e3b 100%);
      box-shadow: 0 6px 24px rgba(5,150,105,0.45);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      z-index: 9999;
      transition: transform 0.25s cubic-bezier(0.25,0.46,0.45,0.94),
                  box-shadow 0.25s ease;
      border: none;
      outline: none;
      animation: sigic-pulse 3s infinite ease-in-out;
    }
    #sigic-bubble:hover {
      transform: scale(1.12);
      box-shadow: 0 10px 32px rgba(5,150,105,0.55);
    }
    #sigic-bubble .sigic-notif {
      position: absolute;
      top: 2px; right: 2px;
      width: 14px; height: 14px;
      background: #d4a843;
      border-radius: 50%;
      border: 2px solid #fff;
      display: none;
    }
    @keyframes sigic-pulse {
      0%,100% { box-shadow: 0 6px 24px rgba(5,150,105,0.45); }
      50%      { box-shadow: 0 6px 32px rgba(5,150,105,0.70); }
    }

    /* Panel del chat */
    #sigic-panel {
      position: fixed;
      bottom: 100px;
      right: 28px;
      width: 380px;
      max-height: 560px;
      background: #fff;
      border-radius: 18px;
      box-shadow: 0 16px 48px rgba(2,44,34,0.18);
      display: flex;
      flex-direction: column;
      z-index: 9998;
      overflow: hidden;
      transform: scale(0.85) translateY(20px);
      opacity: 0;
      pointer-events: none;
      transition: transform 0.28s cubic-bezier(0.25,0.46,0.45,0.94),
                  opacity 0.28s ease;
      border: 1px solid rgba(5,150,105,0.12);
    }
    #sigic-panel.open {
      transform: scale(1) translateY(0);
      opacity: 1;
      pointer-events: all;
    }

    /* Header del panel */
    .sigic-header {
      background: linear-gradient(135deg, #064e3b 0%, #011a12 100%);
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 2px solid #d4a843;
      flex-shrink: 0;
    }
    .sigic-header-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .sigic-header-icon {
      font-size: 22px;
    }
    .sigic-header-info h3 {
      font-family: system-ui, sans-serif;
      font-size: 13px;
      font-weight: 800;
      color: #fff;
      margin: 0;
      letter-spacing: 0.04em;
    }
    .sigic-header-info p {
      font-size: 10px;
      color: #6ee7b7;
      margin: 0;
    }
    .sigic-close {
      background: rgba(255,255,255,0.1);
      border: none;
      color: #fff;
      width: 28px; height: 28px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s;
      flex-shrink: 0;
    }
    .sigic-close:hover { background: rgba(255,255,255,0.2); }

    /* Mensajes */
    .sigic-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: linear-gradient(180deg, #f8fffe 0%, #f0fdf4 100%);
    }
    .sigic-msg {
      display: flex;
      flex-direction: column;
      max-width: 85%;
    }
    .sigic-msg.user  { align-self: flex-end; }
    .sigic-msg.bot   { align-self: flex-start; }
    .sigic-msg .bubble {
      padding: 10px 14px;
      border-radius: 14px;
      font-size: 13px;
      line-height: 1.5;
      font-family: system-ui, sans-serif;
    }
    .sigic-msg.user .bubble {
      background: linear-gradient(135deg, #047857 0%, #064e3b 100%);
      color: #fff;
      border-top-right-radius: 3px;
    }
    .sigic-msg.bot .bubble {
      background: #fff;
      color: #022c22;
      border: 1px solid rgba(5,150,105,0.12);
      border-top-left-radius: 3px;
      box-shadow: 0 2px 8px rgba(2,44,34,0.05);
    }
    .sigic-msg .ts {
      font-size: 10px;
      color: #9ca3af;
      margin-top: 3px;
    }
    .sigic-msg.user .ts { align-self: flex-end; }
    .sigic-msg.bot  .ts { align-self: flex-start; }

    /* Typing dots */
    .sigic-typing {
      display: none;
      align-self: flex-start;
      background: #fff;
      border: 1px solid rgba(5,150,105,0.12);
      border-radius: 14px;
      border-top-left-radius: 3px;
      padding: 10px 14px;
      gap: 4px;
      align-items: center;
      box-shadow: 0 2px 8px rgba(2,44,34,0.05);
    }
    .sigic-typing.show { display: flex; }
    .sigic-dot {
      width: 6px; height: 6px;
      background: #10b981;
      border-radius: 50%;
      animation: sigic-bounce 1.4s infinite ease-in-out both;
    }
    .sigic-dot:nth-child(1){animation-delay:-0.32s}
    .sigic-dot:nth-child(2){animation-delay:-0.16s}
    @keyframes sigic-bounce {
      0%,80%,100%{transform:scale(0)} 40%{transform:scale(1)}
    }

    /* Input */
    .sigic-input-area {
      padding: 12px 14px;
      background: #fff;
      border-top: 1px solid rgba(5,150,105,0.1);
      flex-shrink: 0;
    }
    .sigic-input-row {
      display: flex;
      gap: 8px;
      background: #ecfdf5;
      border: 1px solid rgba(5,150,105,0.15);
      border-radius: 99px;
      padding: 5px 5px 5px 14px;
      align-items: center;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .sigic-input-row:focus-within {
      border-color: #10b981;
      box-shadow: 0 0 0 3px rgba(16,185,129,0.12);
      background: #fff;
    }
    .sigic-input {
      flex: 1;
      border: none;
      background: transparent;
      outline: none;
      font-size: 13px;
      color: #022c22;
      font-family: system-ui, sans-serif;
    }
    .sigic-send {
      background: linear-gradient(135deg, #059669 0%, #065f46 100%);
      color: #fff;
      border: none;
      width: 32px; height: 32px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s;
      box-shadow: 0 2px 8px rgba(5,150,105,0.3);
      flex-shrink: 0;
    }
    .sigic-send:hover {
      transform: scale(1.1);
      box-shadow: 0 4px 12px rgba(5,150,105,0.4);
    }

    /* Responsive */
    @media (max-width: 440px) {
      #sigic-panel { width: calc(100vw - 20px); right: 10px; bottom: 90px; }
      #sigic-bubble { right: 16px; bottom: 16px; }
    }
  `;
  document.head.appendChild(style);

  // ── HTML del widget ──────────────────────────────────────────────────────────
  const wrapper = document.createElement('div');
  wrapper.innerHTML = `
    <!-- Panel de chat -->
    <div id="sigic-panel">
      <div class="sigic-header">
        <div class="sigic-header-left">
          <span class="sigic-header-icon">☕</span>
          <div class="sigic-header-info">
            <h3>SIGIC-IA</h3>
            <p>Asistente inteligente · En línea</p>
          </div>
        </div>
        <button class="sigic-close" id="sigic-close-btn">✕</button>
      </div>
      <div class="sigic-messages" id="sigic-msgs">
        <div class="sigic-msg bot">
          <div class="bubble">¡Hola! Soy SIGIC-IA ☕<br>Puedo consultarte datos en tiempo real sobre recolectores, fincas, pagos, insumos y más. ¿En qué te ayudo?</div>
          <span class="ts" id="sigic-welcome-ts"></span>
        </div>
        <div class="sigic-typing" id="sigic-typing">
          <div class="sigic-dot"></div>
          <div class="sigic-dot"></div>
          <div class="sigic-dot"></div>
        </div>
      </div>
      <div class="sigic-input-area">
        <div class="sigic-input-row">
          <input type="text" class="sigic-input" id="sigic-input"
            placeholder="Pregunta sobre fincas, pagos, recolectores..." autocomplete="off">
          <button class="sigic-send" id="sigic-send-btn">➤</button>
        </div>
      </div>
    </div>

    <!-- Burbuja flotante -->
    <button id="sigic-bubble">
      ☕
      <span class="sigic-notif" id="sigic-notif"></span>
    </button>
  `;
  document.body.appendChild(wrapper);

  // ── Lógica ───────────────────────────────────────────────────────────────────
  const panel   = document.getElementById('sigic-panel');
  const bubble  = document.getElementById('sigic-bubble');
  const closeBtn= document.getElementById('sigic-close-btn');
  const input   = document.getElementById('sigic-input');
  const sendBtn = document.getElementById('sigic-send-btn');
  const msgs    = document.getElementById('sigic-msgs');
  const typing  = document.getElementById('sigic-typing');
  const notif   = document.getElementById('sigic-notif');

  document.getElementById('sigic-welcome-ts').textContent =
    new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});

  let isOpen = false;

  function togglePanel() {
    isOpen = !isOpen;
    panel.classList.toggle('open', isOpen);
    bubble.style.transform = isOpen ? 'scale(0.9)' : '';
    notif.style.display = 'none';
    if (isOpen) setTimeout(() => input.focus(), 300);
  }

  bubble.addEventListener('click', togglePanel);
  closeBtn.addEventListener('click', togglePanel);

  function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function addMsg(text, role) {
    const wrap = document.createElement('div');
    wrap.className = `sigic-msg ${role}`;
    wrap.innerHTML = `
      <div class="bubble">${text.replace(/\n/g, '<br>')}</div>
      <span class="ts">${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
    `;
    msgs.insertBefore(wrap, typing);
    msgs.scrollTop = msgs.scrollHeight;
  }

  async function send() {
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    addMsg(q, 'user');

    typing.classList.add('show');
    msgs.scrollTop = msgs.scrollHeight;

    try {
      const res = await fetch('/api/chatbot/consultar/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf()
        },
        body: JSON.stringify({ pregunta: q })
      });
      const data = await res.json();
      typing.classList.remove('show');

      if (res.ok) {
        addMsg(data.respuesta, 'bot');
      } else {
        addMsg('⚠️ ' + (data.error || 'Error al consultar.'), 'bot');
      }
    } catch (err) {
      typing.classList.remove('show');
      addMsg('⚠️ Error de conexión: ' + err.message, 'bot');
    }

    // Mostrar notif si el panel está cerrado
    if (!isOpen) {
      notif.style.display = 'block';
    }
  }

  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

})();
