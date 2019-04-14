__all__ = ["BaseInfoModel", "ReferrerObject", "info_and", "info_or"]

import re

from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.functional import cached_property

from ..helpers import extract_host

_info_replacer_templ = '\x1e{}.*\x1e'


def info_and(*args, **kwargs):
    q = models.Q()
    for query in args:
        if isinstance(query, models.Q):
            q &= query
        else:
            q &= models.Q(
                info__contains="\x1e{}\x1e".format(query)
            )
    for name, query in kwargs.items():
        if query is None:
            q &= models.Q(
                info__contains="\x1e{}=".format(name)
            )
        else:
            q &= models.Q(
                info__contains="\x1e{}={}\x1e".format(name, query)
            )
    return q


def info_or(*args, **kwargs):
    q = models.Q()
    for query in args:
        if isinstance(query, models.Q):
            q |= query
        else:
            q |= models.Q(
                info__contains="\x1e{}\x1e".format(query)
            )
    for name, query in kwargs.items():
        if query is None:
            q |= models.Q(
                info__contains="\x1e{}=".format(name)
            )
        else:
            q |= models.Q(
                info__contains="\x1e{}={}\x1e".format(name, query)
            )
    return q


def info_field_validator(value):
    _ = gettext
    if value[-1] != "\x1e":
        raise ValidationError(
            _('%(value)s ends not with "\\x1e"'),
            code="syntax",
            params={'value': value},
        )
    if value[0] != "\x1e":
        raise ValidationError(
            _('%(value)s starts not with "\\x1e"'),
            code="syntax",
            params={'value': value},
        )
    # check elements
    for elem in value.split("\x1e"):
        if elem == "":
            continue
        f = elem.find("=")
        # no flag => allow multiple instances
        if f != -1:
            continue
        counts = 0
        counts += value.count("\x1e%s\x1e" % elem)
        # check: is flag used as key in key, value storage
        counts += value.count("\x1e%s=" % elem)
        assert counts > 0, value
        if counts > 1:
            raise ValidationError(
                _('flag not unique: %(element)s in %(value)s'),
                params={'element': elem, 'value': value},
            )


class ReferrerObject(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    url = models.URLField(
        max_length=600, db_index=True, unique=True, editable=False
    )

    @cached_property
    def host(self):
        return extract_host(self.url)


class BaseInfoModel(models.Model):

    class Meta:
        abstract = True

    # for extra information over content, admin only editing
    # format: \nflag1\nflag2\nfoo=true\nfoo2=xd\n...\nendfoo=xy\n
    # every section must start and end with \n every keyword must be unique and
    # in this format: keyword=
    # no unneccessary spaces!
    info = models.TextField(
        null=False, editable=False,
        validators=[info_field_validator]
    )

    def getflag(self, flag):
        if "\x1e%s\x1e" % flag in self.info:
            return True
        return False

    def getlist(self, key, amount=None):
        info = self.info
        ret = []
        pstart = info.find("\x1e%s=" % key)
        while pstart != -1:
            tmpstart = pstart+len(key)+2
            pend = info.find("\x1e", tmpstart)
            if pend == -1:
                raise Exception(
                    "Info field error: doesn't end with \"\\x1e\": \"%s\"" %
                    info
                )
            ret.append(info[tmpstart:pend])
            pstart = info.find("\x1e%s=" % key, pend)
            # if amount=0 => bool(amount) == false
            if amount and amount <= len(ret):
                break
        return ret

    def replace_info(self, **kwargs):
        """
            Warning! Order dependend (especially for unique tests)
        """
        rep_replace = []
        rep_missing = []
        self.info = self.info.replace("{}", "{{}}")
        for name, val in kwargs.items():
            pattern = re.compile(
                _info_replacer_templ.format(re.escape(name)), re.M
            )
            if not val:
                # remove name
                self.info = pattern.sub(
                    "\x1e", self.info, 0
                )
                continue
            # count replacements
            self.info, count1 = pattern.subn(
                "\x1e{}\x1e", self.info, 1
            )
            if count1 == 0:
                rep = rep_missing
            else:
                rep = rep_replace
                self.info = pattern.sub(
                    "\x1e", self.info, 0
                )
            if val is True:
                rep.append(name)
            elif isinstance(val, (tuple, list)):
                rep.append("\x1e".join(
                    map(
                        lambda x: "{}={}".format(name, x),
                        val
                    )
                ))
            else:
                rep.append("{}={}".format(name, val))
        self.info = self.info.format(*rep_replace)
        if rep_missing:
            self.info = "{}\x1e{}\x1e".format(
                self.info, "\x1e".join(rep_missing)
            )
        return rep_missing

    def info_and(self, *args, **kwargs):
        return info_and(*args, **kwargs)

    def info_or(self, *args, **kwargs):
        return info_or(*args, **kwargs)
