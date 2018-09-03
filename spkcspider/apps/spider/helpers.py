__all__ = (
    "token_nonce", "MAX_NONCE_SIZE", "ALLOW_ALL_FILTER_FUNC", "cmp_pw",
    "get_settings_func", "generate_embedded"
)


import os
import base64
import logging
import zipfile
import tempfile
import time

from functools import lru_cache
from importlib import import_module
from django.conf import settings
from django.http import FileResponse

MAX_NONCE_SIZE = 90

if MAX_NONCE_SIZE % 3 != 0:
    raise Exception("MAX_NONCE_SIZE must be multiple of 3")


def ALLOW_ALL_FILTER_FUNC(*args, **kwargs):
    return True


# O_CREAT is correct
_fperm = os.O_RDWR | os.O_RDWR | os.O_CREAT | os.O_EXCL
_fperm |= getattr(os, "O_BINARY", 0)


def generate_embedded(func, context, obj=None):
    from .models import UserComponent, AssignedContent
    directory = getattr(settings, "TMP_EMBEDDED_DIR", None)
    if directory:
        # not neccessary posix
        if not obj:
            path = os.path.join(directory, "main.zip")
            _time = int(time.time())-43200  # update all 12 hours
        elif isinstance(obj, UserComponent):
            path = os.path.join(
                directory, "uc_{}.zip".format(obj.id)
            )
            _time = int(time.time())-7200  # update all 2 hours
        elif isinstance(obj, AssignedContent):  # currently not used
            path = os.path.join(
                directory, "ac_{}.zip".format(obj.id)
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
    return ret


@lru_cache()
def get_settings_func(name, default):
    filterpath = getattr(
        settings, name,
        default
    )
    if callable(filterpath):
        return filterpath
    else:
        module, name = filterpath.rsplit(".", 1)
        return getattr(import_module(module), name)


def token_nonce(size=None):
    if not size:
        from .forms import INITIAL_NONCE_SIZE
        size = int(INITIAL_NONCE_SIZE)
    if size > MAX_NONCE_SIZE:
        logging.warning("Nonce too big")
    if size % 3 != 0:
        raise Exception("SPIDER_NONCE_SIZE must be multiple of 3")
    return base64.urlsafe_b64encode(
        os.urandom(size)
    ).decode('ascii')


def cmp_pw(pw_source, pw_user):
    error = False
    len_pw1 = len(pw_source)
    for i in range(0, len(pw_user)):
        if len_pw1 <= i:
            # fake
            pw_user[i] != pw_user[i]
            error = True
        elif pw_source[i] != pw_user[i]:
            error = True
    return (not error and len(pw_source) == len(pw_user))
