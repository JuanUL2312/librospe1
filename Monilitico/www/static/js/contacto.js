
    (() => {
        'use strict';
        
        // Validación del formulario
        const forms = document.querySelectorAll('.needs-validation');
        
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                event.preventDefault();
                event.stopPropagation();
                
                if (!form.checkValidity()) {
                    form.classList.add('was-validated');
                    return;
                }
                
                // Simular envío (aquí iría la llamada AJAX real)
                const submitBtn = form.querySelector('button[type="submit"]');
                const originalText = submitBtn.innerHTML;
                
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Enviando...';
                
                // Simular envío (reemplazar con fetch real)
                setTimeout(() => {
                    // Ocultar formulario y mostrar éxito
                    document.getElementById('mensajeExito').style.display = 'block';
                    form.reset();
                    form.classList.remove('was-validated');
                    
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                    
                    // Ocultar mensaje después de 5 segundos
                    setTimeout(() => {
                        const mensajeExito = document.getElementById('mensajeExito');
                        if (mensajeExito) {
                            mensajeExito.style.display = 'none';
                        }
                    }, 5000);
                }, 1500);
                
                // Para envío real, usar este código:
                /*
                const formData = new FormData(form);
                fetch('/api/contacto', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('mensajeExito').style.display = 'block';
                        form.reset();
                        form.classList.remove('was-validated');
                    }
                })
                .finally(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                });
                */
            });
        });
        
        // Validación en tiempo real para inputs
        const inputs = document.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
        });
    })();
    
    // Mejorar experiencia táctil en móviles
    if ('ontouchstart' in window) {
        document.querySelectorAll('.btn, .card').forEach(element => {
            element.addEventListener('touchstart', function() {
                // Solo para botones
                if (this.classList && this.classList.contains('btn')) {
                    this.style.transform = 'scale(0.97)';
                }
            });
            element.addEventListener('touchend', function() {
                if (this.classList && this.classList.contains('btn')) {
                    this.style.transform = '';
                }
            });
        });
    }
