import os
import uuid

from django.core.exceptions import ValidationError

try:
    import cloudinary.uploader
except ImportError:
    cloudinary = None

ALLOWED_UPLOAD_TYPES = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip', '.rar'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


class FileUploadService:
    def validate(self, uploaded_file):
        if not uploaded_file:
            return
        extension = os.path.splitext(uploaded_file.name)[1].lower()
        if extension not in ALLOWED_UPLOAD_TYPES:
            raise ValidationError('Unsupported file type.')
        if uploaded_file.size > MAX_UPLOAD_SIZE:
            raise ValidationError('File exceeds 10 MB limit.')

    def upload(self, uploaded_file, folder):
        if not uploaded_file:
            return ''
        self.validate(uploaded_file)
        if cloudinary is None:
            raise ValidationError('Cloudinary package is not installed.')
        result = cloudinary.uploader.upload(
            uploaded_file,
            folder=folder,
            public_id=str(uuid.uuid4()),
            resource_type='auto',
        )
        return result['secure_url']
