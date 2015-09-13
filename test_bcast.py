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

if rank == 0:
  data = scipy.randn(3,3)
  print "Node 0 before bcast"
  comm.bcast(data,root=0) 
  print "Node 0 after bcast"
  comm.bcast(data,root=1) 
  print "Node 0 after listening"
elif rank == 1:
  data = scipy.randn(3,3)
  print "Node 1 before bcast"
  comm.bcast(data,root=1)
  print "Node 1 after bcast"
  comm.bcast(data,root=0)
  print "Node 1 after listening"
#elif rank == 2:
else:
  data = 2
  data0 = None
  data1 = None
  data0 = comm.bcast(data0, root=0)
  print "N{}: 0:".format(rank), data0
  sleep(2*rank)
  data1 = comm.bcast(data1, root=1)
  print "N{}: 1:".format(rank), data1
#elif rank == 3:
#  data = 3
#  data0 = None
#  data1 = None
#  data0 = comm.bcast(data0, root=0)
#  print "N{}: 0:".format(rank), data0
#  data1 = comm.bcast(data1, root=1)
#  print "N{}: 1:".format(rank), data1

print "N{}:".format(rank), data
