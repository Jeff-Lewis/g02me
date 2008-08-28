from django.conf.urls.defaults import *
import views
import map

urlpatterns = patterns('',
    (r'^$', views.Home),
    (r'^map.*', map.Lookup)
)
