
    (function() {
        'use strict';
        
        const form = document.getElementById('resetForm');
        const emailInput = document.getElementById('emailInput');
        const submitBtn = document.getElementById('submitBtn');
        
        // Validación en tiempo real del email
        if (emailInput) {
            emailInput.addEventListener('input', function() {
                const email = this.value.trim();
                const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
                
                if (email === '') {
                    this.classList.remove('is-valid', 'is-invalid');
                } else if (isValid) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
        }
        
        // Validación al enviar el formulario
        if (form) {
            form.addEventListener('submit', function(event) {
                const email = emailInput.value.trim();
                let isValid = true;
                
                // Validar email
                if (!email) {
                    emailInput.classList.add('is-invalid');
                    isValid = false;
                } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                    emailInput.classList.add('is-invalid');
                    isValid = false;
                } else {
                    emailInput.classList.remove('is-invalid');
                    emailInput.classList.add('is-valid');
                }
                
                if (!isValid) {
                    event.preventDefault();
                    event.stopPropagation();
                    
                    // Mostrar mensaje de error
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'alert alert-danger alert-dismissible fade show mt-3';
                    errorDiv.innerHTML = `
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Por favor ingresa un correo electrónico válido
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    `;
                    form.insertBefore(errorDiv, form.querySelector('.d-grid'));
                    
                    // Auto cerrar después de 3 segundos
                    setTimeout(() => {
                        if (errorDiv && errorDiv.remove) errorDiv.remove();
                    }, 3000);
                } else {
                    // Mostrar estado de carga
                    if (submitBtn) {
                        const originalText = submitBtn.innerHTML;
                        submitBtn.disabled = true;
                        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Enviando...';
                        
                        // Restaurar después de 10 segundos por si hay error
                        setTimeout(() => {
                            if (submitBtn.disabled) {
                                submitBtn.disabled = false;
                                submitBtn.innerHTML = originalText;
                            }
                        }, 10000);
                    }
                }
                
                form.classList.add('was-validated');
            });
        }
        
        // Prevenir envíos duplicados
        if (submitBtn) {
            form.addEventListener('submit', function() {
                if (submitBtn.disabled) {
                    event.preventDefault();
                }
            });
        }
    })();
    
    // Mejorar experiencia táctil en móviles
    if ('ontouchstart' in window) {
        document.querySelectorAll('.btn').forEach(element => {
            element.addEventListener('touchstart', function() {
                if (!this.disabled) {
                    this.style.transform = 'scale(0.97)';
                }
            });
            element.addEventListener('touchend', function() {
                this.style.transform = '';
            });
            element.addEventListener('touchcancel', function() {
                this.style.transform = '';
            });
        });
    }
    
    // Limpiar estado de validación al hacer foco
    if (emailInput) {
        emailInput.addEventListener('focus', function() {
            this.classList.remove('is-invalid');
        });
    }
