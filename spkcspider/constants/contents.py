__all__ = [
    "VariantType", "TravelLoginType",
    "dangerous_login_choices", "loggedin_active_tprotections",
    "essential_contents"
]


import enum


essential_contents = {
    "domainmode", "defaultactions"
}


class VariantType(str, enum.Enum):
    # a not assigned
    # use persistent token
    #  can be used for some kind of federation
    #  warning: if token is deleted persisted content is deleted
    persist = "b"
    # update content is without form/for form updates it is not rendered
    # required for still beeing able to update elemental parameters
    raw_update = "c"
    # raw_add not required, archieved by returning response

    # don't list as contentvariant for user (for computer only stuff)
    # set unlisted as default in info field
    # if feature: unlist as a public visible feature
    unlisted = "d"
    # activates domain mode
    domain_mode = "e"
    # allow outside applications push content to spiders
    # adds by default unlisted info attribute
    # appears in features of userComponent
    # counts as foreign content
    # don't list as content variant for user (
    #    except feature_connect and not unique
    # )
    component_feature = "f"
    # same, but assigns to contents
    content_feature = "g"

    # is content unique for usercomponent
    # together with strength level 10: unique for user
    unique = "h"
    # can be used as anchor, will be hashed on verification if primary
    anchor = "i"
    # add as contentvariant (except if unlisted), and create feature
    feature_connect = "j"
    # add as machine creatable content
    machine = "k"
    # exclude from exports
    no_export = "l"

    def __str__(self):
        # output value instead of member name
        return self.value


class TravelLoginType(str, enum.Enum):
    # don't show protected contents and components
    hide = "a"
    # switches to hiding if trigger was activated
    trigger_hide = "b"
    # disable login
    disable = "c"
    # disable login if triggered
    trigger_disable = "C"
    # wipe travel protected contents and components
    # Note: noticable if shared contents are removed
    wipe = "d"
    # wipe user, self destruct user on login, Note: maybe noticable
    wipe_user = "e"

    def __str__(self):
        # output value instead of member name
        return self.value


dangerous_login_choices = {
    TravelLoginType.wipe,
    TravelLoginType.wipe_user
}

loggedin_active_tprotections = {
    TravelLoginType.hide,
    TravelLoginType.disable
}
