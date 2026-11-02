"""Passenger entry point for the isolated API Gateway subsite."""
from app_api import app as flask_app


class StripPrefix:
    """Remove the Alwaysdata subsite prefix before Flask route matching."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            script_name = environ.get("SCRIPT_NAME", "").rstrip("/")
            if not script_name.endswith(self.prefix):
                environ["SCRIPT_NAME"] = script_name + self.prefix
        return self.app(environ, start_response)


application = StripPrefix(flask_app, "/api-gateway")
