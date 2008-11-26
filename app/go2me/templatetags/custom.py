from django import template
from django.template.defaultfilters import stringfilter

from util import local

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
    
@register.filter(name='mult')
def MultFilter(value, arg):
    try:
        return float(value) * float(arg)
    except:
        return 0.0

@register.filter(name='urlizetop')
@stringfilter
def urlizetop(value, sAttr=None):
    from django.utils.html import urlize
    "Converts URLs in plain text into clickable links - with additional attribute text inserted in <a> tags."
    value = urlize(value, nofollow=True)
    return value.replace('<a ', '<a target="_top" ')
    
# --------------------------------------------------------------------
# String utilities - format date as an "age"
# --------------------------------------------------------------------

@register.filter(name='Age')
def SAgeReq(dt):
    # Return the age (time between time of request and a date) as a string
    return SAgeDdt(local.dtNow - dt)

def SAgeDdt(ddt):
    """ Format a date as an "age" """
    if ddt.days < 0:
        return "future?"
    months = int(ddt.days*12/365)
    years = int(ddt.days/365)
    if years >= 1:
        return "%d year%s ago" % (years, SPlural(years))
    if months >= 3:
        return "%d months ago" % months 
    if ddt.days == 1:
        return "yesterday"
    if ddt.days > 1:
        return "%d days ago" % ddt.days
    hrs = int(ddt.seconds/60/60)
    if hrs >= 1:
        return "%d hour%s ago" % (hrs, SPlural(hrs))
    minutes = round(ddt.seconds/60)
    if minutes < 1:
        return "seconds ago"
    return "%d minute%s ago" % (minutes, SPlural(minutes))

def SPlural(n, sPlural="s", sSingle=''):
    return [sSingle, sPlural][n!=1]

# --------------------------------------------------------------------
# setvar tag from Django issue: http://code.djangoproject.com/ticket/1322
# --------------------------------------------------------------------

class SetVariable(template.Node):
    def __init__(self, varname, nodelist):
        self.varname = varname
        self.nodelist = nodelist

    def render(self,context):
        context[self.varname] = self.nodelist.render(context) 
        return ''

@register.tag(name='setvar')
def setvar(parser, token):
    """
    Set value to content of a rendered block. 
    {% setvar var_name %}
     ....
    {% endsetvar
    """
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, varname = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires a single argument for variable name" % token.contents.split()[0]

    nodelist = parser.parse(('endsetvar',))
    parser.delete_first_token()
    return SetVariable(varname, nodelist)

# --------------------------------------------------------------------
# with tag back-ported from Django 1.0
# --------------------------------------------------------------------

class WithNode(template.Node):
    def __init__(self, var, name, nodelist):
        self.var = var
        self.name = name
        self.nodelist = nodelist

    def __repr__(self):
        return "<WithNode>"

    def render(self, context):
        val = self.var.resolve(context)
        context.push()
        context[self.name] = val
        output = self.nodelist.render(context)
        context.pop()
        return output

@register.tag(name='with')
def do_with(parser, token):
    """
    Adds a value to the context (inside of this block) for caching and easy
    access.

    For example::

        {% with person.some_sql_method as total %}
            {{ total }} object{{ total|pluralize }}
        {% endwith %}
    """
    bits = list(token.split_contents())
    if len(bits) != 4 or bits[2] != "as":
        raise TemplateSyntaxError("%r expected format is 'value as name'" %
                                  bits[0])
    var = parser.compile_filter(bits[1])
    name = bits[3]
    nodelist = parser.parse(('endwith',))
    parser.delete_first_token()
    return WithNode(var, name, nodelist)

