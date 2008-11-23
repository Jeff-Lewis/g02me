from django import template
from django.template.defaultfilters import stringfilter
register = template.Library()

@register.filter(name='ellipsis')
@stringfilter
def ellipsis(value, arg):
    """
    Truncates a string more than arg characters and appends elipsis
    """
    try:
        length = int(arg)
    except ValueError: # invalid literal for int()
        return value # Fail silently.
    if (len(value) > length):
        return value[:length] + "..."
    else:
        return value

@register.filter(name='urlizetop')
@stringfilter
def urlizetop(value, sAttr=None):
    from django.utils.html import urlize
    "Converts URLs in plain text into clickable links - with additional attribute text inserted in <a> tags."
    value = urlize(value, nofollow=True)
    return value.replace('<a ', '<a target="_top" ')
    

