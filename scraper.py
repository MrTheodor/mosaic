# -*- coding: utf-8 -*-
from mpi4py import MPI
import flickr_scraper
from PIL import Image
import scipy, threading, time

from ScraperPool import *


def process(pars):
#%% load the parameters that CAN be specified from the command line
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    iters = pars['iters']

#%% MPI stuff
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
#%% identify oneself
    print "Scraper, node {} out of {}".format(rank, size) 

#%% receive parameters from the master
    scraperPars = comm.recv(source=0, tag=0, status=status)
    print "S{}: received params from Master".format(rank)
    tags = scraperPars['tags']
    PixPerTile = scraperPars['PixPerTile']
    poolSize = scraperPars['poolSize']
    
    TileSize = 3*scipy.prod(PixPerTile)

#%% Initiate the flickr scraper
    fs = flickr_scraper.flickrScraper()
    
#%% outer iteration
    for it in range(iters):
        # this will represent the how manyth page this will be IN TOTAL FOR ALL THREADS
        totalpage = it*NScrapers + rank-1
        # then compute which page of which tag to search for
        (page, tagid) = divmod(totalpage, len(tags))
        tag = tags[tagid]
        print "S{}: will search for page {} of tag {}".format(rank, page, tag)

        # retrieve urls
        urls = fs.scrapeTag(tag, per_page, page=page, sort='interestingness-desc') 
        print "S{}: tag {} scraped for page {}".format(rank, tag, page)

        # fetch the files
        fp = FetcherPool(fs.fetchFileData, urls, poolSize)
        arrs = fp.executeJobs()
        for i range(per_page - len(arrs)):
            arrs.append(arrs[-1])
        print "S{}: {} files fetched for iter {}".format(rank, len(arrs), it)
        
        # concatenate the arrs list into a matrix
        arrvs = scipy.concatenate(arrs, axis=0)
        ids = totalpage*per_page + scipy.arange(len(arrs), dtype=int)

        # create an array consiting of the ids and the photo arrays to be sent
        # to the Placers
        scraperRes = scipy.array(scipy.concatenate((ids.reshape((ids.size,1)), arrvs), axis=1), dtype='i')
#        # Pad the arrays out to be per-page wide, as this is expected by the placers
#        scraperRes = scipy.pad(scraperRes, ((0, per_page-len(arrs)),(0,0)), mode='edge')
#        scraperRes = scipy.array(64*scipy.randn(per_page, 1+TileSize), dtype='i')
        print "S{}: broadcasting to Placer nodes".format(rank), scraperRes[:,0]
        for placer in range(1+NScrapers, 1+NScrapers+NPlacers):
            comm.Isend([scraperRes, MPI.INT], dest=placer, tag=2)
        print "S{}: broadcasted ids at iter {}".format(rank, it)
        time.sleep(10)

#%% signal completion
    print "S{}: reached the end of its career".format(rank)
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
    
    
