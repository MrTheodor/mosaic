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
        N = par['fidelity']
        self.compareSize = (N,N)
    
    # reduces a photo (of any size) given as an MxNx3 scipy array (or should it be a PIL image?)
    # down to some more easily compared representation
    # baasically a coarse graining
    def compactRepresentation(self, photo):
        if len(photo.shape) == 3: # must be NxNx3
            if photo.shape[2] == 3: # must be NxNx3
                return scipy.misc.imresize(photo, self.compareSize)
        return scipy.ones((self.compareSize[0], self.compareSize[1], 3))*scipy.NaN
        
    # provide some distance between two compact representations of photos
    # if photo1==photo2, distance should ideally be zeros
    # here the L2-norm distance is used
    def compactDistance_old(self, rep1, rep2):
        print rep1.shape
        print rep2.shape
        return scipy.sqrt(scipy.sum((rep1-rep2)**2, axis=None))
        
    
    def compactDistance(self, rep1, rep2):
        rep1_avg = np.mean(np.mean(rep1, axis=0), axis=0)
        rep2_avg = np.mean(np.mean(rep2, axis=0), axis=0)
        return scipy.sqrt(scipy.sum((rep1_avg - rep2_avg)**2))
        
