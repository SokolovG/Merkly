import logging

from backend.src.presentation.routes import create_app

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")


app = create_app()
