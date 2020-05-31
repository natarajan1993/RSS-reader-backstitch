from django import forms

from feeds.models import Source

class SourceCreateForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = ['name','feed_url']