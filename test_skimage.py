#! /usr/bin/env python
# vim:fenc=utf-8
#
# By Jakub Krajniak & Keith Myerscough CC BY-NC-SA

from mpi4py import MPI
from time import sleep
import scipy
from skimage import color

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
status = MPI.Status()

rgb = scipy.array(255*scipy.rand(10,10,3), dtype=int)
rgb[0,0,:] = 32
lab = color.rgb2lab(rgb)

print rgb
print lab[0,0,:]
