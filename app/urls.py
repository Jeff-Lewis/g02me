from django.conf.urls.defaults import *
import map

urlpatterns = patterns('',
    (r'^$', map.Home),
    (r'^\+map.*', map.MakeAlias),
    (r'^\+info.*', map.Head),
    (r'^([0-9A-Za-z-_]+)', map.FrameSet),
)
