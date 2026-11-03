/* The puppy (Lore's art). Loaded only on the visits when it plays; see PERRITO_JS in views.py.
 *
 * A dog pillow sits next to "Hola, Lore". The puppy walks out from behind the left menu to the
 * pillow, turns around on it twice the way dogs do before settling, then lies down facing
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
  var side = D.querySelector(".side"), r = side ? side.getBoundingClientRect() : null;
  var x0 = r && r.right > 0 ? r.right + sx : sx;     // behind the menu, or the screen edge on phones
  var ancho = D.documentElement.clientWidth;

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
  caja.style.cssText = "position:absolute;width:" + wpx + "px;z-index:19;transform-origin:50% 100%";
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

  // One frame of the body. fase: stride phase; sweep: how far a planted paw travels (units);
  // echado: 0 standing .. 1 lying (legs folded, body lowered); giro: facing, -1..1 (side-on at ±1,
  // seen end-on near 0). Returns where the head sits, in drawing units.
  function postura(fase, sweep, echado, giro) {
    var bob = -1.4 * Math.cos(4 * Math.PI * fase) * (1 - echado) + 22 * echado;
    var hom = { x: HOMBRO.x, y: HOMBRO.y + bob }, cad = { x: CADERA.x, y: CADERA.y + bob };
    ["LH", "RH", "LF", "RF"].forEach(function (k) {
      var tr = k.charAt(1) === "H", L = tr ? TRAS : DEL, pp = frac(fase - PASO[k]), b = PASO.apoyo;
      var raiz = tr ? { x: cad.x + 2, y: cad.y - 4 } : { x: hom.x + 2, y: hom.y - 4 };
      // the far-side legs stand on a farther line of the ground, so they sit a little higher;
      // seen end-on (turning) the two sides spread further apart
      var lejos = k.charAt(0) === "L" ? (3 + 7 * (1 - Math.abs(giro))) * (1 - echado) : 0;
      raiz.y -= lejos;
      var px, py, ang;   // paw position, and the angle of the lowest bone (degrees from straight
                         // down; positive = paw ahead of the wrist or hock)
      if (pp < b) {      // stance: paw planted, the body passes over it
        px = raiz.x + sweep / 2 - sweep * pp / b; py = SUELO;
        ang = tr ? 24 : 8;   // the hock sits behind and above the paw; the pastern slopes a little
      } else {           // swing: lift, fold and reach forward
        var q = (pp - b) / (1 - b), e = q - Math.sin(2 * Math.PI * q) / (2 * Math.PI), s1 = Math.sin(Math.PI * q);
        px = raiz.x - sweep / 2 + sweep * e; py = SUELO - (tr ? 8 : 10) * s1;
        if (tr) ang = 24 - 70 * s1 * (1 - q) + 20 * s1 * q;           // hock flexes: paw trails, then reaches
        else ang = q < 0.6 ? 8 - 115 * Math.sin(Math.PI * q / 0.6)    // wrist folds: paw tucks up behind
                           : 8 + 14 * Math.sin(Math.PI * (q - 0.6) / 0.4);   // then the leg reaches forward
      }
      // lying down: front legs stretched forward along the pillow, hind legs folded under
      py -= lejos;
      px = lerp(px, tr ? raiz.x + 12 : raiz.x + 20, echado); py = lerp(py, SUELO - 2, echado);
      ang = lerp(ang, tr ? 80 : 85, echado);
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
      "C" + (cad.x - 16) + " " + (cad.y - 22) + " " + (cad.x + 10) + " " + top + " " + ((cad.x + hom.x) / 2) + " " + top +
      "C" + (hom.x - 6) + " " + top + " " + (hom.x + 30) + " " + (hom.y - 30) + " " + (hom.x + 30) + " " + (hom.y + 4) +
      "C" + (hom.x + 28) + " " + (hom.y + 16) + " " + (cad.x - 4) + " " + (cad.y + 16) + " " + (cad.x - 14) + " " + (cad.y + 2) + "Z");
    torsoLuz.setAttribute("d", torso.getAttribute("d"));
    ancas.setAttribute("cx", cad.x - 2); ancas.setAttribute("cy", cad.y - 6);
    cola.setAttribute("transform", "translate(" + (cad.x - 16) + " " + (cad.y - 22) + ") rotate(" +
      (Math.sin(2 * Math.PI * fase * 1.5) * 16) + ")");
    // facing: squeeze the body around the head's line so it turns behind the head
    var piv = lerp(CENTRO, CABEZA_X, echado);
    cuerpo.setAttribute("transform", "translate(" + piv + " 0) scale(" + giro + " 1) translate(" + (-piv) + " 0)");
    var ag = Math.abs(giro), mitad = piv + giro * (CENTRO - piv);
    sombra.setAttribute("cx", lerp(mitad, piv + giro * (CABEZA_X - 18 - piv), echado));
    sombra.setAttribute("cy", SUELO + 1 - 2 * (1 - ag) * (1 - echado));
    sombra.setAttribute("rx", lerp(30 + 22 * ag, 46, echado) * (1 + 0.04 * bob * (1 - echado)));
    sombra.setAttribute("ry", lerp(4 + 6 * (1 - ag), 7, echado));
    // the head rides the shoulders a beat late, nodding slightly with each step
    var nod = Math.sin(4 * Math.PI * fase - 0.9) * (1 - echado);
    return { x: piv + giro * (CABEZA_X - piv), y: hom.y - 6 - bob * 0.5 + 0.8 * nod + 30 * echado, r: 1.6 * nod * (giro < 0 ? -1 : 1) };
  }
  function cabezaEn(c) {
    cabeza.setAttribute("transform", "translate(" + c.x + " " + c.y + ") rotate(" + (c.r || 0) + " 0 -10)");
  }

  // ---- motion --------------------------------------------------------------------------------
  var arriba = piso - SUELO * u;                      // div top so the paws stand on the pillow line
  var meta = almCx - CENTRO * u;                      // body centred over the pillow
  var x = x0 - wpx, v = 0, VEL = clamp(ancho * 0.09, 90, 125), fase = 0, t = 0, antes = null;
  var aplasto = false, estado = "camina", tEstado = 0, R = almW * 0.17;
  var VUELTAS = 2, T_VUELTAS = 2.8, T_ECHARSE = 1.2;
  var HZ = 2.6;                                       // a small dog's brisk walk

  function coloca(px, py, escala, inclina) {
    caja.style.left = px + "px"; caja.style.top = py + "px";
    caja.style.transform = (escala === 1 ? "" : "scale(" + escala + ") ") + (inclina ? "rotate(" + inclina + "deg)" : "");
  }

  function cuadro(ahora) {
    if (antes == null) antes = ahora;
    var dt = Math.min(0.05, (ahora - antes) / 1000); antes = ahora; t += dt;
    var sweep;
    if (estado === "camina") {
      var resta = meta - x;
      v = Math.min(VEL * Math.min(1, 0.2 + t / 0.4), VEL * clamp(resta / 60, 0.25, 1));   // ease in and out
      x = Math.min(meta, x + v * dt);
      fase = frac(fase + HZ * (0.35 + 0.65 * v / VEL) * dt);
      sweep = clamp((v / u) * PASO.apoyo / (HZ * (0.35 + 0.65 * v / VEL)), 0, 46);
      cabezaEn(postura(fase, sweep, 0, 1));
      coloca(x, arriba, 1);
      if (meta - x < 0.5) { estado = "vueltas"; tEstado = t; }
    } else if (estado === "vueltas") {
      // turning round on the pillow: a small loop seen from the side; the body faces the way it
      // walks (side-on at the front and back of the loop, end-on at the sides)
      var k = clamp((t - tEstado) / T_VUELTAS, 0, 1);
      var theta = 2 * Math.PI * VUELTAS * suave(k);
      var cz = Math.cos(theta), giro = (cz < 0 ? -1 : 1) * Math.max(0.28, Math.abs(cz));
      fase = frac(fase + HZ * 0.8 * dt);
      cabezaEn(postura(fase, 16, 0, giro));
      // nearer the viewer at the front of the loop: lower and bigger; farther at the back;
      // leaning into the turn while it moves across
      coloca(meta + R * Math.sin(theta), arriba - 5 * (1 - cz), 0.9 + 0.1 * cz,
        -3.5 * Math.sin(theta) * Math.sin(Math.PI * k));
      if (k >= 1) { estado = "echarse"; tEstado = t; }
    } else {
      // fold the legs, sink into the pillow, and turn to face forward
      var e = suave((t - tEstado) / T_ECHARSE), giro2 = lerp(1, 0.04, suave((t - tEstado) / (T_ECHARSE * 0.8)));
      cabezaEn(postura(fase, 0, e, giro2));
      manos.setAttribute("opacity", suave((e - 0.5) * 2));
      manos.setAttribute("transform", "translate(0 " + (SUELO - 9 + 4 * (1 - e)) + ")");
      // a small settle as the weight lands: the pillow gives, the body sinks and comes back up
      var asiento = Math.sin(Math.PI * clamp((t - tEstado - T_ECHARSE * 0.75) / 0.55, 0, 1));
      coloca(lerp(meta, almCx - CABEZA_X * u, e), arriba + 2.5 * asiento, 1);
      if (!aplasto && e > 0.8) {
        aplasto = true;
        [fondo.div, frente.div].forEach(function (d) {
          d.style.transformOrigin = "50% 80%";
          d.animate([{ transform: "scale(1,1)" }, { transform: "scale(1.03,0.9)" }, { transform: "scale(1,1)" }],
            { duration: 600, easing: "ease-out" });
        });
      }
      if (e >= 1) {
        // settled: slow breathing as a Web Animation, so no frame loop keeps running
        caja.animate([{ transform: "scale(1,1)" }, { transform: "scale(1.012,1.03)" }, { transform: "scale(1,1)" }],
          { duration: 3400, iterations: Infinity, easing: "ease-in-out" });
        return;
      }
    }
    W.requestAnimationFrame(cuadro);
  }

  var pre = new Image();
  pre.onload = function () {
    D.body.appendChild(fondo.div);
    D.body.appendChild(caja);
    D.body.appendChild(frente.div);
    fondo.div.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, fill: "both" });
    frente.div.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, fill: "both" });
    cabezaEn(postura(0, 0, 0, 1));
    coloca(x, arriba, 1);
    setTimeout(function () { W.requestAnimationFrame(cuadro); }, 700);
  };
  pre.src = IMG;
})();
