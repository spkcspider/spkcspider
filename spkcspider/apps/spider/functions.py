__all__ = ["rate_limit_default", "allow_all_filter", "generate_embedded"]


import zipfile
import tempfile
import time
from django.http import Http404
from django.http import FileResponse


def rate_limit_default(view, request):
    time.sleep(1)
    raise Http404()


def allow_all_filter(*args, **kwargs):
    return True


def generate_embedded(func, context, obj=None):
    expires = context.get("token_expires", None)
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
