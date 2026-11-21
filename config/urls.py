from django.contrib import admin
from django.urls import path, include
from portal import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.signin, name="signin"),
    path('language/', views.switch, name="language"),
    path('signout/', views.signout, name="signout"),
    path('health/<slug:page>/', views.portal, name="portal"),
]
