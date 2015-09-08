# -*- coding: utf-8 -*-
"""
Created on Wed Sep  2 18:47:12 2015

@author: keith

Google image scraper test
"""

import urllib2
import simplejson
import cStringIO
import urllib
import time

from PIL import Image

fetcher = urllib2.build_opener()
searchTerm = 'parrot'

start = time.time()
files = []
for startIndex in range(0,60,4):
    searchUrl = "http://ajax.googleapis.com/ajax/services/search/images?v=1.0&q=" + searchTerm + "&start={:d}".format(startIndex)
    f = fetcher.open(searchUrl)
    deserialized_output = simplejson.load(f)
    
    for i in range(4):
        imageUrl = deserialized_output['responseData']['results'][i]['unescapedUrl']
        files.append(cStringIO.StringIO(urllib.urlopen(imageUrl).read()))
#        try:
#            img = Image.open(files[-1])
#            img.show()
#        except IOError:
#            print "Image load failed, continuing with next image, there are plenty of fish in the sea!"
            
print time.time()-start