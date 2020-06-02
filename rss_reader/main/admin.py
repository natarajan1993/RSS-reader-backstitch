from django.contrib import admin

from .models import *

admin.site.register(Source)
admin.site.register(Post)
admin.site.register(Enclosure)
admin.site.register(WebProxy)