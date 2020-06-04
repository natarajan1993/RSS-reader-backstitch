# Full credit to django-feed-reader https://github.com/xurble/django-feed-reader
from django.db import models
from django.utils.timezone import utc
from django.contrib.auth.models import User
from django.template.defaultfilters import date as _date
from django.template.defaultfilters import time as _time

import time
import datetime
from urllib.parse import urlencode
import logging
import sys
import email
from bs4 import BeautifulSoup

class Source(models.Model):
    # This is an actual feed that we poll
    name          = models.CharField(max_length=255, blank=True, null=True) # Name of the source
    site_url      = models.CharField(max_length=255, blank=True, null=True) # URL for the parent site of source
    feed_url      = models.CharField(max_length=255) # Actual url of the RSS feed
    image_url     = models.CharField(max_length=255, blank=True, null=True) # Any associated images with the feed
    
    description   = models.TextField(null=True, blank=True) # Description for the source

    last_polled   = models.DateTimeField(max_length=255, blank=True, null=True) # Datetime the source was last polled
    due_poll      = models.DateTimeField(default=datetime.datetime(1900, 1, 1)) # Time to poll the source next. Changed in utils.py. default to distant past to put new sources to front of queue

    #The basic concept is that a feed publisher may provide a special HTTP header, called an ETag, when it publishes a feed. You should send this ETag back to the server on subsequent requests. If the feed has not changed since the last time you requested it, the server will return a special HTTP status code (304) and no feed data.
    etag          = models.CharField(max_length=255, blank=True, null=True)

    last_modified = models.CharField(max_length=255, blank=True, null=True) # just pass this back and forward between server and me , no need to parse
    
    last_result    = models.CharField(max_length=255,blank=True,null=True) # Result of last poll. Set in utils.py
    interval       = models.PositiveIntegerField(default=400) # Interval between polls
    last_success   = models.DateTimeField(null=True) # Datetime of last successful poll
    last_change    = models.DateTimeField(null=True) # Datetime of last change in the feed
    live           = models.BooleanField(default=True) # Boolean if the feed is live or not. Set in utils.py
    status_code    = models.PositiveIntegerField(default=0) # HTTP status code
    last_302_url   = models.CharField(max_length=255, null=True, blank=True) # Last redirect url
    last_302_start = models.DateTimeField(null=True, blank=True) # Time we got redirected last time. Used to set temporary or permanent redirects
    
    max_index     = models.IntegerField(default=0)
    
    num_subs      = models.IntegerField(default=1) # Only use is to set the user agent for non-cloudflare links
    
    is_cloudflare  = models.BooleanField(default=False)

    owner = models.ForeignKey(User,on_delete=models.CASCADE)

    
    def __str__(self):
        return self.display_name
    
    @property
    def best_link(self):
        #the html link else the feed link
        if self.site_url is None or self.site_url == '':
            return self.feed_url
        else:
            return self.site_url

    @property
    def display_name(self):
        if self.name is None or self.name == "":
            return self.best_link
        else:
            return self.name
    

class Post(models.Model):

    # an entry in a feed
    
    source        = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='posts')
    title         = models.TextField(blank=True)
    body          = models.TextField()
    link          = models.CharField(max_length=512, blank=True, null=True)
    found         = models.DateTimeField(auto_now_add=True)
    created       = models.DateTimeField(db_index=True)
    guid          = models.CharField(max_length=255, blank=True, null=True, db_index=True) # The unique ID for each post we use to check for repeats. Either the feed has it, or use the link, or use a md5 hash
    author        = models.CharField(max_length=255, blank=True, null=True)
    index         = models.IntegerField(db_index=True)
    image_url     = models.CharField(max_length=255,blank=True,null=True)

    def save(self, *args, **kwargs):
        soup = BeautifulSoup(self.body)
        if len(soup.get_text()) <= 1:
            self.body = ""
        else:
            self.body = soup.get_text()[:300] + "..."

        images = soup.find_all('img') # Get all image tags in body s

        if len(images) > 0:
            self.image_url = images[0]['src'] # Just select the first image in the array of image tags
        super(Post, self).save(*args, **kwargs) 

    @property
    def title_url_encoded(self):
        try:
            ret = urlencode({"X":self.title})
            if len(ret) > 2: ret = ret[2:]
        except:
            logging.info("Failed to url encode title of post {}".format(self.id))
            ret = ""        

    def __str__(self):
        return f"{self.title}|{self.source.name}"

    class Meta:
        ordering = ["index"]
        
class WebProxy(models.Model):
    # this class if for Cloudflare avoidance and contains a list of potential
    # web proxies that we can try, scraped from the internet
    address = models.CharField(max_length=255)
    
    def __str__(self):
        return "Proxy:{}".format(self.address)


class LastChecked(models.Model):
    checked_time = models.DateTimeField(auto_now=False, auto_now_add=False, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    # def __str__(self):
    #     return str(self.checked_time) # Wed Jun 3 2020, 8:30 am