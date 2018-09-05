__all__ = [
    "rate_limit_default", "allow_all_filter", "generate_embedded",
    "embed_file_default"
]

import os
import zipfile
import tempfile
import time
from django.core.exceptions import ValidationError
from django.http import Http404
from django.http import FileResponse
from django.utils.translation import gettext as _
from django.conf import settings


def rate_limit_default(view, request):
    time.sleep(1)
    raise Http404()


def allow_all_filter(*args, **kwargs):
    return True


def validate_file(value):
    max_size = getattr(settings, "MAX_FILE_SIZE", None)
    if max_size and value.size > max_size:
        raise ValidationError(
            _("%(name)s is too big"),
            code='max_size',
            params={'name': value.name},
        )


def embed_file_default(prefix, name, value, zipf, context):
    path = "{}{}/{}".format(
        prefix, name, os.path.basename(value.name)
    )

    override = (
        (
            context["request"].user.is_superuser or
            context["request"].user.is_staff
        ) and context["request"].GET.get("embed_big", "") == "true"
    )
    if (
        value.size < getattr(settings, "MAX_EMBED_SIZE", 20000000) or
        override
    ):
        zipf.write(value.path, path)
        return {"file": path}
    elif context["scope"] == "export":
        # link always direct to files in exports
        url = value.url
        if "://" not in getattr(settings, "MEDIA_URL", ""):
            url = "{}{}".format(context["hostpart"], url)
        return {"url": url}
    else:
        # only file filet has files yet
        url = context["content"].associated.get_absolute_url("download")
        url = "{}{}?{}".format(
            context["hostpart"],
            url, context["context"]["spider_GET"].urlencode()
        )
        return {"url": url}


def generate_embedded(func, context, obj=None):
    expires = context.get("expires", None)
    fil = tempfile.SpooledTemporaryFile(max_size=2048)
    with zipfile.ZipFile(fil, "w") as zip:
        func(zip, context)
    # now reset
    fil.seek(0, 0)
    ret = FileResponse(
        fil,
        content_type='application/force-download'
    )
    ret['Content-Disposition'] = 'attachment; filename=result.zip'
    if expires:
        ret['X-Token-Expires'] = expires
    return ret
