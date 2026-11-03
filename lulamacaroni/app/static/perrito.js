/* The puppy (Lore's art). Loaded only on the visits when it plays; see PERRITO_JS in views.py.
 * The portrait, on its side, peeks its head out from behind the left menu, looks around and
 * ducks back. Decoration only: pointer-events none, aria-hidden, removed when done.
 */
(function () {
  "use strict";
  var W = window, D = document;
  var IMG = "/perrito.png", RATIO = 1136 / 1246; // the trimmed artwork's height / width

  // ---- layout -------------------------------------------------------------------------------
  var side = D.querySelector(".side"), r = side ? side.getBoundingClientRect() : null;
  var conMenu = !!(r && r.right > 0), x0 = conMenu ? r.right : 0, ancho = W.innerWidth;

  function caja(w) {
    var c = D.createElement("div");
    c.className = "perrito";
    c.setAttribute("aria-hidden", "true");
    c.style.width = w + "px";
    return c;
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  // ---- peek -------------------------------------------------------------------------------
  function asoma() {
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
      a.finished.then(function () { setTimeout(function () { c.remove(); }, 650); });
    };
  }

  asoma();
})();
