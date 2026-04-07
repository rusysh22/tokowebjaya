/* ===== Hero Pin Ribbons — Toko Web Jaya =====
   Two S-curve ribbons (main + smaller echo above).
   Glow orb at bottom-center of hero.
   Mouse hover: spring-deflect on both ribbons.
   Pure Canvas API — no external dependencies.
============================================= */

(function () {
  const canvas = document.getElementById("hero-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  // ── Ribbon definitions ─────────────────────────────────────
  // Each ribbon has its own S-curve control points (fractions of W/H)
  // and its own size/opacity scale.
  const RIBBONS = [
    {
      // Main ribbon — bottom, large
      pinCount:       140,
      pinHeightFront: 120,
      pinHeightBack:  10,
      dotRadiusFront: 3.8,
      dotRadiusBack:  0.8,
      opacityFront:   0.92,
      opacityBack:    0.08,
      // S-curve: two cubic Bezier segments
      // Segment A
      A: { p0:[0.00,0.82], p1:[0.18,0.95], p2:[0.38,0.30], p3:[0.50,0.45] },
      // Segment B
      B: { p0:[0.50,0.45], p1:[0.62,0.60], p2:[0.82,0.10], p3:[1.00,0.22] },
    },
    {
      // Echo ribbon — above main, medium height for 3D depth illusion
      pinCount:       160,
      pinHeightFront: 100,
      pinHeightBack:  8,
      dotRadiusFront: 2.4,
      dotRadiusBack:  0.55,
      opacityFront:   0.50,
      opacityBack:    0.05,
      // Shifted upward by ~0.18H relative to main ribbon
      A: { p0:[0.00,0.64], p1:[0.18,0.77], p2:[0.38,0.12], p3:[0.50,0.27] },
      B: { p0:[0.50,0.27], p1:[0.62,0.42], p2:[0.82,-0.08], p3:[1.00,0.04] },
    },
  ];

  const MOUSE = {
    radius:     150,
    force:      60,
    decay:      0.07,
    smoothIn:   0.15,
  };

  const COLOR = "202,255,0";

  // ── Pulse config ───────────────────────────────────────────
  // A pulse sweeps from u=0 (front) to u=1 (back) over `duration` ms.
  // After finishing, next pulse fires after `interval` ms (+ random jitter).
  const PULSE = {
    duration:     1800,   // ms to travel front → back
    interval:     3000,   // ms between pulses (base)
    jitter:       1200,   // random ± added to interval
    width:        0.12,   // half-width of highlight band (in u units)
    brightBoost:  0.85,   // extra opacity at pulse center
    sizeBoost:    0.7,    // extra dot radius multiplier at pulse center
  };

  let W = 0, H = 0;
  let animId = null;
  let mouseX = -9999, mouseY = -9999;

  // Built pin arrays + spring state per ribbon
  let ribbonData = null;

  // Pin density: ~1 pin per N px of width, clamped
  function calcPinCount(densityPx, min, max) {
    return Math.max(min, Math.min(max, Math.round(W / densityPx)));
  }

  function resize() {
    const sec = canvas.parentElement;
    W = canvas.width  = sec.offsetWidth;
    H = canvas.height = sec.offsetHeight;

    // Pin count scales with width (~1 pin per 7-8px)
    RIBBONS[0].pinCount = calcPinCount(7, 80,  220);
    RIBBONS[1].pinCount = calcPinCount(6, 100, 260);

    // Pin height scales with screen height so ribbons aren't too tall/short
    const hScale = Math.min(1, H / 900);
    RIBBONS[0].pinHeightFront = Math.round(120 * hScale);
    RIBBONS[0].pinHeightBack  = Math.round(10  * hScale);
    RIBBONS[1].pinHeightFront = Math.round(100 * hScale);
    RIBBONS[1].pinHeightBack  = Math.round(8   * hScale);

    ribbonData = null;
  }

  // ── Bezier ─────────────────────────────────────────────────
  function cbPt(t, p0, p1, p2, p3) {
    const v = 1 - t;
    return {
      x: v*v*v*p0[0] + 3*v*v*t*p1[0] + 3*v*t*t*p2[0] + t*t*t*p3[0],
      y: v*v*v*p0[1] + 3*v*v*t*p1[1] + 3*v*t*t*p2[1] + t*t*t*p3[1],
    };
  }

  function buildRibbon(def) {
    const { pinCount, A, B } = def;
    const halfA = Math.floor(pinCount / 2);
    const halfB = pinCount - halfA;
    const pins  = [];

    // Resolve fractions to pixels
    const rA = {
      p0: [A.p0[0]*W, A.p0[1]*H], p1: [A.p1[0]*W, A.p1[1]*H],
      p2: [A.p2[0]*W, A.p2[1]*H], p3: [A.p3[0]*W, A.p3[1]*H],
    };
    const rB = {
      p0: [B.p0[0]*W, B.p0[1]*H], p1: [B.p1[0]*W, B.p1[1]*H],
      p2: [B.p2[0]*W, B.p2[1]*H], p3: [B.p3[0]*W, B.p3[1]*H],
    };

    for (let i = 0; i < halfA; i++) {
      const t  = i / (halfA - 1);
      const pt = cbPt(t, rA.p0, rA.p1, rA.p2, rA.p3);
      pins.push({ x: pt.x, y: pt.y, u: i / (pinCount - 1) });
    }
    for (let i = 0; i < halfB; i++) {
      const t  = i / (halfB - 1);
      const pt = cbPt(t, rB.p0, rB.p1, rB.p2, rB.p3);
      pins.push({ x: pt.x, y: pt.y, u: (halfA + i) / (pinCount - 1) });
    }

    const n = pinCount;
    return {
      def,
      pins,
      disp:  new Float32Array(n),
      dispX: new Float32Array(n),
      velY:  new Float32Array(n),
      velX:  new Float32Array(n),
      // Pulse state
      pulseStart: null,   // timestamp when current pulse started (null = idle)
      pulseNext:  null,   // timestamp when next pulse should fire
    };
  }

  function buildAll(now) {
    return RIBBONS.map((def, i) => {
      const rd = buildRibbon(def);
      // Stagger initial pulse so ribbon 1 and 2 don't fire simultaneously
      rd.pulseNext = now + i * (PULSE.interval * 0.6) + Math.random() * PULSE.jitter;
      return rd;
    });
  }

  // ── Events ─────────────────────────────────────────────────
  const section = canvas.parentElement;

  function updateMouse(cx, cy) {
    const rect = canvas.getBoundingClientRect();
    mouseX = cx - rect.left;
    mouseY = cy - rect.top;
  }

  section.addEventListener("mousemove",  (e) => updateMouse(e.clientX, e.clientY));
  section.addEventListener("mouseleave", ()  => { mouseX = -9999; mouseY = -9999; });
  section.addEventListener("touchmove",  (e) => {
    if (e.touches.length > 0) updateMouse(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  section.addEventListener("touchend", () => { mouseX = -9999; mouseY = -9999; });

  // ── Draw natural bloom glow at bottom-center ───────────────
  function drawGlow() {
    const cx = W * 0.50;
    const cy = H;               // anchored at bottom edge, light blooms upward

    // Outer soft halo — very wide, barely visible
    const r1 = H * 0.90;
    const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r1);
    g1.addColorStop(0,   "rgba(202,255,0,0.09)");
    g1.addColorStop(0.5, "rgba(202,255,0,0.03)");
    g1.addColorStop(1,   "rgba(202,255,0,0)");
    ctx.beginPath();
    ctx.arc(cx, cy, r1, 0, Math.PI * 2);
    ctx.fillStyle = g1;
    ctx.fill();

    // Inner bloom — warm, smooth
    const r2 = H * 0.40;
    const g2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r2);
    g2.addColorStop(0,    "rgba(202,255,0,0.22)");
    g2.addColorStop(0.45, "rgba(202,255,0,0.07)");
    g2.addColorStop(1,    "rgba(202,255,0,0)");
    ctx.beginPath();
    ctx.arc(cx, cy, r2, 0, Math.PI * 2);
    ctx.fillStyle = g2;
    ctx.fill();
  }

  // ── Draw one ribbon ────────────────────────────────────────
  function drawRibbon(rd, pulseU) {
    const { def, pins, disp, dispX, velY, velX } = rd;
    const n = def.pinCount;

    // Spring physics
    for (let i = 0; i < n; i++) {
      const pin  = pins[i];
      const dx   = pin.x - mouseX;
      const dy   = pin.y - mouseY;
      const dist = Math.sqrt(dx*dx + dy*dy);

      let tY = 0, tX = 0;
      if (dist < MOUSE.radius && dist > 0.5) {
        const s = 1 - dist / MOUSE.radius;
        const e = s * s * s;
        tY = MOUSE.force * e;
        tX = (dx / dist) * MOUSE.force * e * 0.5;
      }

      velY[i] += (tY - disp[i])  * MOUSE.smoothIn;
      velX[i] += (tX - dispX[i]) * MOUSE.smoothIn;
      velY[i] *= (1 - MOUSE.decay);
      velX[i] *= (1 - MOUSE.decay);
      disp[i]  += velY[i];
      dispX[i] += velX[i];
    }

    // Render back-to-front
    for (let i = n - 1; i >= 0; i--) {
      const pin   = pins[i];
      const depth = 1 - pin.u;   // 1=front, 0=back

      // Pulse highlight: cosine bell centered at pulseU
      const pDiff = pin.u - pulseU;
      const pEnv  = Math.abs(pDiff) < PULSE.width
        ? Math.cos((pDiff / PULSE.width) * Math.PI * 0.5)
        : 0;

      const baseH = def.pinHeightBack + (def.pinHeightFront - def.pinHeightBack) * depth;
      // Pop: only in first half (u < 0.5), fades out toward mid
      const popFade = Math.max(0, 1 - pin.u * 2);   // 1 at front → 0 at u=0.5
      const pinH  = baseH + pEnv * baseH * 0.35 * popFade;
      const opa   = Math.min(1, (def.opacityBack + (def.opacityFront - def.opacityBack) * depth) + pEnv * PULSE.brightBoost);
      const dotR  = (def.dotRadiusBack + (def.dotRadiusFront - def.dotRadiusBack) * depth) * (1 + pEnv * PULSE.sizeBoost);
      const lw    = (0.3 + 1.2 * depth) * (1 + pEnv * 0.8);

      const bx = pin.x + dispX[i];
      const by = pin.y;
      const ty = pin.y - pinH - disp[i];

      if (by - ty < 0.5) continue;

      const grad = ctx.createLinearGradient(bx, ty, bx, by);
      grad.addColorStop(0,   `rgba(${COLOR},${Math.min(1, opa)})`);
      grad.addColorStop(0.5, `rgba(${COLOR},${Math.min(1, opa * 0.28)})`);
      grad.addColorStop(1,   `rgba(${COLOR},0)`);

      ctx.beginPath();
      ctx.moveTo(bx, ty);
      ctx.lineTo(bx, by);
      ctx.strokeStyle = grad;
      ctx.lineWidth   = lw;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(bx, ty, dotR, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${COLOR},${Math.min(1, opa * 1.2)})`;
      ctx.fill();
    }
  }

  // ── Main loop ──────────────────────────────────────────────
  function draw(ts) {
    if (!ribbonData) ribbonData = buildAll(ts);

    ctx.clearRect(0, 0, W, H);

    drawGlow();

    for (const rd of ribbonData) {
      // ── Pulse timing ──
      if (rd.pulseStart === null && ts >= rd.pulseNext) {
        rd.pulseStart = ts;
      }
      let pulseU = -999;
      if (rd.pulseStart !== null) {
        const progress = (ts - rd.pulseStart) / PULSE.duration;
        pulseU = progress;            // 0→1 as pulse travels front→back
        if (progress > 1 + PULSE.width) {
          // Pulse finished — schedule next
          rd.pulseStart = null;
          rd.pulseNext  = ts + PULSE.interval + (Math.random() * 2 - 1) * PULSE.jitter;
        }
      }
      drawRibbon(rd, pulseU);
    }

    animId = requestAnimationFrame(draw);
  }

  // ── Visibility API ─────────────────────────────────────────
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cancelAnimationFrame(animId);
    } else {
      animId = requestAnimationFrame(draw);
    }
  });

  // ── Init ───────────────────────────────────────────────────
  if (window.innerWidth < 768) {
    canvas.style.display = "none";
    return;
  }

  resize();
  window.addEventListener("resize", () => {
    if (window.innerWidth < 768) {
      cancelAnimationFrame(animId);
      canvas.style.display = "none";
      return;
    }
    canvas.style.display = "";
    resize();
  });
  animId = requestAnimationFrame(draw);
})();
