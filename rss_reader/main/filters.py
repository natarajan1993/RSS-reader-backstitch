import django_filters as filters
from django_filters.widgets import RangeWidget, LinkWidget
from .models import Post
from django import forms

class PostFilter(filters.FilterSet):
    created = filters.DateFromToRangeFilter(field_name='created',
                                            widget=RangeWidget(attrs={'class':"form-control",
                                                                      'placeholder': 'mm/dd/yyyy',
                                                                      'type':'date'}))
    sort = filters.OrderingFilter(fields=(
                                            ("created","created"),
                                            ("title","title"),
                                            ("description","description"),
                                        ),
                                        field_labels={
                                            'created':"Published Date",
                                            'title':"Title",
                                            'description':"Description",
                                        },
                                        choices=[
                                            ('created',"Oldest"),
                                            ('-created',"Latest"),
                                            ('title',"By Title (A-Z)"),
                                            ('-title',"By Title (Z-A)"),
                                            ('description',"By Description (A-Z)"),
                                            ('-description',"By Description (Z-A)"),
                                        ],
                                        widget=forms.RadioSelect)
    class Meta:
        model = Post
        fields = {
                  'source__name':['icontains'],
                  'title':['icontains'],
                 }