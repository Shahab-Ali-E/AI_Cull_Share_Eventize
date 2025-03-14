import os
from fastapi.templating import Jinja2Templates

# Get the absolute path of the `templates` directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Path to `utils`
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")  # Go one level up to find `templates`

# Initialize Jinja2Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)
