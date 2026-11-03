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
  var MUSLO = 24, CANILLA = 24;
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

  var cuerpo = el("g", {}, svg);                      // flips and folds; the head never does
  var g = el("g", { filter: "url(#pf-fuzz)" }, cuerpo);
  function pata(color, manga) {
    var gr = el("g", {}, g);
    return {
      muslo: el("path", { stroke: manga || color, "stroke-width": manga ? 15 : 14, "stroke-linecap": "round", fill: "none" }, gr),
      canilla: el("path", { stroke: color, "stroke-width": 12, "stroke-linecap": "round", fill: "none" }, gr),
      pie: el("ellipse", { rx: 7.5, ry: 4.8, fill: color, stroke: FUR_LINEA, "stroke-width": 0.8 }, gr),
    };
  }
  var P = {};
  P.LH = pata(FUR_LEJOS); P.LF = pata(FUR_LEJOS, SUETER_LEJOS);
  var cola = el("g", {}, g);
  [[0, 0, 9], [-6, -6, 7], [3, -9, 6.5], [-2, 5, 6]].forEach(function (b) {
    el("circle", { cx: b[0], cy: b[1], r: b[2], fill: FUR, stroke: FUR_LINEA, "stroke-width": 0.8 }, cola);
  });
  var ancas = el("ellipse", { rx: 19, ry: 17, fill: FUR, stroke: FUR_LINEA, "stroke-width": 0.8 }, g);
  var torso = el("path", { fill: "url(#pf-rib)", stroke: RIBETE, "stroke-width": 1 }, g);
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

  function ik(ax, ay, fx, fy, dobla) {
    var dx = fx - ax, dy = fy - ay, d = Math.sqrt(dx * dx + dy * dy) || 0.01, max = MUSLO + CANILLA - 0.01;
    if (d > max) { fx = ax + dx / d * max; fy = ay + dy / d * max; dx = fx - ax; dy = fy - ay; d = max; }
    var a = (MUSLO * MUSLO - CANILLA * CANILLA + d * d) / (2 * d), h = Math.sqrt(Math.max(0, MUSLO * MUSLO - a * a));
    var mx = ax + dx * a / d, my = ay + dy * a / d;
    return { kx: mx - dobla * h * dy / d, ky: my + dobla * h * dx / d, fx: fx, fy: fy };
  }

  // One frame of the body. fase: stride phase; sweep: how far a planted paw travels (units);
  // echado: 0 standing .. 1 lying (legs folded, body lowered); giro: facing, -1..1 (side-on at ±1,
  // seen end-on near 0). Returns where the head sits, in drawing units.
  function postura(fase, sweep, echado, giro) {
    var bob = -1.4 * Math.cos(4 * Math.PI * fase) * (1 - echado) + 22 * echado;
    var hom = { x: HOMBRO.x, y: HOMBRO.y + bob }, cad = { x: CADERA.x, y: CADERA.y + bob };
    ["LH", "RH", "LF", "RF"].forEach(function (k) {
      var tr = k.charAt(1) === "H", raiz = tr ? cad : hom, pp = frac(fase - PASO[k]), b = PASO.apoyo, fx, fy;
      if (pp < b) { fx = raiz.x + sweep / 2 - sweep * pp / b; fy = SUELO; }
      else {
        var q = (pp - b) / (1 - b), e = q - Math.sin(2 * Math.PI * q) / (2 * Math.PI);
        fx = raiz.x - sweep / 2 + sweep * e; fy = SUELO - 9 * Math.sin(Math.PI * q);
      }
      fx = lerp(fx, raiz.x + (tr ? 16 : -14), echado); fy = lerp(fy, raiz.y + 10, echado);
      var s = ik(raiz.x, raiz.y, fx, fy, tr ? 1 : -1), leg = P[k];
      leg.muslo.setAttribute("d", "M" + raiz.x + " " + raiz.y + "L" + s.kx + " " + s.ky);
      leg.canilla.setAttribute("d", "M" + s.kx + " " + s.ky + "L" + s.fx + " " + s.fy);
      leg.pie.setAttribute("cx", s.fx + 2.5); leg.pie.setAttribute("cy", s.fy);
    });
    var top = Math.min(hom.y, cad.y) - 32;
    torso.setAttribute("d",
      "M" + (cad.x - 14) + " " + (cad.y + 2) +
      "C" + (cad.x - 16) + " " + (cad.y - 22) + " " + (cad.x + 10) + " " + top + " " + ((cad.x + hom.x) / 2) + " " + top +
      "C" + (hom.x - 6) + " " + top + " " + (hom.x + 30) + " " + (hom.y - 30) + " " + (hom.x + 30) + " " + (hom.y + 4) +
      "C" + (hom.x + 28) + " " + (hom.y + 16) + " " + (cad.x - 4) + " " + (cad.y + 16) + " " + (cad.x - 14) + " " + (cad.y + 2) + "Z");
    ancas.setAttribute("cx", cad.x - 2); ancas.setAttribute("cy", cad.y - 6);
    cola.setAttribute("transform", "translate(" + (cad.x - 16) + " " + (cad.y - 22) + ") rotate(" +
      (Math.sin(2 * Math.PI * fase * 1.5) * 16) + ")");
    // facing: squeeze the body around the head's line so it turns behind the head
    var piv = lerp(CENTRO, CABEZA_X, echado);
    cuerpo.setAttribute("transform", "translate(" + piv + " 0) scale(" + giro + " 1) translate(" + (-piv) + " 0)");
    return { x: piv + giro * (CABEZA_X - piv), y: hom.y - 6 - bob * 0.5 + 30 * echado };
  }
  function cabezaEn(c) { cabeza.setAttribute("transform", "translate(" + c.x + " " + c.y + ")"); }

  // ---- motion --------------------------------------------------------------------------------
  var arriba = piso - SUELO * u;                      // div top so the paws stand on the pillow line
  var meta = almCx - CENTRO * u;                      // body centred over the pillow
  var x = x0 - wpx, v = 0, VEL = clamp(ancho * 0.09, 90, 125), fase = 0, t = 0, antes = null;
  var estado = "camina", tEstado = 0, R = almW * 0.17;
  var VUELTAS = 2, T_VUELTAS = 2.8, T_ECHARSE = 1.2;
  var HZ = 2.6;                                       // a small dog's brisk walk

  function coloca(px, py, escala) {
    caja.style.left = px + "px"; caja.style.top = py + "px";
    caja.style.transform = escala === 1 ? "" : "scale(" + escala + ")";
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
      coloca(meta + R * Math.sin(theta), arriba - 3 * (1 - cz), 0.95 + 0.05 * cz);
      if (k >= 1) { estado = "echarse"; tEstado = t; }
    } else {
      // fold the legs, sink into the pillow, and turn to face forward
      var e = suave((t - tEstado) / T_ECHARSE), giro2 = lerp(1, 0.04, suave((t - tEstado) / (T_ECHARSE * 0.8)));
      cabezaEn(postura(fase, 0, e, giro2));
      manos.setAttribute("opacity", suave((e - 0.5) * 2));
      manos.setAttribute("transform", "translate(0 " + (SUELO - 9 + 4 * (1 - e)) + ")");
      coloca(lerp(meta, almCx - CABEZA_X * u, e), arriba, 1);
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
