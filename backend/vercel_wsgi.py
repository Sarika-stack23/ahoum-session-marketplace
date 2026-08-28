import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
path = str(Path(__file__).resolve().parent)
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application
app = get_wsgi_application()
