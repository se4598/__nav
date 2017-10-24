from django.conf.urls import url

from c3nav.mapdata.views import history, tile

urlpatterns = [
    url(r'^(?P<level>\d+)/(?P<zoom>\d+)/(?P<x>-?\d+)/(?P<y>-?\d+).(?P<format>png|svg)$', tile, name='mapdata.tile'),
    url(r'^history/(?P<level>\d+)/(?P<mode>base|render).(?P<format>png|data)$', history, name='mapdata.history'),
]