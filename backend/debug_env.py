from app.core.config import settings
import os

print(f"GOOGLE_API_KEY from settings: '{settings.GOOGLE_API_KEY}'")
print(f"GOOGLE_API_KEY from os.environ: '{os.environ.get('GOOGLE_API_KEY')}'")
