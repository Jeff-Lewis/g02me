from django.conf.urls.defaults import *
from views import *

urlpatterns = patterns('',
    (r'^$', Home),
    (r'^admin(/(?P<command>[a-z\-]+))?$', Admin),
    (r'^([0-9A-Za-z-_]+)$', FrameSet),
    (r'^info/([0-9A-Za-z-_]+)$', Head),
    (r'^user/([0-9A-Za-z-_]+)$', UserHistory),    
    (r'^tag/([0-9A-Za-z-_ ]+)$', TagHistory),
    (r'^map/$', MakeAlias),
    (r'^\+map$', MakeAlias), # Original bookmarklet - backward compatible
    (r'^comment/$', MakeComment),
)
