__all__ = ["rate_limit_default", "allow_all_filter", "generate_embedded"]


import os
import zipfile
import tempfile
import time
from django.http import Http404
from django.http import FileResponse
from django.conf import settings

from .models import UserComponent, AssignedContent


def rate_limit_default(view, request):
    time.sleep(1)
    raise Http404()


def allow_all_filter(*args, **kwargs):
    return True


# O_CREAT is correct
_fperm = os.O_RDWR | os.O_RDWR | os.O_CREAT | os.O_EXCL
_fperm |= getattr(os, "O_BINARY", 0)


def generate_embedded(func, context, obj=None):
    directory = getattr(settings, "TMP_EMBEDDED_DIR", None)
    expires = context.get("token_expires", None)
    if directory:
        # not always posix pathes, in case of Storage, it would be true
        # but storage would expose them, bad
        if not obj:
            path = os.path.join(directory, "main-export.zip")
            _time = int(time.time())-43200  # update all 12 hours
        elif isinstance(obj, UserComponent):
            path = os.path.join(
                directory, "uc_{}_{}.zip".format(
                    context["maindic"]["scope"], obj.id
                )
            )
            _time = int(time.time())-7200  # update all 2 hours
        elif isinstance(obj, AssignedContent):  # currently not used
            path = os.path.join(
                directory, "ac_{}_{}.zip".format(
                    context["maindic"]["scope"], obj.id
                )
            )
            _time = int(time.time())-300  # update all 5 minutes
            _time_ob = int(obj.modified.time())
            if _time_ob < _time:  # don't update if object is current
                _time = _time_ob
        try:
            res = os.stat(path)
            if res.st_mtime < _time:
                os.path.unlink(path)
            else:
                fil = open(path, "rb")
                ret = FileResponse(
                    fil,
                    content_type='application/force-download'
                )
                ret['Content-Disposition'] = 'attachment; filename=result.zip'
                if expires:
                    ret['X-Token-Expires'] = expires
                return ret
        except FileNotFoundError:
            pass
        try:
            fil = os.open(path, _fperm, mode=0o770)
        except FileExistsError:
            # wait some time
            time.sleep(5)
            # try again
            return generate_embedded(func, context, obj)
    else:
        fil = tempfile.SpooledTemporaryFile(max_size=2048)
    with zipfile.ZipFile(fil, "w") as zip:
        func(zip, context)
    if directory:
        # write on disk if not temporary
        fil.flush()
        os.fsync(fil.fileno())
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
