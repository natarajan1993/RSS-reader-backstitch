from django.shortcuts import render

def home(request):
    return render(request,'main/home.html')

def feeds(request):
    return render(request, 'main/feeds.html')