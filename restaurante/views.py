from rest_framework import viewsets
from .models import Producto, Mesa, Mozo
from .serializers import ProductoSerializer, MesaSerializer, MozoSerializer

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer

class MesaViewSet(viewsets.ModelViewSet):
    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer

class MozoViewSet(viewsets.ModelViewSet):
    queryset = Mozo.objects.all()
    serializer_class = MozoSerializer