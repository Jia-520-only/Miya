/* Modified from HALOFLUX by Ryder191. Miya's presence layer and visual direction.
 * Original license and attribution are preserved in lab.html and LICENSE. */
window.MiyaFlux = (() => {
  if (!new URLSearchParams(location.search).has('miya')) return null;
  const tau = Math.PI * 2;
  const state = {
    online: false, activity: null, memoryCount: null, platformCount: null,
    color: '#94b8ef', mode: 'resonance', ambient: false,
    paused: matchMedia('(prefers-reduced-motion: reduce)').matches,
    hasRendered: false, energy: 0.2, time: 0, echo: 0, avatarReady: false,
    portrait: { zoom: 1, x: 50, y: 42, flow: 32 },
  };
  const preset = {
    camera: 0, camZoom: 0, ringWidth: 0.9, ringShadow: 0, parallax: 0,
    tempo: 1, ringSpeed: 0.9, ringPause: 1.4, rimBright: 0.9,
    rimWidth: 0.8, rimDensity: 0.8, dataFlicker: 0.45,
    webBright: 0.62, webPulseBase: 0.14, webPulseAmp: 0.44, webSpin: 0.4,
    runnerCount: 240, runnerBright: 0.8, runnerSpeed: 0.65,
    cometPerBeat: 1.3, cometBurst: 4, cometTrickle: 0.5, cometLines: 0.75,
    cometWidth: 0.65, cometSpeed: 0.7, cometBright: 0.8,
    beamBright: 0.9, beamLen: 0.85, beamWidth: 0.6, beamGlow: 1.3,
    beamBounce: 1, dashBright: 1.1, hazeCount: 7, hazeBright: 0.5,
    flyerCount: 0.8, flyerBright: 1, flyerWidth: 0.8, flyerSpeed: 1,
    burstRate: 0.8, burstSize: 0.8, burstBright: 1, flareRate: 0.6,
    flareBright: 0.7, glow: 0.75, depthBlur: 0.6, depthDim: 0.65,
    bokeh: 0, atmos: 0.3, vignette: 0.5, scan: 0,
  };
  const finite = (v, max) => typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.min(v, max) : null;
  const origin = location.origin;
  const fileOrigin = location.protocol === 'file:';
  const defaultAvatar = new URL('./miya-avatar.png', location.href).href;
  let avatar = null, avatarSource = '';
  const render = () => window.dispatchEvent(new Event('miya:render'));
  function loadAvatar(source) {
    if (source === avatarSource) return;
    avatarSource = source;
    const image = new Image();
    image.onload = () => {
      if (source !== avatarSource) return;
      avatar = image; state.avatarReady = true; render();
    };
    image.onerror = () => {
      if (source !== avatarSource) return;
      if (source !== defaultAvatar) loadAvatar(defaultAvatar);
      else { avatar = null; state.avatarReady = false; render(); }
    };
    image.src = source;
  }
  const bounded = (value, min, max, fallback) => typeof value === 'number' && Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback;
  window.addEventListener('message', event => {
    const trustedOrigin = event.origin === origin || (fileOrigin && event.origin === 'null');
    if (event.source !== parent || !trustedOrigin) return;
    const data = event.data;
    if (data?.type === 'miya:portrait') {
      const source = data.source;
      if (typeof source === 'string' && (source === defaultAvatar || (source.length < 2_000_000 && /^data:image\/(jpeg|png|webp);base64,[\da-z+/=]+$/i.test(source))))
        loadAvatar(source);
      state.portrait = {
        zoom: bounded(data.zoom, 1, 2.5, 1),
        x: bounded(data.x, 0, 100, 50),
        y: bounded(data.y, 0, 100, 42),
        flow: bounded(data.flow, 0, 75, 32),
      };
      render(); return;
    }
    if (data?.type !== 'miya:presence') return;
    const memory = finite(data.memoryCount, Number.MAX_SAFE_INTEGER);
    if (data.online === true && state.online && memory !== null && state.memoryCount !== null && memory > state.memoryCount)
      state.echo = 1;
    state.online = data.online === true;
    state.activity = state.online ? finite(data.activity, 100) : null;
    state.memoryCount = state.online ? memory : null;
    state.platformCount = state.online ? finite(data.platformCount, 1000) : null;
    if (typeof data.color === 'string' && /^#[\da-f]{6}$/i.test(data.color)) state.color = data.color;
    if (['resonance', 'surge', 'quiet'].includes(data.mode)) state.mode = data.mode;
    state.paused = data.paused === true;
    state.ambient = data.ambient === true;
    render();
  });
  function rgb() {
    return [1, 3, 5].map(i => Number.parseInt(state.color.slice(i, i + 2), 16)).join(',');
  }
  function update(config, dt) {
    state.time += dt;
    const target = state.online ? 0.25 + (state.activity ?? 35) / 135 : 0.15;
    state.energy += (target - state.energy) * (state.paused ? 1 : Math.min(1, dt * 1.6));
    state.echo = Math.max(0, state.echo - dt * 0.32);
    const quiet = state.mode === 'quiet', surge = state.mode === 'surge';
    const gain = quiet ? 0.42 : surge ? 1.65 : 1;
    config.tempo = (0.72 + state.energy * 0.8) * gain;
    config.ringSpeed = (0.6 + state.energy * 0.9) * gain;
    config.runnerCount = Math.round((150 + state.energy * 230) * (quiet ? 0.55 : surge ? 1.35 : 1));
    config.runnerSpeed = (0.42 + state.energy * 0.5) * gain;
    config.beamBright = (0.6 + state.energy * 0.45) * gain;
    config.beamLen = quiet ? 0.5 : surge ? 1.3 : 0.85;
    config.burstRate = quiet ? 0.15 : surge ? 2.2 : 0.7;
    config.flareRate = quiet ? 0.2 : surge ? 1.8 : 0.6;
    config.glow = quiet ? 0.4 : surge ? 1.1 : 0.75;
  }
  function draw(ctx, x, y, radius) {
    const t = state.time, col = rgb();
    const breath = 0.5 + 0.5 * Math.sin(t * (0.85 + state.energy * 0.65));
    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    ctx.translate(x, y);
    const shade = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 0.78);
    shade.addColorStop(0, 'rgba(8,17,38,.98)');
    shade.addColorStop(0.48, 'rgba(8,17,38,.87)');
    shade.addColorStop(1, 'rgba(8,17,38,0)');
    ctx.fillStyle = shade; ctx.beginPath(); ctx.arc(0, 0, radius * 0.78, 0, tau); ctx.fill();
    // Six anchors refer to Miya's six memory layers. Motion is an artistic expression.
    const labels = ['对话', '短期', '长期', '语义', '知识', '置顶'];
    const nodeRadius = radius * 0.79;
    for (let i = 0; i < 6; i++) {
      const angle = -Math.PI / 2 + i * tau / 6;
      const nx = Math.cos(angle) * nodeRadius, ny = Math.sin(angle) * nodeRadius;
      ctx.strokeStyle = 'rgba(142,177,231,.2)'; ctx.lineWidth = 0.6;
      ctx.beginPath(); ctx.moveTo(nx * 0.66, ny * 0.66); ctx.lineTo(nx * 0.93, ny * 0.93); ctx.stroke();
      ctx.fillStyle = i === 5 ? '#e6edf7' : 'rgba(160,194,243,.8)';
      ctx.beginPath(); ctx.arc(nx, ny, 2 + breath * 0.6, 0, tau); ctx.fill();
      if (radius > 115 && !state.ambient) {
        ctx.font = '9px "Microsoft YaHei", sans-serif'; ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(195,213,241,.75)';
        ctx.fillText(labels[i], nx * 1.12, ny * 1.12 + (ny < 0 ? -2 : 9));
      }
    }
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 3; i++) {
      ctx.save(); ctx.rotate(t * (i % 2 ? -0.07 : 0.055) + i * Math.PI / 3);
      ctx.strokeStyle = i === 1 ? 'rgba(92,137,217,.4)' : `rgba(${col},${0.2 + breath * 0.1})`;
      ctx.lineWidth = 0.7;
      ctx.beginPath(); ctx.ellipse(0, 0, radius * 0.62, radius * 0.34, 0, 0, tau); ctx.stroke();
      const a = t * 0.4 + i * 2.1;
      ctx.fillStyle = i === 1 ? '#dce8f8' : `rgba(${col},.95)`;
      ctx.beginPath(); ctx.arc(Math.cos(a) * radius * 0.62, Math.sin(a) * radius * 0.34, 1.8, 0, tau); ctx.fill();
      ctx.restore();
    }
    drawPortrait(ctx, radius, t, col, breath);
    if (state.echo > 0) {
      ctx.strokeStyle = `rgba(204,222,250,${state.echo * 0.7})`; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(0, 0, radius * (1.0 + (1 - state.echo) * 0.6), 0, tau); ctx.stroke();
    }
    ctx.restore();
  }
  function drawPortrait(ctx, radius, t, col, breath) {
    const r = radius * 0.66;
    ctx.save(); ctx.globalCompositeOperation = 'source-over';
    ctx.shadowColor = '#537bc4'; ctx.shadowBlur = 14 + breath * 5;
    ctx.strokeStyle = '#c6daf6'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(0, 0, r + 4, 0, tau); ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(100,146,223,.55)'; ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.arc(0, 0, r + 8, 0, tau); ctx.stroke();
    // Small cobalt scrolls recall painted porcelain around the portrait rim.
    for (let i = 0; i < 24; i++) {
      ctx.save(); ctx.rotate(i * tau / 24);
      ctx.strokeStyle = i % 3 ? 'rgba(128,168,232,.4)' : 'rgba(225,235,250,.65)';
      ctx.beginPath(); ctx.moveTo(r + 11, -3);
      ctx.bezierCurveTo(r + 18, -7, r + 18, 7, r + 11, 3); ctx.stroke();
      ctx.restore();
    }
    ctx.beginPath(); ctx.arc(0, 0, r, 0, tau); ctx.clip();
    ctx.fillStyle = '#16294c'; ctx.fillRect(-r, -r, r * 2, r * 2);
    if (avatar) {
      const { zoom, x, y } = state.portrait;
      const side = Math.min(avatar.naturalWidth, avatar.naturalHeight) / zoom;
      const sx = (avatar.naturalWidth - side) * x / 100;
      const sy = (avatar.naturalHeight - side) * y / 100;
      ctx.drawImage(avatar, sx, sy, side, side, -r, -r, r * 2, r * 2);
    } else {
      ctx.font = `${Math.max(20, r * 0.7)}px SimSun, serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = '#dce7f7'; ctx.fillText('弥', 0, 0);
    }
    const glaze = ctx.createLinearGradient(-r, -r, r, r);
    glaze.addColorStop(0, 'rgba(226,237,251,.06)');
    glaze.addColorStop(0.6, 'rgba(22,50,102,0)');
    glaze.addColorStop(1, 'rgba(20,47,97,.18)');
    ctx.fillStyle = glaze; ctx.fillRect(-r, -r, r * 2, r * 2);
    // This separate foreground pass stays above the image, with no face rotation.
    const flow = state.portrait.flow / 100;
    if (flow > 0) {
      ctx.globalCompositeOperation = 'screen';
      const sweep = ((t * (state.mode === 'surge' ? 0.4 : 0.19)) % 1.5 - 0.75) * r * 2;
      const scan = ctx.createLinearGradient(0, sweep - r * 0.35, 0, sweep + r * 0.35);
      scan.addColorStop(0, 'rgba(130,178,246,0)');
      scan.addColorStop(0.5, `rgba(156,202,255,${flow * 0.4})`);
      scan.addColorStop(1, 'rgba(130,178,246,0)');
      ctx.fillStyle = scan; ctx.fillRect(-r, -r, r * 2, r * 2);
      ctx.font = `${Math.max(5, r * 0.045)}px Consolas, monospace`;
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      const words = ['MIYA', '0101', 'SOUL', 'M-LINK', '1100', 'RECALL', '0110'];
      for (let i = 0; i < 14; i++) {
        const py = -r + ((i * 0.147 + t * 0.12) % 2) * r;
        const px = -r + ((i * 0.431 + t * 0.055) % 1.65) * r;
        ctx.fillStyle = `rgba(${col},${flow * (0.3 + (i % 3) * 0.15)})`;
        ctx.fillText(words[i % words.length], px, py);
        ctx.strokeStyle = `rgba(192,220,255,${flow * 0.65})`; ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(px, py + 4); ctx.lineTo(px + r * 0.22, py + 4); ctx.stroke();
      }
      ctx.strokeStyle = `rgba(197,222,255,${flow * 0.3})`; ctx.lineWidth = 0.5;
      for (let i = 0; i < 4; i++) {
        const ph = t * 0.16 + i * 1.7;
        ctx.beginPath();
        ctx.moveTo(-r, Math.sin(ph) * r * 0.65);
        ctx.bezierCurveTo(-r * 0.3, Math.cos(ph) * r, r * 0.3, Math.sin(ph) * r, r, Math.cos(ph) * r * 0.65); ctx.stroke();
      }
    }
    ctx.restore();
  }
  loadAvatar(defaultAvatar);
  parent.postMessage({ type: 'miya:ready' }, fileOrigin || origin === 'null' ? '*' : origin);
  return { state, preset, update, draw, rgb, get paused() { return state.paused; },
    get hasRendered() { return state.hasRendered; }, set hasRendered(v) { state.hasRendered = v; } };
})();
