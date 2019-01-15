__all__ = ["BaseInfoModel", "info_and", "info_or"]

import re

from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext


_info_replacer_templ = '\n{}.*\n'


def info_and(*args, **kwargs):
    q = models.Q()
    for query in args:
        if isinstance(query, models.Q):
            q &= query
        else:
            q &= models.Q(
                info__contains="\n{}\n".format(query)
            )
    for name, query in kwargs.items():
        if query is None:
            q &= models.Q(
                info__contains="\n{}=".format(name)
            )
        else:
            q &= models.Q(
                info__contains="\n{}={}\n".format(name, query)
            )
    return q

def info_or(*args, **kwargs):
    q = models.Q()
    for query in args:
        if isinstance(query, models.Q):
            q |= query
        else:
            q |= models.Q(
                info__contains="\n{}\n".format(query)
            )
    for name, query in kwargs.items():
        if query is None:
            q |= models.Q(
                info__contains="\n{}=".format(name)
            )
        else:
            q |= models.Q(
                info__contains="\n{}={}\n".format(name, query)
            )
    return q


def info_field_validator(value):
    _ = gettext
    if value[-1] != "\n":
        raise ValidationError(
            _('%(value)s ends not with "\\n"'),
            code="syntax",
            params={'value': value},
        )
    if value[0] != "\n":
        raise ValidationError(
            _('%(value)s starts not with "\\n"'),
            code="syntax",
            params={'value': value},
        )
    # check elements
    for elem in value.split("\n"):
        f = elem.find("=")
        # no flag => allow multiple instances
        if f != -1:
            continue
        counts = 0
        counts += value.count("\n%s\n" % elem)
        # check: is flag used as key in key, value storage
        counts += value.count("\n%s=" % elem)
        assert(counts > 0)
        if counts > 1:
            raise ValidationError(
                _('flag not unique: %(element)s in %(value)s'),
                params={'element': elem, 'value': value},
            )

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
        if "\n%s\n" % flag in self.info:
            return True
        return False

    def getlist(self, key, amount=None):
        info = self.info
        ret = []
        pstart = info.find("\n%s=" % key)
        while pstart != -1:
            tmpstart = pstart+len(key)+2
            pend = info.find("\n", tmpstart)
            if pend == -1:
                raise Exception(
                    "Info field error: doesn't end with \"\\n\": \"%s\"" %
                    info
                )
            ret.append(info[tmpstart:pend])
            pstart = info.find("\n%s=" % key, pend)
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
                    "\n", self.info, 0
                )
                continue
            self.info, count1 = pattern.subn(
                "\n{}\n", self.info, 1
            )
            if count1 == 0:
                rep = rep_missing
            else:
                rep = rep_replace
                self.info = pattern.sub(
                    "\n", self.info, 0
                )
            if val is True:
                rep.append(name)
            elif isinstance(val, (tuple, list)):
                rep.append("\n".join(
                    map(
                        lambda x: "{}={}".format(name, x),
                        val
                    )
                ))
            else:
                rep.append("{}={}".format(name, val))
        self.info = self.info.format(*rep_replace)
        if rep_missing:
            self.info = "{}\n{}\n".format(self.info, "\n".join(rep_missing))
        return rep_missing

    def info_and(self, *args, **kwargs):
        return info_and(*args, **kwargs)

    def info_or(self, *args, **kwargs):
        return info_or(*args, **kwargs)
