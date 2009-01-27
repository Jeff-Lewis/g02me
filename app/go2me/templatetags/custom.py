from django import template
from django.template.defaultfilters import stringfilter

import util
import settings

import re

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

# ------------------------------------------------------------------
# urlized copied (modified) from Django html.py
# ------------------------------------------------------------------

# Configuration for urlize() function
LEADING_PUNCTUATION  = ['(', '<', '&lt;']
TRAILING_PUNCTUATION = ['.', ',', ')', '>', '\n', '&gt;']

# list of possible strings used for bullets in bulleted lists
DOTS = ['&middot;', '*', '\xe2\x80\xa2', '&#149;', '&bull;', '&#8226;']

unencoded_ampersands_re = re.compile(r'&(?!(\w+|#\d+);)')
word_split_re = re.compile(r'(\s+)')
punctuation_re = re.compile('^(?P<lead>(?:%s)*)(?P<middle>.*?)(?P<trail>(?:%s)*)$' % \
    ('|'.join([re.escape(x) for x in LEADING_PUNCTUATION]),
    '|'.join([re.escape(x) for x in TRAILING_PUNCTUATION])))
simple_email_re = re.compile(r'^\S+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+$')

def urlize(text, trim_url_limit=None, nofollow=False, target=None, extra=None):
    """
    Converts any URLs in text into clickable links. Works on http://, https:// and
    www. links. Links can have trailing punctuation (periods, commas, close-parens)
    and leading punctuation (opening parens) and it'll still do the right thing.

    If trim_url_limit is not None, the URLs in link text will be limited to
    trim_url_limit characters.

    If nofollow is True, the URLs in link text will get a rel="nofollow" attribute.
    
    If target is given, set as target attribute of link (e.g., _blank, _top, or <frame_name>)
    """
    trim_url = lambda x, limit=trim_url_limit: limit is not None and (x[:limit] + (len(x) >=limit and '...' or ''))  or x
    words = word_split_re.split(text)
    nofollow_attr = nofollow and ' rel="nofollow"' or ''
    
    sTarget = ''
    if target is not None:
        sTarget = ' target="%s"' % target
        
    sPattern = r'<a href="%(href)s"%(nofollow)s%(target)s>%(trim)s</a>'
    if extra is not None:
        sPattern += extra
        
    for i, word in enumerate(words):
        match = punctuation_re.match(word)
        if match:
            lead, middle, trail = match.groups()
            if simple_email_re.match(middle):
                middle = '<a href="mailto:%s">%s</a>' % (middle, middle)
            else:
                sTrim = trim_url(middle)
                if util.regDomain.match(middle):
                    middle = 'http://' + middle
                if middle.startswith('http://') or middle.startswith('https://'):
                    middle = sPattern % {'target':sTarget, 'href':util.Href(middle),
                                         'nofollow':nofollow_attr, 'trim':sTrim}

            if lead + middle + trail != word:
                words[i] = lead + middle + trail
    return ''.join(words)

@register.filter(name='urlizecomment')
@stringfilter
def urlizecomment(value, sAttr=None):
    # Converts URLs in plain text into clickable links
    return urlize(value, nofollow=True, target="content-frame",
                  extra=r'&nbsp;<a title="New ' + settings.sSiteName +
                        r' Page" target="_blank" href="/map/?url=%(href)s"><img class="inline-link" src="/images/go2me-link.png"></a>')

    
# --------------------------------------------------------------------
# String utilities - format date as an "age"
# --------------------------------------------------------------------

@register.filter(name='Age')
def SAgeReq(dt):
    # Return the age (time between time of request and a date) as a string
    return SAgeDdt(util.local.dtNow - dt)

def SAgeDdt(ddt):
    """ Format a date as an "age" """
    if ddt.days < 0:
        return "in the future?"
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

