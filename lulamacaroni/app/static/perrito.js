/* The puppy (Lore's art). Loaded only on the visits when it plays; see PERRITO_JS in views.py.
 *
 * A dog pillow sits next to "Hola, Lore". The puppy pops its head in from the right edge of the
 * screen, tilts its head at Lore, ducks back out, then walks in across the page to the pillow,
 * sniffs it, turns around on it twice the way dogs do before settling, then lies down facing
 * forward and stays there, breathing slowly.
 *
 * The head is Lore's original cut-out, shown unchanged (scaled evenly, never mirrored, cropped,
 * stretched or redrawn). The body, legs, paws and pillow are drawn to match the art (red ribbed
 * sweater, cream curly fur, ochre pillow). The walk is a dog's lateral-sequence walk (left hind,
 * left fore, right hind, right fore) with planted paws that don't slide.
 * Decoration only: pointer-events none, aria-hidden.
 */
(function () {
  "use strict";
  var W = window, D = document, NS = "http://www.w3.org/2000/svg";
  var IMG = "/perrito.png", RATIO = 1136 / 1246; // the trimmed artwork's height / width

  function el(tag, attrs, parent) {
    var e = D.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function suave(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
  function frac(v) { return v - Math.floor(v); }

  // ---- where: the pillow goes right after the greeting ----------------------------------------
  var h1 = D.querySelector("main h1");
  if (!h1) return;
  var rango = D.createRange(); rango.selectNodeContents(h1);
  var texto = rango.getBoundingClientRect(), sx = W.scrollX, sy = W.scrollY;
  var ancho = D.documentElement.clientWidth;
  var borde = sx + ancho;                             // the right edge of the screen: it comes in there

  var wpx = Math.round(clamp(ancho * 0.09, 96, 128)); // dog drawing width (walking, side view)
  var VB_W = 200, VB_H = 140, SUELO = 132, u = wpx / VB_W, hpx = wpx * VB_H / VB_W;
  var almW = Math.round(wpx * 0.82), almH = Math.round(almW * 0.34);
  var almX = Math.round(texto.right + sx + 22), almCx = almX + almW / 2;
  var piso = Math.round(texto.bottom + sy - 2);      // the pillow's top surface, level with the text
  if (almX + almW > sx + ancho - 8) return;          // no room next to the name: skip quietly

  // ---- the pillow (two layers: the dog lies between them) -------------------------------------
  var OCRE = "#CC842E", OCRE_CLARO = "#E2A85E", OCRE_OSCURO = "#9A5C1C", CEREZA = "#9C0F0C";
  function capa(z, id) {
    var d = D.createElement("div");
    d.className = "perrito"; d.setAttribute("aria-hidden", "true");
    d.style.cssText = "position:absolute;left:" + almX + "px;top:" + (piso - almH * 0.45) + "px;width:" +
      almW + "px;z-index:" + z;
    var s = el("svg", { viewBox: "0 0 100 34", width: almW, height: almH });
    s.style.display = "block"; s.style.overflow = "visible";
    d.appendChild(s);
    var f = el("filter", { id: id, x: "-5%", y: "-20%", width: "110%", height: "140%" }, el("defs", {}, s));
    el("feTurbulence", { type: "fractalNoise", baseFrequency: "1.1", numOctaves: "2", seed: "7", result: "n" }, f);
    el("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: "1.8", xChannelSelector: "R", yChannelSelector: "G" }, f);
    return { div: d, g: el("g", { filter: "url(#" + id + ")" }, s) };
  }
  var fondo = capa(18, "pf-cojin"), frente = capa(19, "pf-cojin2");
  el("ellipse", { cx: 50, cy: 20, rx: 49, ry: 13, fill: OCRE_OSCURO }, fondo.g);   // side
  el("ellipse", { cx: 50, cy: 15, rx: 47, ry: 11, fill: OCRE }, fondo.g);          // rim
  el("ellipse", { cx: 50, cy: 15, rx: 34, ry: 6.5, fill: OCRE_CLARO }, fondo.g);   // the dip
  // the front lip of the rim, drawn over the dog's tummy, with cherry piping
  el("path", { d: "M3 16 C 10 31, 90 31, 97 16 C 97 22, 92 33, 50 33 C 8 33, 3 22, 3 16 Z", fill: OCRE_OSCURO }, frente.g);
  el("path", { d: "M3 15 C 12 27, 88 27, 97 15", fill: "none", stroke: OCRE, "stroke-width": 7, "stroke-linecap": "round" }, frente.g);
  el("path", { d: "M5 17.5 C 14 29, 86 29, 95 17.5", fill: "none", stroke: CEREZA, "stroke-width": 1.2, "stroke-dasharray": "3 2" }, frente.g);

  // ---- the dog -------------------------------------------------------------------------------
  // Leg bones (drawing units), in proportion to the head (74 wide).
  // Front: shoulder joint → humerus → elbow (points back) → forearm → wrist/carpus → pastern → paw.
  // Hind: hip → femur → stifle/knee (points forward) → tibia → hock (points back) → metatarsus → paw.
  var DEL = { a: 21, b: 18, c: 7 }, TRAS = { a: 19, b: 19, c: 13 };
  var HOMBRO = { x: 124, y: 88 }, CADERA = { x: 70, y: 88 }, CENTRO = 100, CABEZA_X = 140;
  var FUR = "#F4E8CC", FUR_LEJOS = "#DCCAA3", FUR_LINEA = "#CDB98F";
  var SUETER = "#7E1D23", SUETER_LEJOS = "#62151A", RIBETE = "#661419";
  // Lateral-sequence walk: each paw touches down a quarter stride after the one before.
  var PASO = { LH: 0, LF: 0.25, RH: 0.5, RF: 0.75, apoyo: 0.62 };

  var caja = D.createElement("div");
  caja.className = "perrito"; caja.setAttribute("aria-hidden", "true");
  caja.style.cssText = "position:absolute;width:" + wpx + "px;transform-origin:50% 100%";
  // a strip as wide as the screen that hides whatever is past its edge, so the dog can peek in
  // from off-screen without making the page scroll sideways
  var escena = D.createElement("div");
  escena.className = "perrito"; escena.setAttribute("aria-hidden", "true");
  escena.appendChild(caja);
  var svg = el("svg", { viewBox: "0 0 " + VB_W + " " + VB_H, width: wpx, height: hpx });
  svg.style.display = "block"; svg.style.overflow = "visible";
  caja.appendChild(svg);

  var defs = el("defs", {}, svg);
  var fz = el("filter", { id: "pf-fuzz", x: "-10%", y: "-10%", width: "120%", height: "120%" }, defs);
  el("feTurbulence", { type: "fractalNoise", baseFrequency: "0.9", numOctaves: "2", seed: "3", result: "n" }, fz);
  el("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: "3.2", xChannelSelector: "R", yChannelSelector: "G" }, fz);
  var pat = el("pattern", { id: "pf-rib", width: "4", height: "8", patternUnits: "userSpaceOnUse" }, defs);
  el("rect", { width: "4", height: "8", fill: SUETER }, pat);
  el("rect", { width: "1.3", height: "8", fill: RIBETE }, pat);
  // light from above and in front: a soft highlight on the back, shade under the belly
  var vol = el("linearGradient", { id: "pf-vol", x1: "0", y1: "0", x2: "0", y2: "1" }, defs);
  el("stop", { offset: "0", "stop-color": "#fff", "stop-opacity": "0.22" }, vol);
  el("stop", { offset: "0.45", "stop-color": "#fff", "stop-opacity": "0" }, vol);
  el("stop", { offset: "1", "stop-color": "#2a0806", "stop-opacity": "0.38" }, vol);
  var anca = el("radialGradient", { id: "pf-anca", cx: "0.4", cy: "0.3", r: "0.75" }, defs);
  el("stop", { offset: "0", "stop-color": "#FFF6E2" }, anca);
  el("stop", { offset: "0.6", "stop-color": FUR }, anca);
  el("stop", { offset: "1", "stop-color": FUR_LEJOS }, anca);
  var bl = el("filter", { id: "pf-sombra", x: "-30%", y: "-200%", width: "160%", height: "500%" }, defs);
  el("feGaussianBlur", { stdDeviation: "2.6" }, bl);
  // contact shadow on the ground: it follows the body, never flips
  var sombra = el("ellipse", { fill: "#3b2410", opacity: "0.28", filter: "url(#pf-sombra)" }, svg);

  var cuerpo = el("g", {}, svg);                      // flips and folds; the head never does
  var g = el("g", { filter: "url(#pf-fuzz)" }, cuerpo);
  function hueso(gr, color, ancho) {
    return el("path", { stroke: color, "stroke-width": ancho, "stroke-linecap": "round", "stroke-linejoin": "round", fill: "none" }, gr);
  }
  function pata(color, manga) {
    var gr = el("g", {}, g), del = !!manga;
    return {
      sup: hueso(gr, manga || color, del ? 17 : 18),   // humerus in its sleeve / the thigh (femur)
      med: hueso(gr, color, del ? 13 : 12),             // forearm / shank (tibia)
      inf: hueso(gr, color, del ? 10 : 8.5),                       // pastern / metatarsus below the wrist or hock
      pie: el("ellipse", { rx: 7, ry: 4.4, fill: color, stroke: FUR_LINEA, "stroke-width": 0.8 }, gr),
    };
  }
  var P = {};
  P.LH = pata(FUR_LEJOS); P.LF = pata(FUR_LEJOS, SUETER_LEJOS);
  var cola = el("g", {}, g);
  [[0, 0, 9], [-6, -6, 7], [3, -9, 6.5], [-2, 5, 6]].forEach(function (b) {
    el("circle", { cx: b[0], cy: b[1], r: b[2], fill: FUR, stroke: FUR_LINEA, "stroke-width": 0.8 }, cola);
  });
  var ancas = el("ellipse", { rx: 19, ry: 17, fill: "url(#pf-anca)", stroke: FUR_LINEA, "stroke-width": 0.8 }, g);
  var torso = el("path", { fill: "url(#pf-rib)", stroke: RIBETE, "stroke-width": 1 }, g);
  var torsoLuz = el("path", { fill: "url(#pf-vol)" }, g);   // roundness: same outline, shaded
  P.RH = pata(FUR); P.RF = pata(FUR, SUETER);

  var cabeza = el("g", {}, svg);
  var hw = 74, hh = hw * RATIO;
  var im = el("image", { width: hw, height: hh, x: -hw / 2, y: -hh + 14, preserveAspectRatio: "xMidYMid meet" }, cabeza);
  im.setAttributeNS("http://www.w3.org/1999/xlink", "href", IMG);
  im.setAttribute("href", IMG);
  var manos = el("g", { filter: "url(#pf-fuzz)", opacity: 0 }, svg);   // front paws, in front of the chest when lying
  [-13, 13].forEach(function (dx) {
    el("ellipse", { cx: CABEZA_X + dx, cy: 0, rx: 10, ry: 6.5, fill: FUR, stroke: FUR_LINEA, "stroke-width": 0.8 }, manos);
  });

  // Two bones from (ax, ay) to (fx, fy); the middle joint points back (+1) or forward (-1).
  function ik(ax, ay, fx, fy, A, B, dobla) {
    var dx = fx - ax, dy = fy - ay, d = Math.sqrt(dx * dx + dy * dy) || 0.01, max = A + B - 0.01;
    if (d > max) { fx = ax + dx / d * max; fy = ay + dy / d * max; dx = fx - ax; dy = fy - ay; d = max; }
    var a = (A * A - B * B + d * d) / (2 * d), h = Math.sqrt(Math.max(0, A * A - a * a));
    var mx = ax + dx * a / d, my = ay + dy * a / d;
    return { kx: mx - dobla * h * dy / d, ky: my + dobla * h * dx / d, fx: fx, fy: fy };
  }
  function linea(path, x1, y1, x2, y2) { path.setAttribute("d", "M" + x1 + " " + y1 + "L" + x2 + " " + y2); }
  var RAD = Math.PI / 180;

  // Smooth looping curve through keyframes [[phase, value], ...] (Catmull-Rom, phase 0..1).
  function curva(K, p) {
    var n = K.length, i = n - 1;
    for (var j = 0; j < n; j++) if (K[j][0] > p) { i = (j + n - 1) % n; break; }
    var a = K[i][0], b2 = i + 1 < n ? K[i + 1][0] : K[0][0] + 1, q = p < a ? p + 1 : p;
    var f = (q - a) / (b2 - a);
    var p0 = K[(i + n - 1) % n][1], p1 = K[i][1], p2 = K[(i + 1) % n][1], p3 = K[(i + 2) % n][1];
    return 0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (3 * p1 - p0 - 3 * p2 + p3) * f * f * f);
  }
  // Angle of the lowest bone over one stride, from touchdown (0) through toe-off (PASO.apoyo) and
  // the swing, in degrees from straight down (positive = paw ahead of the joint). Shapes follow
  // published walking kinematics of dogs: the carpus extends a little under load, folds hard
  // (about 90°) just after the paw leaves the ground, then opens to reach; the hock yields at
  // touchdown, extends to push off, flexes through early swing and opens before landing.
  var ANG_DEL = [[0, 6], [0.3, 14], [0.55, 4], [0.62, -16], [0.72, -92], [0.84, -42], [0.94, 12]];
  var ANG_TRAS = [[0, 18], [0.15, 27], [0.45, 14], [0.62, -6], [0.75, -44], [0.88, 4], [0.96, 22]];

  // One frame of the body. fase: stride phase; sweep: how far a planted paw travels (units);
  // eT / eD: hind and front ends lowered, 0 standing .. 1 lying (a dog sits first, then walks its
  // front paws out); giro: facing, -1..1 (side-on at ±1, seen end-on near 0); quieto: 0 walking
  // .. 1 standing square; baja: head lowered to sniff. Returns where the head sits.
  function postura(fase, sweep, eT, eD, giro, quieto, baja) {
    var echado = (eT + eD) / 2, b = PASO.apoyo, carga = {}, golpe = 0;
    ["LH", "RH", "LF", "RF"].forEach(function (k) {
      var pp = frac(fase - PASO[k]);
      carga[k] = pp < b ? Math.sin(Math.PI * pp / b) : 0;
      if (k.charAt(1) === "F" && pp < 0.22) golpe += Math.sin(Math.PI * pp / 0.22);   // front paw lands
    });
    var anda = 1 - quieto;
    // each girdle vaults over its planted legs (highest at mid-stance), as in a real walk
    var subeD = -1.3 * (carga.LF + carga.RF - 0.64) * anda, subeT = -1.3 * (carga.LH + carga.RH - 0.64) * anda;
    var hom = { x: HOMBRO.x, y: HOMBRO.y + subeD * (1 - eD) + 22 * eD };
    var cad = { x: CADERA.x, y: CADERA.y + subeT * (1 - eT) + 22 * eT };
    ["LH", "RH", "LF", "RF"].forEach(function (k) {
      var tr = k.charAt(1) === "H", L = tr ? TRAS : DEL, pp = frac(fase - PASO[k]), e = tr ? eT : eD;
      var raiz = tr ? { x: cad.x + 2, y: cad.y - 4 } : { x: hom.x + 2, y: hom.y - 4 };
      // the far-side legs stand on a farther line of the ground, so they sit a little higher;
      // seen end-on (turning) the two sides spread further apart
      var lejos = k.charAt(0) === "L" ? (3 + 7 * (1 - Math.abs(giro))) * (1 - e) : 0;
      raiz.y -= lejos;
      var px, py, ang = curva(tr ? ANG_TRAS : ANG_DEL, pp);
      if (pp < b) {      // stance: paw planted, the body passes over it
        px = raiz.x + sweep / 2 - sweep * pp / b; py = SUELO;
      } else {           // swing: lift (front paws higher than hind), and reach forward
        var q = (pp - b) / (1 - b), av = q - Math.sin(2 * Math.PI * q) / (2 * Math.PI);
        px = raiz.x - sweep / 2 + sweep * av;
        py = SUELO - (tr ? 8 : 11) * Math.sin(Math.PI * Math.pow(q, tr ? 0.85 : 0.75));
      }
      // standing still: every paw under its joint
      px = lerp(px, raiz.x + (tr ? 1 : 0), quieto); py = lerp(py, SUELO, quieto); ang = lerp(ang, tr ? 20 : 6, quieto);
      py -= lejos;
      // lying down: hind legs folded under (hocks flat on the bed), front legs stretched forward
      px = lerp(px, tr ? raiz.x + 12 : raiz.x + 20, e); py = lerp(py, SUELO - 2, e);
      ang = lerp(ang, tr ? 80 : 85, e);
      var jx = px - L.c * Math.sin(ang * RAD), jy = py - L.c * Math.cos(ang * RAD);   // wrist or hock
      var s = ik(raiz.x, raiz.y, jx, jy, L.a, L.b, tr ? -1 : 1), leg = P[k];
      linea(leg.sup, raiz.x, raiz.y, s.kx, s.ky);    // humerus / femur
      linea(leg.med, s.kx, s.ky, s.fx, s.fy);        // forearm / tibia
      linea(leg.inf, s.fx, s.fy, px, py);            // pastern / metatarsus
      leg.pie.setAttribute("cx", px + 3); leg.pie.setAttribute("cy", py - 1);
    });
    var top = Math.min(hom.y, cad.y) - 32;
    torso.setAttribute("d",
      "M" + (cad.x - 14) + " " + (cad.y + 2) +
      "C" + (cad.x - 16) + " " + (cad.y - 22) + " " + (cad.x + 10) + " " + (cad.y - 32) + " " + ((cad.x + hom.x) / 2) + " " + top +
      "C" + (hom.x - 6) + " " + (hom.y - 32) + " " + (hom.x + 30) + " " + (hom.y - 30) + " " + (hom.x + 30) + " " + (hom.y + 4) +
      "C" + (hom.x + 28) + " " + (hom.y + 16) + " " + (cad.x - 4) + " " + (cad.y + 16) + " " + (cad.x - 14) + " " + (cad.y + 2) + "Z");
    torsoLuz.setAttribute("d", torso.getAttribute("d"));
    ancas.setAttribute("cx", cad.x - 2); ancas.setAttribute("cy", cad.y - 6);
    cola.setAttribute("transform", "translate(" + (cad.x - 16) + " " + (cad.y - 22) + ") rotate(" +
      (Math.sin(2 * Math.PI * fase * 1.5) * 16 * (1 - eT * 0.7)) + ")");
    // facing: squeeze the body around the head's line so it turns behind the head
    var piv = lerp(CENTRO, CABEZA_X, eD);
    cuerpo.setAttribute("transform", "translate(" + piv + " 0) scale(" + giro + " 1) translate(" + (-piv) + " 0)");
    var ag = Math.abs(giro), mitad = piv + giro * (CENTRO - piv);
    sombra.setAttribute("cx", lerp(mitad, piv + giro * (CABEZA_X - 18 - piv), echado));
    sombra.setAttribute("cy", SUELO + 1 - 2 * (1 - ag) * (1 - echado));
    sombra.setAttribute("rx", lerp(30 + 22 * ag, 46, echado) * (1 - 0.03 * (subeD + subeT)));
    sombra.setAttribute("ry", lerp(4 + 6 * (1 - ag), 7, echado));
    // the head dips as each front paw takes the weight (the nod vets watch for), and drops to sniff
    var nod = golpe * anda * (1 - eD), dir = giro < 0 ? -1 : 1;
    return {
      x: piv + giro * (CABEZA_X - piv) + dir * 6 * baja,
      y: hom.y - 6 - subeD * 0.4 * (1 - eD) + 1.8 * nod + 13 * baja + 8 * eD,
      r: dir * (2 * nod + 8 * baja),
    };
  }
  function cabezaEn(c) {
    cabeza.setAttribute("transform", "translate(" + c.x + " " + c.y + ") rotate(" + (c.r || 0) + " 0 -10)");
  }

  // ---- motion --------------------------------------------------------------------------------
  var arriba = piso - SUELO * u;                      // div top so the paws stand on the pillow line
  var meta = almCx - CENTRO * u;                      // body centred over the pillow
  // A small dog walks briskly at about 2 strides a second; its speed is set so planted paws never slide.
  var HZ = 2.2, VEL = clamp(ancho * 0.075, 66, 92);
  var DIR = -1;                                       // it comes from the right, so it faces left
  var ESC_ALTO = Math.round(hpx + 80), ESC_TOP = Math.round(arriba - 50);
  escena.style.cssText = "position:absolute;left:" + sx + "px;top:" + ESC_TOP + "px;width:" + ancho +
    "px;height:" + ESC_ALTO + "px;overflow:hidden;z-index:19";
  var FUERA = borde + 2, ASOMADO = borde - 95 * u;     // hidden just past the edge / head and shoulders in
  var x = FUERA, v = 0, fase = 0, t = 0, antes = null;
  var aplasto = false, estado = "asoma", tEstado = 0, R = almW * 0.13;
  var T_OLFATEA = 1.1, VUELTAS = 2, T_VUELTAS = 3.4, T_ECHARSE = 1.9;

  function coloca(px, py, escala, inclina) {
    caja.style.left = (px - sx) + "px"; caja.style.top = (py - ESC_TOP) + "px";
    caja.style.transform = (escala === 1 ? "" : "scale(" + escala + ") ") + (inclina ? "rotate(" + inclina + "deg)" : "");
  }
  function cambia(s) { estado = s; tEstado = t; }

  function cuadro(ahora) {
    if (antes == null) antes = ahora;
    var dt = Math.min(0.05, (ahora - antes) / 1000); antes = ahora; t += dt;
    var k, hz;
    if (estado === "asoma") {
      // pops its head in, tilts it one way and the other (the curious dog look), ducks back out
      var a = t - tEstado, c;
      if (a < 0.35) x = lerp(FUERA, ASOMADO, suave(a / 0.35));
      else if (a < 1.6) x = ASOMADO;
      else x = lerp(ASOMADO, FUERA, suave((a - 1.6) / 0.3));
      c = postura(fase, 0, 0, 0, DIR, 1, 0);
      if (a > 0.45 && a < 1.55) c.r += 11 * Math.sin(2 * Math.PI * (a - 0.45) / 1.1);
      cabezaEn(c);
      coloca(x, arriba, 1);
      if (a > 2.5) { x = FUERA; cambia("camina"); }
    } else if (estado === "camina") {
      var resta = x - meta;
      v = Math.min(VEL * Math.min(1, 0.25 + (t - tEstado) / 0.6), VEL * clamp(resta / 50, 0.2, 1));   // ease in and out
      x = Math.max(meta, x - v * dt);
      hz = HZ * (0.45 + 0.55 * v / VEL);              // slower steps when it slows down
      fase = frac(fase + hz * dt);
      var parar = clamp(1 - resta / 25, 0, 1);         // squares up its legs as it arrives
      cabezaEn(postura(fase, clamp((v / u) * PASO.apoyo / hz, 0, 44), 0, 0, DIR, suave(parar), 0));
      coloca(x, arriba, 1);
      if (resta < 0.5) cambia("olfatea");
    } else if (estado === "olfatea") {
      // stops, puts its nose down to the bed, then looks up
      k = clamp((t - tEstado) / T_OLFATEA, 0, 1);
      cabezaEn(postura(fase, 0, 0, 0, DIR, 1, Math.sin(Math.PI * k)));
      if (k >= 1) cambia("vueltas");
    } else if (estado === "vueltas") {
      // turning round on the bed, nose low: a tight loop seen from the side; the body faces the way
      // it walks (side-on at the front and back of the loop, end-on at the sides)
      k = clamp((t - tEstado) / T_VUELTAS, 0, 1);
      var theta = 2 * Math.PI * VUELTAS * suave(k);
      var cz = Math.cos(theta), giro = DIR * (cz < 0 ? -1 : 1) * Math.max(0.28, Math.abs(cz));
      var arranque = suave(k * 6) * suave((1 - k) * 6);   // steps start and stop with the loop
      fase = frac(fase + HZ * 0.9 * dt * arranque);
      cabezaEn(postura(fase, 18 * arranque, 0, 0, giro, 1 - arranque, 0.35 * arranque));
      // nearer the viewer at the front of the loop: lower and bigger; farther at the back;
      // leaning into the turn while it moves across
      coloca(meta + DIR * R * Math.sin(theta), arriba - 5 * (1 - cz), 0.9 + 0.1 * cz,
        -3.5 * DIR * Math.sin(theta) * Math.sin(Math.PI * k));
      if (k >= 1) cambia("echarse");
    } else {
      // sits first (hind end down), then walks the front paws out and lowers the chest, turning to
      // face forward; the bed gives as the weight lands
      var s = t - tEstado;
      var eT = suave(s / 0.75), eD = suave((s - 0.6) / 1.0), giro2 = lerp(DIR, -0.04, suave((s - 0.7) / 1.0));
      cabezaEn(postura(fase, 0, eT, eD, giro2, 1, 0));
      manos.setAttribute("opacity", suave((eD - 0.5) * 2));
      manos.setAttribute("transform", "translate(0 " + (SUELO - 9 + 4 * (1 - eD)) + ")");
      var asiento = Math.sin(Math.PI * clamp((s - 1.35) / 0.55, 0, 1));
      coloca(lerp(meta, almCx - CABEZA_X * u, eD), arriba + 2.5 * asiento, 1);
      if (!aplasto && eD > 0.8) {
        aplasto = true;
        [fondo.div, frente.div].forEach(function (d) {
          d.style.transformOrigin = "50% 80%";
          d.animate([{ transform: "scale(1,1)" }, { transform: "scale(1.03,0.9)" }, { transform: "scale(1,1)" }],
            { duration: 600, easing: "ease-out" });
        });
      }
      if (s >= T_ECHARSE) {
        // settled: one deep sigh, then slow breathing, as Web Animations (no frame loop keeps running)
        var suspiro = caja.animate([{ transform: "scale(1,1)" }, { transform: "scale(1.03,1.07)", offset: 0.4 },
          { transform: "scale(1,0.99)", offset: 0.8 }, { transform: "scale(1,1)" }], { duration: 1800, easing: "ease-in-out" });
        suspiro.onfinish = function () {
          caja.animate([{ transform: "scale(1,1)" }, { transform: "scale(1.012,1.03)" }, { transform: "scale(1,1)" }],
            { duration: 3400, iterations: Infinity, easing: "ease-in-out" });
        };
        return;
      }
    }
    W.requestAnimationFrame(cuadro);
  }

  var pre = new Image();
  pre.onload = function () {
    D.body.appendChild(fondo.div);
    D.body.appendChild(escena);
    D.body.appendChild(frente.div);
    fondo.div.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, fill: "both" });
    frente.div.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, fill: "both" });
    cabezaEn(postura(0, 0, 0, 0, DIR, 1, 0));
    coloca(x, arriba, 1);
    setTimeout(function () { W.requestAnimationFrame(cuadro); }, 700);
  };
  pre.src = IMG;
})();
