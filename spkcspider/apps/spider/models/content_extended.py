__all__ = [
    "DataContent", "AttachedFile", "AttachedTimeSpan", "AttachedBlob"
]

import posixpath

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.http import HttpResponseRedirect
from jsonfield import JSONField
from ranged_response import RangedFileResponse

from spkcspider.utils.security import create_b64_token

from ..abstract_models import BaseContent
from ..conf import FILE_TOKEN_SIZE


def get_file_path(instance, filename):
    ret = getattr(settings, "SPIDER_FILE_DIR", "spider_files")
    # try 100 times to find free filename
    # but should not take more than 1 try
    # IMPORTANT: strip . to prevent creation of htaccess files or similar
    for _i in range(0, 100):
        ret_path = default_storage.generate_filename(
            posixpath.join(
                ret, str(instance.associated.usercomponent.user.pk),
                create_b64_token(FILE_TOKEN_SIZE), filename.lstrip(".")
            )
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise FileExistsError("Unlikely event: no free filename")
    return ret_path


class DataContent(BaseContent):
    """
        inherit from it, it will maybe replace the generic relation
    """
    quota_data = JSONField()
    free_data = JSONField()

    def get_size(self):
        s = super().get_size()
        memv = memoryview(self.quota_data)
        s += memv.nbytes
        memv.release()
        return s


class BaseAttached(models.Model):
    name = models.CharField(max_length=50, default="", blank=True)
    unique = models.BooleanField(default=False, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class AttachedTimeSpan(BaseAttached):
    content = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE, related_name="timespans"
    )
    start = models.DateTimeField()
    stop = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="AttachedTimeSpan_unique",
                fields=["name"],
                condition=models.Q(unique=True)
            )
        ]

    def get_size(self):
        return 0


class AttachedFile(BaseAttached):
    content = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE, related_name="files"
    )
    file = models.FileField(upload_to=get_file_path, null=False, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="AttachedFile_unique",
                fields=["name"],
                condition=models.Q(unique=True)
            )
        ]

    def get_response(self, request=None, name=None, add_extension=False):
        if not request:
            response = HttpResponseRedirect(
                redirect_to=self.file.url
            )
        else:
            response = RangedFileResponse(
                request,
                self.file.file,
                content_type='application/octet-stream'
            )
            if not name:
                name = posixpath.basename(self.file.name)
            if add_extension and "." not in name:  # use ending of saved file
                ext = self.file.name.rsplit(".", 1)
                if len(ext) > 1:
                    name = "%s.%s" % (name, ext[1])
            # name is sanitized to not contain \n, and other ugly control chars
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % posixpath.basename(name.replace(
                    r'"', r'\"'
                ))
        return response

    def get_size(self):
        return self.file.size

    def save(self, *args, **kw):
        if self.pk is not None:
            orig = AttachedFile.objects.get(pk=self.pk)
            if orig.file != self.file:
                orig.file.delete(False)
        super().save(*args, **kw)


class AttachedBlob(BaseAttached):
    content = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE, related_name="blobs"
    )
    blob = models.BinaryField(default=b"", editable=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="AttachedBlobSpan_unique",
                fields=["name"],
                condition=models.Q(unique=True)
            )
        ]

    def get_size(self):
        return len(self.blob)
