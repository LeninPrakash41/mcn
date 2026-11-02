/* The Mummy: a first-person tomb escape game built on Three.js. */
(() => {
  'use strict';

  // ---------- constants ----------
  const S = 4;              // size of one grid cell (world units)
  const WALL_H = 4.2;
  const EYE_H = 1.65;
  const PLAYER_R = 0.6;
  const WALK = 4.5, SPRINT = 7.5;
  const MAX_HEALTH = 100;

  // ---------- DOM ----------
  const $ = (id) => document.getElementById(id);
  const canvas = $('game');
  const ui = {
    hud: $('hud'), menu: $('menu'), pause: $('pause'), levelDone: $('level-done'), over: $('gameover'),
    level: $('hud-level'), scarabs: $('hud-scarabs'), score: $('hud-score'), time: $('hud-time'),
    health: $('bar-health'), oil: $('bar-oil'), stamina: $('bar-stamina'),
    message: $('message'), damage: $('damage'), minimap: $('minimap'),
    name: $('name'), levelSummary: $('level-summary'), finalSummary: $('final-summary'),
    scoresMenu: $('scores-menu'), scoresOver: $('scores-over'),
  };
  const mm = ui.minimap.getContext('2d');

  // ---------- renderer / scene ----------
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x030201);
  scene.fog = new THREE.FogExp2(0x030201, 0.085);
  const camera = new THREE.PerspectiveCamera(72, window.innerWidth / window.innerHeight, 0.05, 80);
  camera.rotation.order = 'YXZ';
  scene.add(camera);
  scene.add(new THREE.HemisphereLight(0x3a2a18, 0x0a0604, 0.32));
  const torch = new THREE.PointLight(0xffa24a, 1.6, 18, 2);
  torch.position.set(0.25, -0.15, -0.2);
  camera.add(torch);

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  // ---------- procedural textures ----------
  function rng(seed) { // small deterministic PRNG for textures
    let s = seed >>> 0;
    return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  }

  function canvasTex(size, draw, repeat = 1) {
    const c = document.createElement('canvas');
    c.width = c.height = size;
    draw(c.getContext('2d'), size);
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(repeat, repeat);
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return t;
  }

  function noise(ctx, size, r, amount) {
    const img = ctx.getImageData(0, 0, size, size);
    for (let i = 0; i < img.data.length; i += 4) {
      const n = (r() - 0.5) * amount;
      img.data[i] += n; img.data[i + 1] += n; img.data[i + 2] += n;
    }
    ctx.putImageData(img, 0, 0);
  }

  function drawGlyph(ctx, kind, x, y, s) {
    ctx.beginPath();
    switch (kind) {
      case 0: // eye
        ctx.ellipse(x, y, s * 0.5, s * 0.22, 0, 0, Math.PI * 2);
        ctx.moveTo(x + s * 0.1, y); ctx.arc(x, y, s * 0.1, 0, Math.PI * 2);
        ctx.moveTo(x - s * 0.1, y + s * 0.2); ctx.lineTo(x - s * 0.2, y + s * 0.5);
        break;
      case 1: // looped cross
        ctx.ellipse(x, y - s * 0.3, s * 0.16, s * 0.2, 0, 0, Math.PI * 2);
        ctx.moveTo(x - s * 0.35, y - s * 0.05); ctx.lineTo(x + s * 0.35, y - s * 0.05);
        ctx.moveTo(x, y - s * 0.1); ctx.lineTo(x, y + s * 0.5);
        break;
      case 2: // bird-ish
        ctx.arc(x - s * 0.1, y - s * 0.25, s * 0.12, 0, Math.PI * 2);
        ctx.moveTo(x - s * 0.2, y - s * 0.1); ctx.quadraticCurveTo(x + s * 0.4, y, x + s * 0.3, y + s * 0.35);
        ctx.moveTo(x - s * 0.05, y + s * 0.3); ctx.lineTo(x - s * 0.05, y + s * 0.5);
        break;
      case 3: // water zigzag
        ctx.moveTo(x - s * 0.5, y);
        for (let i = 0; i < 6; i++) ctx.lineTo(x - s * 0.5 + (i + 1) * s / 6, y + (i % 2 ? -1 : 1) * s * 0.12);
        break;
      case 4: // reed
        ctx.moveTo(x, y + s * 0.5); ctx.lineTo(x, y - s * 0.4);
        ctx.moveTo(x, y - s * 0.4); ctx.quadraticCurveTo(x + s * 0.3, y - s * 0.3, x + s * 0.1, y - s * 0.05);
        break;
      default: // sun
        ctx.arc(x, y, s * 0.25, 0, Math.PI * 2);
        ctx.moveTo(x + s * 0.06, y); ctx.arc(x, y, s * 0.06, 0, Math.PI * 2);
    }
    ctx.stroke();
  }

  const wallTex = canvasTex(512, (ctx, n) => {
    const r = rng(7);
    ctx.fillStyle = '#a8844f'; ctx.fillRect(0, 0, n, n);
    noise(ctx, n, r, 40);
    const rows = 6, bh = n / rows;
    ctx.strokeStyle = 'rgba(40,25,10,.75)'; ctx.lineWidth = 3;
    for (let row = 0; row < rows; row++) {
      const y = row * bh, off = row % 2 ? n / 6 : 0;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(n, y); ctx.stroke();
      for (let x = off; x < n + 1; x += n / 3) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + bh); ctx.stroke(); }
      for (let x = off; x < n; x += n / 3) { // shade blocks slightly differently
        ctx.fillStyle = `rgba(${r() < .5 ? '0,0,0' : '255,230,180'},${r() * 0.08})`;
        ctx.fillRect(x + 2, y + 2, n / 3 - 4, bh - 4);
      }
    }
    // a band of carved glyphs in the middle rows
    ctx.strokeStyle = 'rgba(55,32,12,.85)'; ctx.lineWidth = 3; ctx.lineCap = 'round';
    for (let row = 2; row <= 3; row++) {
      for (let i = 0; i < 6; i++) {
        drawGlyph(ctx, Math.floor(r() * 6), (i + 0.5) * n / 6, (row + 0.5) * bh, bh * 0.7);
      }
    }
  });

  const floorTex = canvasTex(256, (ctx, n) => {
    const r = rng(3);
    ctx.fillStyle = '#5c4529'; ctx.fillRect(0, 0, n, n);
    noise(ctx, n, r, 50);
    ctx.strokeStyle = 'rgba(15,9,4,.8)'; ctx.lineWidth = 3;
    ctx.strokeRect(1, 1, n / 2 - 2, n / 2 - 2); ctx.strokeRect(n / 2 + 1, 1, n / 2 - 2, n / 2 - 2);
    ctx.strokeRect(1, n / 2 + 1, n / 2 - 2, n / 2 - 2); ctx.strokeRect(n / 2 + 1, n / 2 + 1, n / 2 - 2, n / 2 - 2);
    for (let i = 0; i < 30; i++) { // sand drifts
      ctx.fillStyle = `rgba(200,170,110,${r() * 0.12})`;
      ctx.beginPath(); ctx.arc(r() * n, r() * n, 6 + r() * 26, 0, Math.PI * 2); ctx.fill();
    }
  });

  const ceilTex = canvasTex(256, (ctx, n) => {
    const r = rng(11);
    ctx.fillStyle = '#2a1f14'; ctx.fillRect(0, 0, n, n);
    noise(ctx, n, r, 30);
    ctx.fillStyle = 'rgba(232,182,74,.18)'; // faded painted stars
    for (let i = 0; i < 14; i++) {
      const x = r() * n, y = r() * n, s = 4 + r() * 4;
      ctx.beginPath();
      for (let k = 0; k < 10; k++) {
        const a = k * Math.PI / 5, rad = k % 2 ? s * 0.4 : s;
        ctx.lineTo(x + Math.cos(a) * rad, y + Math.sin(a) * rad);
      }
      ctx.fill();
    }
  });

  const bandageTex = canvasTex(128, (ctx, n) => {
    const r = rng(5);
    ctx.fillStyle = '#c9bb98'; ctx.fillRect(0, 0, n, n);
    for (let i = -n; i < n * 2; i += 7 + r() * 6) {
      ctx.strokeStyle = `rgba(${70 + r() * 40},${55 + r() * 30},${30 + r() * 20},${0.35 + r() * 0.4})`;
      ctx.lineWidth = 1 + r() * 2.5;
      ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(n, i + n * (0.25 + r() * 0.2)); ctx.stroke();
    }
    noise(ctx, n, r, 35);
  });

  const glowTex = canvasTex(64, (ctx, n) => {
    const g = ctx.createRadialGradient(n / 2, n / 2, 0, n / 2, n / 2, n / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.3, 'rgba(255,255,255,.45)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, n, n);
  });

  // ---------- shared materials / geometry ----------
  const mat = {
    wall: new THREE.MeshLambertMaterial({ map: wallTex }),
    floor: new THREE.MeshLambertMaterial({ map: floorTex }),
    ceil: new THREE.MeshLambertMaterial({ map: ceilTex }),
    bandage: new THREE.MeshLambertMaterial({ map: bandageTex }),
    eye: new THREE.MeshBasicMaterial({ color: 0xff3b1f }),
    gold: new THREE.MeshStandardMaterial({ color: 0xe8b64a, emissive: 0x6b4a10, metalness: 0.9, roughness: 0.3 }),
    lapis: new THREE.MeshStandardMaterial({ color: 0x1d3d8f, emissive: 0x0a1640, metalness: 0.4, roughness: 0.4 }),
    clay: new THREE.MeshLambertMaterial({ color: 0x8a4a22 }),
    stone: new THREE.MeshLambertMaterial({ color: 0x8c7048, map: wallTex }),
    doorLocked: new THREE.MeshBasicMaterial({ color: 0x8a1a10, transparent: true, opacity: 0.75, side: THREE.DoubleSide }),
    doorOpen: new THREE.MeshBasicMaterial({ color: 0x40e0c0, transparent: true, opacity: 0.8, side: THREE.DoubleSide }),
  };
  const glowMat = (color) => new THREE.SpriteMaterial({ map: glowTex, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });

  // ---------- audio (tiny WebAudio synth) ----------
  let actx = null;
  function audio() {
    if (!actx) { try { actx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { actx = null; } }
    return actx;
  }
  function tone({ freq = 440, to = freq, dur = 0.2, type = 'sine', vol = 0.2, filter = 0 }) {
    const a = audio(); if (!a) return;
    const o = a.createOscillator(), g = a.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, a.currentTime);
    o.frequency.exponentialRampToValueAtTime(Math.max(20, to), a.currentTime + dur);
    g.gain.setValueAtTime(vol, a.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur);
    let node = o;
    if (filter) { const f = a.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = filter; o.connect(f); node = f; }
    node.connect(g); g.connect(a.destination);
    o.start(); o.stop(a.currentTime + dur + 0.05);
  }
  const sfx = {
    scarab: () => { tone({ freq: 880, to: 1320, dur: 0.18, vol: 0.15 }); setTimeout(() => tone({ freq: 1320, to: 1760, dur: 0.25, vol: 0.12 }), 90); },
    oil: () => tone({ freq: 300, to: 520, dur: 0.3, type: 'triangle', vol: 0.18 }),
    hurt: () => tone({ freq: 180, to: 60, dur: 0.35, type: 'sawtooth', vol: 0.25, filter: 900 }),
    groan: (vol) => tone({ freq: 95 + Math.random() * 25, to: 55, dur: 1.4, type: 'sawtooth', vol: 0.18 * vol, filter: 380 }),
    open: () => { tone({ freq: 220, to: 440, dur: 0.8, type: 'triangle', vol: 0.2 }); tone({ freq: 330, to: 660, dur: 0.9, vol: 0.12 }); },
    step: () => tone({ freq: 120, to: 70, dur: 0.07, type: 'triangle', vol: 0.05, filter: 400 }),
  };

  // ---------- maze ----------
  let grid = [], GW = 0, GH = 0;
  const isWall = (cx, cz) => cx < 0 || cz < 0 || cx >= GW || cz >= GH || grid[cz][cx] === 1;
  const cellOf = (v) => Math.floor(v / S + 0.5);
  const wallAt = (x, z) => isWall(cellOf(x), cellOf(z));

  function generateMaze(cells) {
    GW = GH = cells * 2 + 1;
    grid = Array.from({ length: GH }, () => new Array(GW).fill(1));
    const stack = [[1, 1]];
    grid[1][1] = 0;
    while (stack.length) {
      const [x, z] = stack[stack.length - 1];
      const dirs = [[2, 0], [-2, 0], [0, 2], [0, -2]].sort(() => Math.random() - 0.5);
      let moved = false;
      for (const [dx, dz] of dirs) {
        const nx = x + dx, nz = z + dz;
        if (nx > 0 && nz > 0 && nx < GW - 1 && nz < GH - 1 && grid[nz][nx] === 1) {
          grid[z + dz / 2][x + dx / 2] = 0; grid[nz][nx] = 0;
          stack.push([nx, nz]); moved = true; break;
        }
      }
      if (!moved) stack.pop();
    }
    // knock out some extra walls so there are loops to escape through
    const extra = Math.floor(cells * cells * 0.12);
    for (let i = 0; i < extra; i++) {
      const x = 1 + Math.floor(Math.random() * (GW - 2)), z = 1 + Math.floor(Math.random() * (GH - 2));
      if (grid[z][x] !== 1) continue;
      const horiz = !isWall(x - 1, z) && !isWall(x + 1, z) && isWall(x, z - 1) && isWall(x, z + 1);
      const vert = !isWall(x, z - 1) && !isWall(x, z + 1) && isWall(x - 1, z) && isWall(x + 1, z);
      if (horiz || vert) grid[z][x] = 0;
    }
  }

  function bfs(sx, sz, tx = -1, tz = -1) {
    const dist = Array.from({ length: GH }, () => new Array(GW).fill(-1));
    const prev = new Map();
    const q = [[sx, sz]]; dist[sz][sx] = 0;
    for (let h = 0; h < q.length; h++) {
      const [x, z] = q[h];
      if (x === tx && z === tz) break;
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nx = x + dx, nz = z + dz;
        if (!isWall(nx, nz) && dist[nz][nx] < 0) {
          dist[nz][nx] = dist[z][x] + 1; prev.set(nz * GW + nx, z * GW + x); q.push([nx, nz]);
        }
      }
    }
    return { dist, prev };
  }

  function path(sx, sz, tx, tz) {
    if (isWall(tx, tz)) return [];
    const { dist, prev } = bfs(sx, sz, tx, tz);
    if (dist[tz][tx] < 0) return [];
    const out = [];
    let k = tz * GW + tx;
    const start = sz * GW + sx;
    while (k !== start) { out.push([k % GW, Math.floor(k / GW)]); k = prev.get(k); }
    return out.reverse();
  }

  function lineOfSight(x1, z1, x2, z2) {
    const d = Math.hypot(x2 - x1, z2 - z1), steps = Math.ceil(d / 0.5);
    for (let i = 1; i < steps; i++) {
      const t = i / steps;
      if (wallAt(x1 + (x2 - x1) * t, z1 + (z2 - z1) * t)) return false;
    }
    return true;
  }

  const blocked = (x, z, r) => wallAt(x - r, z - r) || wallAt(x + r, z - r) || wallAt(x - r, z + r) || wallAt(x + r, z + r);

  // ---------- models ----------
  function makeMummy() {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.3, 1.0, 10), mat.bandage);
    body.position.y = 1.2; g.add(body);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.27, 12, 10), mat.bandage);
    head.position.y = 1.95; head.scale.set(1, 1.1, 1); g.add(head);
    for (const sx of [-0.1, 0.1]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(0.045, 6, 6), mat.eye);
      eye.position.set(sx, 1.98, -0.24); g.add(eye);
    }
    const eyeGlow = new THREE.Sprite(glowMat(0xff2a10));
    eyeGlow.position.set(0, 1.98, -0.26); eyeGlow.scale.set(0.6, 0.35, 1); g.add(eyeGlow);
    const mkLimb = (w, h, x, y) => {
      const pivot = new THREE.Group(); pivot.position.set(x, y, 0);
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), mat.bandage);
      m.position.y = -h / 2; pivot.add(m); g.add(pivot); return pivot;
    };
    const arms = [mkLimb(0.17, 0.75, -0.45, 1.6), mkLimb(0.17, 0.75, 0.45, 1.6)];
    arms.forEach((a) => { a.rotation.x = Math.PI / 2.2; }); // outstretched, reaching
    const legs = [mkLimb(0.2, 0.75, -0.16, 0.75), mkLimb(0.2, 0.75, 0.16, 0.75)];
    // loose trailing bandage strip
    const strip = new THREE.Mesh(new THREE.PlaneGeometry(0.1, 0.7), new THREE.MeshLambertMaterial({ map: bandageTex, side: THREE.DoubleSide }));
    strip.position.set(0.25, 1.0, 0.3); strip.rotation.z = 0.3; g.add(strip);
    return { group: g, arms, legs, strip };
  }

  function makeScarab() {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.28, 14, 10), mat.gold);
    body.scale.set(0.8, 0.45, 1.1); g.add(body);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.12, 10, 8), mat.gold);
    head.position.set(0, 0, -0.33); g.add(head);
    const gem = new THREE.Mesh(new THREE.OctahedronGeometry(0.1), mat.lapis);
    gem.position.set(0, 0.12, 0.02); g.add(gem);
    const glow = new THREE.Sprite(glowMat(0xffc35a));
    glow.scale.set(1.6, 1.6, 1); g.add(glow);
    return g;
  }

  function makeOilJar() {
    const g = new THREE.Group();
    const pts = [[0, 0], [0.18, 0.02], [0.24, 0.18], [0.2, 0.36], [0.09, 0.44], [0.1, 0.52], [0, 0.52]].map(([x, y]) => new THREE.Vector2(x, y));
    const jar = new THREE.Mesh(new THREE.LatheGeometry(pts, 14), mat.clay);
    g.add(jar);
    const glow = new THREE.Sprite(glowMat(0xff8a1e));
    glow.position.y = 0.3; glow.scale.set(1.2, 1.2, 1); g.add(glow);
    return g;
  }

  function makeDoor() {
    const g = new THREE.Group();
    const pillarGeo = new THREE.BoxGeometry(0.5, 3.4, 0.5);
    const lp = new THREE.Mesh(pillarGeo, mat.stone); lp.position.set(-1.2, 1.7, 0); g.add(lp);
    const rp = new THREE.Mesh(pillarGeo, mat.stone); rp.position.set(1.2, 1.7, 0); g.add(rp);
    const lintel = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.5, 0.6), mat.stone); lintel.position.y = 3.6; g.add(lintel);
    const portal = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 3.4), mat.doorLocked); portal.position.y = 1.7; g.add(portal);
    const glow = new THREE.Sprite(glowMat(0xff3a20)); glow.position.y = 1.8; glow.scale.set(4, 4, 1); g.add(glow);
    return { group: g, portal, glow };
  }

  function makeSconce() {
    const g = new THREE.Group();
    const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.06, 0.2, 8), mat.gold);
    g.add(cup);
    const flame = new THREE.Sprite(glowMat(0xff9a30)); flame.position.y = 0.25; flame.scale.set(0.7, 1.0, 1); g.add(flame);
    return { group: g, flame };
  }

  // ---------- game state ----------
  const player = { x: 0, z: 0, yaw: 0, pitch: 0, health: MAX_HEALTH, oil: 100, stamina: 100, bob: 0, stepT: 0, knock: { x: 0, z: 0 } };
  const keys = {};
  let state = 'menu';
  let level = 1, score = 0, levelTime = 0, totalTime = 0, levelScarabs = 0;
  let levelGroup = null, mummies = [], scarabs = [], jars = [], sconces = [], door = null, exitCell = null;
  let revealed = new Set();
  let msgTimer = 0, revealTimer = 0, hudTimer = 0, groanTimer = 2, sealedMsgCooldown = 0;

  function disposeLevel() {
    if (!levelGroup) return;
    levelGroup.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
    scene.remove(levelGroup);
    levelGroup = null;
  }

  function freeCells() {
    const out = [];
    for (let z = 1; z < GH - 1; z++) for (let x = 1; x < GW - 1; x++) if (!grid[z][x]) out.push([x, z]);
    return out;
  }

  function buildLevel() {
    disposeLevel();
    levelGroup = new THREE.Group();
    scene.add(levelGroup);
    generateMaze(Math.min(5 + level * 2, 19));

    // walls as one instanced mesh
    const wallCells = [];
    for (let z = 0; z < GH; z++) for (let x = 0; x < GW; x++) if (grid[z][x]) wallCells.push([x, z]);
    const walls = new THREE.InstancedMesh(new THREE.BoxGeometry(S, WALL_H, S), mat.wall, wallCells.length);
    const m4 = new THREE.Matrix4();
    wallCells.forEach(([x, z], i) => { m4.makeTranslation(x * S, WALL_H / 2, z * S); walls.setMatrixAt(i, m4); });
    levelGroup.add(walls);

    const span = GW * S;
    const floorT = floorTex.clone(); floorT.needsUpdate = true; floorT.repeat.set(GW, GH);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(span, span), new THREE.MeshLambertMaterial({ map: floorT }));
    floor.rotation.x = -Math.PI / 2; floor.position.set(span / 2 - S / 2, 0, span / 2 - S / 2);
    levelGroup.add(floor);
    const ceilT = ceilTex.clone(); ceilT.needsUpdate = true; ceilT.repeat.set(GW / 2, GH / 2);
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(span, span), new THREE.MeshLambertMaterial({ map: ceilT }));
    ceil.rotation.x = Math.PI / 2; ceil.position.set(span / 2 - S / 2, WALL_H, span / 2 - S / 2);
    levelGroup.add(ceil);

    // start + exit (farthest reachable cell)
    const { dist } = bfs(1, 1);
    let far = [1, 1];
    for (let z = 0; z < GH; z++) for (let x = 0; x < GW; x++) if (dist[z][x] > dist[far[1]][far[0]]) far = [x, z];
    exitCell = far;
    door = makeDoor();
    door.group.position.set(far[0] * S, 0, far[1] * S);
    // face the open neighbour
    for (const [dx, dz, rot] of [[1, 0, -Math.PI / 2], [-1, 0, Math.PI / 2], [0, 1, Math.PI], [0, -1, 0]]) {
      if (!isWall(far[0] + dx, far[1] + dz)) { door.group.rotation.y = rot; break; }
    }
    levelGroup.add(door.group);

    // place pickups / enemies on free cells, away from the start
    const pool = freeCells().filter(([x, z]) => !(x === far[0] && z === far[1]) && dist[z][x] > 3)
      .sort(() => Math.random() - 0.5);
    const take = (minDist = 0) => {
      const i = pool.findIndex(([x, z]) => dist[z][x] >= minDist);
      return i >= 0 ? pool.splice(i, 1)[0] : null;
    };

    scarabs = []; jars = []; mummies = []; sconces = [];
    levelScarabs = 3 + level;
    for (let i = 0; i < levelScarabs; i++) {
      const c = take(); if (!c) break;
      const mesh = makeScarab(); mesh.position.set(c[0] * S, 0.9, c[1] * S);
      levelGroup.add(mesh); scarabs.push({ mesh, cell: c, phase: Math.random() * 6 });
    }
    levelScarabs = scarabs.length;
    for (let i = 0; i < 2 + Math.floor(level / 2); i++) {
      const c = take(); if (!c) break;
      const mesh = makeOilJar(); mesh.position.set(c[0] * S + (Math.random() - 0.5), 0, c[1] * S + (Math.random() - 0.5));
      levelGroup.add(mesh); jars.push({ mesh, cell: c });
    }
    const mummyCount = Math.min(1 + level, 8);
    for (let i = 0; i < mummyCount; i++) {
      const c = take(8) || take(); if (!c) break;
      const m = makeMummy();
      m.group.position.set(c[0] * S, 0, c[1] * S);
      levelGroup.add(m.group);
      mummies.push({ ...m, x: c[0] * S, z: c[1] * S, state: 'wander', target: null, prevCell: null, path: [], repath: 0,
        lastSeen: null, cooldown: 0, phase: Math.random() * 6, speedChase: Math.min(2.7 + 0.25 * level, 5.2), speedWander: 1.5 });
    }

    // decorative wall sconces
    for (const [x, z] of freeCells().sort(() => Math.random() - 0.5).slice(0, Math.floor(GW * 0.8))) {
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        if (isWall(x + dx, z + dz)) {
          const s = makeSconce();
          s.group.position.set(x * S + dx * (S / 2 - 0.15), 2.4, z * S + dz * (S / 2 - 0.15));
          levelGroup.add(s.group); sconces.push({ ...s, phase: Math.random() * 6 }); break;
        }
      }
    }

    // reset player
    player.x = S; player.z = S; player.pitch = 0;
    player.yaw = !isWall(2, 1) ? -Math.PI / 2 : Math.PI;
    player.oil = 100; player.stamina = 100; player.knock = { x: 0, z: 0 };
    levelTime = 0; revealed = new Set();
    showMessage(`Level ${level}: find ${levelScarabs} scarabs`, 3);
  }

  // ---------- UI helpers ----------
  function showMessage(text, secs = 2) {
    ui.message.textContent = text; ui.message.classList.add('show'); msgTimer = secs;
  }
  const fmtTime = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
  function show(el) { [ui.menu, ui.pause, ui.levelDone, ui.over].forEach((o) => o.classList.toggle('hidden', o !== el)); }

  function updateHud() {
    ui.level.textContent = level;
    ui.scarabs.textContent = `${levelScarabs - scarabs.length} / ${levelScarabs}`;
    ui.score.textContent = score;
    ui.time.textContent = fmtTime(levelTime);
    ui.health.style.width = `${Math.max(0, player.health)}%`;
    ui.oil.style.width = `${Math.max(0, player.oil)}%`;
    ui.stamina.style.width = `${Math.max(0, player.stamina)}%`;
  }

  function drawMinimap() {
    const n = ui.minimap.width, cs = n / GW;
    mm.clearRect(0, 0, n, n);
    for (const k of revealed) {
      const x = k % GW, z = Math.floor(k / GW);
      mm.fillStyle = grid[z][x] ? '#3d2c14' : '#8a6d40';
      mm.fillRect(x * cs, z * cs, cs + 0.5, cs + 0.5);
    }
    const ek = exitCell[1] * GW + exitCell[0];
    if (revealed.has(ek)) {
      mm.fillStyle = scarabs.length ? '#c0301e' : '#40e0c0';
      mm.fillRect(exitCell[0] * cs, exitCell[1] * cs, cs, cs);
    }
    mm.fillStyle = '#ffd36a';
    for (const s of scarabs) if (revealed.has(s.cell[1] * GW + s.cell[0])) {
      mm.beginPath(); mm.arc((s.cell[0] + 0.5) * cs, (s.cell[1] + 0.5) * cs, cs * 0.3, 0, Math.PI * 2); mm.fill();
    }
    mm.fillStyle = '#ff9a2e';
    for (const j of jars) if (revealed.has(j.cell[1] * GW + j.cell[0])) {
      mm.fillRect((j.cell[0] + 0.3) * cs, (j.cell[1] + 0.3) * cs, cs * 0.4, cs * 0.4);
    }
    // player arrow
    const px = (player.x / S + 0.5) * cs, pz = (player.z / S + 0.5) * cs;
    mm.save(); mm.translate(px, pz); mm.rotate(-player.yaw);
    mm.fillStyle = '#fff'; mm.beginPath();
    mm.moveTo(0, -cs * 0.7); mm.lineTo(cs * 0.45, cs * 0.45); mm.lineTo(-cs * 0.45, cs * 0.45); mm.closePath(); mm.fill();
    mm.restore();
  }

  function revealAround() {
    const cx = cellOf(player.x), cz = cellOf(player.z), R = 3;
    for (let dz = -R; dz <= R; dz++) for (let dx = -R; dx <= R; dx++) {
      const x = cx + dx, z = cz + dz;
      if (x < 0 || z < 0 || x >= GW || z >= GH) continue;
      if (lineOfSight(player.x, player.z, x * S - Math.sign(dx) * S * 0.45, z * S - Math.sign(dz) * S * 0.45)) revealed.add(z * GW + x);
    }
  }

  // ---------- leaderboard (server if available, else localStorage) ----------
  const LOCAL_KEY = 'the-mummy-scores';
  function localScores() { try { return JSON.parse(localStorage.getItem(LOCAL_KEY)) || []; } catch (e) { return []; } }
  function saveLocal(entry) {
    try {
      const list = localScores().concat(entry).sort((a, b) => b.score - a.score).slice(0, 10);
      localStorage.setItem(LOCAL_KEY, JSON.stringify(list));
      return list;
    } catch (e) { return [entry]; }
  }
  async function fetchScores() {
    try {
      const r = await fetch('/api/scores', { cache: 'no-store' });
      if (r.ok) return await r.json();
    } catch (e) { /* no server: fall through */ }
    return localScores();
  }
  async function submitScore(entry) {
    try {
      const r = await fetch('/api/scores', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(entry) });
      if (r.ok) return (await r.json()).top;
    } catch (e) { /* no server */ }
    return saveLocal(entry);
  }
  function renderScores(el, list) {
    el.innerHTML = '';
    if (!list.length) { el.innerHTML = '<li class="empty">No explorers yet. Be the first.</li>'; return; }
    for (const s of list) {
      const li = document.createElement('li');
      li.textContent = `${s.name} (lvl ${s.level})`;
      const sp = document.createElement('span'); sp.textContent = s.score; li.appendChild(sp);
      el.appendChild(li);
    }
  }

  // ---------- flow ----------
  function lockPointer() { if (canvas.requestPointerLock) canvas.requestPointerLock(); }

  function startGame() {
    audio();
    level = 1; score = 0; totalTime = 0; player.health = MAX_HEALTH;
    buildLevel();
    state = 'playing';
    show(null); ui.hud.classList.remove('hidden');
    lockPointer();
  }

  function completeLevel() {
    const par = 60 + level * 30;
    const timeBonus = Math.max(0, Math.round((par - levelTime) * 5));
    const bonus = 500 * level + timeBonus;
    score += bonus;
    player.health = Math.min(MAX_HEALTH, player.health + 30);
    sfx.open();
    state = 'levelDone';
    if (document.exitPointerLock) document.exitPointerLock();
    ui.levelSummary.textContent = `Level ${level} cleared in ${fmtTime(levelTime)}. Escape bonus ${500 * level}, time bonus ${timeBonus}. Score: ${score}. You regain some strength.`;
    show(ui.levelDone);
  }

  async function gameOver() {
    state = 'over';
    if (document.exitPointerLock) document.exitPointerLock();
    ui.finalSummary.textContent = `The mummies claimed you on level ${level} after ${fmtTime(totalTime)}. Final score: ${score}.`;
    show(ui.over);
    const name = (ui.name.value.trim() || 'Nameless').replace(/[^\w .\-]/g, '').slice(0, 20) || 'Nameless';
    renderScores(ui.scoresOver, await submitScore({ name, score, level }));
  }

  $('start').addEventListener('click', startGame);
  ui.name.addEventListener('keydown', (e) => { if (e.key === 'Enter') startGame(); });
  $('resume').addEventListener('click', () => { state = 'playing'; show(null); lockPointer(); });
  ui.pause.addEventListener('click', (e) => { if (e.target === ui.pause) { state = 'playing'; show(null); lockPointer(); } });
  $('next-level').addEventListener('click', () => { level++; buildLevel(); state = 'playing'; show(null); lockPointer(); });
  $('restart').addEventListener('click', startGame);
  canvas.addEventListener('click', () => { if (state === 'playing' && document.pointerLockElement !== canvas) lockPointer(); });

  document.addEventListener('pointerlockchange', () => {
    if (document.pointerLockElement !== canvas && state === 'playing') { state = 'paused'; show(ui.pause); }
  });
  document.addEventListener('mousemove', (e) => {
    if (state !== 'playing' || document.pointerLockElement !== canvas) return;
    player.yaw -= e.movementX * 0.0022;
    player.pitch = Math.max(-1.2, Math.min(1.2, player.pitch - e.movementY * 0.0022));
  });
  document.addEventListener('keydown', (e) => {
    keys[e.code] = true;
    if (e.code === 'KeyP' && state === 'playing') { state = 'paused'; if (document.exitPointerLock) document.exitPointerLock(); show(ui.pause); }
  });
  document.addEventListener('keyup', (e) => { keys[e.code] = false; });
  window.addEventListener('blur', () => { for (const k in keys) keys[k] = false; });

  // ---------- update ----------
  function hurt(amount, fromX, fromZ) {
    player.health -= amount;
    sfx.hurt();
    ui.damage.classList.add('hit');
    setTimeout(() => ui.damage.classList.remove('hit'), 60);
    const dx = player.x - fromX, dz = player.z - fromZ, d = Math.hypot(dx, dz) || 1;
    player.knock.x = (dx / d) * 9; player.knock.z = (dz / d) * 9;
    if (player.health <= 0) gameOver();
  }

  function moveWithCollision(obj, dx, dz, r) {
    if (!blocked(obj.x + dx, obj.z, r)) obj.x += dx;
    if (!blocked(obj.x, obj.z + dz, r)) obj.z += dz;
  }

  function updatePlayer(dt) {
    let fx = 0, fz = 0;
    if (keys.KeyW || keys.ArrowUp) fz -= 1;
    if (keys.KeyS || keys.ArrowDown) fz += 1;
    if (keys.KeyA || keys.ArrowLeft) fx -= 1;
    if (keys.KeyD || keys.ArrowRight) fx += 1;
    const moving = fx || fz;
    const sprinting = moving && (keys.ShiftLeft || keys.ShiftRight) && player.stamina > 1;
    player.stamina = Math.max(0, Math.min(100, player.stamina + (sprinting ? -32 : 16) * dt));
    if (moving) {
      const len = Math.hypot(fx, fz); fx /= len; fz /= len;
      const sin = Math.sin(player.yaw), cos = Math.cos(player.yaw);
      const speed = sprinting ? SPRINT : WALK;
      const wx = (fx * cos + fz * sin) * speed * dt, wz = (-fx * sin + fz * cos) * speed * dt;
      moveWithCollision(player, wx, wz, PLAYER_R);
      player.bob += dt * (sprinting ? 13 : 9);
      player.stepT -= dt;
      if (player.stepT <= 0) { sfx.step(); player.stepT = sprinting ? 0.3 : 0.45; }
    }
    // knockback decays
    if (player.knock.x || player.knock.z) {
      moveWithCollision(player, player.knock.x * dt, player.knock.z * dt, PLAYER_R);
      player.knock.x *= Math.pow(0.02, dt); player.knock.z *= Math.pow(0.02, dt);
      if (Math.hypot(player.knock.x, player.knock.z) < 0.1) player.knock = { x: 0, z: 0 };
    }

    // torch
    player.oil = Math.max(0, player.oil - dt * (1.5 + level * 0.1));
    const f = player.oil / 100;
    const flicker = 0.9 + 0.1 * Math.sin(performance.now() * 0.023) * Math.sin(performance.now() * 0.0071);
    torch.intensity = (0.35 + 1.4 * f) * flicker;
    torch.distance = 4 + 15 * f;
    scene.fog.density = 0.16 - 0.08 * f;

    camera.position.set(player.x, EYE_H + Math.sin(player.bob) * 0.06, player.z);
    camera.rotation.set(player.pitch, player.yaw, 0);

    // pickups
    for (let i = scarabs.length - 1; i >= 0; i--) {
      const s = scarabs[i];
      if (Math.hypot(s.mesh.position.x - player.x, s.mesh.position.z - player.z) < 1.1) {
        levelGroup.remove(s.mesh); scarabs.splice(i, 1); score += 100; sfx.scarab();
        if (scarabs.length) showMessage(`Scarab found. ${scarabs.length} remain`, 1.8);
        else { showMessage('The sealed door grinds open!', 3); door.portal.material = mat.doorOpen; door.glow.material = glowMat(0x40e0c0); sfx.open(); }
      }
    }
    for (let i = jars.length - 1; i >= 0; i--) {
      const j = jars[i];
      if (Math.hypot(j.mesh.position.x - player.x, j.mesh.position.z - player.z) < 1.1) {
        levelGroup.remove(j.mesh); jars.splice(i, 1); player.oil = Math.min(100, player.oil + 50); score += 25; sfx.oil();
        showMessage('Torch refilled', 1.5);
      }
    }
    // exit door
    const dd = Math.hypot(exitCell[0] * S - player.x, exitCell[1] * S - player.z);
    sealedMsgCooldown -= dt;
    if (dd < 1.4) {
      if (!scarabs.length) completeLevel();
      else if (sealedMsgCooldown <= 0) { showMessage(`The door is sealed. ${scarabs.length} scarab${scarabs.length > 1 ? 's' : ''} remain`, 2); sealedMsgCooldown = 3; }
    }
  }

  function updateMummies(dt, t) {
    const sight = 6 + 12 * (player.oil / 100);
    let nearestChase = Infinity;
    for (const m of mummies) {
      const dx = player.x - m.x, dz = player.z - m.z, dist = Math.hypot(dx, dz);
      const sees = dist < sight && lineOfSight(m.x, m.z, player.x, player.z);
      const mc = [cellOf(m.x), cellOf(m.z)];
      const pc = [cellOf(player.x), cellOf(player.z)];
      if (sees) { m.state = 'chase'; m.lastSeen = pc; }
      m.repath -= dt; m.cooldown -= dt;

      let tx, tz, speed;
      if (m.state === 'chase') {
        speed = m.speedChase;
        nearestChase = Math.min(nearestChase, dist);
        if (sees && dist < 2.6) { tx = player.x; tz = player.z; }
        else {
          if (m.repath <= 0 || !m.path.length) { m.path = path(mc[0], mc[1], m.lastSeen[0], m.lastSeen[1]); m.repath = 0.4; }
          if (m.path.length && m.path[0][0] === mc[0] && m.path[0][1] === mc[1] &&
              Math.hypot(m.path[0][0] * S - m.x, m.path[0][1] * S - m.z) < 0.3) m.path.shift();
          if (m.path.length) { tx = m.path[0][0] * S; tz = m.path[0][1] * S; }
          else if (sees) { tx = player.x; tz = player.z; }
          else { m.state = 'wander'; m.target = null; } // reached last known spot, lost the trail
        }
      }
      if (m.state === 'wander') {
        speed = m.speedWander;
        if (!m.target || Math.hypot(m.target[0] * S - m.x, m.target[1] * S - m.z) < 0.2) {
          const opts = [[1, 0], [-1, 0], [0, 1], [0, -1]].map(([ox, oz]) => [mc[0] + ox, mc[1] + oz])
            .filter(([x, z]) => !isWall(x, z));
          const fresh = opts.filter((c) => !m.prevCell || c[0] !== m.prevCell[0] || c[1] !== m.prevCell[1]);
          const pick = (fresh.length ? fresh : opts);
          m.prevCell = mc;
          m.target = pick[Math.floor(Math.random() * pick.length)] || mc;
        }
        tx = m.target[0] * S; tz = m.target[1] * S;
      }

      if (tx !== undefined) {
        const mx = tx - m.x, mz = tz - m.z, md = Math.hypot(mx, mz);
        if (md > 0.01) {
          const step = Math.min(md, speed * dt);
          moveWithCollision(m, (mx / md) * step, (mz / md) * step, 0.45);
          const targetRot = Math.atan2(-mx, -mz);
          let diff = targetRot - m.group.rotation.y;
          diff = Math.atan2(Math.sin(diff), Math.cos(diff));
          m.group.rotation.y += diff * Math.min(1, dt * 6);
        }
      }

      // shambling animation
      const sp = m.state === 'chase' ? 7 : 4;
      m.phase += dt * sp;
      m.legs[0].rotation.x = Math.sin(m.phase) * 0.45;
      m.legs[1].rotation.x = -Math.sin(m.phase) * 0.45;
      m.arms[0].rotation.x = Math.PI / 2.2 + Math.sin(m.phase * 0.5) * 0.12;
      m.arms[1].rotation.x = Math.PI / 2.2 - Math.sin(m.phase * 0.5) * 0.12;
      m.group.rotation.z = Math.sin(m.phase * 0.5) * 0.06;
      m.strip.rotation.z = 0.3 + Math.sin(t * 3 + m.phase) * 0.25;
      m.group.position.set(m.x, Math.abs(Math.sin(m.phase)) * 0.05, m.z);

      if (dist < 1.35 && m.cooldown <= 0 && state === 'playing') { m.cooldown = 1.2; hurt(18 + level * 2, m.x, m.z); }
    }
    groanTimer -= dt;
    if (nearestChase < 14 && groanTimer <= 0) { sfx.groan(1 - nearestChase / 14); groanTimer = 2 + Math.random() * 3; }
  }

  function updateProps(dt, t) {
    for (const s of scarabs) {
      s.mesh.rotation.y += dt * 1.5;
      s.mesh.position.y = 0.9 + Math.sin(t * 2 + s.phase) * 0.12;
    }
    for (const j of jars) j.mesh.children[1].material.opacity = 0.6 + Math.sin(t * 4) * 0.2;
    for (const s of sconces) {
      const k = 0.85 + 0.15 * Math.sin(t * 13 + s.phase) * Math.sin(t * 7.3 + s.phase * 2);
      s.flame.scale.set(0.7 * k, 1.0 * k, 1);
    }
    if (door) door.glow.material.opacity = 0.55 + Math.sin(t * 2.5) * 0.2;
  }

  // ---------- loop ----------
  let last = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    const t = now / 1000;
    if (state === 'playing') {
      levelTime += dt; totalTime += dt;
      updatePlayer(dt);
      if (state === 'playing') updateMummies(dt, t);
      revealTimer -= dt;
      if (revealTimer <= 0) { revealAround(); revealTimer = 0.15; }
      hudTimer -= dt;
      if (hudTimer <= 0) { updateHud(); drawMinimap(); hudTimer = 0.1; }
      if (msgTimer > 0) { msgTimer -= dt; if (msgTimer <= 0) ui.message.classList.remove('show'); }
    }
    if (levelGroup) updateProps(dt, t);
    renderer.render(scene, camera);
  }

  // menu backdrop: a slow orbit through a demo maze
  level = 1; buildLevel(); ui.message.classList.remove('show');
  camera.position.set(S, EYE_H, S);
  fetchScores().then((list) => renderScores(ui.scoresMenu, list));
  requestAnimationFrame(frame);
  (function menuCam() {
    if (state !== 'menu') return;
    player.yaw += 0.003;
    camera.position.set(player.x, EYE_H, player.z);
    camera.rotation.set(0, player.yaw, 0);
    torch.intensity = 1.4; torch.distance = 16;
    requestAnimationFrame(menuCam);
  })();

  // test hook (used by automated checks; harmless in play)
  window.__mummy = {
    get state() { return state; }, get level() { return level; }, get score() { return score; },
    get player() { return player; }, get mummies() { return mummies.length; }, get scarabs() { return scarabs.length; },
    start: () => { startGame(); }, // pointer lock is optional for the hook
    forceState: (s) => { state = s; show(null); },
    collectAll: () => { for (const s of scarabs.slice()) { player.x = s.mesh.position.x; player.z = s.mesh.position.z; updatePlayer(0.001); } },
    nearMummy: () => { const m = mummies[0]; player.x = m.x; player.z = m.z; for (const [dx, dz] of [[2, 0], [-2, 0], [0, 2], [0, -2]]) if (!blocked(m.x + dx, m.z + dz, PLAYER_R)) { player.x = m.x + dx; player.z = m.z + dz; player.yaw = Math.atan2(dx, dz); break; } },
    goToExit: () => { player.x = exitCell[0] * S; player.z = exitCell[1] * S; },
  };
})();
