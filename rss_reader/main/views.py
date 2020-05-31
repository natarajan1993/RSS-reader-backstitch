from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm

from rest_framework import generics
from feeds import models as feeds_models
from feeds import utils as feeds_utils

from .models import *
from .serializers import *
from .forms import *

import datetime

def home(request):
    if request.GET.get("new_posts"):
        feeds_utils.update_feeds()
    posts = feeds_models.Post.objects.filter(source__owner = request.user)
    return render(request,'main/home.html',{"posts":posts})

@login_required(redirect_field_name='home')
def get_feeds(request):
    queryset = feeds_models.Source.objects.filter(owner=request.user)
    return render(request, 'main/feeds.html', {'feeds':queryset})

@login_required(redirect_field_name='home')
def add_feed(request):
    form = FeedCreateForm()
    if request.method == 'POST':
        form = FeedCreateForm(request.POST)
        if form.is_valid():
            feeds_models.Source.objects.create(
                name=form.cleaned_data.get("name"),
                feed_url=form.cleaned_data.get("url"),
                owner=request.user,
                due_poll=datetime.datetime.now()
            )
            return redirect('feeds')
        else:
            print(form.errors)
            return HttpResponse("""your form is wrong, reload on <a href = "{{ url : 'add_feed'}}">reload</a>""")
    else:
        return render(request, 'main/add_feed.html', {'add_feed':form})

@login_required(redirect_field_name='home')
def update_feed(request, feed_id):
    try:
        feed = Feed.objects.get(id = int(feed_id),owner=request.user)
    except Feed.DoesNotExist:
        return redirect('feeds')
    feed_form = FeedCreateForm(request.POST or None,instance=feed)
    if feed_form.is_valid():
       feed_form.save()
       return redirect('feeds')
    return render(request, 'main/update_feed.html', {'update_feed':feed_form, 'feed':feed})

@login_required(redirect_field_name='home')
def delete_feed(request, feed_id):
    try:
        feed = Feed.objects.get(id = int(feed_id), owner=request.user)
    except Feed.DoesNotExist:
        return redirect('feeds')
    
    feed.delete()
    return redirect('feeds')

def signup_view(request):
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        form.save()
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=password)
        login(request, user)
        return redirect('home')
    return render(request, 'main/signup.html', {'form': form})
