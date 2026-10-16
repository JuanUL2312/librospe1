
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

        function cambiarTipoDocumentoRegistro() {
            const esCE = tipoDocSel && tipoDocSel.value === 'CE';
            if (!numeroDocInput) return;
            if (esCE) {
                numeroDocLabel.textContent = 'Carnet de Extranjería *';
                numeroDocInput.placeholder = '9 caracteres (letras y números)';
                numeroDocInput.maxLength = 9;
                if (nombresInput) { nombresInput.readOnly = false; nombresInput.placeholder = 'Ingrese nombres'; }
                if (apellidosInput) { apellidosInput.readOnly = false; apellidosInput.placeholder = 'Ingrese apellidos'; }
            } else {
                numeroDocLabel.textContent = 'DNI *';
                numeroDocInput.placeholder = '12345678';
                numeroDocInput.maxLength = 8;
                if (nombresInput) { nombresInput.readOnly = true; nombresInput.placeholder = 'Se autocompletará con DNI'; }
                if (apellidosInput) { apellidosInput.readOnly = true; apellidosInput.placeholder = 'Se autocompletará con DNI'; }
            }
            numeroDocInput.value = '';
            if (nombresInput) nombresInput.value = '';
            if (apellidosInput) apellidosInput.value = '';
        }

        async function consultarDniCliente() {
            const esCE = tipoDocSel && tipoDocSel.value === 'CE';
            if (esCE) {
                if (nombresInput) nombresInput.readOnly = false;
                if (apellidosInput) apellidosInput.readOnly = false;
                return;
            }
            const val = numeroDocInput ? numeroDocInput.value.trim() : '';
            if (val.length !== 8 || !/^\d{8}$/.test(val)) {
                if (nombresInput) { nombresInput.value = ''; nombresInput.readOnly = true; }
                if (apellidosInput) { apellidosInput.value = ''; apellidosInput.readOnly = true; }
                return;
            }
            const loading = document.getElementById('docLoading');
            const errorDiv = document.getElementById('docError');
            const hint = document.getElementById('nombresHint');
            if (loading) loading.style.display = 'block';
            if (errorDiv) errorDiv.style.display = 'none';
            try {
                const res = await fetch('/api/public/consultar-dni/' + val);
                const data = await res.json();
                if (loading) loading.style.display = 'none';
                if (data.success && data.nombres) {
                    if (nombresInput) { nombresInput.value = data.nombres; nombresInput.readOnly = true; }
                    if (apellidosInput) { apellidosInput.value = data.apellidos || ''; apellidosInput.readOnly = true; }
                    if (hint) hint.textContent = 'Nombre cargado desde RENIEC (no editable).';
                } else {
                    if (nombresInput) { nombresInput.readOnly = false; nombresInput.placeholder = 'No encontrado, ingrese manualmente'; }
                    if (apellidosInput) { apellidosInput.readOnly = false; apellidosInput.placeholder = 'No encontrado, ingrese manualmente'; }
                    if (hint) hint.textContent = 'No se encontró en RENIEC, puedes editar manualmente.';
                    if (errorDiv) { errorDiv.style.display='block'; errorDiv.textContent='⚠️ DNI no encontrado, ingrese nombres manualmente.'; }
                }
            } catch(e) {
                if (loading) loading.style.display='none';
                if (nombresInput) nombresInput.readOnly = false;
                if (apellidosInput) apellidosInput.readOnly = false;
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
                    if (nombresInput) { nombresInput.value=''; nombresInput.readOnly=true; }
                    if (apellidosInput) { apellidosInput.value=''; apellidosInput.readOnly=true; }
                }
            });
            numeroDocInput.addEventListener('blur', consultarDniCliente);
        }
        // Inicializa readonly para DNI
        if (nombresInput) nombresInput.readOnly = true;
        if (apellidosInput) apellidosInput.readOnly = true;

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
    