# -*- coding: utf-8 -*-
"""
Created on Sun Sep 13 21:16:08 2015

@author: keith
"""

from PIL import Image
import scipy
import photo_match_tinyimg as photo_match

pm = photo_match.photoMatch({'fidelity': 3})

Img1 = Image.open('KWM24489.JPG')
Arr1 = scipy.array(Img1)
Img2 = Image.open('KWM24495.JPG')
Arr2 = scipy.array(Img2)

Arrv1 = Arr1.reshape(scipy.prod(Arr1.shape))
Arrv2 = Arr2.reshape(scipy.prod(Arr2.shape))

compact1 = pm.compactRepresentation(Arr1)
compact2 = pm.compactRepresentation(Arr2)

compacts = scipy.concatenate((compact1, compact2), axis=0)

dist = pm.compactDistance(compact1, compacts)
