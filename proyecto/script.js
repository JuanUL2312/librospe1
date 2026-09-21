/* ================================================================
   FLORES AMARILLAS — Te Amo | script.js
   Galaxia + corazón de partículas + girasoles + música + tarjeta
   ================================================================ */
'use strict';

/* ============ CANVAS ============ */
var canvas = document.getElementById('scene');
var ctx = canvas.getContext('2d');
var W = window.innerWidth, H = window.innerHeight;
var DPR = Math.min(window.devicePixelRatio || 1, 2);

function setup() {
  W = window.innerWidth; H = window.innerHeight;
  canvas.width = W * DPR; canvas.height = H * DPR;
  canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  buildScene();
}
window.addEventListener('resize', setup);

/* ============ ESTADO ============ */
var T = 0;
var started = false;
var stars = [];
var heartPts = [];
var minis = [];
var petals = [];
var lastPetal = 0;
var groundY = 0, heartCX = 0, heartCY = 0, heartS = 1, bigR = 60;
var warping = false, warpP = 0, warpStars = [];
var bigHit = null, miniHits = [];
var heartSpin = 0, heartBoost = 0, heartHit = null, spinAnim = 1;

function rnd(a, b) { return a + Math.random() * (b - a); }

/* ============ ESTRELLAS ============ */
function initStars() {
  stars = [];
  for (var i = 0; i < 380; i++) {
    stars.push({ x: Math.random() * W, y: Math.random() * H, r: rnd(0.3, 1.7),
      a: rnd(0.3, 1), sp: rnd(0.01, 0.05), ph: rnd(0, 6.28), gold: Math.random() > 0.8 });
  }
}

/* ============ CORAZON DE PARTICULAS ============ */
function initHeart() {
  heartPts = [];
  heartCX = W / 2; heartCY = H * 0.30;
  heartS = Math.min(W, H) * 0.011;
  bigR = Math.min(W, H) * 0.075;
  var N = Math.min(900, Math.floor(W * H / 1600));
  for (var i = 0; i < N; i++) {
    var t = Math.random() * Math.PI * 2;
    var edge = Math.random() < 0.45;
    var k = edge ? 1 : Math.sqrt(Math.random());
    var x = 16 * Math.pow(Math.sin(t), 3) * k;
    var y = (13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) * k;
    heartPts.push({ bx: heartCX + x * heartS, by: heartCY - y * heartS,
      ph: rnd(0, 6.28), sp: rnd(1, 3), r: rnd(0.7, 2.1), edge: edge });
  }
}

/* ============ MINI GIRASOLES (orbitan el anillo) ============ */
function initMinis() {
  minis = [];
  groundY = H * 0.68;
  var n = 9;
  for (var i = 0; i < n; i++) {
    minis.push({ a: (i / n) * Math.PI * 2, ring: rnd(0.85, 1.25),
      sp: rnd(0.10, 0.22) * (Math.random() < 0.5 ? 1 : -1),
      r: rnd(10, 20), ph: rnd(0, 6.28), rot: rnd(0, 6.28) });
  }
}

function buildScene() { initStars(); initHeart(); initMinis(); initWarp(); }

/* ============ DIBUJO: GIRASOL 3D ============ */
function sunflower(x, y, R, rot, t) {
  var i, a, z, px, py, sc, wob, tilt, petals;
  ctx.save();
  ctx.translate(x, y + Math.sin(t * 1.4) * R * 0.08);
  ctx.rotate(rot + Math.sin(t * 0.9) * 0.12);

  tilt = Math.sin(t * 1.1 + rot) * 0.48;
  wob = Math.cos(t * 1.7 + rot) * 0.10;
  petals = [];

  for (i = 0; i < 18; i++) {
    a = (i / 18) * Math.PI * 2;
    z = Math.sin(a + tilt);
    petals.push({ a: a, z: z });
  }
  petals.sort(function (p1, p2) { return p1.z - p2.z; });

  // Halo posterior para separar la flor del fondo.
  var halo = ctx.createRadialGradient(0, 0, R * 0.15, 0, 0, R * 1.45);
  halo.addColorStop(0, 'rgba(255,214,80,.34)');
  halo.addColorStop(1, 'rgba(255,214,80,0)');
  ctx.fillStyle = halo;
  ctx.beginPath(); ctx.arc(0, 0, R * 1.45, 0, Math.PI * 2); ctx.fill();

  for (i = 0; i < petals.length; i++) {
    a = petals[i].a;
    z = petals[i].z;
    sc = 0.72 + (z + 1) * 0.22;
    px = Math.cos(a) * R * 0.66 * (1 + wob);
    py = Math.sin(a) * R * 0.54 * (1 - wob * 0.5);

    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(a + Math.PI / 2 + Math.sin(t * 2.1 + i) * 0.05);
    ctx.scale(sc * (0.80 + z * 0.10), sc);

    var bright = 0.55 + (z + 1) * 0.23;
    var g = ctx.createRadialGradient(0, -R * 0.32, 1, 0, 0, R * 0.60);
    g.addColorStop(0, 'rgba(255,255,190,' + bright + ')');
    g.addColorStop(0.45, 'rgba(255,226,70,' + bright + ')');
    g.addColorStop(1, 'rgba(218,139,0,' + (0.55 + z * 0.20) + ')');
    ctx.fillStyle = g;
    ctx.shadowColor = 'rgba(255,205,55,' + (0.40 + Math.max(0, z) * 0.55) + ')';
    ctx.shadowBlur = R * (0.18 + Math.max(0, z) * 0.22);
    ctx.beginPath();
    ctx.moveTo(0, -R * 0.56);
    ctx.bezierCurveTo(R * 0.24, -R * 0.42, R * 0.29, R * 0.18, 0, R * 0.40);
    ctx.bezierCurveTo(-R * 0.29, R * 0.18, -R * 0.24, -R * 0.42, 0, -R * 0.56);
    ctx.fill();
    ctx.restore();
  }

  ctx.shadowBlur = 0;
  var squash = 1 + Math.sin(t * 1.2 + rot) * 0.08;
  var cg = ctx.createRadialGradient(-R * 0.12, -R * 0.12, R * 0.04, 0, 0, R * 0.48);
  cg.addColorStop(0, '#8a5418');
  cg.addColorStop(0.58, '#4a2a0c');
  cg.addColorStop(1, '#170b02');
  ctx.save();
  ctx.scale(1 + tilt * 0.12, 1 / squash);
  ctx.fillStyle = cg;
  ctx.shadowColor = 'rgba(255,202,73,.85)'; ctx.shadowBlur = R * 0.22;
  ctx.beginPath(); ctx.arc(0, 0, R * 0.42, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0;

  // Semillas con pequeno parallax para que el centro tambien respire en 3D.
  for (i = 0; i < 32; i++) {
    a = (i / 32) * Math.PI * 2 + t * 0.12;
    var d = R * 0.32 * (((i * 17) % 11) / 11);
    var seedZ = 0.55 + 0.45 * Math.sin(a + tilt);
    ctx.beginPath();
    ctx.arc(Math.cos(a) * d * (1 + tilt * 0.12), Math.sin(a) * d / squash, R * (0.024 + seedZ * 0.018), 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,221,115,' + (0.22 + seedZ * 0.36) + ')';
    ctx.fill();
  }
  ctx.restore();
  ctx.restore();
}

/* ============ TEXTO EN ARCOS (fijo y legible) ============ */
function arcStatic(text, cx, cy, rx, ry, a0, a1, size, flip) {
  var chars = Array.from(text);
  var n = chars.length;
  for (var i = 0; i < n; i++) {
    var a = a0 + (a1 - a0) * (n === 1 ? 0.5 : i / (n - 1));
    var x = cx + Math.cos(a) * rx, y = cy + Math.sin(a) * ry;
    ctx.save(); ctx.translate(x, y); ctx.rotate(a + (flip ? -Math.PI / 2 : Math.PI / 2));
    ctx.font = 'bold ' + size + 'px Georgia, serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(255,214,102,.95)';
    ctx.shadowColor = 'rgba(255,200,60,.9)'; ctx.shadowBlur = 10;
    ctx.fillText(chars[i], 0, 0);
    ctx.restore();
  }
}
function orbitTexts(front, cx, gy, grx, gry, fs) {
  if (!front) {
    var b1 = Math.sin(T * 1.1) * 5, b2 = Math.sin(T * 1.1 + 2) * 5;
    arcStatic('🌻 SIEMPRE TU 🌻   21 DE SEPTIEMBRE   🌼 PARA TI MI AMOR 🌼', cx, H * 0.545 + b1, W * 0.36, 26, Math.PI * 1.14, Math.PI * 1.86, fs, false);
    arcStatic('🌼 FLORES AMARILLAS 🌼   MI PERSONA FAVORITA   🌻 AMOR BONITO 🌻', cx, H * 0.60 + b2, W * 0.33, 24, Math.PI * 1.14, Math.PI * 1.86, fs, false);
  } else {
    var b3 = Math.sin(T * 1.1 + 4) * 5;
    arcStatic('✨ MI ZONA BONITA ✨   TE LAS MERECES   ✨ MI UNIVERSO ✨', cx, H * 0.775 + b3, W * 0.32, 24, Math.PI * 0.86, Math.PI * 0.14, fs, true);
  }
}
function orbitMinis(front, cx, gy, grx, gry) {
  for (var i = 0; i < minis.length; i++) {
    var m = minis[i];
    var a = m.a + T * m.sp;
    var isFront = Math.sin(a) >= 0;
    if (isFront !== front) continue;
    var depth = (Math.sin(a) + 1) / 2;
    var x = cx + Math.cos(a) * grx * m.ring;
    var y = gy + Math.sin(a) * gry * m.ring;
    ctx.save(); ctx.globalAlpha = 0.35 + 0.65 * depth;
    miniHits[i] = { x: x, y: y, r: m.r * (0.55 + 0.7 * depth) + 10 };
    sunflower(x, y, m.r * (0.55 + 0.7 * depth), m.rot + T * 0.1, T + m.ph);
    ctx.restore();
  }
}

/* ============ PETALOS ============ */
function spawnPetal() {
  petals.push({ x: rnd(0, W), y: -20, s: rnd(4, 10), vy: rnd(0.6, 1.6),
    vx: rnd(-0.5, 0.5), ph: rnd(0, 6.28), rot: rnd(0, 6.28), vr: rnd(-0.05, 0.05), a: rnd(0.5, 1) });
}

/* ============ VIAJE WARP 3D ============ */
function initWarp() {
  warpStars = [];
  for (var i = 0; i < 240; i++) {
    warpStars.push({ x: rnd(-1, 1), y: rnd(-1, 1), z: rnd(0.1, 1), sp: rnd(0.25, 0.7) });
  }
}
function drawWarp(dt) {
  warpP += dt / 2.2;
  ctx.fillStyle = 'rgba(0,0,0,.45)';
  ctx.fillRect(0, 0, W, H);
  var cx = W / 2, cy = H / 2, f = Math.min(W, H) * 0.9;
  var speed = 1 + warpP * 4;
  for (var i = 0; i < warpStars.length; i++) {
    var s = warpStars[i];
    s.z -= s.sp * speed * dt;
    if (s.z < 0.06) { s.z = 1; s.x = rnd(-1, 1); s.y = rnd(-1, 1); }
    var px = cx + (s.x / s.z) * f, py = cy + (s.y / s.z) * f;
    var pz = s.z + s.sp * speed * dt * 3;
    var qx = cx + (s.x / pz) * f, qy = cy + (s.y / pz) * f;
    var bright = Math.max(0, Math.min(1, 1.2 - s.z));
    ctx.strokeStyle = 'rgba(255,220,130,' + (0.25 + bright * 0.75) + ')';
    ctx.lineWidth = 1 + bright * 2;
    ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(px, py); ctx.stroke();
  }
  var g = ctx.createRadialGradient(cx, cy, 1, cx, cy, Math.min(W, H) * 0.5 * warpP + 10);
  g.addColorStop(0, 'rgba(255,240,180,' + (0.5 * warpP) + ')');
  g.addColorStop(1, 'rgba(255,240,180,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  if (warpP >= 1) {
    warping = false; started = true;
    document.getElementById('warpmsg').classList.remove('show');
    btn.classList.add('show');
    startMusic();
  }
}

/* ============ BUCLE PRINCIPAL ============ */
function draw() {
  T += 0.016;
  if (warping) { drawWarp(0.016); requestAnimationFrame(draw); return; }
  ctx.fillStyle = 'rgba(0,0,0,.35)';
  ctx.fillRect(0, 0, W, H);

  var i, s;
  for (i = 0; i < stars.length; i++) {
    s = stars[i];
    var tw = 0.4 + 0.6 * Math.abs(Math.sin(T * s.sp * 60 + s.ph));
    ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fillStyle = s.gold ? 'rgba(255,230,150,' + (s.a * tw) + ')' : 'rgba(255,255,255,' + (s.a * tw * 0.9) + ')';
    ctx.fill();
  }

  var cx = W / 2, gy = groundY;
  var grx = Math.min(W * 0.42, 520) * (1 + 0.02 * Math.sin(T * 4.2));
  var gry = grx * 0.16 * (1 + 0.12 * Math.sin(T * 0.6));

  var halo = ctx.createRadialGradient(cx, gy, 10, cx, gy, grx * 1.4);
  halo.addColorStop(0, 'rgba(255,190,60,.30)'); halo.addColorStop(1, 'rgba(255,190,60,0)');
  ctx.fillStyle = halo;
  ctx.beginPath(); ctx.ellipse(cx, gy, grx * 1.4, gry * 2.2, 0, 0, Math.PI * 2); ctx.fill();

  ctx.save();
  ctx.strokeStyle = 'rgba(255,215,110,.85)'; ctx.lineWidth = 3;
  ctx.shadowColor = '#ffcf5e'; ctx.shadowBlur = 22;
  ctx.beginPath(); ctx.ellipse(cx, gy, grx, gry, 0, 0, Math.PI * 2); ctx.stroke();
  ctx.lineWidth = 1.2; ctx.shadowBlur = 8;
  ctx.beginPath(); ctx.ellipse(cx, gy, grx * 1.12, gry * 1.35, 0, 0, Math.PI * 2); ctx.stroke();
  ctx.restore();

  /* Te Amo */
  ctx.save();
  ctx.font = 'italic bold ' + Math.floor(Math.min(W, H) * 0.085) + 'px "Brush Script MT", Georgia, cursive';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillStyle = '#ffe9a8';
  ctx.shadowColor = '#ffcf5e'; ctx.shadowBlur = 30 + 12 * Math.sin(T * 2);
  ctx.fillText('Te Amo', cx, H * 0.115);
  ctx.restore();

  /* Corazón 3D: giro + latido + giro 360° al clic */
  var beat = 1 + 0.05 * Math.sin(T * 4.2) + 0.02 * Math.sin(T * 9);
  var wob = 1 + 0.05 * Math.sin(T * 0.7);
  var ry3d = 0.55 * Math.sin(T * 0.6);
  var cosRy = Math.cos(ry3d), sinRy = Math.sin(ry3d);
  if (spinAnim < 1) {
    spinAnim = Math.min(1, spinAnim + 0.016 / 1.4);
    var e = spinAnim < 0.5 ? 4 * spinAnim * spinAnim * spinAnim : 1 - Math.pow(-2 * spinAnim + 2, 3) / 2;
    heartSpin = e * Math.PI * 2;
  } else { heartSpin = 0; }
  heartBoost = Math.max(0, heartBoost - 0.016 * 0.6);
  heartHit = { x: heartCX, y: heartCY, r: 19 * heartS * beat + heartBoost * 40 };
  for (i = 0; i < heartPts.length; i++) {
    var p = heartPts[i];
    var fl = Math.sin(T * p.sp + p.ph) * 3;
    var rx0 = (p.bx - heartCX), ry0 = (p.by - heartCY);
    var cs0 = Math.cos(heartSpin), sn0 = Math.sin(heartSpin);
    var rdx = rx0 * cs0 - ry0 * sn0, rdy = rx0 * sn0 + ry0 * cs0;
    var dx = rdx * beat * wob, dy = rdy * beat;
    var blen = Math.sqrt(dx * dx + dy * dy) + 1;
    dx += (dx / blen) * heartBoost * 60;
    dy += (dy / blen) * heartBoost * 60;
    var gl = p.edge ? 0.95 : 0.55 + 0.3 * Math.sin(T * 3 + p.ph);
    var x3 = dx * cosRy;
    var nx = dx / (heartS * 16 + 1);
    var light = Math.max(0.35, Math.min(1, 0.72 + nx * sinRy * 0.9));
    ctx.beginPath(); ctx.arc(heartCX + x3, heartCY + dy + fl, p.r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,214,100,' + (gl * light) + ')';
    ctx.fill();
  }

  /* Textos y flores traseras (detrás del girasol) */
  var fs = Math.max(11, Math.floor(Math.min(W, H) * 0.022));
  orbitTexts(false, cx, gy, grx, gry, fs);
  orbitMinis(false, cx, gy, grx, gry);

  /* Girasol grande en la punta del corazón */
  var tipY = heartCY + 17 * heartS * beat;
  ctx.save();
  ctx.strokeStyle = 'rgba(90,160,70,.9)'; ctx.lineWidth = 5;
  ctx.beginPath(); ctx.moveTo(cx, tipY + bigR * 0.4);
  ctx.quadraticCurveTo(cx + 8, tipY + bigR * 1.4, cx, groundY - 6); ctx.stroke();
  ctx.restore();
  sunflower(cx, tipY + bigR * 0.75, bigR, T * 0.15, T);
  bigHit = { x: cx, y: tipY + bigR * 0.75, r: bigR * 1.15 };

  /* Textos y flores frontales */
  orbitTexts(true, cx, gy, grx, gry, fs);
  orbitMinis(true, cx, gy, grx, gry);

  /* Fecha bajo el girasol */
  ctx.save();
  ctx.font = 'bold ' + Math.floor(fs * 1.05) + 'px Georgia, serif';
  ctx.textAlign = 'center'; ctx.fillStyle = '#ffd766';
  ctx.shadowColor = '#ffcf5e'; ctx.shadowBlur = 12;
  ctx.fillText('21 DE SEPTIEMBRE', cx, Math.min(gy + gry * 2.4, H - 56));
  ctx.restore();

  /* Pétalos cayendo */
  if (started && petals.length < 50 && T - lastPetal > 0.25) { spawnPetal(); lastPetal = T; }
  for (i = petals.length - 1; i >= 0; i--) {
    var q = petals[i];
    q.y += q.vy; q.x += q.vx + Math.sin(q.ph) * 0.7; q.ph += 0.05; q.rot += q.vr;
    if (q.y > H + 30) { petals.splice(i, 1); continue; }
    ctx.save(); ctx.translate(q.x, q.y); ctx.rotate(q.rot);
    ctx.beginPath(); ctx.ellipse(0, 0, q.s * 0.5, q.s, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,214,100,' + q.a + ')'; ctx.fill();
    ctx.restore();
  }

  requestAnimationFrame(draw);
}

setup();
draw();

/* ============ ESTELA DEL RATON ============ */
var lastTrail = 0;
document.addEventListener('mousemove', function (e) {
  var now = Date.now();
  if (now - lastTrail < 50) return;
  lastTrail = now;
  var d = document.createElement('div');
  d.style.cssText = 'position:fixed;left:' + (e.clientX - 3) + 'px;top:' + (e.clientY - 3) + 'px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle,#fff,#ffd966);box-shadow:0 0 12px #ffd966;pointer-events:none;z-index:6;transition:opacity 1s,transform 1s;';
  document.body.appendChild(d);
  requestAnimationFrame(function () { d.style.opacity = '0'; d.style.transform = 'scale(.2) translateY(-20px)'; });
  setTimeout(function () { d.remove(); }, 1100);
});

/* ============ TARJETA GIRASOLES (clic en flores + VOLVER) ============ */
var MSGS = [
  "🌻 Eres mi sol: aunque el universo sea infinito, mi luz siempre te encontrará a ti. Te amo. 💛",
  "💛 Gracias por existir y pintar todos mis días de amarillo.",
  "🌼 Eres mi persona favorita en esta y en todas las galaxias.",
  "✨ Cada pétalo de esta flor guarda un te quiero para ti.",
  "🌻 Dicen que las flores amarillas son amor sincero… entonces todo este universo es para ti.",
  "💛 Contigo, hasta los días más grises florecen.",
  "🌟 Entre millones de estrellas, tú eres la más brillante de mi cielo.",
  "🌼 Prometo cuidarte como se cuida a un girasol: dándote luz todos los días.",
  "💛 Mi zona bonita siempre serás tú, hoy y siempre.",
  "🌻 21 de septiembre: el día en que las flores recuerdan cuánto te amo."
];
function openCard(idx) {
  document.getElementById('girmsg').textContent = MSGS[idx % MSGS.length];
  document.querySelector('#gircard .girflower').textContent = idx === 0 ? '🌻' : '🌼';
  var card = document.getElementById('gircard');
  card.classList.add('show');
  card.setAttribute('aria-hidden', 'false');
}
function closeCard() {
  var card = document.getElementById('gircard');
  card.classList.remove('show');
  card.setAttribute('aria-hidden', 'true');
}
document.getElementById('back').addEventListener('click', function (e) {
  e.stopPropagation();
  closeCard();
});
document.getElementById('gircard').addEventListener('click', function (e) {
  if (e.target.id === 'gircard') closeCard();
});
canvas.addEventListener('click', function (e) {
  if (!started || warping) return;
  if (document.getElementById('gircard').classList.contains('show')) return;
  var r = canvas.getBoundingClientRect();
  var mx = e.clientX - r.left, my = e.clientY - r.top, i, h;
  if (heartHit && Math.hypot(mx - heartHit.x, my - heartHit.y) < heartHit.r) { heartBurst(heartHit.x, heartHit.y); return; }
  if (bigHit && Math.hypot(mx - bigHit.x, my - bigHit.y) < bigHit.r) { openCard(0); return; }
  for (i = 0; i < miniHits.length; i++) {
    h = miniHits[i];
    if (h && Math.hypot(mx - h.x, my - h.y) < h.r) { openCard(i + 1); return; }
  }
});
document.addEventListener('mousemove', function (e) {
  if (!started || warping) return;
  var r = canvas.getBoundingClientRect();
  var mx = e.clientX - r.left, my = e.clientY - r.top, hit = false, i, h;
  if (heartHit && Math.hypot(mx - heartHit.x, my - heartHit.y) < heartHit.r) hit = true;
  if (bigHit && Math.hypot(mx - bigHit.x, my - bigHit.y) < bigHit.r) hit = true;
  if (!hit) {
    for (i = 0; i < miniHits.length; i++) {
      h = miniHits[i];
      if (h && Math.hypot(mx - h.x, my - h.y) < h.r) { hit = true; break; }
    }
  }
  canvas.style.cursor = hit ? 'pointer' : 'crosshair';
});

/* Explosión del corazón al clic */
function heartBurst(x, y) {
  heartBoost = 1; spinAnim = 0;
  for (var i = 0; i < 14; i++) {
    (function (k) {
      setTimeout(function () {
        var s = document.createElement('span');
        s.textContent = ['💛', '💖', '❤', '🌼'][k % 4];
        s.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;z-index:55;pointer-events:none;font-size:' + (16 + Math.random() * 18) + 'px;transition:all 1.4s ease-out;';
        document.body.appendChild(s);
        var dx = (Math.random() - 0.5) * 220, dy = -120 - Math.random() * 160;
        requestAnimationFrame(function () {
          s.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(1.4) rotate(' + (Math.random() * 60 - 30) + 'deg)';
          s.style.opacity = '0';
        });
        setTimeout(function () { s.remove(); }, 1500);
      }, k * 60);
    })(i);
  }
}

/* ============ MUSICA DE FONDO: archivo local MP3 ============ */
var playing = false, timer = null;
var btn = document.getElementById('music-btn');
var BG = document.getElementById('bgmusic');
if (BG) { try { BG.volume = 0.8; } catch (e) {} }
function startMusic() {
  playing = true; btn.textContent = '♫';
  if (timer) { clearTimeout(timer); timer = null; }
  if (BG) { try { var p = BG.play(); if (p && p.catch) { p.catch(function () {}); } } catch (e) {} }
}
function stopMusic() {
  playing = false;
  if (timer) { clearTimeout(timer); timer = null; }
  if (BG) { try { BG.pause(); } catch (e) {} }
  btn.textContent = '♪';
}
btn.addEventListener('click', function (e) { e.stopPropagation(); playing ? stopMusic() : startMusic(); });

/* ============ TARJETA 3D (sigue al raton) ============ */
(function () {
  var intro = document.getElementById('intro');
  var card = document.querySelector('.card');
  if (!intro || !card) return;
  intro.addEventListener('mousemove', function (e) {
    var r = card.getBoundingClientRect();
    var dx = (e.clientX - (r.left + r.width / 2)) / r.width;
    var dy = (e.clientY - (r.top + r.height / 2)) / r.height;
    card.style.transform = 'rotateY(' + (dx * 14) + 'deg) rotateX(' + (-dy * 12) + 'deg) translateZ(24px)';
  });
  intro.addEventListener('mouseleave', function () { card.style.transform = 'none'; });
})();

/* ============ ENTRADA ============ */
document.getElementById('enter').addEventListener('click', function () {
  var intro = document.getElementById('intro');
  intro.classList.add('hide');
  document.getElementById('warpmsg').classList.add('show');
  warpP = 0; warping = true;
  setTimeout(function () { intro.remove(); }, 900);
});
