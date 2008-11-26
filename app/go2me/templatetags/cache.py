# File copied from Django 1.0 distribution

from django.template import Library, Node, TemplateSyntaxError, VariableDoesNotExist, resolve_variable
from django.template import resolve_variable
from google.appengine.api import memcache as cache
import settings

register = Library()

class CacheNode(Node):
    def __init__(self, nodelist, expire_time_var, fragment_name, vary_on):
        self.nodelist = nodelist
        self.expire_time_var = expire_time_var
        self.fragment_name = fragment_name
        self.vary_on = vary_on

    def render(self, context):
        try:
            expire_time = resolve_variable(self.expire_time_var, context)
        except VariableDoesNotExist:
            raise TemplateSyntaxError('"cache" tag got an unknkown variable: %r' % self.expire_time_var.var)
        try:
            expire_time = int(expire_time)
        except (ValueError, TypeError):
            raise TemplateSyntaxError('"cache" tag got a non-integer timeout value: %r' % expire_time)
        # Build a unicode key for this fragment and all vary-on's.
        if settings.CACHE_ON:
            cache_key = u':'.join([self.fragment_name] + [urlquote(resolve_variable(var, context)) for var in self.vary_on])
            value = cache.get(cache_key)
        else:
            value = None
        if value is None:
            value = self.nodelist.render(context)
            if settings.CACHE_ON:
                cache.set(cache_key, value, expire_time)
        return value

@register.tag(name='cache')
def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load cache %}
        {% cache [expire_time] [fragment_name] %}
            .. some expensive processing ..
        {% endcache %}

    This tag also supports varying by a list of arguments::

        {% load cache %}
        {% cache [expire_time] [fragment_name] [var1] [var2] .. %}
            .. some expensive processing ..
        {% endcache %}

    Each unique set of arguments will result in a unique cache entry.
    """
    nodelist = parser.parse(('endcache',))
    parser.delete_first_token()
    tokens = token.contents.split()
    if len(tokens) < 3:
        raise TemplateSyntaxError(u"'%r' tag requires at least 2 arguments." % tokens[0])
    return CacheNode(nodelist, tokens[1], tokens[2], tokens[3:])
