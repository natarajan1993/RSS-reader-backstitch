from django.db import models
from django.contrib.auth.models import User

class Feed(models.Model):
    name = models.CharField(max_length=50)
    url = models.CharField(max_length=50)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)


    def __str__(self):
        return self.name
    