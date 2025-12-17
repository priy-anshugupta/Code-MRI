from app.core.config import settings

print("Listing available Gemini models...")
try:
    # Prefer the new SDK if available
    try:
        from google import genai as genai_new
        client = genai_new.Client(api_key=settings.GOOGLE_API_KEY)
        models = list(client.models.list())
        for m in models:
            # Print everything; callers can filter as needed.
            print(m.name)
    except ImportError:
        # Fallback to older SDK
        import google.generativeai as genai_old  # type: ignore
        genai_old.configure(api_key=settings.GOOGLE_API_KEY)
        for m in genai_old.list_models():
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
