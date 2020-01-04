"""
Form messages
"""


__all__ = [
    "help_text_static_token", "help_text_features_components",
    "help_text_features_contents", "time_help_text", "travel_protection"
]

from django.utils.translation import gettext_lazy as _


help_text_static_token = _("""Generate a new static token with variable strength<br/>
Tokens protect against bruteforce and attackers<br/>
If you have problems with attackers (because they know the token),
you can invalidate it with this option and/or add protections<br/>
<table style="color:red;">
<tr>
<td style="vertical-align: top">Warning:</td><td>this removes also access for all services you gave the link<td/>
</tr>
<tr>
<td style="vertical-align: top">Warning:</td><td>public user components disclose static token, regenerate after removing
public attribute from component for restoring protection</td>
</tr>
</table>
""")  # noqa: E501


help_text_features_components = _("""
Features which should be active on component and user content<br/>
Note: persistent Features (=features which use a persistent token) require and enable "Persistence"
""")  # noqa: E501


help_text_features_contents = _("""
Features which should be active on user content<br/>
Note: persistent Features (=features which use a persistent token) require the active "Persistence" Feature on usercomponent. They are elsewise excluded.
""")  # noqa: E501


time_help_text = _(
    "Time in \"{timezone}\" timezone"
)


travel_protection = _(
    "Hide: Hide protected contents and components<br/>"
    "Hide if triggered: Hide protected contents and components if triggered<br/>"  # noqa: E501
    "Disable: Disable Login (not available on Self-Protection (useless))<br/>"
    "Disable if triggered: Hide protected contents and components and disable login if triggered<br/>"  # noqa: E501
    "Wipe: Wipe protected content on login (maybe not available)<br/>"
    "Wipe User: destroy user on login (maybe not available)<br/><br/>"
    "Note: login protections work only on login. Except hide and disable protections, which works also for logged in users<br/>"  # noqa: E501
    "Note: the hide and disable protections disable also admin access when active (elsewise easy circumventable)"  # noqa: E501
)
