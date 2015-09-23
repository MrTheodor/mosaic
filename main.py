#! /usr/bin/env python
# vim:fenc=utf-8
#
# By Korneel Dumon, Jakub Krajniak and Keith Myerscough CC BY-NC-SA


import sys
sys.path.append('.')

import master
import placer
import scraper
from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
status = MPI.Status()

pars = {'NScrapers': 1, 'NPlacers': 1, 'iters': 2, 'per_page': 10, 'MaxTilesVert': 8, 'fidelity': 1, 'poolSize': 20, 'UsedPenalty': 0.}

for i in range(len(sys.argv[:])):
    name = sys.argv[i]
    if name in pars:
        pars[name] = int(sys.argv[i+1])
if pars['per_page'] > 500:
    pars['per_page'] = 500

obj = None
if rank == 0:
    master.process(pars)
elif rank < 1+pars['NScrapers']:
    scraper.process(pars)
elif rank < 1+pars['NScrapers']+pars['NPlacers']:
    obj = placer.MinDistPlacer(pars)
    obj.process()
    #placer.process(pars)

del obj
MPI.Finalize()
