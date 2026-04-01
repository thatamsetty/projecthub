import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

try:
    import cloudinary.uploader
except ImportError:
    cloudinary = None

ALLOWED_UPLOAD_TYPES = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip', '.rar'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


class FileUploadService:
    def validate(self, uploaded_file, max_upload_size=MAX_UPLOAD_SIZE):
        if not uploaded_file:
            return
        extension = os.path.splitext(uploaded_file.name)[1].lower()
        if extension not in ALLOWED_UPLOAD_TYPES:
            raise ValidationError('Unsupported file type.')
        if uploaded_file.size > max_upload_size:
            max_mb = int(max_upload_size / (1024 * 1024))
            raise ValidationError(f'File exceeds {max_mb} MB limit.')

    def upload(self, uploaded_file, folder, max_upload_size=MAX_UPLOAD_SIZE):
        if not uploaded_file:
            return ''
        self.validate(uploaded_file, max_upload_size=max_upload_size)

        if cloudinary is not None:
            try:
                result = cloudinary.uploader.upload(
                    uploaded_file,
                    folder=folder,
                    public_id=str(uuid.uuid4()),
                    resource_type='auto',
                )
                return result['secure_url']
            except Exception:
                # Fallback to local media storage if Cloudinary is misconfigured/unavailable.
                pass

        return self._save_local(uploaded_file, folder)

    def _save_local(self, uploaded_file, folder):
        extension = os.path.splitext(uploaded_file.name)[1].lower()
        filename = f'{uuid.uuid4()}{extension}'
        normalized_folder = (folder or 'uploads').strip('/').replace('\\', '/')
        relative_path = f'{normalized_folder}/{filename}'
        saved_path = default_storage.save(relative_path, uploaded_file)

        media_url = (settings.MEDIA_URL or '/media/').rstrip('/')
        return f'{media_url}/{saved_path}'.replace('\\', '/')
