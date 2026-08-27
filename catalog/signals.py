from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Category, ProductImage


def delete_stored_file_if_unreferenced(name, storage):
    if not name:
        return
    if ProductImage.objects.filter(image=name).exists() or Category.objects.filter(image=name).exists():
        return
    storage.delete(name)


@receiver(post_delete, sender=ProductImage)
def delete_product_image_file(sender, instance, **kwargs):
    delete_stored_file_if_unreferenced(instance.image.name, instance.image.storage)


@receiver(post_delete, sender=Category)
def delete_category_image_file(sender, instance, **kwargs):
    delete_stored_file_if_unreferenced(instance.image.name, instance.image.storage)
