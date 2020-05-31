from django import forms

from feeds.models import Source

from .models import Feed

class FeedCreateForm(forms.ModelForm):
    class Meta:
        model = Feed
        fields = ['name','url']
        
class SourceCreateForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = ['name','feed_url']