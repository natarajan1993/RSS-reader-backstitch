from django import forms

from .models import Source
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    username = forms.CharField(max_length=30)
    email = forms.EmailField(max_length=200)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', )

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