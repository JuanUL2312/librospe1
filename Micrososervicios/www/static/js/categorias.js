
  // Confirmación de eliminación. Si tiene productos, se desactiva en lugar de borrarse.
  function confirmarEliminacion(nombre, productos) {
    if (productos > 0) {
      return confirm(
        'La categoría "' + nombre + '" tiene ' + productos + ' producto(s) asociado(s).\n\n' +
        'No se puede eliminar: se DESACTIVARÁ en su lugar.\n\n¿Continuar?'
      );
    }
    return confirm(
      '¿Estás seguro de que deseas eliminar la categoría "' + nombre + '"?\n\n' +
      'No tiene productos asociados. Esta acción no se puede deshacer.'
    );
  }

  // Filtro de búsqueda en la tabla
  function filtrarCategorias() {
    const busqueda = document.getElementById('buscarCategoria');
    if (!busqueda) return;

    const termino = busqueda.value.toLowerCase().trim();
    const rows = document.querySelectorAll('#tablaCategorias tbody tr');
    let contador = 0;

    rows.forEach(row => {
      const nombre = row.getAttribute('data-nombre') || '';
      if (termino === '' || nombre.includes(termino)) {
        row.style.display = '';
        contador++;
      } else {
        row.style.display = 'none';
      }
    });

    const contadorSpan = document.getElementById('contadorCategorias');
    if (contadorSpan) {
      contadorSpan.textContent = contador;
    }
  }

  let searchTimeout;
  const buscarInput = document.getElementById('buscarCategoria');
  if (buscarInput) {
    buscarInput.addEventListener('keyup', function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(filtrarCategorias, 250);
    });
  }
