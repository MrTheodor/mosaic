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
many = 10000
if rank == 0:
  data = scipy.array(100*scipy.randn(many,3), dtype='i')
  print "N{}: ".format(rank), data[0,:]
  print "Node 0 before isend"
  for r in range(2,4):
    comm.Isend([data, MPI.INT],dest=r,tag=0) 
  data = scipy.array(100*scipy.randn(many,3), dtype='i')
  print "N{}: ".format(rank), data[0,:]
  for r in range(2,4):
    comm.Isend([data, MPI.INT],dest=r,tag=1) 
  print "Node 0 after isend"
elif rank == 1:
  pass
else:
  data0 = scipy.empty((many,3), dtype='i')
  data1 = scipy.empty((many,3), dtype='i')
  sleep(2*rank)
  in0 = comm.Recv([data0, MPI.INT], source=MPI.ANY_SOURCE, tag=0)
  print "N{}: 0:".format(rank), data0[0,:]
  in1 = comm.Recv([data1, MPI.INT], source=MPI.ANY_SOURCE, tag=1)
  print "N{}: 1:".format(rank), data1[0,:]
  print "N{}: 0:".format(rank), in0
  print "N{}: 1:".format(rank), in1
  

#print "N{}:".format(rank), data
