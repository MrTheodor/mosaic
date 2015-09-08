# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 19:44:51 2015

@author: keith

Makes a mosaic out of an example image using a stream of 
tile images, rather than a fixed list of tile images
"""

import os
import sys
import time
import scipy
import itertools

from PIL import Image
from multiprocessing import Process, Queue, cpu_count
import flickr_scraper
import photo_match_tinygrey as photo_match
from matplotlib import pyplot as plt
from matplotlib import cm as cm
plt.close('all')

NPlacers = 2
NScrapers = 1

#%% adjust the image to have the correct shape (aspect ratio) for turning it into a mosaic
PixPerTile = scipy.array((75,75))
MaxTilesVert = 20
TilesVert = int(MaxTilesVert/NPlacers) * NPlacers

TargetImg = Image.open('./KWM18333.JPG')
TargetSize = TargetImg.size
TilesHor = (TargetSize[0]*PixPerTile[1]*TilesVert)/(TargetSize[1]*PixPerTile[0])
Tiles = scipy.array((TilesHor, TilesVert), dtype=int)
TilesPerNode = scipy.array((TilesHor, TilesVert/NPlacers), dtype=int)
TotalTilesPerNode = scipy.prod(TilesPerNode)
Pixels = Tiles*PixPerTile
UnscaledWidth = (TargetSize[1]*Tiles[0])/Tiles[1]# the width of the original size image to yield the correct aspect ratio
CropMargin = (TargetSize[0] - UnscaledWidth)/2
#TargetImg.crop((0,0,))
#TargetImg.resize(Pixels)
CroppedImg = TargetImg.transform((UnscaledWidth,TargetSize[1]), Image.EXTENT, (CropMargin,0, CropMargin+UnscaledWidth,TargetImg.size[1]))
CroppedArr = scipy.array(CroppedImg)

#%% reduce CroppedArr to NPlacers NodeArrs
NodeHeightInCroppedArr = float(TargetSize[1])/NPlacers
sections = scipy.array(scipy.arange(NodeHeightInCroppedArr, TargetSize[1], NodeHeightInCroppedArr), dtype=int)
NodeArrs = scipy.split(CroppedArr, sections, axis=0) # each tile in the image

#%% reduce NodeArr to TilesPerNode TileArrs
NodeArr = NodeArrs.pop(0)

pm = photo_match.photoMatch()
TileArrs = [] # each tile in the image
TileCompacts = [] # each tile in the image
whichSources = scipy.zeros((TotalTilesPerNode), dtype=int)
Distances = scipy.ones((TotalTilesPerNode))*scipy.Inf # the quality of the current fit for each tile (put at infinity to start with)

TileWidthInCroppedArr = float(UnscaledWidth)/Tiles[0]
vertSections = scipy.array(scipy.arange(TileWidthInCroppedArr, UnscaledWidth-.5*TileWidthInCroppedArr, TileWidthInCroppedArr), dtype=int)
VertSplitArrs = scipy.split(NodeArr, vertSections, axis=1)
for VertSplitArr in VertSplitArrs:
    TileHeightInCroppedArr = float(VertSplitArr.shape[0])/Tiles[1]*NPlacers
    horSections = scipy.array(scipy.arange(TileHeightInCroppedArr, VertSplitArr.shape[0]-.5*TileHeightInCroppedArr, TileHeightInCroppedArr), dtype=int)
    SplitArrs = scipy.split(VertSplitArr, horSections, axis=0)
    for SplitArr in SplitArrs:
        TileArrs.append(SplitArr)
        TileCompacts.append(pm.compactRepresentation(SplitArr))

#%% scrape images off flickr
fs = flickr_scraper.flickrScraper()

per_page = 60
filesKeep = {} # the files that actually need to be kept, will be filled after each search, 
# to keep certain files before they are disregarded in the new search

#%%
tag = 'Art'
for page in range(3,6):
    newSources = []
    urls = fs.scrapeTag(tag, per_page, page=page) 
    print "tag {} scraped for page {}".format(tag, page), " at ", time.time()
    
    files = fs.fetchFiles(urls)
    print "files fetched for page {}".format(page), " at ", time.time()
    for f in range(len(files)):
        print "\rfile: ",
        print f,
        Compact = pm.compactRepresentation(scipy.array(Image.open(files[f])))
        
        for t in range(TotalTilesPerNode):
            Distance = pm.compactDistance(TileCompacts[t], Compact)
            if Distance < Distances[t]:
                whichSources[t] = page*per_page + f
                newSources.append(whichSources[t])
                Distances[t] = Distance
#                print "placed photo {} at position {}".format(whichSources[t],t)
    print "\nat ", time.time()
    print "\n", whichSources
    print " of which new "
    print scipy.unique(newSources)
    for source in scipy.unique(newSources):
#        print "Source {} is new at page {}".format(source, page)
        filesKeep[source] = files[source - page*per_page]
    
    # compose the image (so far)
    NodeOutCols = []
    t = 0
    for col in range(TilesPerNode[0]):
        NodeOutColTiles = []
        for row in range(TilesPerNode[1]):
            TileOut = scipy.array(Image.open(filesKeep[whichSources[t]]))
            NodeOutColTiles.append(TileOut)
            t+= 1
        NodeOutCols.append(scipy.concatenate(NodeOutColTiles, axis=0))
    NodeOut = scipy.concatenate(NodeOutCols, axis=1)
    plt.figure(page)
    plt.imshow(NodeOut)
    plt.show()
#%%
plt.figure()
plt.imshow(scipy.array(NodeOut.sum(axis=2), dtype=float)/255, cmap = cm.Greys_r)
    
plt.figure()
plt.imshow(NodeArr)
        