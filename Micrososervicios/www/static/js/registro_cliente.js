
        function togglePassword(inputId, iconId) {
            const input = document.getElementById(inputId);
            const icon = document.getElementById(iconId);
            if (!input) return;
            if (input.type === 'password') {
                input.type = 'text';
                if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
            } else {
                input.type = 'password';
                if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
            }
        }

        // --- Tipo de documento: DNI / Carnet de Extranjería ---
        const tipoDocSel = document.getElementById('tipo_documento');
        const numeroDocInput = document.getElementById('numero_documento');
        const numeroDocLabel = document.getElementById('numeroDocLabel');
        const nombresInput = document.getElementById('nombresInput');
        const apellidosInput = document.getElementById('apellidosInput');

        // Sombrea (y bloquea) los campos de nombre/apellidos cuando el dato
        // viene de RENIEC, para que se vea que NO se pueden editar.
        function aplicarBloqueoNombre(bloquear, mensajeHint, esError) {
            [nombresInput, apellidosInput].forEach(function(campo) {
                if (!campo) return;
                campo.readOnly = !!bloquear;
                campo.classList.toggle('campo-bloqueado', !!bloquear);
            });
            const hint = document.getElementById('nombresHint');
            if (hint && mensajeHint) {
                hint.textContent = mensajeHint;
                hint.classList.remove('text-muted', 'text-success', 'text-warning');
                hint.classList.add(esError ? 'text-warning' : (bloquear ? 'text-success' : 'text-muted'));
            }
        }

        // true si los nombres actuales vienen de RENIEC (no escritos a mano).
        var nombreDesdeReniec = false;
        if (nombresInput) {
            nombresInput.addEventListener('input', function () { nombreDesdeReniec = false; });
        }
        if (apellidosInput) {
            apellidosInput.addEventListener('input', function () { nombreDesdeReniec = false; });
        }
        // Limpia los nombres auto-completados (no los escritos a mano).
        function limpiarNombresAutoCompletados() {
            if (!nombreDesdeReniec) return;
            if (nombresInput) nombresInput.value = '';
            if (apellidosInput) apellidosInput.value = '';
            nombreDesdeReniec = false;
        }

        function cambiarTipoDocumentoRegistro() {
            const esCE = tipoDocSel && tipoDocSel.value === 'CE';
            if (!numeroDocInput) return;
            if (esCE) {
                numeroDocLabel.textContent = 'Carnet de Extranjería *';
                numeroDocInput.placeholder = '9 caracteres (letras y números)';
                numeroDocInput.maxLength = 9;
                if (nombresInput) nombresInput.placeholder = 'Ingrese nombres';
                if (apellidosInput) apellidosInput.placeholder = 'Ingrese apellidos';
                aplicarBloqueoNombre(false, 'Carnet de Extranjería: ingrese los nombres manualmente.');
            } else {
                numeroDocLabel.textContent = 'DNI *';
                numeroDocInput.placeholder = '12345678';
                numeroDocInput.maxLength = 8;
                if (nombresInput) nombresInput.placeholder = 'Se autocompletará con DNI';
                if (apellidosInput) apellidosInput.placeholder = 'Se autocompletará con DNI';
                aplicarBloqueoNombre(true, 'Ingresa DNI para cargar nombres automáticamente.');
            }
            numeroDocInput.value = '';
            if (nombresInput) nombresInput.value = '';
            if (apellidosInput) apellidosInput.value = '';
            nombreDesdeReniec = false;
        }

        async function consultarDniCliente() {
            const esCE = tipoDocSel && tipoDocSel.value === 'CE';
            if (esCE) {
                aplicarBloqueoNombre(false, 'Carnet de Extranjería: ingrese los nombres manualmente.');
                return;
            }
            const val = numeroDocInput ? numeroDocInput.value.trim() : '';
            if (val.length !== 8 || !/^\d{8}$/.test(val)) {
                if (nombresInput) nombresInput.value = '';
                if (apellidosInput) apellidosInput.value = '';
                aplicarBloqueoNombre(true, 'Ingresa DNI para cargar nombres automáticamente.');
                return;
            }
            const loading = document.getElementById('docLoading');
            const errorDiv = document.getElementById('docError');
            if (loading) loading.style.display = 'block';
            if (errorDiv) errorDiv.style.display = 'none';
            try {
                const res = await fetch('/api/public/consultar-dni/' + val);
                const data = await res.json();
                if (loading) loading.style.display = 'none';
                if (data.success && data.nombres) {
                    if (nombresInput) nombresInput.value = data.nombres;
                    if (apellidosInput) apellidosInput.value = data.apellidos || '';
                    nombreDesdeReniec = true;
                    // Nombre encontrado en RENIEC: se sombrea y no se puede editar.
                    aplicarBloqueoNombre(true, 'Nombre cargado desde RENIEC (no editable).');
                } else {
                    limpiarNombresAutoCompletados();
                    if (nombresInput) nombresInput.placeholder = 'No encontrado, ingrese manualmente';
                    if (apellidosInput) apellidosInput.placeholder = 'No encontrado, ingrese manualmente';
                    aplicarBloqueoNombre(false, 'No se encontró en RENIEC, puedes editar manualmente.', true);
                    if (errorDiv) { errorDiv.style.display='block'; errorDiv.textContent='⚠️ DNI no encontrado, ingrese nombres manualmente.'; }
                }
            } catch(e) {
                if (loading) loading.style.display='none';
                aplicarBloqueoNombre(false, 'No se pudo consultar RENIEC, ingrese los nombres manualmente.', true);
            }
        }

        if (numeroDocInput) {
            numeroDocInput.addEventListener('input', function () {
                const esCE = tipoDocSel && tipoDocSel.value === 'CE';
                const filtered = esCE
                    ? this.value.replace(/[^A-Za-z0-9]/g, '').slice(0, 9)
                    : this.value.replace(/\D/g, '').slice(0, 8);
                this.value = filtered;
                if ((esCE && this.value.length === 9) || (!esCE && this.value.length === 8)) {
                    consultarDniCliente();
                } else if (!esCE && this.value.length < 8) {
                    if (nombresInput) nombresInput.value = '';
                    if (apellidosInput) apellidosInput.value = '';
                    nombreDesdeReniec = false;
                    aplicarBloqueoNombre(true, 'Ingresa DNI para cargar nombres automáticamente.');
                }
            });
            numeroDocInput.addEventListener('blur', consultarDniCliente);
        }
        // Inicializa readonly (sombreado) para DNI
        aplicarBloqueoNombre(true, 'Ingresa DNI para cargar nombres automáticamente.');

        // --- Ubigeo: departamento -> provincia -> distrito ---
        // La plantilla nueva fija Departamento (JUNIN) y Provincia (HUANCAYO) como
        // inputs readonly y deja elegir solo el Distrito. La plantilla antigua usa
        // selects en cascada. Se soportan ambas para no romper durante el despliegue
        // (las plantillas quedan cacheadas hasta que la app se reinicia).
        const depEl = document.getElementById('departamento');
        const provEl = document.getElementById('provincia');
        const distSel = document.getElementById('distrito');
        const DEP_FIJO = 'JUNIN';
        const PROV_FIJA = 'HUANCAYO';
        const depEsSelect = depEl && depEl.tagName === 'SELECT';

        function llenar(select, items, placeholder) {
            select.innerHTML = '<option value="">' + placeholder + '</option>';
            items.forEach(function(it) {
                const opt = document.createElement('option');
                opt.value = it.nombre;
                opt.textContent = it.nombre;
                select.appendChild(opt);
            });
        }

        function cargarDistritos(provId) {
            return fetch('/api/distritos/' + provId)
                .then(function(r) { return r.json(); })
                .then(function(distritos) {
                    if (distritos && distSel) llenar(distSel, distritos, 'Seleccione distrito');
                });
        }

        if (depEsSelect) {
            // --- Plantilla antigua: selects en cascada editables ---
            let departamentos = [];
            fetch('/api/departamentos')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    departamentos = data;
                    llenar(depEl, data, 'Seleccione departamento');
                });

            depEl.addEventListener('change', function() {
                provEl.innerHTML = '<option value="">Seleccione provincia</option>';
                distSel.innerHTML = '<option value="">Seleccione distrito</option>';
                const dep = departamentos.find(function(d) { return d.nombre === depEl.value; });
                if (!dep) return;
                fetch('/api/provincias/' + dep.id)
                    .then(function(r) { return r.json(); })
                    .then(function(provincias) { llenar(provEl, provincias, 'Seleccione provincia'); });
            });

            provEl.addEventListener('change', function() {
                distSel.innerHTML = '<option value="">Seleccione distrito</option>';
                const dep = departamentos.find(function(d) { return d.nombre === depEl.value; });
                if (!dep) return;
                fetch('/api/provincias/' + dep.id)
                    .then(function(r) { return r.json(); })
                    .then(function(provincias) {
                        const prov = provincias.find(function(p) { return p.nombre === provEl.value; });
                        if (!prov) return;
                        cargarDistritos(prov.id);
                    });
            });
        } else {
            // --- Plantilla nueva: JUNIN/HUANCAYO fijos, solo distrito editable ---
            fetch('/api/departamentos')
                .then(function(r) { return r.json(); })
                .then(function(departamentos) {
                    const dep = (departamentos || []).find(function(d) {
                        return String(d.nombre).toUpperCase() === DEP_FIJO;
                    });
                    if (!dep) return null;
                    if (depEl) depEl.value = dep.nombre;
                    return fetch('/api/provincias/' + dep.id).then(function(r) { return r.json(); });
                })
                .then(function(provincias) {
                    if (!provincias) return null;
                    const prov = provincias.find(function(p) {
                        return String(p.nombre).toUpperCase() === PROV_FIJA;
                    });
                    if (!prov) return null;
                    if (provEl) provEl.value = prov.nombre;
                    return cargarDistritos(prov.id);
                });
        }

        document.querySelector('form').addEventListener('submit', function(e) {
            let clave = document.querySelector('input[name="clave"]').value;
            let confirmar = document.getElementById('confirmar_clave').value;
            if (clave !== confirmar) {
                e.preventDefault();
                alert('❌ Las contraseñas no coinciden');
            }
        });
    