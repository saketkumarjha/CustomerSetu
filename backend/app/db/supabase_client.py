import threading
from supabase import create_client, Client
from app.core.config import get_settings

_local = threading.local()


def get_supabase() -> Client:
    if not hasattr(_local, "client"):
        settings = get_settings()
        _local.client = create_client(settings.supabase_url, settings.supabase_key)
    return _local.client