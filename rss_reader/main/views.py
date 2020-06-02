from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import ListView

from rest_framework import generics
from feeds import models as feeds_models
from feeds import utils as feeds_utils

from .forms import *
from .filters import *

import datetime

@login_required(redirect_field_name='login')
def home(request):
    # feeds_utils.update_feeds()
    if request.GET.get("new_posts"):
        feeds_utils.update_feeds()
    last_checked = datetime.datetime.now()
    
    post_list = feeds_models.Post.objects.filter(source__owner = request.user).order_by('-created')
    page = request.GET.get('page',1)
   
    f = PostFilter(request.GET or None, queryset=post_list)
    paginator = Paginator(f.qs,20)
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    return render(request,'main/home.html',{"posts":posts,"filter":f, "last_checked":last_checked})

@login_required(redirect_field_name='login')
def get_feeds(request):
    queryset = feeds_models.Source.objects.filter(owner=request.user)
    return render(request, 'main/feeds.html', {'feeds':queryset})

@login_required(redirect_field_name='login')
def add_feed(request):
    form = SourceCreateForm()
    if request.method == 'POST':
        form = SourceCreateForm(request.POST)
        if form.is_valid():
            feeds_models.Source.objects.create(
                name=form.cleaned_data.get("name"),
                feed_url=form.cleaned_data.get("feed_url"),
                owner=request.user,
                due_poll=datetime.datetime.now()
            )
            return redirect('feeds')
        else:
            print(form.errors)
            return HttpResponse("""your form is wrong, reload on <a href = "{{ url : 'add_feed'}}">reload</a>""")
    else:
        return render(request, 'main/add_feed.html', {'add_feed':form})

@login_required(redirect_field_name='login')
def update_feed(request, feed_id):
    try:
        feed = feeds_models.Source.objects.get(id = int(feed_id),owner=request.user)
    except feeds_models.Source.DoesNotExist:
        return redirect('feeds')
    feed_form = SourceCreateForm(request.POST or None,instance=feed)
    if feed_form.is_valid():
       feed_form.save()
       return redirect('feeds')
    return render(request, 'main/update_feed.html', {'update_feed':feed_form, 'feed':feed})

@login_required(redirect_field_name='login')
def delete_feed(request, feed_id):
    try:
        feed = feeds_models.Source.objects.get(id = int(feed_id), owner=request.user)
    except feeds_models.Source.DoesNotExist:
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
