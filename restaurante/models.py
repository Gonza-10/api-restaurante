from django.db import models

class Producto(models.Model):
    # Definimos los atributos conectándolos con las columnas exactas de SQL Server
    nombre = models.CharField(max_length=80, db_column='Nombre')
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, db_column='PrecioActual')
    categoria = models.CharField(max_length=50, db_column='Categoria')

    class Meta:
        db_table = 'Producto'
        managed = False

    def __str__(self):
        return self.nombre

class Mesa(models.Model):
    numero = models.IntegerField(db_column='Numero')
    capacidad_maxima = models.IntegerField(db_column='CapacidadMaxima')

    class Meta:
        db_table = 'Mesa'
        managed = False

class Mozo(models.Model):
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, db_column='Apellido')

    class Meta:
        db_table = 'Mozo'
        managed = False