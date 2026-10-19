/* Alertas de pedidos entrantes en tiempo real (Panel Salesiano).
 *
 * Consulta GET /api/pedidos/nuevos?desde=<ultimo_id> cada 15 s y avisa con:
 *   - toast en pantalla (clic -> /pedidos)
 *   - sonido corto (WebAudio, sin archivos externos)
 *   - notificacion de escritorio si el navegador otorga permiso
 *   - badge en el boton "Pedidos" del panel
 *
 * La primera consulta solo fija el punto de partida (sin alertas); luego,
 * todo pedido con id mayor genera aviso. Si el usuario esta en /pedidos, el
 * badge se limpia solo.
 */
(function () {
    "use strict";

    var INTERVALO_MS = 15000;
    var CLAVE = "panel_ultimo_pedido_id";
    var baseListo = sessionStorage.getItem(CLAVE) !== null;
    var ultimoId = parseInt(sessionStorage.getItem(CLAVE) || "0", 10) || 0;
    var sinAvisar = 0;

    function badge() {
        return document.getElementById("contador-pedidos-nuevos");
    }

    function pintarBadge() {
        var b = badge();
        if (!b) return;
        if (sinAvisar > 0 && location.pathname !== "/pedidos") {
            b.textContent = sinAvisar > 99 ? "99+" : String(sinAvisar);
            b.style.display = "";
        } else {
            b.style.display = "none";
        }
    }

    function sonar() {
        try {
            var Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return;
            var ctx = new Ctx();
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = "sine";
            gain.gain.value = 0.12;
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.setValueAtTime(660, ctx.currentTime + 0.18);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        } catch (e) { /* sin audio disponible */ }
    }

    function notificarEscritorio(pedido) {
        try {
            if (!("Notification" in window)) return;
            if (Notification.permission === "granted") {
                new Notification("Nuevo pedido #" + pedido.id, {
                    body: pedido.cliente + " - S/ " + pedido.total.toFixed(2),
                    tag: "pedido-" + pedido.id
                });
            } else if (Notification.permission === "default") {
                Notification.requestPermission().then(function (p) {
                    if (p === "granted") {
                        new Notification("Nuevo pedido #" + pedido.id, {
                            body: pedido.cliente + " - S/ " + pedido.total.toFixed(2)
                        });
                    }
                });
            }
        } catch (e) { /* sin soporte */ }
    }

    function toast(pedido) {
        var t = document.createElement("div");
        t.className = "position-fixed top-0 end-0 m-3 px-3 py-2 bg-success text-white rounded-4 shadow-lg";
        t.style.zIndex = "9999";
        t.style.cursor = "pointer";
        t.style.fontSize = "0.85rem";
        t.innerHTML = '<i class="fas fa-bell me-2"></i><b>Nuevo pedido #' + pedido.id + "</b> - " +
            pedido.cliente + " - S/ " + pedido.total.toFixed(2) +
            ' <span class="ms-2 text-white-50">(' + (pedido.tipo_entrega === "delivery" ? "Delivery" : "Recojo") + ")</span>";
        t.onclick = function () { window.location.href = "/pedidos"; };
        document.body.appendChild(t);
        setTimeout(function () { t.remove(); }, 10000);
    }

    function avisar(pedidos) {
        if (!pedidos.length) return;
        sonar();
        notificarEscritorio(pedidos[0]);
        toast(pedidos[0]);
        sinAvisar += pedidos.length;
        pintarBadge();
    }

    function consultar() {
        fetch("/api/pedidos/nuevos?desde=" + ultimoId, { credentials: "same-origin" })
            .then(function (r) { return r.ok ? r.json() : []; })
            .then(function (pedidos) {
                if (!Array.isArray(pedidos) || !pedidos.length) { pintarBadge(); return; }
                var maxId = Math.max.apply(null, pedidos.map(function (p) { return p.id; }));
                if (!baseListo) {
                    // Primera consulta: solo fija el punto de partida.
                    baseListo = true;
                } else {
                    avisar(pedidos);
                }
                ultimoId = Math.max(ultimoId, maxId);
                sessionStorage.setItem(CLAVE, String(ultimoId));
                pintarBadge();
            })
            .catch(function () { /* red caida: se reintenta en el proximo tick */ });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", consultar);
    } else {
        consultar();
    }
    setInterval(consultar, INTERVALO_MS);
    window.addEventListener("focus", pintarBadge);
})();
