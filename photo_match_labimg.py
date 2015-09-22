# -*- coding: utf-8 -*-
"""
Created on Fri Sep  4 22:54:26 2015

@author: keith
"""

import scipy
from scipy import misc, ndimage
from skimage import color
#from matplotlib import pyplot as plt

class photoMatch(object):
    
    def __init__(self, par={'fidelity': 5}):
        print "Initializing an instance of the photo match that uses the L2 distance between two arrays in Lab colour space as its metric"
        self.type = 'Tiny image, comparing mean'
        N = par['fidelity']
        self.N = N
        self.weights = scipy.array([1, .9, .9])
        self.compareSize = (N,N)
        self.totalSize = 3*N*N
        self.fullSize = (75,75)
    
    # reduces a photo (of any size) given as an MxNx3 scipy array (or should it be a PIL image?)
    # down to some more easily compared representation
    # baasically a coarse graining
    def compactRepresentation(self, arrs):
        N = self.N
        if len(arrs.shape) == 4:
            result = scipy.zeros((arrs.shape[0], N,N, 3))
            for i in range(arrs.shape[0]):
                result[i,...] = color.rgb2lab(scipy.misc.imresize(arrs[i], (N,N)))
        elif len(arrs.shape) == 3: # arrs is in fact just arr
            result = color.rgb2lab(scipy.misc.imresize(arrs, (N,N))).reshape(1,N,N,3)
        return result
        
    # provide some distance between two compact representations of photos
    # if photo1==photo2, distance should ideally be zeros
    # here the L2-norm distance is used
    def compactDistance(self, target, candidates):
        #compare the candidates to the target accordin to some measure
        targetarr = scipy.array(target.reshape((self.totalSize/3, 3)), dtype=int)
        candidatesarr = scipy.array(candidates.reshape((candidates.shape[0], self.totalSize/3, 3)), dtype=int)
        print scipy.sum((targetarr - candidatesarr)**2*self.weights, axis=1)
        return scipy.sum((targetarr - candidatesarr)**2*self.weights, axis=(1,2))
        
    def formatOutput(self, arr):
        return arr

if __name__ == "__main__":
    from matplotlib import pyplot as plt
    from PIL import Image
    plt.close('all')
    
    pm = photoMatch({'fidelity' : 5})
    
    TargetArr = scipy.zeros((100, 100, 3), dtype='uint8')
    TargetArr[...,2] = scipy.arange(0,100,1)
    TargetArr[...,1] = TargetArr[...,2].T
    TargetCompact = pm.compactRepresentation(TargetArr)
    
    K = 5
    CandArrs = scipy.ones((K,100,100,3), dtype='uint8')
#    CandArrs[...] = TargetArr
    for k in range(K):
        CandArrs[k,...]*= k*(255/10)
    CandCompacts = pm.compactRepresentation(CandArrs)
    
    plt.figure()
    plt.imshow(TargetArr, interpolation='None')
    
    plt.figure()
    plt.imshow(color.lab2rgb(TargetCompact[0,...]), interpolation='None')
    
    plt.figure()
    plt.imshow(CandArrs[4,...], interpolation='None')
    
    plt.figure()
    plt.imshow(color.lab2rgb(CandCompacts[4,...]), interpolation='None')
    
    dist = pm.compactDistance(TargetCompact, CandCompacts)