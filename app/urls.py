from django.conf.urls.defaults import *
import views

urlpatterns = patterns('',
    (r'^$', views.Home),
    (r'^user/([0-9A-Za-z-_]+)', views.UserHistory),    
    (r'^tag/([0-9A-Za-z-_ ]+)', views.TagHistory),
    (r'^\+map.*', views.MakeAlias),
    (r'^\+comment.*', views.MakeComment),
    (r'^\+info.*', views.Head),
    (r'^([0-9A-Za-z-_]+)', views.FrameSet),
)
