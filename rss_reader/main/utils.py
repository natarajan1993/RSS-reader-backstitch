# Full credit to django-feed-reader https://github.com/xurble/django-feed-reader
"""
1. Take the list of sources from the view and send it to read_feed()
2. read_feed() will use Python's requests() to read the feed url
    - Navigate all the redirects and set the redirect specific fields in the model
    - If feed is protected by cloudflare, proxies are activated
        - Each proxy is tried on each retry until we burn through all of them
    - 400 and 500 errors are simply logged and ignored
    - 300 redirect errors are checked for temporary or permanent redirects and then the url of the source is modified with the redirect url
    - 200 codes are good -> The headers are set from the request headers and the body and url is sent to the parser delegator
3. Parser delegator is import_feed() which checks if the feed is XML or JSON and uses the appropriate parsing function
    - Adds an index to the post and returns the status which is logged in read_feed()
4. parse_feed_xml() or parse_feed_json() takes in the source instance, the feed body content and the output instance. Sets the source title, description, image for the source
    - Sets the title, url, description and guid
    - Checks if the guid already exists. Saves the post if it does not exist"""
from django.db.models import Q

from django.utils import timezone

from .models import Source, Post, WebProxy

import feedparser as parser

import time
import datetime

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests

import pyrfc3339
import json

from django.conf import settings

import hashlib
from random import choice
import logging



class NullOutput(object):
    # little class for when we have no outputter    
    def write(self, string):
        print(string)


def _customize_sanitizer(fp):
    # Remove all weird attributes from the feed

    bad_attributes = [
        "align",
        "valign",
        "hspace",
        "class",
        "width",
        "height"
    ]
    
    for item in bad_attributes:
        try:
            if item in fp._HTMLSanitizer.acceptable_attributes: # _HTMLSanitizer is from the feedparser module
                fp._HTMLSanitizer.acceptable_attributes.remove(item)
        except Exception:
            logging.debug("Could not remove {}".format(item))
            

def get_agent(source_feed):
    # Get a random user agent from our list if the feed is protected by cloudflare
    if source_feed.is_cloudflare:
        agent = random_user_agent()
        logging.error("using agent: {}".format(agent))
    else: # If it's not cloudflare just generate a default user agent
        agent = "{user_agent} (+{server}; Updater; {subs} subscribers)".format(user_agent=settings.FEEDS_USER_AGENT, server=settings.FEEDS_SERVER, subs=source_feed.num_subs)

    return agent

def random_user_agent():

    return choice([
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393",
        "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)",
        "Mozilla/5.0 (iPad; CPU OS 8_4_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H321 Safari/600.1.4",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1",
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (Linux; Android 5.0; SAMSUNG SM-N900 Build/LRX21V) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/2.1 Chrome/34.0.1847.76 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 6.0.1; SAMSUNG SM-G570Y Build/MMB29K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/4.0 Chrome/44.0.2403.133 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0"
    ])



def fix_relative(html, url):
    # Helper function that takes a relative path and converts it into a http address
    try:
        base = "/".join(url.split("/")[:3])

        html = html.replace("src='//", "src='http://")
        html = html.replace('src="//', 'src="http://')


        html = html.replace("src='/", "src='%s/" % base)
        html = html.replace('src="/', 'src="%s/' % base)
    
    except Exception as ex:
        pass    

    return html
        

def update_feeds(sources=None, max_feeds=3, output=NullOutput()):
    # Function that goes through each source for the user and checks for updates
    # Added functionality to only update the user's feeds when the button is pressed
    if sources is None: # Redundant check if the view did not pass in any user specific sources, then check all of them
        todo = Source.objects.filter(Q(due_poll__lt = timezone.now()) & Q(live = True))
    else:
        todo = sources

    
    output.write("Queue size is {}".format(todo.count()))

    sources = todo.order_by("due_poll")[:max_feeds] # Clamps the max updated feeds at once to only 3 but we changed it to all feeds in models.py

    output.write("\nProcessing %d\n\n" % sources.count())


    for src in sources:
        read_feed(src, output)
        
    # kill bad proxies
    
    WebProxy.objects.filter(address='X').delete()
    
    
def read_feed(source_feed, output=NullOutput()):
    # Function that goes through each and every source for the user and navigates the redirects and updates model
    # Calls appropriate xml or json parser for each feed
    old_interval = source_feed.interval


    was302 = False
    
    output.write("\n------------------------------\n")
    
    source_feed.last_polled = timezone.now()
    
    agent = get_agent(source_feed)

    headers = { "User-Agent": agent } #identify ourselves 


    proxies = {}
    proxy = None
    if source_feed.is_cloudflare :
        # If it's a cloudflare link, then change the proxy to a new one
        try:
            proxy = get_proxy(output)
            
            if proxy.address != "X":
            
                proxies = {
                  'http': "http://" + proxy.address,
                  'https': "https://" + proxy.address,
                }
        except:
            pass    


    if source_feed.etag:
        headers["If-None-Match"] = str(source_feed.etag)
    if source_feed.last_modified:
        headers["If-Modified-Since"] = str(source_feed.last_modified)

    output.write("\nFetching %s" % source_feed.feed_url)
    
    ret = None
    try:
        # Just getting the status response from the feed
        ret = requests.get(source_feed.feed_url, headers=headers, allow_redirects=False, timeout=20, proxies=proxies)
        source_feed.status_code = ret.status_code # This is the HTTP status code
        source_feed.last_result = "Unhandled Case"
        output.write(str(ret))
    except Exception as ex:
        logging.error("Fetch feed error: " + str(ex))
        source_feed.last_result = ("Fetch error:" + str(ex))[:255]
        source_feed.status_code = 0
        output.write("\nFetch error: " + str(ex))

        # If there is an error try a different proxy for next check check
        if proxy:
            source_feed.lastResult = "Proxy failed. Next retry will use new proxy"
            source_feed.status_code = 1  # this will stop us increasing the interval

            output.write("\nBurning the proxy.")
            proxy.delete()
            source_feed.interval /= 2


    """Handle all the redirect issues and set the fields in the model"""
    if ret is None and source_feed.status_code == 1: # Edge case
        pass
    elif ret == None or source_feed.status_code == 0: # Retry case
        source_feed.interval += 120 # Increase retry time
    elif ret.status_code < 200 or ret.status_code >= 500:
        #errors, impossible return codes
        source_feed.interval += 120 # Increase retry time
        source_feed.last_result = "Server error fetching feed (%d)" % ret.status_code
    elif ret.status_code == 404:
        #not found
        source_feed.interval += 120 # Increase retry time
        source_feed.last_result = "The feed could not be found"
    elif ret.status_code == 403 or ret.status_code == 410: #Forbidden or gone

        if "Cloudflare" in ret.text or ("Server" in ret.headers and "cloudflare" in ret.headers["Server"]):

            if source_feed.is_cloudflare and proxy is not None:
                # Feed is blocked by cloudflare
                proxy.delete()
                output.write("\Proxy seemed to also be blocked, burning")
                source_feed.interval /= 2
                source_feed.lastResult = "Proxy kind of worked but still got cloudflared."
            else:            
                source_feed.is_cloudflare = True
                source_feed.last_result = "Blocked by Cloudflare (grr)"
        else:
            source_feed.last_result = "Feed is no longer accessible."
            source_feed.live = False
            

    elif ret.status_code >= 400 and ret.status_code < 500:
        #treat as bad request. Turn off the feed
        source_feed.live = False
        source_feed.last_result = "Bad request (%d)" % ret.status_code
    elif ret.status_code == 304:
        #not modified
        source_feed.interval += 10
        source_feed.last_result = "Not modified"
        source_feed.last_success = timezone.now()
        
        if source_feed.last_success and (timezone.now() - source_feed.last_success).days > 7:
            # If it's been more than 7 days since any change, reset the last modified
            source_feed.last_result = "Clearing etag/last modified due to lack of changes"
            source_feed.etag = None
            source_feed.last_modified = None
        
        
    
    elif ret.status_code == 301 or ret.status_code == 308: #permenant redirect
        new_url = "" # Redirect url
        try:
            if "Location" in ret.headers: # Get redirect url from headers
                new_url = ret.headers["Location"]
            
                if new_url[0] == "/":
                    #find the domain from the feed
                    
                    base = "/".join(source_feed.feed_url.split("/")[:3])
                    
                
                    new_url = base + new_url


                source_feed.feed_url = new_url
            
                source_feed.last_result = "Moved"
            else:
                source_feed.last_result = "Feed has moved but no location provided"
        except Exception as Ex:
            output.write("\nError redirecting.")
            source_feed.last_result = "Error redirecting feed to " + new_url  
            pass
    elif ret.status_code == 302 or ret.status_code == 303 or ret.status_code == 307: #Temporary redirect
        new_url = ""
        was302 = True
        try:
            new_url = ret.headers["Location"]
            
            if new_url[0] == "/":
                #find the domain from the feed
                start = source_feed.feed_url[:8]
                end = source_feed.feed_url[8:]
                if end.find("/") >= 0:
                    end = end[:end.find("/")]
                
                new_url = start + end + new_url
                
            
            ret = requests.get(new_url, headers=headers, allow_redirects=True, timeout=20)
            source_feed.status_code = ret.status_code
            source_feed.last_result = "Temporary Redirect to " + new_url

            if source_feed.last_302_url == new_url:
                #this is where we 302'd to last time
                td = timezone.now() - source_feed.last_302_start
                if td.days > 60:
                    source_feed.feed_url = new_url
                    source_feed.last_302_url = " "
                    source_feed.last_302_start = None
                    source_feed.last_result = "Permanent Redirect to " + new_url 
                else:
                    source_feed.last_result = "Temporary Redirect to " + new_url + " since " + source_feed.last_302_start.strftime("%d %B")

            else:
                source_feed.last_302_url = new_url
                source_feed.last_302_start = timezone.now()

                source_feed.last_result = "Temporary Redirect to " + new_url + " since " + source_feed.last_302_start.strftime("%d %B")


        except Exception as ex:     
            source_feed.last_result = "Failed Redirection to " + new_url +  " " + str(ex)
            source_feed.interval += 60
    
    #NOT ELIF, WE HAVE TO START THE IF AGAIN TO COPE WTIH 302
    if ret and ret.status_code >= 200 and ret.status_code < 300: # All the 200 status codes cases

        # 200 is OK so setting the OK flag as True
        ok = True
        changed = False 
        
        # If we came here from a redirect, get a new etag and remove the last modified time
        if was302:
            source_feed.etag = None
            source_feed.last_modified = None
        else:
            try:
                source_feed.etag = ret.headers["etag"]
            except Exception as ex:
                source_feed.etag = None                                   
            try:
                source_feed.last_modified = ret.headers["Last-Modified"]
            except Exception as ex:
                source_feed.last_modified = None                                   
        
        output.write("\netag:%s\nLast Mod:%s\n\n" % (source_feed.etag,source_feed.last_modified))


        content_type = "Not Set"
        if "Content-Type" in ret.headers:
            content_type = ret.headers["Content-Type"]

        #----------------Finally send the call to parse the feed after handling and setting all redirects-------------------
        (ok,changed) = import_feed(source_feed=source_feed, feed_body=ret.content, content_type=content_type, output=output)
        
        if ok and changed:
            source_feed.interval /= 2
            source_feed.last_result = " OK (updated)" #and temporary redirects
            source_feed.last_change = timezone.now()
            
        elif ok:
            source_feed.last_result = "OK"
            source_feed.interval += 20 # we slow down feeds a little more that don't send headers we can use
        else: #not OK
            source_feed.interval += 120
    
    # Clamp the next update interval to not less than an hour or more than 24 hours
    if source_feed.interval < 60:
        source_feed.interval = 60 # no less than 1 hour
    if source_feed.interval > (60 * 24):
        source_feed.interval = (60 * 24) # no more than a day
    
    output.write("\nUpdating source_feed.interval from %d to %d\n" % (old_interval, source_feed.interval))
    td = datetime.timedelta(minutes=source_feed.interval)
    source_feed.due_poll = timezone.now() + td # Update to when the next time the feed needs to be updated
    source_feed.save()
        

def import_feed(source_feed, feed_body, content_type, output=NullOutput()):
    # Determine whethere the feed is xml or json and parse that accordingly

    ok = False
    changed = False
    
    if "xml" in content_type or feed_body[0:1] == b"<":
        (ok,changed) = parse_feed_xml(source_feed, feed_body, output)
    elif "json" in content_type or feed_body[0:1] == b"{":
        (ok,changed) = parse_feed_json(source_feed, str(feed_body, "utf-8"), output)
    else:
        ok = False
        source_feed.last_result = "Unknown Feed Type: " + content_type

    if ok and changed: #Update when the source was last changed if it was successfully updated
        source_feed.last_result = " OK (updated)" #and temporary redirects
        source_feed.last_change = timezone.now()
        
        idx = source_feed.max_index
        # give indices to posts based on created date
        posts = Post.objects.filter(Q(source=source_feed) & Q(index=0)).order_by("created")
        for p in posts:
            idx += 1
            p.index = idx
            p.save()
            
        source_feed.max_index = idx
    
    return (ok, changed)
    

    
def parse_feed_xml(source_feed, feed_content, output):
    # Parse the feed if it's a XML feed. Also changes the source title, url, description and image if it's present in the body of the feed
    ok = True
    changed = False 

    #output.write(ret.content)           
    try:
        
        _customize_sanitizer(parser)
        f = parser.parse(feed_content) #Using python's feedparser module
        entries = f['entries'] # Get all the entries in the XML body
        if len(entries):
            source_feed.last_success = timezone.now() #in case we start auto unsubscribing long dead feeds
        else:
            source_feed.last_result = "Feed is empty"
            ok = False

    except Exception as ex:
        source_feed.last_result = "Feed Parse Error"
        entries = []
        ok = False
    
    if ok:
        try:
            source_feed.name = f.feed.title # Get the name of the source
        except Exception as ex:
            pass

        try:
            source_feed.site_url = f.feed.link # Get the url of the source
        except Exception as ex:
            pass
    

        try:
            source_feed.image_url = f.feed.image.href # Get any images
        except:
            pass


        # either of these is fine, prefer description over summary
        # also feedparser will give us itunes:summary etc if there
        try:
            source_feed.description = f.feed.summary # Get any description or summary tags
        except:
            pass

        try:
            source_feed.description = f.feed.description
        except:
            pass



        #output.write(entries)
        entries.reverse() # Entries are typically in reverse chronological order - put them in right order
        for e in entries:
        

            # we are going to take the longest attrib between the content, summary, summary_detail and description tags
            body = ""
            
            if hasattr(e, "content"):
                for c in e.content:
                    if len(c.value) > len(body):
                        body = c.value
            
            if hasattr(e, "summary"):
                if len(e.summary) > len(body):
                    body = e.summary

            if hasattr(e, "summary_detail"):
                if len(e.summary_detail.value) > len(body):
                    body = e.summary_detail.value

            if hasattr(e, "description"):
                if len(e.description) > len(body):
                    body = e.description


            body = fix_relative(body, source_feed.site_url)
            
            try:
                guid = e.guid # Set the guid that we are using as the unique id to check for repeats
            except Exception as ex:
                try: # If it doesn't have a guid, set the url as the guid
                    guid = e.link
                except Exception as ex: # If there's no link, create a random ID and set that as the guid
                    m = hashlib.md5()
                    m.update(body.encode("utf-8"))
                    guid = m.hexdigest()
                    
            try:
                # TODO: Reduce number of database accessess. Get all posts for source as array and check with that
                p  = Post.objects.filter(source=source_feed).filter(guid=guid)[0] # Check if the post has already been recovered
                output.write("EXISTING " + guid + "\n")

            except Exception as ex:
                output.write("NEW " + guid + "\n")
                p = Post(index=0, body=" ")
                p.found = timezone.now() # Set when the post was created. Could probably replace with auto_now_add in the model
                changed = True
                p.source = source_feed # Set the source of the post as the source we are currently parsing
    
            try:
                title = e.title  # Set the title and the url for the post
            except Exception as ex:
                title = ""
                        
            try:
                p.link = e.link # Set the title and the url for the post
            except Exception as ex:
                p.link = ''
            p.title = title

            try:
                p.image_url = e.image.href # Set any images for the post. Overriding in the model's save() method to parse image tags in the body
            except:
                pass


            try:
                # When the post was created. Could also replace with auto_now_add
                p.created  = datetime.datetime.fromtimestamp(time.mktime(e.published_parsed)).replace(tzinfo=timezone.utc)

            except Exception as ex:
                output.write("CREATED ERROR")     
                p.created  = timezone.now()
        
            p.guid = guid # Set the guid of the post
            try:
                p.author = e.author # Set the author of the post
            except Exception as ex:
                p.author = ""


            try:
                p.save() # Finally save the post
            except Exception as ex:
                output.write(str(ex))


            try:
                p.body = body                          
                p.save() # Finally save the post
                # output.write(p.body)
            except Exception as ex:
                output.write(str(ex))
                output.write(p.body)

    return (ok,changed)
    
    
    
def parse_feed_json(source_feed, feed_content, output):
    # Exactly the same as parsing xml but we are using the python json parser to load the feed
    ok = True
    changed = False 

    try:
        f = json.loads(feed_content)
        entries = f['items'] # Get all the items in the body
        if len(entries):
            source_feed.last_success = timezone.now() #in case we start auto unsubscribing long dead feeds
        else:
            source_feed.last_result = "Feed is empty"
            source_feed.interval += 120
            ok = False

    except Exception as ex:
        source_feed.last_result = "Feed Parse Error"
        entries = []
        source_feed.interval += 120
        ok = False
    
    if ok:
    
    
        if "expired" in f and f["expired"]:
            # This feed says it is done for now. source_feed.interval to max
            source_feed.interval = (24*3*60)
            source_feed.last_result = "This feed has expired"
            return (False, False, source_feed.interval)

        try:
            source_feed.site_url = f["home_page_url"]
            source_feed.name = f["title"]
        except Exception as ex:
            pass


        if "description" in f:
            _customize_sanitizer(parser)
            source_feed.description = parser._sanitizeHTML(f["description"], "utf-8", 'text/html')
            
        _customize_sanitizer(parser)
        source_feed.name = parser._sanitizeHTML(source_feed.name, "utf-8", 'text/html')

        if "icon" in f:
            source_feed.image_url = f["icon"]


        #output.write(entries)
        entries.reverse() # Entries are typically in reverse chronological order - put them in right order
        for e in entries:
            body = " "
            if "content_text" in e:
                body = e["content_text"]
            if "content_html" in e:
                body = e["content_html"] # prefer html over text
                
            body = fix_relative(body,source_feed.site_url)
            
            

            try:
                guid = e["id"]
            except Exception as ex:
                try:
                    guid = e["url"]
                except Exception as ex:
                    m = hashlib.md5()
                    m.update(body.encode("utf-8"))
                    guid = m.hexdigest()
                    
            try:
                p  = Post.objects.filter(source=source_feed).filter(guid=guid)[0]
                output.write("EXISTING " + guid + "\n")

            except Exception as ex:
                output.write("NEW " + guid + "\n")
                p = Post(index=0, body=' ')
                p.found = timezone.now()
                changed = True
                p.source = source_feed
    
            try:
                title = e["title"]
            except Exception as ex:
                title = ""      
                
            # borrow the RSS parser's sanitizer
            _customize_sanitizer(parser)
            body  = parser._sanitizeHTML(body, "utf-8", 'text/html') # TODO: validate charset ??
            _customize_sanitizer(parser)
            title = parser._sanitizeHTML(title, "utf-8", 'text/html') # TODO: validate charset ??
            # no other fields are ever marked as |safe in the templates

            if "banner_image" in e:
                p.image_url = e["banner_image"]                

            if "image" in e:
                p.image_url = e["image"]                

                        
            try:
                p.link = e["url"]
            except Exception as ex:
                p.link = ''
            
            p.title = title

            try:
                p.created  = pyrfc3339.parse(e["date_published"])
            except Exception as ex:
                output.write("CREATED ERROR")     
                p.created  = timezone.now()
        
        
            p.guid = guid
            try:
                p.author = e["author"]
            except Exception as ex:
                p.author = ""
                
            p.save()
            
            try:
                p.body = body                       
                p.save()
                # output.write(p.body)
            except Exception as ex:
                output.write(str(ex))
                output.write(p.body)

    return (ok,changed)
    

def get_proxy(out=NullOutput()):
    # Function that returns the latest proxy from the list of proxies
    p = WebProxy.objects.first()
    
    if p is None:
        find_proxies(out)
        p = WebProxy.objects.first()
    
    out.write("Proxy: {}".format(str(p)))
    
    return p 
    
    

def find_proxies(out=NullOutput()):
    # Function that creates a new proxy from the list of proxies to prevent cloudflare blocking
    
    out.write("\nLooking for proxies\n")
    
    try:
        req = requests.get("https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list.txt", timeout=30)
        if req.status_code == 200:
            list = req.text
            
            list = list.split("\n")
            
            # remove header
            list = list[4:]
            
            for item in list:
                if ":" in item:
                    item = item.split(" ")[0]
                    WebProxy(address=item).save()


                        
    except Exception as ex:
        logging.error("Proxy scrape error: {}".format(str(ex)))
        out.write("Proxy scrape error: {}\n".format(str(ex)))
            
    if WebProxy.objects.count() == 0:
        # something went wrong.
        # to stop infinite loops we will insert duff proxys now
        for i in range(20):
            WebProxy(address="X").save()
        out.write("No proxies found.\n")
    
    