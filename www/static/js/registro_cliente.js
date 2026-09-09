
        // --- Selects en cascada: departamento -> provincia -> distrito ---
        const depSel = document.getElementById('departamento');
        const provSel = document.getElementById('provincia');
        const distSel = document.getElementById('distrito');
        let departamentos = [];

        function llenar(select, items, placeholder) {
            select.innerHTML = '<option value="">' + placeholder + '</option>';
            items.forEach(function(it) {
                const opt = document.createElement('option');
                opt.value = it.nombre;
                opt.textContent = it.nombre;
                select.appendChild(opt);
            });
        }

        // Cargar departamentos al cargar la página
        fetch('/api/departamentos')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                departamentos = data;
                llenar(depSel, data, 'Seleccione departamento');
            });

        depSel.addEventListener('change', function() {
            provSel.innerHTML = '<option value="">Seleccione provincia</option>';
            distSel.innerHTML = '<option value="">Seleccione distrito</option>';
            const dep = departamentos.find(function(d) { return d.nombre === depSel.value; });
            if (!dep) return;
            fetch('/api/provincias/' + dep.id)
                .then(function(r) { return r.json(); })
                .then(function(provincias) { llenar(provSel, provincias, 'Seleccione provincia'); });
        });

        provSel.addEventListener('change', function() {
            distSel.innerHTML = '<option value="">Seleccione distrito</option>';
            const dep = departamentos.find(function(d) { return d.nombre === depSel.value; });
            if (!dep) return;
            fetch('/api/provincias/' + dep.id)
                .then(function(r) { return r.json(); })
                .then(function(provincias) {
                    const prov = provincias.find(function(p) { return p.nombre === provSel.value; });
                    if (!prov) return;
                    return fetch('/api/distritos/' + prov.id).then(function(r) { return r.json(); });
                })
                .then(function(distritos) {
                    if (!distritos) return;
                    llenar(distSel, distritos, 'Seleccione distrito');
                });
        });

        document.querySelector('form').addEventListener('submit', function(e) {
            let clave = document.querySelector('input[name="clave"]').value;
            let confirmar = document.getElementById('confirmar_clave').value;
            if (clave !== confirmar) {
                e.preventDefault();
                alert('❌ Las contraseñas no coinciden');
            }
        });
    