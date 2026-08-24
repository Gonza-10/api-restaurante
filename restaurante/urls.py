from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductoViewSet, MesaViewSet, MozoViewSet

router = DefaultRouter()
router.register(r'productos', ProductoViewSet)
router.register(r'mesas', MesaViewSet)
router.register(r'mozos', MozoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]