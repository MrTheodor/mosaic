# -*- coding: utf-8 -*-
import flickr
import urllib
from PIL import Image
import scipy

class flickrScraper(object):
    
    def __init__(self):
        api_key = 'f49f4273470a5bb1504142d20aeee4d6'
        api_secret = '0156db5ea3a6a21b'
        flickr.API_KEY = api_key
        flickr.API_SECRET = api_secret
        
        print  "This product uses the Flickr API but is not endorsed or certified by Flickr." #legal
    
    def get_url_proper(self, photo): #but slow, many API calls
        return photo.getURL(size='Square', urlType='source')
    
    def get_url(self, photo): #not good, but fast
        return u'https://farm6.staticflickr.com/{:s}/{:s}_{:s}_s.jpg'.format(photo.server, photo.id, photo.secret)
        
    def scrapeTag(self, tags, per_page, page=1, sort='interestingness=desc'):
        photos = flickr.photos_search(tags=tags, per_page=per_page, page=page, sort=sort)
        
        urls = []
        for photo in photos:
            urls.append(self.get_url(photo))
        
        return urls
        
    def fetchFiles(self, urls):
        files = []
        for url in urls:
            file, mime = urllib.urlretrieve(url)
            files.append(file)
        return files

    def fetchFileData(self, url):
        arr = None
        while arr is None:
            try:
                im = Image.open(urllib.urlretrieve(url)[0])
                arr = scipy.array(im)
                if len(arr.shape) == 2:
		    # greyscale handling in the scraper might be the best way
		    # it certainly is the first possibility, so negate the requirement for further handling
                    arr = arr.reshape((arr.shape[0], arr.shape[1], 1))
                    arr = scipy.concatenate((arr, arr, arr), axis=2)
                else:
                    if arr.shape[2] == 4: # image with alpha channel
                        arr = arr[:,:,:3]
                arr = arr.reshape((1,arr.size))
            except:
                # print "******ERRORS*********"
                arr =  None
        return arr
