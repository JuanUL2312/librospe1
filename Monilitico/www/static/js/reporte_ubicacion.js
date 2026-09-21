// ============================================================
// Reporte de Ventas por Ubicación - filtros en cascada (AJAX)
// Sin recargar la página: departamento -> provincia -> distrito
// ============================================================
(function () {
    const estado = document.getElementById('ubigeoEstado');
    if (!estado) return;

    const depSel = document.getElementById('filtroDepartamento');
    const provSel = document.getElementById('filtroProvincia');
    const distSel = document.getElementById('filtroDistrito');
    const periodoSel = document.getElementById('filtroPeriodo');
    const resultados = document.getElementById('ubicacionResultados');
    const btnFiltrar = document.getElementById('btnFiltrar');
    const formulario = document.getElementById('filtroForm');

    // Valores que el servidor mostró al cargar la página (solo se aplican una vez)
    const estadoInicial = {
        dep: estado.dataset.dep || '',
        prov: estado.dataset.prov || '',
        dist: estado.dataset.dist || ''
    };

    let departamentos = [];
    let provinciasCache = {};

    function llenar(select, items) {
        select.innerHTML = '';
        items.forEach(function (it) {
            const opt = document.createElement('option');
            opt.value = it;
            opt.textContent = it;
            select.appendChild(opt);
        });
    }

    // Mantiene los enlaces de PDF/Excel alineados con los filtros actuales
    function actualizarExport() {
        const params = new URLSearchParams();
        params.set('periodo', periodoSel.value);
        if (depSel.value) params.set('departamento', depSel.value);
        if (provSel.value) params.set('provincia', provSel.value);
        if (distSel.value) params.set('distrito', distSel.value);
        const pdf = document.getElementById('btnExportPdf');
        const xls = document.getElementById('btnExportExcel');
        if (pdf) pdf.href = '/reportes/ventas_por_ubicacion/pdf?' + params.toString();
        if (xls) xls.href = '/reportes/ventas_por_ubicacion/excel?' + params.toString();
    }

    // Recarga solo la tabla del reporte vía AJAX
    function aplicarFiltroUbicacion() {
        const fd = new FormData();
        fd.append('periodo', periodoSel.value);
        fd.append('departamento', depSel.value || '');
        fd.append('provincia', provSel.value || '');
        fd.append('distrito', distSel.value || '');

        resultados.innerHTML =
            '<div class="text-center py-8"><div class="spinner-border text-primary" style="width:3rem;height:3rem;"></div>' +
            '<p class="mt-3 text-muted fw-bold">Cargando reporte...</p></div>';

        fetch('/reportes/ventas_por_ubicacion/fragmento', {
            method: 'POST',
            credentials: 'same-origin',
            body: fd,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
            .then(function (html) {
                resultados.innerHTML = html;
                actualizarExport();
            })
            .catch(function () {
                resultados.innerHTML =
                    '<div class="alert alert-danger text-center py-5 fw-bold">❌ Error al cargar el reporte. Inténtalo de nuevo.</div>';
            });
    }

    function cargarDistritos(restaurar) {
        distSel.disabled = true;
        distSel.innerHTML = '<option value="">Todos los distritos</option>';
        const dep = departamentos.find(function (d) { return d.nombre === depSel.value; });
        if (!dep) return;
        const prov = (provinciasCache[dep.id] || []).find(function (p) { return p.nombre === provSel.value; });
        if (!prov) return;
        fetch('/api/distritos/' + prov.id)
            .then(function (r) { return r.json(); })
            .then(function (distritos) {
                llenar(distSel, distritos.map(function (d) { return d.nombre; }));
                distSel.disabled = false;
                if (restaurar && estadoInicial.dist &&
                    distritos.some(function (d) { return d.nombre === estadoInicial.dist; })) {
                    distSel.value = estadoInicial.dist;
                }
            });
    }

    function cargarProvincias(restaurar) {
        provSel.disabled = true;
        distSel.disabled = true;
        provSel.innerHTML = '<option value="">Todas las provincias</option>';
        distSel.innerHTML = '<option value="">Todos los distritos</option>';
        const dep = departamentos.find(function (d) { return d.nombre === depSel.value; });
        if (!dep) return;
        fetch('/api/provincias/' + dep.id)
            .then(function (r) { return r.json(); })
            .then(function (provincias) {
                provinciasCache[dep.id] = provincias;
                llenar(provSel, provincias.map(function (p) { return p.nombre; }));
                provSel.disabled = false;
                if (restaurar && estadoInicial.prov &&
                    provincias.some(function (p) { return p.nombre === estadoInicial.prov; })) {
                    provSel.value = estadoInicial.prov;
                    cargarDistritos(true);
                }
            });
    }

    function cargarDepartamentos() {
        fetch('/api/departamentos')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                departamentos = data;
                llenar(depSel, data.map(function (d) { return d.nombre; }));
                if (estadoInicial.dep &&
                    data.some(function (d) { return d.nombre === estadoInicial.dep; })) {
                    depSel.value = estadoInicial.dep;
                    cargarProvincias(true);
                }
                actualizarExport();
            });
    }

    // --- Eventos ---
    depSel.addEventListener('change', function () {
        cargarProvincias(false);
        aplicarFiltroUbicacion();
    });

    provSel.addEventListener('change', function () {
        cargarDistritos(false);
        aplicarFiltroUbicacion();
    });

    distSel.addEventListener('change', function () {
        aplicarFiltroUbicacion();
    });

    periodoSel.addEventListener('change', function () {
        aplicarFiltroUbicacion();
    });

    if (btnFiltrar) {
        btnFiltrar.addEventListener('click', function () {
            aplicarFiltroUbicacion();
        });
    }

    if (formulario) {
        formulario.addEventListener('submit', function (e) {
            e.preventDefault();
            aplicarFiltroUbicacion();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        cargarDepartamentos();
        actualizarExport();
    });
})();