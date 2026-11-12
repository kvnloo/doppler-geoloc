// Live hero: plane 1 flies past the microphone while its wavefronts bunch up ahead of it, and the
// scope reveals the real spectrogram of that pass with the fitted Doppler curve, on one shared clock.
// Numbers come from hero_curve.json (fitted f0, speed, closest slant distance); the texture is the
// real whitened spectrogram (hero_spec.png). The sound button plays a synthesized replay of the fit.
(async () => {
  const hero = document.querySelector('.hero');
  const sky = hero && hero.querySelector('.hero-sky');
  const scope = hero && hero.querySelector('.scope-cv');
  if (!sky || !scope) return;
  const C = 343, RUN = 8000, HOLD = 1400, EMIT = 2.4;
  const cfg = await fetch('assets/hero_curve.json').then((r) => r.json());
  const img = new Image(); img.src = 'assets/hero_spec.png'; await img.decode().catch(() => {});
  const { v, d, window_s: W, f_lo, f_hi, curve_hz: curve } = cfg;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hzOut = hero.querySelector('.hz'), tOut = hero.querySelector('.tt');
  const btn = hero.querySelector('.listen');
  const LIME = '218,250,156';
  const stacked = matchMedia('(max-width: 760px), (max-width: 1100px) and (orientation: portrait)');

  const fit = (cv) => {
    const r = cv.getBoundingClientRect(), k = Math.min(devicePixelRatio || 1, 2);
    cv.width = Math.round(r.width * k); cv.height = Math.round(r.height * k);
    return { w: r.width, h: r.height, k };
  };
  let S, P, geo;
  const layout = () => {
    S = fit(sky); P = fit(scope);
    const cs = getComputedStyle(hero), num = (n, f) => parseFloat(cs.getPropertyValue(n)) || f;
    const micX = S.w * num('--mic-x', 0.7);
    let lineY = S.h * num('--line-y', 0.2), scale = Math.min(S.w * 1.05, 1600) / (v * 2 * W); // the pass spans about the screen
    const hr = hero.getBoundingClientRect(), cr = hero.querySelector('.acts').getBoundingClientRect();
    const wide = !stacked.matches;
    if (!wide) { // stacked: the flyover sits in the gap between the actions and the scope, mic clear of the card
      const top = cr.bottom - hr.top + 34, gap = hero.querySelector('.scope').getBoundingClientRect().top - hr.top - 30 - top;
      scale = Math.min(scale, gap * 0.78 / d); lineY = top + (gap - d * scale) * 0.45;
    } // where the copy sits, the rings fade out so they never cross the words
    geo = { micX, lineY, scale, micY: lineY + d * scale, maxR: Math.max(S.w, S.h) * 0.75, wide,
      quiet: wide ? cr.right - hr.left + 40 : cr.bottom - hr.top + 24 };
  };
  layout(); new ResizeObserver(layout).observe(hero);

  // heard time s (0 = heard closest approach) -> geometric time and slant distance of the wave heard now
  const heard = (s) => { const tg = s + d / C; let tau = tg; for (let i = 0; i < 6; i++) tau = tg - Math.hypot(v * tau, d) / C; return { tg, tau, r: Math.hypot(v * tau, d) }; };
  const hzAt = (s) => { const x = (s + W) / (2 * W) * (curve.length - 1), i = Math.max(0, Math.min(curve.length - 2, Math.floor(x))); return curve[i] + (curve[i + 1] - curve[i]) * (x - i); };

  const plane = (g, x, y) => {
    g.save(); g.translate(x, y); g.fillStyle = '#fff';
    g.beginPath(); g.ellipse(0, 0, 11, 2.1, 0, 0, 7); g.fill();
    g.beginPath(); g.moveTo(2, 0); g.lineTo(-2, -10); g.lineTo(-5, -10); g.lineTo(-3, 0); g.lineTo(-5, 10); g.lineTo(-2, 10); g.closePath(); g.fill();
    g.beginPath(); g.moveTo(-8, 0); g.lineTo(-11, -4); g.lineTo(-12, -4); g.lineTo(-11, 0); g.lineTo(-12, 4); g.lineTo(-11, 4); g.closePath(); g.fill();
    g.restore();
  };

  const drawSky = (s, fade) => {
    const g = sky.getContext('2d'), { micX, micY, lineY, scale, maxR } = geo;
    g.setTransform(S.k, 0, 0, S.k, 0, 0); g.clearRect(0, 0, S.w, S.h);
    const { tg, tau } = heard(s), px = micX + v * tg * scale;
    // flight path and closest-approach drop line
    g.strokeStyle = `rgba(255,255,255,.14)`; g.lineWidth = 1; g.setLineDash([2, 6]);
    g.beginPath(); g.moveTo(0, lineY); g.lineTo(S.w, lineY); g.moveTo(micX, lineY); g.lineTo(micX, micY - 10); g.stroke(); g.setLineDash([]);
    // wavefronts: one ring per emission, centred where the plane was when it sent it
    let hit = 0;
    for (let te = Math.ceil((-W - 80) / EMIT) * EMIT; te <= tg; te += EMIT) {
      const R = C * (tg - te) * scale; if (R <= 0 || R > maxR) continue;
      const cx = micX + v * te * scale, a = 0.42 * (1 - R / maxR) ** 1.8 * fade;
      g.strokeStyle = `rgba(${LIME},${a})`; g.lineWidth = 1.2;
      g.beginPath(); g.arc(cx, lineY, R, 0, Math.PI * 2); g.stroke();
      hit = Math.max(hit, 1 - Math.min(1, Math.abs(Math.hypot(micX - cx, micY - lineY) - R) / 10));
    }
    const q = geo.wide ? g.createLinearGradient(0, 0, geo.quiet, 0) : g.createLinearGradient(0, 0, 0, geo.quiet);
    q.addColorStop(0, 'rgba(0,0,0,.92)'); q.addColorStop(0.7, 'rgba(0,0,0,.8)'); q.addColorStop(1, 'rgba(0,0,0,0)');
    g.globalCompositeOperation = 'destination-out'; g.fillStyle = q; g.fillRect(0, 0, geo.wide ? geo.quiet : S.w, geo.wide ? S.h : geo.quiet);
    g.globalCompositeOperation = 'source-over';
    // the sight line to the point that emitted the sound being heard now
    const ex = micX + v * tau * scale;
    g.strokeStyle = `rgba(${LIME},${0.35 * fade})`; g.lineWidth = 1;
    g.beginPath(); g.moveTo(ex, lineY); g.lineTo(micX, micY); g.stroke();
    const pa = geo.wide ? Math.min(1, Math.max(0, (px - geo.quiet + 40) / 120)) : 1; // the plane leaves the words alone too
    g.globalAlpha = pa; plane(g, px, lineY); g.globalAlpha = 1;
    // microphone: pulses as each wavefront arrives, so arrivals crowd together on approach
    const glow = g.createRadialGradient(micX, micY, 0, micX, micY, 70);
    glow.addColorStop(0, `rgba(${LIME},${0.16 + 0.22 * hit})`); glow.addColorStop(1, `rgba(${LIME},0)`);
    g.fillStyle = glow; g.fillRect(micX - 70, micY - 70, 140, 140);
    g.fillStyle = `rgb(${LIME})`; g.beginPath(); g.arc(micX, micY, 5 + 3 * hit, 0, 7); g.fill();
    g.font = '12px ui-monospace, "SF Mono", Menlo, monospace'; g.fillStyle = 'rgba(255,255,255,.62)';
    const tag = (txt, x, y) => { // a label on a soot chip, kept inside the screen
      const w = g.measureText(txt).width; x = Math.max(10, Math.min(S.w - w - 10, x));
      g.fillStyle = 'rgba(15,15,15,.85)'; g.fillRect(x - 5, y - 12, w + 10, 17); g.fillStyle = 'rgba(255,255,255,.78)'; g.fillText(txt, x, y);
    };
    g.textAlign = 'left';
    tag('microphone', micX + 14, micY + 4);
    tag(`${(d / 1000).toFixed(1)} km at closest`, micX + 8, lineY + (micY - lineY) * 0.62);
    const pl = `plane 1 · ${Math.round(v)} m/s`;
    if (pa > 0.5) tag(pl, px + 16 + g.measureText(pl).width > S.w - 10 ? px - 16 - g.measureText(pl).width : px + 16, lineY - 16);
  };

  const drawScope = (s, fade) => {
    const g = scope.getContext('2d'), { w, h, k } = P;
    g.setTransform(k, 0, 0, k, 0, 0); g.clearRect(0, 0, w, h);
    const u = (s + W) / (2 * W), X = (t) => (t + W) / (2 * W) * w, Y = (f) => h - (f - f_lo) / (f_hi - f_lo) * h;
    g.globalAlpha = 0.14 * fade; g.drawImage(img, 0, 0, w, h);
    g.globalAlpha = 0.8 * fade; const sw = img.naturalWidth * u; if (sw > 1) g.drawImage(img, 0, 0, sw, img.naturalHeight, 0, 0, w * u, h);
    g.globalAlpha = 1;
    g.font = '11px ui-monospace, "SF Mono", Menlo, monospace'; g.fillStyle = 'rgba(255,255,255,.45)'; g.textAlign = 'left';
    for (const f of [80, 120, 160, 200]) { g.fillStyle = 'rgba(0,0,0,.7)'; g.fillRect(0, Y(f) - 8, 34, 15); g.fillStyle = 'rgba(255,255,255,.7)'; g.fillRect(0, Y(f), 5, 1); g.fillText(f, 8, Y(f) + 4); }
    g.strokeStyle = `rgba(${LIME},${fade})`; g.lineWidth = 2.4; g.shadowColor = `rgba(${LIME},.8)`; g.shadowBlur = 10;
    g.beginPath(); const n = Math.max(1, Math.round(u * (curve.length - 1)));
    for (let i = 0; i <= n; i++) { const t = -W + 2 * W * i / (curve.length - 1); i ? g.lineTo(X(t), Y(curve[i])) : g.moveTo(X(t), Y(curve[i])); }
    g.stroke(); g.shadowBlur = 0;
    if (u < 1) {
      g.fillStyle = 'rgba(255,255,255,.5)'; g.fillRect(X(s), 0, 1, h);
      g.fillStyle = `rgb(${LIME})`; g.beginPath(); g.arc(X(s), Y(hzAt(s)), 4.5, 0, 7); g.fill();
    }
  };

  const render = (s, fade = 1) => {
    drawSky(s, fade); drawScope(s, fade);
    hzOut.textContent = `${hzAt(s).toFixed(1)} Hz`;
    tOut.textContent = `${s < 0 ? '−' : '+'}${Math.abs(s).toFixed(0).padStart(2, '0')} s`;
  };
  if (reduce) { render(W); return; }

  // shared clock: the loop restarts when the sound starts, so picture and sound stay together
  let t0 = performance.now(), live = true, raf = 0;
  const tick = (now) => {
    const ph = (now - t0) % (RUN + HOLD), u = Math.min(ph / RUN, 1);
    const fade = ph > RUN + HOLD - 300 ? 0.35 + 0.65 * (RUN + HOLD - ph) / 300 : 1; // reset dims, never blanks
    render(-W + 2 * W * u, fade);
    raf = live ? requestAnimationFrame(tick) : 0;
  };
  const go = (on) => { live = on; if (on && !raf) raf = requestAnimationFrame(tick); };
  new IntersectionObserver(([e]) => go(e.isIntersecting && !document.hidden)).observe(hero);
  document.addEventListener('visibilitychange', () => go(!document.hidden));

  // synthesized replay of the fitted curve: one octave up so phone speakers carry it, louder near closest approach
  let ac, voice;
  const stop = () => { if (voice) { voice.forEach((n) => { try { n.stop(); } catch {} }); voice = null; } btn.setAttribute('aria-pressed', 'false'); hero.classList.remove('is-playing'); };
  btn.addEventListener('click', () => {
    if (voice) return stop();
    ac = ac || new AudioContext(); ac.resume();
    const dur = RUN / 1000, N = 400, fr = new Float32Array(N), gn = new Float32Array(N), t = ac.currentTime + 0.05;
    for (let i = 0; i < N; i++) { const s = -W + 2 * W * i / (N - 1); fr[i] = hzAt(s) * 2; gn[i] = 0.04 + 0.32 * (d / heard(s).r) ** 2; }
    const out = ac.createGain(); out.gain.value = 0; out.connect(ac.destination);
    out.gain.setValueCurveAtTime(gn, t, dur); out.gain.setTargetAtTime(0, t + dur, 0.08);
    const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 1400; lp.connect(out);
    const o1 = ac.createOscillator(), o2 = ac.createOscillator(), g2 = ac.createGain();
    o1.type = 'sawtooth'; o2.type = 'triangle'; g2.gain.value = 0.6;
    o1.frequency.setValueCurveAtTime(fr, t, dur); o2.frequency.setValueCurveAtTime(fr.map((x) => x * 2), t, dur);
    o1.connect(lp); o2.connect(g2).connect(lp);
    const nb = ac.createBuffer(1, ac.sampleRate * (dur + 0.4), ac.sampleRate), ch = nb.getChannelData(0);
    let b = 0; for (let i = 0; i < ch.length; i++) { b = 0.97 * b + 0.03 * (Math.random() * 2 - 1); ch[i] = b * 0.9; }
    const ns = ac.createBufferSource(), ng = ac.createGain(); ns.buffer = nb; ng.gain.value = 0.5; ns.connect(ng).connect(ac.destination);
    [o1, o2, ns].forEach((n) => { n.start(t); n.stop(t + dur + 0.4); });
    voice = [o1, o2, ns]; o1.onended = stop;
    t0 = performance.now() + 50; go(true);
    btn.setAttribute('aria-pressed', 'true'); hero.classList.add('is-playing');
  });
})();
