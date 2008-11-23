from django.conf.urls.defaults import *
from go2me.views import *

urlpatterns = patterns('',
    (r'^$', Home),
    (r'^([0-9A-Za-z-_]+)$', FrameSet),
    (r'^info/([0-9A-Za-z-_]+)$', Head),
    (r'^user/([a-zA-Z0-9_\.\-]{1,20})$', UserView),    
    (r'^tag/([0-9A-Za-z-_]+)$', TagView),
    (r'^map/$', MakeAlias),
    (r'^lookup/$', Lookup),
    (r'^cmd/setusername$', SetUsername),  
    (r'^comment/(?P<command>[a-z\-]+)?$', DoComment),
    (r'^admin/(?P<command>[a-z\-]+)?$', Admin),
    (r'^.*$', CatchAll),
)
