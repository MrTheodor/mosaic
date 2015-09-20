#! /usr/bin/env python
# vim:fenc=utf-8
#
# By Korneel Dumon, Jakub Krajniak and Keith Myerscough CC BY-NC-SA

import master
import scraper
import placer
import sys, os, shutil
from mpi4py import MPI

sys.path.append('.')

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
status = MPI.Status()

pars = {'NScrapers': 1, 'NPlacers': 1, 'iters': 2, 'per_page': 10, 'MaxTilesVert': 8, 'fidelity': 1, 'poolSize': 20, 'savepath' : "./imgs/", 'useDB' : False}

# update default parameters with given values
for i in range(len(sys.argv[:])):
    name = sys.argv[i]
    if name in pars:
        pars[name] = int(sys.argv[i+1])
#if pars['per_page'] > 500:
#    pars['per_page'] = 500

# create empty save-path
if (not pars['useDB']):
    if (os.path.exists(pars['savepath'])):
        shutil.rmtree(pars['savepath'], ignore_errors=True)
    os.mkdir(pars['savepath'])
    
    
if rank == 0:
    master.process(pars)
elif rank < 1+pars['NScrapers']:
    scraper.process(pars)
elif rank < 1+pars['NScrapers']+pars['NPlacers']:
    placer.process(pars)
