from django.contrib import admin
from django.urls import path, include
from portal import views
from portal.docpup import api as docpup_api
from portal.docpup import configuration as docpup_configuration

urlpatterns = [
    path('docpup/config/', docpup_configuration, name='docpup_config'),
    path('docpup/<slug:action>/', docpup_api, name='docpup'),
    path('admin/', admin.site.urls),
    path('', views.signin, name="signin"),
    path('language/', views.switch, name="language"),
    path('signout/', views.signout, name="signout"),
    path('health/<slug:page>/', views.portal, name="portal"),
]
