__all__ = [
    "DataContent", "AttachedFile", "AttachedTimespan", "AttachedBlob"
]

import posixpath

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
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
    # has as an exception a related name (e.g. for speeding up)
    associated = models.OneToOneField(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE, null=True
    )
    quota_data = JSONField(default=dict, blank=True)
    free_data = JSONField(default=dict, blank=True)

    def get_size(self, prepared_attachements=None):
        s = super().get_size(prepared_attachements)
        s += len(str(self.quota_data))
        return s


class BaseAttached(models.Model):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    name = models.CharField(max_length=50, default="", blank=True)
    unique = models.BooleanField(default=False, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    content = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE,
        related_name="%(class)s_set"
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls._meta, "abstract", False):
            BaseContent.attached_names.add(
                "{}_set".format(cls._meta.model_name)
            )

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(
                name="%(class)s_unique",
                fields=("content", "name"),
                condition=models.Q(unique=True)
            )
        ]


class AttachedTimespan(BaseAttached):
    start = models.DateTimeField()
    stop = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    start__lte=models.F("stop")
                ) |
                models.Q(start__isnull=True) |
                models.Q(stop__isnull=True),
                name="%(class)s_order"
            ),
            models.CheckConstraint(
                check=models.Q(
                    start__isnull=False
                ) |
                models.Q(
                    stop__isnull=False
                ),
                name="%(class)s_exist"
            )
        ] + BaseAttached.Meta.constraints

    def clean(self):
        _ = gettext
        if self.start and self.stop:
            if self.start < self.stop:
                raise ValidationError(
                    _("Stop (%(stop)s) < Start (%(start)s)"),
                    params={
                        "start": self.start,
                        "stop": self.stop
                    }
                )
        elif not self.start and not self.stop:
            raise ValidationError(
                _("Timespan empty"),
            )

    def get_size(self):
        # free can be abused
        return 8


class AttachedCounter(BaseAttached):
    counter = models.BigIntegerField()

    def get_size(self):
        # free can be abused
        return 4


class AttachedFile(BaseAttached):
    file = models.FileField(upload_to=get_file_path, null=False, blank=False)
    content = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE,
        # for non bulk updates
        null=True,
        related_name="%(class)s_set"
    )

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
    blob = models.BinaryField(default=b"", editable=True, blank=True)

    def get_size(self):
        return len(self.blob)
