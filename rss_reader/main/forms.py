from django import forms

from .models import Source

class SourceCreateForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = ['name','feed_url']

SORT_CHOICES = [
    ('-created','Published Date'),
    ('title','Title'),
    ('body','Description')
]        

class PostSortForm(forms.Form):
    sort_choices = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=SORT_CHOICES, required=False)