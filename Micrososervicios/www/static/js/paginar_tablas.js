/* Paginación automática para tablas HTML (LibrosPE).
 *
 * Aplica a cualquier <table> con más de 10 filas visibles:
 *   - selector de filas por página (10/25/50/100, recordado en localStorage)
 *   - botones numerados con "..." si hay muchas páginas
 *   - texto "Mostrando X–Y de Z"
 *
 * Convivencia con filtros de búsqueda en cliente (productos, stock-bajo,
 * categorías, etc.): al aplicar se respetan las filas que el filtro dejó
 * visibles y solo se pagina sobre ellas; cada entrada re-aplica con debounce.
 *
 * Tablas dinámicas (AJAX que reemplazan filas) se detectan con un
 * MutationObserver y se re-paginan solas.
 *
 * Exclusión: <table data-sin-paginar> (p. ej. tablas de comprobante/POS).
 */
(function () {
    'use strict';

    var UMBRAL = 10;                 // solo pagina si hay más de 10 filas
    var CLASE = 'paginador-tabla';   // clase del bloque de controles
    var CLAVE_POR_PAGINA = 'librospe_paginador_por_pagina';
    var estados = Object.create(null); // idTabla -> { pagina, porPagina }
    var controles = Object.create(null); // idTabla -> elemento control
    var aplicando = false;
    var contadorIds = 0;

    // ---------------- utilidades ----------------

    function idDe(tabla) {
        if (!tabla.__pgId) {
            tabla.__pgId = tabla.id ? ('t:' + tabla.id) : ('auto:' + (++contadorIds));
        }
        return tabla.__pgId;
    }

    function porPaginaGuardado() {
        var v = 10;
        try {
            v = parseInt(localStorage.getItem(CLAVE_POR_PAGINA), 10);
        } catch (e) { /* modo privado / storage bloqueado */ }
        return (v === 10 || v === 25 || v === 50 || v === 100) ? v : 10;
    }

    function estadoDe(tabla) {
        var id = idDe(tabla);
        if (!estados[id]) {
            estados[id] = { pagina: 1, porPagina: porPaginaGuardado() };
        }
        return estados[id];
    }

    function filasDe(tabla) {
        return tabla.tBodies.length ? Array.prototype.slice.call(tabla.tBodies[0].rows) : [];
    }

    function quitarControl(tabla) {
        var id = idDe(tabla);
        var ctrl = controles[id];
        if (ctrl && ctrl.parentNode) ctrl.parentNode.removeChild(ctrl);
        delete controles[id];
    }

    // ---------------- aplicación principal ----------------

    function aplicar(tabla) {
        if (tabla.hasAttribute('data-sin-paginar')) return;
        var filas = filasDe(tabla);
        if (!filas.length) { quitarControl(tabla); return; }

        // 1) Deshacer lo que el paginador ocultó (restaura el estado real del filtro)
        filas.forEach(function (f) {
            if (f.getAttribute('data-pag-oculto') !== null) {
                f.style.display = '';
                f.removeAttribute('data-pag-oculto');
            }
        });

        // 2) Filas visibles = las que el filtro de búsqueda dejó pasar
        var visibles = filas.filter(function (f) { return f.style.display !== 'none'; });

        if (visibles.length <= UMBRAL) {
            quitarControl(tabla);
            return;
        }

        var est = estadoDe(tabla);
        var totalPaginas = Math.max(1, Math.ceil(visibles.length / est.porPagina));
        if (est.pagina > totalPaginas) est.pagina = totalPaginas;
        if (est.pagina < 1) est.pagina = 1;
        var ini = (est.pagina - 1) * est.porPagina;
        var fin = Math.min(ini + est.porPagina, visibles.length);

        aplicando = true;
        try {
            visibles.forEach(function (f, i) {
                if (i >= ini && i < fin) {
                    if (f.getAttribute('data-pag-oculto') !== null) {
                        f.style.display = '';
                        f.removeAttribute('data-pag-oculto');
                    }
                } else {
                    f.style.display = 'none';
                    f.setAttribute('data-pag-oculto', '1');
                }
            });
        } finally {
            // el flag se libera después del pintado (también muta el DOM)
            setTimeout(function () { aplicando = false; }, 0);
        }

        pintarControl(tabla, visibles.length, ini + 1, fin, totalPaginas, est);
    }

    // ---------------- control de paginación ----------------

    function rangoPaginas(pagina, total) {
        // [1, ..., 4, 5, 6, ..., 20]
        var salida = [];
        if (total <= 7) {
            for (var i = 1; i <= total; i++) salida.push(i);
            return salida;
        }
        salida.push(1);
        var desde = Math.max(2, pagina - 2);
        var hasta = Math.min(total - 1, pagina + 2);
        if (desde > 2) salida.push('...');
        for (var p = desde; p <= hasta; p++) salida.push(p);
        if (hasta < total - 1) salida.push('...');
        salida.push(total);
        return salida;
    }

    function pintarControl(tabla, totalFilas, desde, hasta, totalPaginas, est) {
        var id = idDe(tabla);
        var ctrl = controles[id];
        // El nodo pudo quedar huérfano tras una recarga AJAX del contenedor.
        if (ctrl && !ctrl.parentNode) {
            delete controles[id];
            ctrl = null;
        }
        if (!ctrl) {
            ctrl = document.createElement('div');
            ctrl.className = CLASE + ' d-flex flex-wrap align-items-center gap-2 mt-2 mb-3 justify-content-end';
            ctrl.setAttribute('data-tabla', id);
            controles[id] = ctrl;
            var ancla = tabla.closest('.table-responsive') || tabla;
            ancla.parentNode.insertBefore(ctrl, ancla.nextSibling);
        }

        var pagina = est.pagina;
        var html = '';

        html += '<span class="text-muted small">' +
            '<i class="fas fa-list me-1"></i>Mostrando ' + desde + '–' + hasta +
            ' de ' + totalFilas + '</span>';

        html += '<select class="form-select form-select-sm w-auto" data-pg="porpagina" title="Filas por página">' +
            [10, 25, 50, 100].map(function (n) {
                return '<option value="' + n + '"' + (n === est.porPagina ? ' selected' : '') + '>' + n + '</option>';
            }).join('') + '</select>';

        html += '<ul class="pagination pagination-sm mb-0 flex-wrap">';
        html += '<li class="page-item' + (pagina <= 1 ? ' disabled' : '') + '">' +
            '<a class="page-link" href="#" data-pg="ir" data-p="' + (pagina - 1) + '" aria-label="Anterior">&laquo;</a></li>';
        rangoPaginas(pagina, totalPaginas).forEach(function (p) {
            if (p === '...') {
                html += '<li class="page-item disabled"><span class="page-link">…</span></li>';
            } else {
                html += '<li class="page-item' + (p === pagina ? ' active' : '') + '">' +
                    '<a class="page-link" href="#" data-pg="ir" data-p="' + p + '">' + p + '</a></li>';
            }
        });
        html += '<li class="page-item' + (pagina >= totalPaginas ? ' disabled' : '') + '">' +
            '<a class="page-link" href="#" data-pg="ir" data-p="' + (pagina + 1) + '" aria-label="Siguiente">&raquo;</a></li>';
        html += '</ul>';

        ctrl.innerHTML = html;
    }

    // ---------------- eventos ----------------

    function tablaDeControl(elem) {
        var ctrl = elem.closest('.' + CLASE);
        if (!ctrl) return null;
        var id = ctrl.getAttribute('data-tabla');
        var tablas = document.querySelectorAll('table');
        for (var i = 0; i < tablas.length; i++) {
            if (idDe(tablas[i]) === id) return tablas[i];
        }
        return null;
    }

    document.addEventListener('click', function (ev) {
        var enlace = ev.target.closest ? ev.target.closest('[data-pg="ir"]') : null;
        if (!enlace) return;
        ev.preventDefault();
        var tabla = tablaDeControl(enlace);
        if (!tabla) return;
        var est = estadoDe(tabla);
        est.pagina = parseInt(enlace.getAttribute('data-p'), 10) || 1;
        aplicar(tabla);
    }, true);

    document.addEventListener('change', function (ev) {
        if (!ev.target || ev.target.getAttribute('data-pg') !== 'porpagina') return;
        var tabla = tablaDeControl(ev.target);
        if (!tabla) return;
        var est = estadoDe(tabla);
        est.porPagina = parseInt(ev.target.value, 10) || 10;
        est.pagina = 1;
        try { localStorage.setItem(CLAVE_POR_PAGINA, String(est.porPagina)); } catch (e) { /* sin storage */ }
        aplicar(tabla);
    }, true);

    // Filtros en cliente (inputs de búsqueda, selects): re-paginar con debounce
    // y volver a la página 1. Solo se consideran inputs de búsqueda FUERA de
    // filas (para no molestar mientras se capturan conteos o cantidades).
    var tFiltro = null;
    function rePaginarTrasFiltro() {
        for (var k in estados) estados[k].pagina = 1;
        clearTimeout(tFiltro);
        tFiltro = setTimeout(aplicarTodas, 200);
    }
    document.addEventListener('input', function (ev) {
        var t = ev.target;
        if (!t || t.tagName !== 'INPUT') return;
        var tipo = (t.type || 'text').toLowerCase();
        if (tipo !== 'text' && tipo !== 'search') return;
        if (t.closest && t.closest('td, th')) return;
        rePaginarTrasFiltro();
    }, true);
    document.addEventListener('change', function (ev) {
        var t = ev.target;
        if (!t || t.tagName !== 'SELECT') return;
        if (t.getAttribute('data-pg') === 'porpagina') return;
        if (t.closest && t.closest('td, th')) return;
        rePaginarTrasFiltro();
    }, true);

    function podarControles() {
        var vivos = Object.create(null);
        var tablas = document.querySelectorAll('table');
        for (var i = 0; i < tablas.length; i++) vivos[idDe(tablas[i])] = true;
        for (var k in controles) {
            var ctrl = controles[k];
            if (!vivos[k] || !ctrl.parentNode) {
                if (ctrl.parentNode) ctrl.parentNode.removeChild(ctrl);
                delete controles[k];
            }
        }
    }

    function aplicarTodas() {
        podarControles();
        var tablas = document.querySelectorAll('table:not([data-sin-paginar])');
        for (var i = 0; i < tablas.length; i++) {
            try { aplicar(tablas[i]); } catch (e) { /* tabla rara: no romper la página */ }
        }
    }

    // Tablas dinámicas (AJAX): filas reemplazadas -> re-paginar.
    function observar() {
        if (!window.MutationObserver) return;
        var tMut = null;
        var obs = new MutationObserver(function () {
            if (aplicando) return;
            clearTimeout(tMut);
            tMut = setTimeout(aplicarTodas, 250);
        });
        obs.observe(document.body, { childList: true, subtree: true });
    }

    function iniciar() {
        aplicarTodas();
        observar();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
