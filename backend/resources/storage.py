from django.conf import settings
from django.core.files.storage import FileSystemStorage


def get_private_storage():
    """Private object storage for original PDFs. Its URLs are never exposed to any client."""
    if settings.STORAGE_BACKEND == "s3":
        from storages.backends.s3 import S3Storage

        return S3Storage(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            access_key=settings.AWS_ACCESS_KEY_ID,
            secret_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME,
            default_acl="private",
            file_overwrite=False,
            querystring_auth=True,
        )
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)
