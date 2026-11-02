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

    var rolSistema = document.body ? document.body.getAttribute("data-rol-sistema") : "";
    if (rolSistema !== "administrador" && rolSistema !== "vendedor") return;

    var INTERVALO_MS = 5000;
    var CLAVE = "panel_ultimo_pedido_id";
    var CLAVE_SONIDO = "panel_sonido_pedidos";
    var baseListo = sessionStorage.getItem(CLAVE) !== null;
    var ultimoId = parseInt(sessionStorage.getItem(CLAVE) || "0", 10) || 0;
    var sinAvisar = 0;
    var audioActivo = localStorage.getItem(CLAVE_SONIDO) === "1";
    var contextoAudio = null;

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

    function actualizarBotonSonido() {
        var boton = document.getElementById("activarSonidoPedidos");
        if (!boton) return;
        boton.setAttribute("aria-pressed", audioActivo ? "true" : "false");
        boton.classList.toggle("btn-warning", audioActivo);
        boton.classList.toggle("btn-outline-warning", !audioActivo);
        boton.title = audioActivo ? "Sonido activado; clic para desactivar" : "Activar y probar el sonido de pedidos";
        boton.innerHTML = audioActivo
            ? '<i class="fas fa-volume-high me-1" aria-hidden="true"></i><span class="d-none d-sm-inline">Sonido activo</span>'
            : '<i class="fas fa-volume-xmark me-1" aria-hidden="true"></i><span class="d-none d-sm-inline">Activar sonido</span>';
    }

    function obtenerContextoAudio() {
        try {
            var Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            if (!contextoAudio) contextoAudio = new Ctx();
            return contextoAudio;
        } catch (e) { return null; }
    }

    function tono(ctx, frecuencia, inicio, duracion) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        gain.gain.setValueAtTime(0.0001, inicio);
        gain.gain.exponentialRampToValueAtTime(0.16, inicio + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, inicio + duracion);
        osc.frequency.setValueAtTime(frecuencia, inicio);
        osc.start(inicio);
        osc.stop(inicio + duracion + 0.02);
    }

    function sonar(prueba) {
        if (!audioActivo) return;
        var ctx = obtenerContextoAudio();
        if (!ctx) return;
        var reproducir = function () {
            var ahora = ctx.currentTime;
            tono(ctx, prueba ? 660 : 880, ahora, 0.16);
            tono(ctx, prueba ? 880 : 660, ahora + 0.2, 0.2);
        };
        if (ctx.state === "running") reproducir();
        else ctx.resume().then(reproducir).catch(function () {});
    }

    function activarSonido(probar) {
        audioActivo = true;
        localStorage.setItem(CLAVE_SONIDO, "1");
        actualizarBotonSonido();
        var ctx = obtenerContextoAudio();
        if (ctx) ctx.resume().then(function () { if (probar) sonar(true); }).catch(function () {});
        if ("Notification" in window && Notification.permission === "default") {
            Notification.requestPermission().catch(function () {});
        }
    }

    function desactivarSonido() {
        audioActivo = false;
        localStorage.setItem(CLAVE_SONIDO, "0");
        actualizarBotonSonido();
    }

    function desbloquearConInteraccion(evento) {
        if (!audioActivo && evento.target.closest && evento.target.closest("#activarSonidoPedidos")) return;
        if (!audioActivo) activarSonido(false);
        else {
            var ctx = obtenerContextoAudio();
            if (ctx && ctx.state !== "running") ctx.resume().catch(function () {});
        }
        document.removeEventListener("pointerdown", desbloquearConInteraccion);
        document.removeEventListener("keydown", desbloquearConInteraccion);
    }

    function notificarEscritorio(pedido) {
        try {
            if (!("Notification" in window) || Notification.permission !== "granted") return;
            var entrega = pedido.tipo_entrega === "delivery" ? "Delivery" : "Recojo en tienda";
            new Notification("Nuevo pedido #" + pedido.id, {
                body: entrega + " · " + pedido.cliente + " · S/ " + Number(pedido.total || 0).toFixed(2),
                tag: "pedido-" + pedido.id
            });
        } catch (e) { /* sin soporte */ }
    }

    function toast(pedido) {
        var t = document.createElement("div");
        t.className = "position-fixed top-0 end-0 m-3 px-3 py-2 bg-success text-white rounded-4 shadow-lg";
        t.style.zIndex = "9999";
        t.style.cursor = "pointer";
        t.style.fontSize = "0.85rem";
        var entrega = pedido.tipo_entrega === "delivery" ? "Delivery" : "Recojo en tienda";
        t.textContent = "🔔 Nuevo pedido #" + pedido.id + " · " + entrega + " · " +
            (pedido.cliente || "Cliente") + " · S/ " + Number(pedido.total || 0).toFixed(2);
        t.onclick = function () { window.location.href = "/pedidos"; };
        document.body.appendChild(t);
        setTimeout(function () { t.remove(); }, 10000);
    }

    function avisar(pedidos) {
        if (!pedidos.length) return;
        sonar(false);
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
            .catch(function () { /* red caída: reintentar en el próximo ciclo */ });
    }

    var botonSonido = document.getElementById("activarSonidoPedidos");
    if (botonSonido) {
        actualizarBotonSonido();
        botonSonido.addEventListener("click", function () {
            if (audioActivo) {
                desactivarSonido();
            } else {
                activarSonido(true);
            }
        });
    }
    document.addEventListener("pointerdown", desbloquearConInteraccion);
    document.addEventListener("keydown", desbloquearConInteraccion);

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", consultar);
    } else {
        consultar();
    }
    setInterval(consultar, INTERVALO_MS);
    window.addEventListener("focus", pintarBadge);
})();
