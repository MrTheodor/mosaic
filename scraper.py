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
    print "S{} > init".format(rank) 

#%% receive parameters from the master
    scraperPars = comm.recv(source=0, tag=0, status=status)
    #print "S{}: received params from Master".format(rank)
    tags = scraperPars['tags']
    PixPerTile = scraperPars['PixPerTile']
    poolSize = scraperPars['poolSize']
    
    TileSize = 3*scipy.prod(PixPerTile)

#%% Initiate the flickr scraper
    fs = flickr_scraper.flickrScraper()
    print "S{} < init".format(rank) 
    
#%% outer iteration
    for it in range(iters):
        # this will represent the how manyth page this will be IN TOTAL FOR ALL THREADS
        totalpage = it*NScrapers + rank-1
        # then compute which page of which tag to search for
        (page, tagid) = divmod(totalpage, len(tags))
        tag = tags[tagid]
        #print "S{}: will search for page {} of tag {}".format(rank, page, tag)

        print "S{}: > downloading".format(rank)
        # retrieve urls
        urls = fs.scrapeTag(tag, per_page, page=page, sort='interestingness-desc') 
        #print "S{}: tag {} scraped for page {}".format(rank, tag, page)

        # fetch the files
        fp = FetcherPool(fs.fetchFileData, urls, poolSize)
        arrs = fp.executeJobs()
        for i in range(per_page - len(arrs)):
            arrs.append(arrs[-1])
#        for i in range(per_page):
#            print "S{}: arr {} has shape ".format(rank, i), arrs[i].shape
        #print "S{}: {} files fetched for iter {}".format(rank, len(arrs), it)
        
        # concatenate the arrs list into a matrix
        arrvs = scipy.concatenate(arrs, axis=0)
        ids = totalpage*per_page + scipy.arange(len(arrs), dtype=int)
        print "S{}: < downloading".format(rank)

        # create an array consiting of the ids and the photo arrays to be sent
        # to the Placers
        scraperRes = scipy.array(scipy.concatenate((ids.reshape((ids.size,1)), arrvs), axis=1), dtype='i')
        #scraperRes = scipy.array(scipy.randn(per_page,1+TileSize), dtype='i')
        #print "S{}: scraperRes has shape and type ".format(rank), scraperRes.shape, type(scraperRes[0,0])
        #print "S{}: broadcasting ids {}--{} to {} Placer nodes".format(rank,ids[0], ids[-1], NPlacers)
        #print "S{}: > sending".format(rank)
        # wait for the previous iteration to be completed before continuing
        isSent = [False]*NPlacers
        if it == 0:
            reqs = []
            for placer in range(1+NScrapers, 1+NScrapers+NPlacers):
                print "S{}: sending to Placer node {} at iter {}".format(rank, placer, it)
                reqs.append(comm.Isend([scraperRes, MPI.INT], dest=placer, tag=2))
        else:
            while not all(isSent):
                time.sleep(.1) # a short wait just to keep the log a bit cleaner when printing
                for p in range(NPlacers):
                    if isSent[p] == False:
                        if MPI.Request.Test(reqs[p]):
                            print "S{}: sending to Placer node {} at iter {}".format(rank, 1+NScrapers+p, it)
                            reqs[p] = comm.Isend([scraperRes, MPI.INT], dest=1+NScrapers+p, tag=2)
                            isSent[p] = True
        #print "S{}: broadcasted ids at iter {}".format(rank, it)
        print "S{}: < sending".format(rank)

#%% signal completion
    comm.barrier()
    print "S{}: reached the end of its career".format(rank)
#%%
if __name__=="__main__":
    import photo_match_tinyimg as photo_match
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
    arrvs = fp.executeJobs()
    arrvs = scipy.concatenate(arrvs, axis=0)
    CandidateArrs = arrvs.reshape((len(arrvs),75,75,3))
    
    TargetImg = Image.open('KWM24495.JPG')
    TargetArr = scipy.array(TargetImg)
#    Arr1 = Arr1[:75,:350,:]
    TargetArrs = TargetArr.reshape((scipy.insert(Arr1.shape,0,1)))
    
    plt.figure(1)
    plt.imshow(TargetArr, interpolation='none')
#%%
    for i in range(len(arrs)):
        plt.figure(2)
        plt.subplot(M,M,i+1)
        plt.imshow(arrs[i].reshape((75,75,3)), interpolation='none')
    
    n = 0
    for N in [2]:#[1,2,3,5,10,20,50]:
        n+= 1
        
        pm = photo_match.photoMatch({'fidelity': N})
        TargetCompacts = pm.compactRepresentation(TargetArrs)
        CandidateCompacts= pm.compactRepresentation(CandidateArrs)
            
        
        distances = pm.compactDistance(TargetCompacts, CandidateCompacts)
        imin = scipy.argmin(distances)
        print imin
    
    
