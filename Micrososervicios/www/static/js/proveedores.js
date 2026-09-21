
  // Función de confirmación mejorada para eliminación
  function confirmarEliminacion(nombre) {
    return confirm(`¿Estás seguro de que deseas eliminar al proveedor "${nombre}"?\n\nEsta acción no se puede deshacer.`);
  }
  
  // Función para filtrar proveedores (opcional, si se añade búsqueda)
  function filtrarProveedores() {
    const busqueda = document.getElementById('buscarProveedor');
    if (!busqueda) return;
    
    const termino = busqueda.value.toLowerCase().trim();
    const rows = document.querySelectorAll('#tablaProveedores tbody tr');
    let contador = 0;
    
    rows.forEach(row => {
      const nombre = row.getAttribute('data-nombre') || '';
      const empresa = row.getAttribute('data-empresa') || '';
      
      if (termino === '' || nombre.includes(termino) || empresa.includes(termino)) {
        row.style.display = '';
        contador++;
      } else {
        row.style.display = 'none';
      }
    });
    
    const contadorSpan = document.getElementById('contadorProveedores');
    if (contadorSpan) {
      contadorSpan.textContent = contador;
    }
  }
  
  // Event listeners con debounce si se añade búsqueda
  let searchTimeout;
  const buscarInput = document.getElementById('buscarProveedor');
  if (buscarInput) {
    buscarInput.addEventListener('keyup', function() {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(filtrarProveedores, 250);
    });
  }
  
  // Mejorar experiencia táctil en móviles
  if ('ontouchstart' in window) {
    document.querySelectorAll('.btn, .hover-lift').forEach(element => {
      element.addEventListener('touchstart', function() {
        if (this.classList && this.classList.contains('btn') && !this.disabled) {
          this.style.transform = 'scale(0.97)';
        }
      });
      element.addEventListener('touchend', function() {
        this.style.transform = '';
      });
    });
  }
  
  // Animación al cargar la página
  document.addEventListener('DOMContentLoaded', function() {
    // Agregar tooltips dinámicos en móviles
    if (window.innerWidth <= 576) {
      document.querySelectorAll('[title]').forEach(el => {
        const title = el.getAttribute('title');
        if (title && !el.getAttribute('data-bs-toggle')) {
          // No hacer nada, mantener title nativo
        }
      });
    }
  });
