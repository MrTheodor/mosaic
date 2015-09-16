# -*- coding: utf-8 -*-
from mpi4py import MPI
import flickr_scraper
from PIL import Image
import scipy, threading, time

from ScraperPool import *


def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    iters = pars['iters']

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    print "Scraper, node {} out of {}".format(rank, size) 

    scraperPars = comm.recv(source=0, tag=0, status=status)
    print "S{}: received params from Master".format(rank)
    pm = scraperPars['pm']
    tags = scraperPars['tags']
    PixPerTile = scraperPars['PixPerTile']
    poolSize = scraperPars['poolSize']

    fs = flickr_scraper.flickrScraper()
    
    #%%
    for iter in range(iters):
        # this will represent the how manyth page this will be IN TOTAL FOR ALL THREADS
        totalpage = iter*NScrapers + rank-1
        # then compute which page of which tag to search for
        (page, tagid) = divmod(totalpage, len(tags))
        tag = tags[tagid]
        print "S{}: will search for page {} of tag {}".format(rank, page, tag)

        urls = fs.scrapeTag(tag, per_page, page=page, sort='interestingness-desc') 
        print "S{}: tag {} scraped for page {}".format(rank, tag, page)

        fp = FetcherPool(fs.fetchFileData, urls, poolSize)
        arrs = fp.executeJobs()
        #print "S{}: arrs has length {}".format(rank, len(arrs))
        print "S{}: files fetched for iter {}".format(rank, iter)
        compacts = []
        arrvs = scipy.ones((len(arrs), PixPerTile[0]*PixPerTile[1]*3))*scipy.NaN
        ids = totalpage*per_page + scipy.arange(len(arrs), dtype=int)
        #print "S{}: shape of arrvs is ".format(rank), arrvs.shape
        for i in range(len(arrs)):
            arr = arrs[i]
            #print "S{}: shape of arr is ".format(rank), arr.shape
            compacts.append(pm.compactRepresentation(arr))
            arrvs[i,:arr.shape[1]] = arr
        #arrvs = scipy.concatenate(arrs, axis=0)
        compactvs = scipy.concatenate(compacts, axis=0)

        #print "S{}: len(compactvs) = {}, len(arrs) = {}".format(rank, len(compactvs), len (arrs))
        for i in range(len(compactvs)):
            compactv = compactvs[i]
            #print "S{}: compactvs[{}]".format(rank, i), compactv.shape
        #print "S{}: shapes: ".format(rank), ids.shape, compactvs.shape, arrvs.shape
        scraperResForPlacers = scipy.array(scipy.concatenate((ids.reshape((ids.size,1)), compactvs), axis=1), dtype='i')
        scraperResForMaster  = scipy.array(scipy.concatenate((ids.reshape((ids.size,1)), arrvs), axis=1), dtype='i')
        # Pad the arrays out to be per-page wide, as this is expected by the placers
        scraperResForPlacers = scipy.pad(scraperResForPlacers, ((0, per_page-len(arrs)),(0,0)), mode='edge')
        scraperResForMaster  = scipy.pad(scraperResForMaster , ((0, per_page-len(arrs)),(0,0)), mode='edge')
        #print "S{}: res shape: ".format(rank), scraperResForPlacers.shape
        #print "S{}: res shape: ".format(rank), scraperResForMaster.shape
        #scraperResForPlacers = {'Compacts': Compacts, 'ids': ids}
        #scraperResForMaster  = {'arrs': arrs, 'ids': ids}
        print "S{}: broadcasting to Placer nodes".format(rank)
        for placer in range(1+NScrapers, 1+NScrapers+NPlacers):
            comm.Send([scraperResForPlacers, MPI.INT], dest=placer, tag=2)
        comm.Send([scraperResForMaster, MPI.INT], dest=0, tag=3)
        print "S{}: broadcasted ids at iter {}".format(rank, iter)

#%%
if __name__=="__main__":
    import photo_match_tinygrey as photo_match
    from matplotlib import pyplot as plt
    plt.close('all')
	
    print "testing the scraper Pool"
    M = 2
    N = 10
    per_page = M*M
    rank = 1
    NScrapers = 1
    tag = 'Brugge'

    fs = flickr_scraper.flickrScraper()
    
    #
    urls = fs.scrapeTag(tag, per_page, page=0) 
    print "tag {} scraped for iter {}".format(tag, 0)

    poolsize = 20
    fp = FetcherPool(fs.fetchFileData, urls[rank-1 : per_page : NScrapers],
                     poolsize)
    arrs = fp.executeJobs()
    
    Img1 = Image.open('KWM24495.JPG')
    Arr1 = scipy.array(Img1)
#    Arr1 = Arr1[:75,:350,:]
    
    plt.figure(1)
    plt.imshow(Arr1, interpolation='none')
#%%
    for i in range(len(arrs)):
        plt.figure(2)
        plt.subplot(M,M,i+1)
        plt.imshow(arrs[i].reshape((75,75,3)), interpolation='none')
    
    n = 0
    for N in [2]:#[1,2,3,5,10,20,50]:
        n+= 1
        
        pm = photo_match.photoMatch({'fidelity': N})
        compact1 = pm.compactRepresentation(Arr1)
        compactvs = scipy.zeros((len(arrs), pm.totalSize), dtype=scipy.uint8)
        for i in range(len(arrs)):
            compact = pm.compactRepresentation(arrs[i])
            compactvs[i,:] = compact
    
#            plt.figure(100+N)
#            plt.imshow(compact1.reshape((N,N,3)), interpolation='none')
#            
#            plt.figure(200+N)
#            plt.subplot(M,M,i+1)
#            plt.imshow(compact.reshape((N,N,3)), interpolation='none')
            
        
        distances = pm.compactDistance(compact1, compactvs)
        imin = scipy.argmin(distances)
        print imin
#        plt.figure(5)
#        plt.plot(distances/N**2)
            
        
        plt.figure(3)
        plt.subplot(4,6,3*n-2)
        r = compact1.reshape((N,N,1))
        plt.imshow(scipy.concatenate((r,r,r), axis=2), interpolation='none')
        plt.subplot(4,6,3*n-1)
        plt.imshow(arrs[imin].reshape((75,75,3)), interpolation='none')
        plt.subplot(4,6,3*n)
        r = compactvs[imin,:].reshape((N,N,1))
        plt.imshow(scipy.concatenate((r,r,r), axis=2), interpolation='none')
    
    
