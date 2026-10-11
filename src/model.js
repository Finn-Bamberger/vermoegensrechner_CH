function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeNormals(n, seed) {
  const rnd = mulberry32(seed);
  const z = new Float32Array(n);
  for (let i = 0; i < n; i += 2) {
    let u = rnd(); const v = rnd();
    if (u < 1e-12) u = 1e-12;
    const r = Math.sqrt(-2 * Math.log(u));
    const a = 2 * Math.PI * v;
    z[i] = r * Math.cos(a);
    if (i + 1 < n) z[i + 1] = r * Math.sin(a);
  }
  return z;
}

// Bausteine: A = Startkapital (frei), Bf = 1 CHF/Monat frei, B3 = 1 CHF/Monat in 3a,
// Cf = Steuerersparnis (1 CHF pro Monat 3a-Einzahlung, Jahresende) im freien Depot.
// Das Endvermögen ist linear in den Sparbeträgen, deshalb genügt eine Simulation.
function simulate(p, z) {
  const n = p.nSim, M = p.jahre * 12, dt = 1 / 12, sig = p.vola * Math.sqrt(dt);
  const muF = (p.rendite - p.gebFrei - p.drag - 0.5 * p.vola * p.vola) * dt;
  const mu3 = (p.rendite - p.geb3 - 0.5 * p.vola * p.vola) * dt;
  const eF = Math.exp(muF), e3 = Math.exp(mu3);
  const A = new Float64Array(n).fill(p.start);
  const Bf = new Float64Array(n), B3 = new Float64Array(n), Cf = new Float64Array(n);
  const sim = { A: [A.slice()], Bf: [Bf.slice()], B3: [B3.slice()], Cf: [Cf.slice()], n };
  for (let m = 0; m < M; m++) {
    const idx = p.indexiert ? Math.pow(1 + p.infl, Math.floor(m / 12)) : 1;
    const off = m * n;
    for (let i = 0; i < n; i++) {
      const e = Math.exp(sig * z[off + i]);
      const gF = eF * e, g3 = e3 * e;
      A[i] *= gF;
      Bf[i] = (Bf[i] + idx) * gF;
      B3[i] = (B3[i] + idx) * g3;
      Cf[i] *= gF;
    }
    if ((m + 1) % 12 === 0) {
      for (let i = 0; i < n; i++) Cf[i] += 12 * idx;
      sim.A.push(A.slice()); sim.Bf.push(Bf.slice()); sim.B3.push(B3.slice()); sim.Cf.push(Cf.slice());
    }
  }
  return sim;
}

// Vermögen nach Steuern in heutigen Franken zum Zeitpunkt k (Jahre)
function wealthAt(sim, k, s, mit3a, p, out) {
  const defl = Math.pow(1 + p.infl, -k);
  const x = mit3a ? Math.min(s, p.max3a / 12) : 0;
  const A = sim.A[k], Bf = sim.Bf[k], B3 = sim.B3[k], Cf = sim.Cf[k];
  const tg = p.tg, nb = 1 - p.bezug;
  for (let i = 0; i < sim.n; i++) {
    let w = A[i] + (s - x) * Bf[i];
    if (mit3a) w += tg * x * Cf[i] + nb * x * B3[i];
    out[i] = w * defl;
  }
}

function q(sorted, pr) {
  const pos = (sorted.length - 1) * pr;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

let scratch = null;
function pZiel(sim, s, mit3a, p) {
  if (!scratch || scratch.length !== sim.n) scratch = new Float64Array(sim.n);
  wealthAt(sim, p.jahre, s, mit3a, p, scratch);
  let c = 0;
  for (let i = 0; i < sim.n; i++) if (scratch[i] >= p.ziel) c++;
  return c / sim.n;
}

function needed(sim, p, mit3a, target) {
  if (pZiel(sim, 0, mit3a, p) >= target) return 0;
  let lo = 0, hi = 1e6;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (pZiel(sim, mid, mit3a, p) >= target) hi = mid; else lo = mid;
  }
  return hi;
}
