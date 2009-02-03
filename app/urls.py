from django.conf.urls.defaults import *
from go2me.views import *

urlpatterns = patterns('',
    (r'^$', Home),
    (r'^popular/$', Popular),

    (r'^user/([a-zA-Z0-9_\.\-]{1,20})$', UserView),
    (r'^user/([a-zA-Z0-9_\.\-]{1,20})/picture_(thumb|med|full)$', UserPicture),    
    (r'^tag/([0-9A-Za-z-_]+)$', TagView),

    (r'^profile/$', UserProfile),    

    (r'^map/$', MakeAlias),
    (r'^comment/(?P<command>[a-z\-]+)?$', DoComment),
    (r'^init/$', InitAPI),
    (r'^lookup/$', Lookup),
    (r'^cmd/setusername$', SetUsername),
    (r'^admin/(?P<command>[a-z\-]+)?$', Admin),
    
    (r'^([0-9A-Za-z-_]+)$', FrameSet),
    
    # Archaic
    (r'^info/([0-9A-Za-z-_]+)$', HeadRedirect),

    (r'^.*$', CatchAll),
)
