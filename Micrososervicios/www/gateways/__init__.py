"""Paquete de blueprints del API Gateway puro de LibrosPE.

Cada microservicio del dominio se expone bajo ``/api/v1/<dominio>/...``
mediante un blueprint proxy que: valida el JWT del usuario, registra
auditoría local y reenvía la petición por HTTP al microservicio interno.
"""
from flask import Flask


def registrar_blueprints(app: Flask) -> None:
    """Registra todos los blueprints del gateway API."""
    from . import auth, clientes, inventario, usuarios, ventas

    app.register_blueprint(auth.bp)
    app.register_blueprint(ventas.bp)
    app.register_blueprint(inventario.bp)
    app.register_blueprint(usuarios.bp)
    app.register_blueprint(clientes.bp)
