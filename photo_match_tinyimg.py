# -*- coding: utf-8 -*-
"""
Created on Fri Sep  4 22:54:26 2015

@author: keith
"""

import scipy
from scipy import misc, ndimage
import numpy as np

class photoMatch(object):
    
    def __init__(self, par={'fidelity': 5}):
        print "Initializing an instance of the photo match that uses the L2 distance between two arrays as its metric"
        self.type = 'Tiny image, comparing mean'
        N = par['fidelity']
        self.compareSize = (N,N)
        self.totalSize = 3*N*N
        self.fullSize = (75,75)
    
    # reduces a photo (of any size) given as an MxNx3 scipy array (or should it be a PIL image?)
    # down to some more easily compared representation
    # baasically a coarse graining
    def compactRepresentation(self, photo):
        arr = scipy.ones((self.compareSize[0], self.compareSize[1], 3))*scipy.NaN
        if len(photo.shape) == 3: # an MxNx3 array of of ANY size:
            arr = photo
        elif photo.size == scipy.prod(self.fullSize)*3: # must be NxNx3, with N as in self.fullSize
            arr = photo.reshape((self.fullSize[0],self.fullSize[1],3))
        return scipy.misc.imresize(arr, self.compareSize).reshape((1,self.totalSize))
        
    # provide some distance between two compact representations of photos
    # if photo1==photo2, distance should ideally be zeros
    # here the L2-norm distance is used
    def compactDistance(self, target, candidates):
        #compare the candidates to the target accordin to some measure
        targetarr = target.reshape((self.totalSize/3, 3))
        candidatesarr = candidates.reshape((candidates.shape[0], self.totalSize/3, 3))
        return scipy.sum((targetarr - candidatesarr)**2, axis=(1,2))
        
    def formatOutput(self, arr):
        return arr
