# -*- coding: utf-8 -*-
from mpi4py import MPI
import plogger
import flickr_scraper
from PIL import Image
import scipy, time, os

import ScraperPool

execfile('./params.par')

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

#%% initiate plogger   
    #execfile('../mosaic_gui/daemon/params.par')
    logger = plogger.PLogger(rank, host_url=LOGGER_HOST)

#%% identify oneself
    ##print "Scraper, process {} out of {}".format(rank, size) 
    #print "S{} > init".format(rank) 
    logger.write('Initializing', status=plogger.INIT)

#%% receive parameters from the master
    scraperPars = comm.recv(source=0, tag=0, status=status)
    ##print "S{}: received params from Master".format(rank)
    tags = scraperPars['tags']
    poolSize = scraperPars['poolSize']
    
#%% Initiate the flickr scraper
    if pars['useDB']:
        nbImgs = iters * NScrapers * per_page
        dbImages = os.listdir(pars['savepath'])
        assert (len(dbImages) >= nbImgs)
        fs = flickr_scraper.FlickrScraperDummy(pars['savepath'])
    else:
        fs = flickr_scraper.FlickrScraper()
    #print "S{} < init".format(rank) 
    
#%% outer iteration
    for it in range(iters):
        # this will represent the how manyth page this will be IN TOTAL FOR ALL THREADS
        totalpage = it*NScrapers + rank-1
        # then compute which page of which tag to search for
        (page, tagid) = divmod(totalpage, len(tags))
        tag = tags[tagid]
        ##print "S{}: will search for page {} of tag {}".format(rank, page, tag)

        #print "S{}: > downloading".format(rank)
        logger.write('Downloading images', status=plogger.DOWNLOAD)
        # this will represent the how manyth page this will be IN TOTAL FOR ALL THREADS
        totalpage = it*NScrapers + rank-1
        if pars['useDB']:
            start = it*NScrapers*per_page + (rank-1)*per_page
            end = it*NScrapers*per_page + rank*per_page
            urls = dbImages[start:end]        
        else:
            # then compute which page of which tag to search for
            (page, tagid) = divmod(totalpage, len(tags))
            tag = tags[tagid]
            ##print "S{}: will search for page {} of tag {}".format(rank, page, tag)
            urls = fs.scrapeTag(tag, per_page, page=page, sort='interestingness-desc') 
            ##print "S{}: tag {} scraped for page {}".format(rank, tag, page)
        
        fp = ScraperPool.FetcherPool(fs.fetchFileData, urls, poolSize)  
        arrs = fp.executeJobs()
        for i in range(per_page - len(arrs)):
            arrs.append(arrs[-1])
        ##print "S{}: arrs has length {}".format(rank, len(arrs))
#        #print "S{}: files fetched for iter {}".format(rank, it)
        
        #print "S{}: < downloading".format(rank)

        # concatenate the arrs list into a 4D matrix
        arrs = scipy.concatenate(arrs, axis=0)
        # create an array consiting of the ids and the photo arrays to be sent
        # to the Placers
        ##print "S{}: scraperRes has shape and type ".format(rank), scraperRes.shape, type(scraperRes[0,0])
        ##print "S{}: broadcasting ids {}--{} to {} Placers".format(rank,ids[0], ids[-1], NPlacers)
        #print "S{}: > sending".format(rank)
        logger.write('Sending to placers', status=plogger.SENDING)
        dummy_arrs = scipy.zeros_like(arrs)
        for scraper in range(1, 1+NScrapers):
            if scraper == rank: # on the sending end of bcast
                comm.Bcast(arrs, root=scraper)
            else: # on the receiving end of bcast (but not really interested in the result)
                comm.Bcast(dummy_arrs, root=scraper)
        #print "S{}: < sending".format(rank)

#%% signal completion
    comm.barrier()
    #print "S{}: reached the end of its career".format(rank)
#%%
if __name__=="__main__":
    import photo_match_tinyimg as photo_match
    from matplotlib import pyplot as plt
    plt.close('all')
	
    #print "testing the scraper Pool"
    M = 2
    N = 10
    per_page = M*M
    rank = 1
    NScrapers = 1
    tag = 'Brugge'

    fs = flickr_scraper.flickrScraper()
    
    #
    urls = fs.scrapeTag(tag, per_page, page=0) 
    #print "tag {} scraped for iter {}".format(tag, 0)

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
        #print imin
    
    
