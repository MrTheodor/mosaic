#! /usr/bin/env python
# vim:fenc=utf-8
#
# By Jakub Krajniak & Keith Myerscough CC BY-NC-SA

from mpi4py import MPI
from time import sleep
import scipy

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
status = MPI.Status()

scipy.random.seed(rank)
many = 200000
if rank == 0:
  data = scipy.array(100*scipy.randn(many,1), dtype='i')
  print "N{}: ".format(rank), data[:2,:]
  print "Node 0 before Isend"
  comm.Isend([data, MPI.INT],dest=1,tag=0) 
  print "Node 0 after Isend"
else:
  data = scipy.empty((many,1), dtype='i')
  comm.Recv([data, MPI.INT], source=MPI.ANY_SOURCE, tag=0)
  print "N{}: ".format(rank), data[:2,:]
  

#print "N{}:".format(rank), data
