__all__ = ["WebConfig"]

from django.db import models

# from ..constants import MAX_NONCE_SIZE, hex_size_of_bigid


class WebConfig(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", on_delete=models.CASCADE,
        related_name="webconfigs", null=False, blank=False
    )
    # key = models.SlugField(
    #     max_length=(MAX_NONCE_SIZE*4//3)+hex_size_of_bigid,
    #     db_index=True
    # )
    url = models.URLField(max_length=800)
    config = models.TextField(default="", blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
