/* The puppy (Lore's art). Loaded only on the visits when it plays; see PERRITO_JS in views.py.
 *
 * 1. Peek: the portrait, on its side, pokes its head out from behind the left menu and ducks back.
 * 2. Run: the same head, unchanged, on a four-legged body drawn to match (red ribbed sweater,
 *    cream curly fur). The legs follow a real dog's gait: a trot (diagonal pairs) that speeds up
 *    into a rotary gallop (hind, hind, fore, fore, then a gathered flight). Feet on the ground
 *    don't slide, the body rises in flight and dips on landing, the back flexes, and the head is
 *    held steadier than the body, as dogs do.
 * 3. Trip: a front paw catches in the sweater, the dog pitches forward with a "¡uy!" and rolls
 *    head over heels off the right edge. The roll turns by the distance travelled (no sliding)
 *    and bounces under gravity.
 * Decoration only: pointer-events none, aria-hidden, removed when done.
 */
(function () {
  "use strict";
  var W = window, D = document, NS = "http://www.w3.org/2000/svg";
  var IMG = "/perrito.png", RATIO = 1136 / 1246; // the trimmed artwork's height / width

  // ---- layout -------------------------------------------------------------------------------
  var side = D.querySelector(".side"), r = side ? side.getBoundingClientRect() : null;
  var conMenu = !!(r && r.right > 0), x0 = conMenu ? r.right : 0, ancho = W.innerWidth;
  var top0 = conMenu ? 0 : ((D.querySelector(".top") || {}).offsetHeight || 0);

  function el(tag, attrs, parent) {
    var e = D.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function caja(w) {
    var c = D.createElement("div");
    c.className = "perrito";
    c.setAttribute("aria-hidden", "true");
    c.style.width = w + "px";
    return c;
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function smooth(a, b, v) { var t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
  function frac(v) { return v - Math.floor(v); }

  // ---- 1. peek ------------------------------------------------------------------------------
  function asoma(listo) {
    var w = Math.round(clamp(ancho * 0.07, 56, 92)), h = Math.round(w * RATIO);
    var c = caja(w), img = D.createElement("img");
    img.src = IMG; img.alt = ""; img.style.cssText = "display:block;width:100%;height:auto";
    c.appendChild(img);
    var py = Math.round(W.innerHeight * 0.42), sale = Math.round(w * 0.85);
    var base = "translate(" + Math.round(x0 - (w + h) / 2 - 2) + "px," + py + "px) ";
    function f(dx, rot, off) {
      var k = { transform: base + "translateX(" + dx + "px) rotate(" + rot + "deg)" };
      if (off != null) k.offset = off;
      return k;
    }
    img.onerror = function () { c.remove(); };
    img.onload = function () {
      D.body.appendChild(c);
      var a = c.animate([f(0, 90), f(sale, 84, .22), f(sale, 72, .42), f(sale, 94, .62),
        f(sale - 4, 84, .76), f(0, 90)], { duration: 2300, easing: "ease-in-out", fill: "forwards" });
      a.finished.then(function () { setTimeout(function () { c.remove(); listo(); }, 650); });
    };
  }

  // ---- 2 + 3. the running dog -----------------------------------------------------------------
  // Drawing units: viewBox 0 0 200 140, dog facing right, ground at y = 132.
  var VB_W = 200, VB_H = 140, SUELO = 132;
  var MUSLO = 24, CANILLA = 24;                     // upper and lower leg
  var HOMBRO = { x: 124, y: 88 }, CADERA = { x: 70, y: 88 };
  var FUR = "#F4E8CC", FUR_LEJOS = "#DCCAA3", FUR_LINEA = "#CDB98F";
  var SUETER = "#7E1D23", SUETER_LEJOS = "#62151A", RIBETE = "#661419";

  // Gait tables. Offsets: when each foot touches down, as a fraction of the stride.
  // Trot: diagonal pairs together. Rotary gallop: left hind, right hind, right fore, left fore,
  // then all four in the air with the legs gathered under the body.
  var TROTE = { LH: 0, RF: 0, RH: 0.5, LF: 0.5, apoyo: 0.55, hz: 2.5 };
  var GALOPE = { LH: 0, RH: 0.1, RF: 0.42, LF: 0.52, apoyo: 0.36, hz: 3.2 };

  function dibuja(svg) {
    var defs = el("defs", {}, svg);
    // hand-drawn, fuzzy edges like the colored-pencil art
    var fz = el("filter", { id: "pf-fuzz", x: "-10%", y: "-10%", width: "120%", height: "120%" }, defs);
    el("feTurbulence", { type: "fractalNoise", baseFrequency: "0.9", numOctaves: "2", seed: "3", result: "n" }, fz);
    el("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: "3.2", xChannelSelector: "R", yChannelSelector: "G" }, fz);
    // the sweater's ribbing
    var pat = el("pattern", { id: "pf-rib", width: "4", height: "8", patternUnits: "userSpaceOnUse" }, defs);
    el("rect", { width: "4", height: "8", fill: SUETER }, pat);
    el("rect", { width: "1.3", height: "8", fill: RIBETE }, pat);

    var g = el("g", { filter: "url(#pf-fuzz)" }, svg);
    function pata(color, linea, manga) {
      var gr = el("g", {}, g);
      return {
        muslo: el("path", { stroke: manga || color, "stroke-width": manga ? 15 : 14, "stroke-linecap": "round", fill: "none" }, gr),
        canilla: el("path", { stroke: color, "stroke-width": 12, "stroke-linecap": "round", fill: "none" }, gr),
        pie: el("ellipse", { rx: 7.5, ry: 4.8, fill: color, stroke: linea, "stroke-width": 0.8 }, gr),
      };
    }
    var p = {};
    p.LH = pata(FUR_LEJOS, FUR_LINEA);              // far side, behind the body
    p.LF = pata(FUR_LEJOS, FUR_LINEA, SUETER_LEJOS);
    p.cola = el("g", {}, g);
    [[0, 0, 9], [-6, -6, 7], [3, -9, 6.5], [-2, 5, 6]].forEach(function (b) {
      el("circle", { cx: b[0], cy: b[1], r: b[2], fill: FUR, stroke: FUR_LINEA, "stroke-width": 0.8 }, p.cola);
    });
    p.ancas = el("ellipse", { rx: 19, ry: 17, fill: FUR, stroke: FUR_LINEA, "stroke-width": 0.8 }, g);
    p.torso = el("path", { fill: "url(#pf-rib)", stroke: RIBETE, "stroke-width": 1 }, g);
    p.RH = pata(FUR, FUR_LINEA);                    // near side, in front
    p.RF = pata(FUR, FUR_LINEA, SUETER);
    p.cabeza = el("g", {}, svg);                    // the original art, outside the fuzz filter
    var w = 74, h = w * RATIO;
    var im = el("image", { width: w, height: h, x: -w / 2, y: -h + 14, preserveAspectRatio: "xMidYMid meet" }, p.cabeza);
    im.setAttributeNS("http://www.w3.org/1999/xlink", "href", IMG);
    im.setAttribute("href", IMG);
    return p;
  }

  // Two-bone leg from the body to the paw. The middle joint points back (+1, hind hock) or
  // forward (-1, fore wrist), so hind paws fold forward and front paws fold back in the swing.
  function ik(ax, ay, fx, fy, dobla) {
    var dx = fx - ax, dy = fy - ay, d = Math.sqrt(dx * dx + dy * dy);
    var max = MUSLO + CANILLA - 0.01;
    if (d > max) { fx = ax + dx / d * max; fy = ay + dy / d * max; dx = fx - ax; dy = fy - ay; d = max; }
    var a = (MUSLO * MUSLO - CANILLA * CANILLA + d * d) / (2 * d), hh = Math.sqrt(Math.max(0, MUSLO * MUSLO - a * a));
    var mx = ax + dx * a / d, my = ay + dy * a / d;
    return { kx: mx - dobla * hh * dy / d, ky: my + dobla * hh * dx / d, fx: fx, fy: fy };
  }
  function pon(leg, ax, ay, s) {
    leg.muslo.setAttribute("d", "M" + ax + " " + ay + "L" + s.kx + " " + s.ky);
    leg.canilla.setAttribute("d", "M" + s.kx + " " + s.ky + "L" + s.fx + " " + s.fy);
    leg.pie.setAttribute("cx", s.fx + 2.5); leg.pie.setAttribute("cy", s.fy);
  }

  function corre() {
    var wpx = Math.round(clamp(ancho * 0.12, 104, 158)), hpx = wpx * VB_H / VB_W, u = wpx / VB_W;
    var c = caja(wpx);
    c.style.transformOrigin = "50% 60%";
    var svg = el("svg", { viewBox: "0 0 " + VB_W + " " + VB_H, width: wpx, height: hpx, overflow: "visible" });
    svg.style.display = "block"; svg.style.overflow = "visible";
    c.appendChild(svg);
    var uy = D.createElement("span"); uy.className = "uy"; uy.textContent = "¡uy!"; c.appendChild(uy);
    var p = dibuja(svg);
    D.body.appendChild(c);

    var y0 = top0 + 4, xTropiezo = x0 + (ancho - x0) * 0.5, fuera = ancho + wpx * 0.4;
    var VMAX = clamp(ancho * 0.42, 260, 520);        // px/s at full gallop
    var x = x0 - wpx, v = 0, fase = 0, t = 0, antes = null, estado = "corre";
    var tiempoTropiezo = 0, pitch = 0, alto = 0, vy = 0, giro = 0, vTropiezo = 0;
    var radio = hpx * 0.42;                          // rolling radius when tucked

    function postura(g, sweep, lift, tuck) {
      // body motion from the gait: bob, pitch, back flex (gallop) blended with a small trot bounce
      var bobG = -4.5 * Math.cos(2 * Math.PI * (fase - 0.96)) - 1.2 * Math.cos(4 * Math.PI * (fase - 0.2));
      var bobT = -1.6 * Math.cos(4 * Math.PI * (fase - 0.25));
      var bob = lerp(bobT, bobG, g) - 1.5 * g;
      var cab = lerp(0, -5 * Math.sin(2 * Math.PI * (fase - 0.05)), g); // nose up on hind push
      var flex = lerp(0, 6 * Math.cos(2 * Math.PI * (fase - 0.96)), g);   // gathered in flight
      var hom = { x: HOMBRO.x - flex, y: HOMBRO.y + bob + Math.sin(cab * Math.PI / 180) * 32 };
      var cad = { x: CADERA.x + flex, y: CADERA.y + bob - Math.sin(cab * Math.PI / 180) * 32 };
      var tabla = {};
      ["LH", "RH", "RF", "LF"].forEach(function (k) {
        var off = lerp(TROTE[k], GALOPE[k], g), beta = lerp(TROTE.apoyo, GALOPE.apoyo, g);
        var pp = frac(fase - off), fx, fy, tr = k.charAt(1) === "H";
        var raiz = tr ? cad : hom;
        if (tuck) {
          fx = raiz.x + (tr ? 10 : -8); fy = raiz.y + 18;
        } else if (pp < beta) {                       // stance: paw planted, body passes over it
          var s = pp / beta;
          fx = raiz.x + sweep / 2 - sweep * s + (tr ? -3 : 4); fy = SUELO;
        } else {                                       // swing: lift, fold and reach forward
          var q = (pp - beta) / (1 - beta), e = q - Math.sin(2 * Math.PI * q) / (2 * Math.PI);
          fx = raiz.x - sweep / 2 + sweep * e + (tr ? -3 : 4);
          fy = SUELO - lift * Math.pow(Math.sin(Math.PI * q), 0.8);
        }
        tabla[k] = { raiz: raiz, s: ik(raiz.x, raiz.y, fx, fy, tr ? 1 : -1) };
      });
      ["LH", "RH", "RF", "LF"].forEach(function (k) { pon(p[k], tabla[k].raiz.x, tabla[k].raiz.y, tabla[k].s); });
      var arco = lerp(0, 5 * Math.cos(2 * Math.PI * (fase - 0.96)), g) + 2;
      var top = Math.min(hom.y, cad.y) - 30 - arco;
      p.torso.setAttribute("d",
        "M" + (cad.x - 14) + " " + (cad.y + 2) +
        "C" + (cad.x - 16) + " " + (cad.y - 22) + " " + (cad.x + 10) + " " + top + " " + ((cad.x + hom.x) / 2) + " " + top +
        "C" + (hom.x - 6) + " " + top + " " + (hom.x + 30) + " " + (hom.y - 30) + " " + (hom.x + 30) + " " + (hom.y + 4) +
        "C" + (hom.x + 28) + " " + (hom.y + 16) + " " + (cad.x - 4) + " " + (cad.y + 16) + " " + (cad.x - 14) + " " + (cad.y + 2) + "Z");
      p.ancas.setAttribute("cx", cad.x - 2); p.ancas.setAttribute("cy", cad.y - 6);
      var wag = Math.sin(2 * Math.PI * fase * 2) * 18 * (tuck ? 0.2 : 1);
      p.cola.setAttribute("transform", "translate(" + (cad.x - 16) + " " + (cad.y - 22) + ") rotate(" + wag + ")");
      // head: steadier than the body (half the bob, most of the pitch cancelled)
      var hx = hom.x + 16, hy = hom.y - 6 - bob * 0.5;
      p.cabeza.setAttribute("transform", "translate(" + hx + " " + hy + ") rotate(" + (-cab * 0.7) + ")");
      return cab;
    }

    function cuadro(ahora) {
      if (antes == null) antes = ahora;
      var dt = Math.min(0.05, (ahora - antes) / 1000); antes = ahora; t += dt;
      var cab = 0, sweep, g;
      if (estado === "corre") {
        v = VMAX * (1 - Math.exp(-t / 0.45));          // accelerate out from behind the menu
        g = smooth(VMAX * 0.35, VMAX * 0.75, v);       // trot → gallop as speed builds
        var hz = lerp(TROTE.hz, GALOPE.hz, g), beta = lerp(TROTE.apoyo, GALOPE.apoyo, g);
        fase = frac(fase + hz * dt);
        sweep = clamp((v / u) * beta / hz, 4, 58);     // planted paws move exactly with the ground
        x += v * dt;
        cab = postura(g, sweep, lerp(10, 15, g), false);
        if (x + wpx * 0.6 >= xTropiezo) {
          estado = "tropieza"; tiempoTropiezo = t; vTropiezo = v;
          uy.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none", offset: 0.2 },
            { opacity: 1, offset: 0.75 }, { opacity: 0, transform: "translateY(-6px)" }], { duration: 900, fill: "forwards" });
        }
        c.style.transform = "translate(" + x + "px," + y0 + "px)";
      } else if (estado === "tropieza") {
        // a front paw is caught: the body keeps going and pitches over it
        var k = clamp((t - tiempoTropiezo) / 0.26, 0, 1);
        v = vTropiezo * (1 - 0.25 * k);
        x += v * dt;
        pitch = 48 * k * k;
        postura(lerp(1, 0, k), 20, 6, k > 0.6);
        c.style.transform = "translate(" + x + "px," + y0 + "px) rotate(" + pitch + "deg)";
        if (k >= 1) { estado = "rueda"; vy = -260; alto = 0; giro = pitch; }
      } else {
        // tucked and rolling: turns by distance / radius, bounces under gravity, slowly loses speed
        v = Math.max(vTropiezo * 0.5, v - vTropiezo * 0.35 * dt);
        var dx = v * dt; x += dx; giro += dx / radio * 180 / Math.PI;
        vy += 2300 * dt; alto += vy * dt;
        if (alto > 0) { alto = 0; vy = Math.abs(vy) > 90 ? -Math.abs(vy) * 0.42 : 0; }
        postura(0, 10, 4, true);
        c.style.transform = "translate(" + x + "px," + (y0 + alto) + "px) rotate(" + giro + "deg)";
        if (x > fuera) { c.remove(); return; }
      }
      if (t > 12) { c.remove(); return; }              // safety net
      W.requestAnimationFrame(cuadro);
    }
    W.requestAnimationFrame(cuadro);
  }

  asoma(corre);
})();
