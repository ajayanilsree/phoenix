from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class InvoicePDFStorage(Storage):
    """Use Cloudinary raw assets for PDFs, with local storage for development."""

    def __init__(self):
        if getattr(settings, "CLOUDINARY_CONFIGURED", False):
            from cloudinary_storage.storage import MediaCloudinaryStorage

            self.backend = MediaCloudinaryStorage(resource_type="raw")
        else:
            self.backend = FileSystemStorage()

    def _open(self, name, mode="rb"):
        return self.backend.open(name, mode)

    def _save(self, name, content):
        return self.backend.save(name, content)

    def delete(self, name):
        return self.backend.delete(name)

    def exists(self, name):
        return self.backend.exists(name)

    def url(self, name):
        return self.backend.url(name)

    def size(self, name):
        return self.backend.size(name)

    def get_available_name(self, name, max_length=None):
        return self.backend.get_available_name(name, max_length=max_length)
