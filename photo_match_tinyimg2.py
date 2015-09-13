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
        if photo.size == 75*75*3: # must be NxNx3
            photo = photo.reshape((75,75,3))
            return scipy.misc.imresize(photo, self.compareSize).reshape((1,scipy.prod(self.compareSize)*3))
        return scipy.ones((1, scipy.prod(self.compareSize)*3))*scipy.NaN
        
    # provide some distance between two compact representations of photos
    # if photo1==photo2, distance should ideally be zeros
    # here the L2-norm distance is used
    def compactDistance(self, rep1, rep2):
        rep1_avg = scipy.mean(rep1, axis=0)
        rep2_avg = scipy.mean(rep2, axis=0)
        return scipy.sqrt(scipy.sum((rep1_avg - rep2_avg)**2))
        
