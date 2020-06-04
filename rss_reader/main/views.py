from django.shortcuts import render,redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import ListView
from django.urls import reverse

from . import models as feeds_models
from . import utils as feeds_utils

from .forms import *
from .filters import *

import datetime

def login_excluded(redirect_to):
    """ This decorator kicks authenticated users out of a view 
        https://stackoverflow.com/questions/55062157/how-to-prevent-user-to-access-login-page-in-django-when-already-logged-in""" 
    def _method_wrapper(view_method):
        def _arguments_wrapper(request, *args, **kwargs):
            if request.user.is_authenticated:
                return redirect(redirect_to) 
            return view_method(request, *args, **kwargs)
        return _arguments_wrapper
    return _method_wrapper

def landing(request):
    """Default landing page if user is not logged in"""
    return render(request, 'main/landing.html')

def home(request):
    """Home page with all the user's feeds"""
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('landing'))
    sources = feeds_models.Source.objects.filter(owner=request.user)
    print(sources.filter(name="xkcd.com"))
    if request.GET.get("new_posts"):
        feeds_utils.update_feeds(sources=sources, max_feeds=len(sources))
        last_checked = feeds_models.LastChecked(checked_time=datetime.datetime.now(), owner=request.user)
        last_checked.save()
    last_checked = feeds_models.LastChecked.objects.last()
    
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

@login_required(redirect_field_name='landing')
def get_feeds(request):
    """List view for the user's sources"""

    queryset = feeds_models.Source.objects.filter(owner=request.user)
    return render(request, 'main/feeds.html', {'feeds':queryset})

@login_required(redirect_field_name='login')
def add_feed(request):
    """Create view for the user's feeds"""
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
    """Update view for the user's sources"""
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
    """Delete view for the user's sources"""
    try:
        feed = feeds_models.Source.objects.get(id = int(feed_id), owner=request.user)
    except feeds_models.Source.DoesNotExist:
        return redirect('feeds')
    
    feed.delete()
    return redirect('feeds')

@login_excluded('home')
def signup_view(request):
    """Signup view"""
    form = SignUpForm(request.POST or None)
    if form.is_valid():
        form.save()
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=password)
        login(request, user)
        return redirect('home')
    return render(request, 'main/signup.html', {'form': form})
