from gutcheck.app import create_app
from gutcheck.config import load_settings
from space.guard import protect

app = protect(create_app(load_settings()))
