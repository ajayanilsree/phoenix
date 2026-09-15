from io import BytesIO

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class InvoicePDFStorage(Storage):
    """Use Cloudinary raw assets for PDFs, with local storage for development."""

    def __init__(self):
        if getattr(settings, "CLOUDINARY_CONFIGURED", False):
            from cloudinary_storage.storage import RawMediaCloudinaryStorage

            self.backend = RawMediaCloudinaryStorage()
        else:
            self.backend = FileSystemStorage()

    def _open(self, name, mode="rb"):
        return self.backend.open(name, mode)

    def _save(self, name, content):
        return self.backend.save(name, content)

    def delete(self, name):
        return self.backend.delete(name)

    def exists(self, name):
        if not getattr(settings, "CLOUDINARY_CONFIGURED", False):
            return self.backend.exists(name)

        # RawMediaCloudinaryStorage probes the public delivery URL here. Raw
        # assets on this account require authenticated delivery, so use the
        # Cloudinary Admin API when a real remote existence check is needed.
        import cloudinary.api
        from cloudinary.exceptions import NotFound

        public_id = self.backend._prepend_prefix(name)
        try:
            cloudinary.api.resource(public_id, resource_type="raw", type="upload")
        except NotFound:
            return False
        return True

    def open_for_download(self, name):
        if not getattr(settings, "CLOUDINARY_CONFIGURED", False):
            return self.backend.open(name, "rb")

        import requests
        from cloudinary.utils import private_download_url

        public_id = self.backend._prepend_prefix(name)
        # Cloudinary raw public IDs include the file extension. Keep it in the
        # ID; stripping it makes private_download_url address another asset.
        filename = public_id.rsplit("/", 1)[-1]
        extension = filename.rsplit(".", 1)[-1] if "." in filename else "pdf"
        url = private_download_url(public_id, extension, resource_type="raw", type="upload", attachment=True)
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return BytesIO(response.content)

    def url(self, name):
        return self.backend.url(name)

    def size(self, name):
        return self.backend.size(name)

    def get_available_name(self, name, max_length=None):
        return self.backend.get_available_name(name, max_length=max_length)
