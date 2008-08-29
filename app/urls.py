from django.conf.urls.defaults import *
import views
import map

urlpatterns = patterns('',
    (r'^$', views.Home),
    (r'^map.*', map.MakeAlias),
    (r'^/([0-9]*)', map.FrameSet),
    (r'^info.*', map.Head),
    
)
