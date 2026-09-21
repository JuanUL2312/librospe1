
    $(document).ready(function() {
        $('#tabla-usuarios').DataTable({
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/es-ES.json'
            },
            order: [[0, 'asc']],
            pageLength: 25
        });
    });
