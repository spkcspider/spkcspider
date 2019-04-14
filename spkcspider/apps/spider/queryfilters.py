__all__ = ("filter_components", "filter_contents")

from django.db.models import Q
from django.conf import settings


def filter_components(searchlist, filter_unlisted=True, use_contents=True):
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

    for item in searchlist:
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
    searchlist, idlist, filter_unlisted=True, use_components=False
):
    searchq = Q()
    searchq_exc = Q()

    counter = 0
    unlisted_active = False
    # against ddos
    max_counter = settings.SPIDER_MAX_SEARCH_PARAMETERS

    for item in searchlist:
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

    if idlist:
        # idlist contains int and str entries
        try:
            ids = map(lambda x: int(x), idlist)
        except ValueError:
            # deny any access in case of an incorrect id
            ids = []

        searchq &= (
            Q(
                id__in=ids
            )
        )
    if not unlisted_active:
        if filter_unlisted is True:
            searchq_exc |= Q(info__contains="\x1eunlisted\x1e")
        else:
            searchq_exc |= Q(
                info__contains="\x1eunlisted\x1e",
                priority__lte=filter_unlisted
            )
    return (searchq & ~searchq_exc, counter)
