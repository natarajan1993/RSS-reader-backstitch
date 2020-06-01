import django_filters as filters
from django_filters.widgets import RangeWidget
from feeds.models import Post

class PostFilter(filters.FilterSet):
    created = filters.DateFromToRangeFilter(field_name='created',
                                            widget=RangeWidget(attrs={'placeholder': 'mm/dd/yyyy',
                                                                      'classname':'datepicker'}))
    class Meta:
        model = Post
        fields = {
                  'source__name':['icontains'],
                  'title':['icontains'],
                 }
