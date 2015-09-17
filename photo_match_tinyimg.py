# -*- coding: utf-8 -*-
"""
Created on Fri Sep  4 22:54:26 2015

@author: keith
"""

import scipy
from scipy import misc, ndimage
#from matplotlib import pyplot as plt

class photoMatch(object):
    
    def __init__(self, par={'fidelity': 5}):
        print "Initializing an instance of the photo match that uses the L2 distance between two arrays as its metric"
        self.type = 'Tiny image, comparing mean'
        N = par['fidelity']
        self.N = N
        self.compareSize = (N,N)
        self.totalSize = 3*N*N
        self.fullSize = (75,75)
    
    # reduces a photo (of any size) given as an MxNx3 scipy array (or should it be a PIL image?)
    # down to some more easily compared representation
    # baasically a coarse graining
    def compactRepresentation(self, arrs):
        N = self.N
        arrs_subsampled = scipy.zeros((arrs.shape[0], N,N, 3))
        i = 0
        for arr in arrs:
            arrs_subsampled[i,...] = scipy.misc.imresize(arr, (N,N))
        return arrs_subsampled
        
    # provide some distance between two compact representations of photos
    # if photo1==photo2, distance should ideally be zeros
    # here the L2-norm distance is used
    def compactDistance(self, target, candidates):
        #compare the candidates to the target accordin to some measure
        targetarr = scipy.array(target.reshape((self.totalSize/3, 3)), dtype=int)
        candidatesarr = scipy.array(candidates.reshape((candidates.shape[0], self.totalSize/3, 3)), dtype=int)
        return scipy.sum((targetarr - candidatesarr)**2, axis=(1,2))
        
    def formatOutput(self, arr):
        return arr
