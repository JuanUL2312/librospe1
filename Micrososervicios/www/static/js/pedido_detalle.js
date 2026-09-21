
    (function() {
        'use strict';
        
        // Mejorar experiencia táctil en móviles
        if ('ontouchstart' in window) {
            // Feedback táctil para botones
            document.querySelectorAll('.btn, .form-select').forEach(element => {
                element.addEventListener('touchstart', function() {
                    if (this.classList && this.classList.contains('btn')) {
                        this.style.transform = 'scale(0.97)';
                    }
                    if (this.classList && this.classList.contains('form-select')) {
                        this.style.backgroundColor = '#f8f9fa';
                    }
                });
                element.addEventListener('touchend', function() {
                    if (this.classList && this.classList.contains('btn')) {
                        this.style.transform = '';
                    }
                    if (this.classList && this.classList.contains('form-select')) {
                        this.style.backgroundColor = '';
                    }
                });
            });
        }
        
        // Confirmación antes de cambiar estado del pedido (solo admin)
        const estadoForm = document.querySelector('form[action*="/pedidos/cambiar-estado/"]');
        if (estadoForm) {
            estadoForm.addEventListener('submit', function(e) {
                const select = this.querySelector('select[name="estado"]');
                const nuevoEstado = select.options[select.selectedIndex].text;
                
                if (confirm(`¿Estás seguro de que deseas ${nuevoEstado.toLowerCase()} este pedido?`)) {
                    // Mostrar loading
                    const submitBtn = this.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        const originalText = submitBtn.innerHTML;
                        submitBtn.disabled = true;
                        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
                        
                        // Restaurar después de 5 segundos por si hay error
                        setTimeout(() => {
                            if (submitBtn.disabled) {
                                submitBtn.disabled = false;
                                submitBtn.innerHTML = originalText;
                            }
                        }, 5000);
                    }
                } else {
                    e.preventDefault();
                }
            });
        }
    })();
