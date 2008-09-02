from django.conf.urls.defaults import *
import views

urlpatterns = patterns('',
    (r'^$', views.Home),
    (r'^\+map.*', views.MakeAlias),
    (r'^\+info.*', views.Head),
    (r'^([0-9A-Za-z-_]+)', views.FrameSet),
)
