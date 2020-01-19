__all__ = (
    "filter_components", "filter_contents", "listed_variants_q",
    "machine_variants_q", "active_protections_q",
    "info_and", "info_or", "travelprotection_types_q",
    "loggedin_active_tprotections_q"
)

from django.conf import settings
from django.db.models import Q

from spkcspider.constants import (
    ProtectionStateType, VariantType, loggedin_active_tprotections
)

_base_variants = ~(
    (
        ~Q(ctype__contains=VariantType.feature_connect) &
        Q(ctype__contains=VariantType.component_feature)
    ) |
    Q(ctype__contains=VariantType.content_feature)
)

machine_variants_q = (
    Q(ctype__contains=VariantType.machine) &
    _base_variants  # such features cannot be created
)

active_protections_q = (
    Q(state=ProtectionStateType.enabled) |
    Q(state=ProtectionStateType.instant_fail)
)

loggedin_active_tprotections_q = Q()
for i in loggedin_active_tprotections:
    loggedin_active_tprotections_q |= Q(
        info__contains="\x1etravel_protection_type={}\x1e".format(i)
    )

travelprotection_types_q = (
    Q(ctype__name="TravelProtection") |
    Q(ctype__name="SelfProtection")
)


listed_variants_q = (
    _base_variants &
    ~Q(ctype__contains=VariantType.unlisted)
)


def filter_components(
    search_filters, filter_unlisted=True, use_contents=True
):
    searchq = Q()
    searchq_exc = Q()
    notsearch = Q()

    counter = 0
    # against ddos
    max_counter = settings.SPIDER_MAX_SEARCH_PARAMETERS

    # list only unlisted if explicity requested or export is used
    # ComponentPublicIndex doesn't allow unlisted in any case
    # this is enforced by setting "is_special_user" to False
    if filter_unlisted:
        notsearch = ~Q(contents__info__contains="\x1eunlisted\x1e")

    for item in search_filters:
        if filter_unlisted and item == "_unlisted":
            continue
        if counter > max_counter:
            break
        counter += 1
        if len(item) == 0:
            continue
        use_strict = False
        if item.startswith("!!"):
            _item = item[1:]
        elif item.startswith("__"):
            _item = item[1:]
        elif item.startswith("!_"):
            _item = item[2:]
            use_strict = True
        elif item.startswith("!"):
            _item = item[1:]
        elif item.startswith("_"):
            _item = item[1:]
            use_strict = True
        else:
            _item = item
        qob = Q()
        if use_strict:
            if use_contents:
                qob |= Q(contents__info__contains="\x1e%s\x1e" % _item)
                # exclude unlisted from searchterms
                qob &= notsearch
        else:
            qob |= Q(description__icontains=_item)
        if _item == "index":
            qob |= Q(strength=10)
        elif use_strict:
            qob |= Q(
                name=_item,
                strength__lt=10
            )
        else:
            qob |= Q(
                name__icontains=_item,
                strength__lt=10
            )
        if item.startswith("!!"):
            searchq |= qob
        elif item.startswith("!"):
            searchq_exc |= qob
        else:
            searchq |= qob
    return (searchq & ~searchq_exc, counter)


def filter_contents(
    search_filters, ids=None, filter_unlisted=True, feature_exception=True,
    use_components=False
):
    """
    [summary]

    Arguments:
        search_filters {iterable} -- search filters

    Keyword Arguments:
        ids {[type]} -- [description] (default: {None})
        filter_unlisted {bool} -- [description] (default: {True})
        feature_exception {bool} -- [description] (default: {True})
        use_components {bool} -- [description] (default: {False})

    Returns:
        [type] -- [description]
    """
    searchq = Q()
    searchq_exc = Q()

    counter = 0
    unlisted_active = False
    # against ddos
    max_counter = settings.SPIDER_MAX_SEARCH_PARAMETERS

    for item in search_filters:
        if filter_unlisted is True and item == "_unlisted":
            continue
        elif item == "_unlisted":
            unlisted_active = True
        if counter > max_counter:
            break
        counter += 1
        if len(item) == 0:
            continue
        use_strict = False
        negate = False
        if item.startswith("!!"):
            _item = item[1:]
        elif item.startswith("__"):
            _item = item[1:]
        elif item.startswith("!_"):
            _item = item[2:]
            use_strict = True
            negate = True
        elif item.startswith("!"):
            _item = item[1:]
            negate = True
        elif item.startswith("_"):
            _item = item[1:]
            use_strict = True
        else:
            _item = item
        if use_strict:
            qob = Q(name=_item)
            qob |= Q(info__contains="\x1e%s\x1e" % _item)
            # can exclude/include specific usercomponents names
            if use_components:
                qob |= Q(usercomponent__name=_item)
        else:
            qob = Q(name__icontains=_item)
            qob |= Q(description__icontains=_item)
            qob |= Q(info__icontains=_item)
            # but don't be too broad with unspecific negation
            #   only apply on contents
            if use_components and not negate:
                qob |= Q(usercomponent__name__icontains=_item)
                qob |= Q(usercomponent__description__icontains=_item)
        if negate:
            searchq_exc |= qob
        else:
            searchq |= qob

    if ids:
        # id_collection contains int and str entries
        try:
            ids = map(lambda x: int(x), ids)
        except ValueError:
            # deny any access in case of an incorrect id
            ids = []

        searchq &= (
            Q(
                id__in=ids
            )
        )
    # if cannot set _unlisted
    if not unlisted_active:
        tmp = None
        if filter_unlisted is True:
            # if filter_unlisted is True generally exclude all
            tmp = Q(info__contains="\x1eunlisted\x1e")
        elif filter_unlisted is not False:
            # if filter_unlisted is int exclude all equal and below
            tmp = Q(
                info__contains="\x1eunlisted\x1e",
                priority__lte=filter_unlisted
            )
        if tmp:
            # except if features as they are shown always
            if feature_exception:
                tmp &= ~(
                    Q(
                        ctype__ctype__contains=VariantType.feature_connect
                    ) &
                    ~Q(
                        ctype__ctype__contains=VariantType.unlisted
                    )
                )
            searchq_exc |= tmp
    return (searchq & ~searchq_exc, counter)


def info_and(*args, info_fieldname="info", **kwargs):
    q = Q()
    fname = "%s__contains" % info_fieldname
    for query in args:
        if isinstance(query, Q):
            q &= query
        else:
            q &= Q(
                **{fname: "\x1e%s\x1e" % query}
            )
    for name, query in kwargs.items():
        if query is None:
            q &= Q(
                **{fname: "\x1e%s=" % name}
            )
        elif isinstance(query, (tuple, list, set)):
            for item in query:
                q &= Q(
                    **{fname: "\x1e%s=%s\x1e" % (name, item)}
                )
        else:
            q &= Q(
                **{fname: "\x1e%s=%s\x1e" % (name, query)}
            )
    return q


def info_or(*args, info_fieldname="info", **kwargs):
    q = Q()
    fname = "%s__contains" % info_fieldname
    for query in args:
        if isinstance(query, Q):
            q |= query
        else:
            q |= Q(
                **{fname: "\x1e%s\x1e" % query}
            )
    for name, query in kwargs.items():
        if query is None:
            q |= Q(
                **{fname: "\x1e%s=" % name}
            )
        elif isinstance(query, (tuple, list, set)):
            for item in query:
                q |= Q(
                    **{fname: "\x1e%s=%s\x1e" % (name, item)}
                )
        else:
            q |= Q(
                **{fname: "\x1e%s=%s\x1e" % (name, query)}
            )
    return q
