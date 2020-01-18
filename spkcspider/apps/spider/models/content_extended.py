__all__ = [
    "DataContent", "BaseAttached", "AttachedFile", "AttachedTimespan",
    "AttachedBlob", "SmartTag"
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


def get_file_path(instance, filename) -> str:
    ret = getattr(settings, "SPIDER_FILE_DIR", "spider_files")
    # try 100 times to find free filename
    # but should not take more than 1 try
    # IMPORTANT: strip . to prevent creation of htaccess files or similar
    for _i in range(0, 100):
        ret_path = default_storage.generate_filename(
            posixpath.join(
                ret, str(instance.content.usercomponent.user_id),
                create_b64_token(FILE_TOKEN_SIZE), filename.lstrip(".")
            )
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise FileExistsError("Unlikely event: no free filename")
    return ret_path


class DataContentManager(models.Manager):
    use_in_migrations = True

    def get_queryset(self):
        if self.model._meta.model_name == "datacontent":
            return super().get_queryset()
        return super().get_queryset().filter(
            associated__ctype__code=self.model._meta.model_name
        )


class DataContent(BaseContent):
    """
        inherit from it with proxy objects when possible
        speedier than BaseContent by beeing prefetched
    """
    # has as an exception a related name (e.g. for speeding up)
    # name is "datacontent"
    associated = models.OneToOneField(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE, null=True
    )
    quota_data = JSONField(default=dict, blank=True)
    free_data = JSONField(default=dict, blank=True)

    objects = DataContentManager()

    def get_size(self, prepared_attachements=None) -> int:
        s = super().get_size(prepared_attachements)
        s += len(str(self.quota_data))
        return s


class BaseAttached(models.Model):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    name: str = models.CharField(max_length=50, default="", blank=True)
    unique: bool = models.BooleanField(default=False, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    content = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE,
        related_name="%(class)ss"
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls.Meta, "abstract", False):
            BaseContent.attached_attributenames.add(
                cls.content.field.related_query_name() % {
                    "class": cls.__name__.lower()
                }
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
            if self.stop < self.start:
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

    def get_size(self) -> int:
        # free can be abused
        return 8


class AttachedCounter(BaseAttached):
    counter: int = models.BigIntegerField()

    def get_size(self) -> int:
        # free can be abused
        return 4


class AttachedFile(BaseAttached):
    file = models.FileField(upload_to=get_file_path, null=False, blank=False)

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

    def get_size(self) -> int:
        return len(self.blob)

    @property
    def as_bytes(self) -> bytes:
        return bytes(self.blob)


class SmartTag(BaseAttached):
    """
        This avoids lockups in DataContent.
        And can be used as a per client tag if many changes are expected.
        For ease of use allow target be null

        is in contradiction to attached_to a forward reference
        this means: smarttag.target is added to references
    """
    data: dict = JSONField(default=dict, blank=True)
    free: bool = models.BooleanField(default=False, editable=False)

    target = models.ForeignKey(
        "spider_base.AssignedContent",
        on_delete=models.CASCADE, null=True,
        related_name="%(class)s_sources"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="%(class)s_target_unique",
                fields=("content", "target", "name"),
                condition=models.Q(unique=True)
            ),
            models.UniqueConstraint(
                name="%(class)s_notarget_unique",
                fields=("content", "name"),
                condition=models.Q(unique=True, target__isnull=True)
            ),
            # prevents circular dependencies
            models.CheckConstraint(
                name="%(class)s_content_not_target",
                check=~models.Q(content=models.F("target"))
            )
        ]

    def get_size(self) -> int:
        # sometimes it is useful to have a free reference with data
        # so make here an exception
        return 0 if self.free else len(str(self.data)) + 4
