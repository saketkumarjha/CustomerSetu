import uuid
from app.db.supabase_client import get_supabase
from app.core.config import get_settings


def upload_image_to_storage(file_bytes: bytes, original_filename: str) -> str:
    """
    Upload image bytes to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    settings = get_settings()
    supabase = get_supabase()

    # Generate a unique filename to avoid collisions
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    unique_filename = f"{uuid.uuid4()}.{extension}"
    storage_path = f"complaints/{unique_filename}"

    # Upload to Supabase Storage
    supabase.storage.from_(settings.supabase_storage_bucket).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": f"image/{extension}"}
    )

    # Build and return the public URL
    public_url = (
        f"{settings.supabase_url}/storage/v1/object/public/"
        f"{settings.supabase_storage_bucket}/{storage_path}"
    )
    return public_url