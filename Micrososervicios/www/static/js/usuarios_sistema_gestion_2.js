
    $(document).ready(function() {
        $('#tabla-usuarios').DataTable({
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/es-ES.json'
            },
            order: [[0, 'asc']],
            pageLength: 25
        });
    });

    document.addEventListener('click', function(event) {
        const boton = event.target.closest('[data-password-toggle]');
        if (!boton) return;
        const campo = document.getElementById(boton.dataset.passwordToggle);
        if (!campo) return;
        const mostrar = campo.type === 'password';
        campo.type = mostrar ? 'text' : 'password';
        boton.setAttribute('aria-label', (mostrar ? 'Ocultar' : 'Mostrar') + ' contraseña');
        boton.title = (mostrar ? 'Ocultar' : 'Mostrar') + ' contraseña';
        const icono = boton.querySelector('i');
        if (icono) {
            icono.classList.toggle('fa-eye', !mostrar);
            icono.classList.toggle('fa-eye-slash', mostrar);
        }
    });

    function validarCoincidenciaClave(form) {
        const nueva = form.querySelector('[name="nueva"]');
        const confirmar = form.querySelector('[name="confirmar"]');
        const estado = form.querySelector('[data-coincidencia-clave]');
        if (!nueva || !confirmar || !estado) return true;

        if (!confirmar.value) {
            confirmar.setCustomValidity('');
            estado.textContent = '';
            estado.className = 'form-text';
            return true;
        }

        const coincide = nueva.value === confirmar.value;
        const mensaje = coincide ? 'Las contraseñas coinciden.' : 'Las contraseñas no coinciden.';
        confirmar.setCustomValidity(coincide ? '' : mensaje);
        estado.textContent = mensaje;
        estado.className = coincide ? 'form-text text-success' : 'form-text text-danger';
        return coincide;
    }

    document.addEventListener('input', function(event) {
        if (!event.target.matches('.form-cambio-clave [name="nueva"], .form-cambio-clave [name="confirmar"]')) return;
        validarCoincidenciaClave(event.target.closest('.form-cambio-clave'));
    });

    document.addEventListener('submit', function(event) {
        const form = event.target.closest('.form-cambio-clave');
        if (!form || validarCoincidenciaClave(form)) return;
        event.preventDefault();
        form.querySelector('[name="confirmar"]').reportValidity();
    });
