from django import forms

from .models import Feed

class FeedCreateForm(forms.ModelForm):
    class Meta:
        model = Feed
        fields = ['name','url']