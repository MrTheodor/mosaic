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

    fs = flickr_scraper.flickrScraper()
    
    #%%
    for iter in range(iters):
        # this will represent the how manyth page this will be IN TOTAL FOR ALL THREADS
        totalpage = iter*NScrapers + rank-1
        # then compute which page of which tag to search for
        (page, tagid) = divmod(totalpage, len(tags))
        tag = tags[tagid]
        print "S{}: will search for page {} of tag {}".format(rank, page, tag)

        urls = fs.scrapeTag(tag, per_page, page=page) 
        print "S{}: tag {} scraped for page {}".format(rank, tag, page)

        poolsize = 50
        fp = FetcherPool(fs.fetchFileData, urls, poolsize)
        arrs = fp.executeJobs()
        #print "S{}: arrs has length {}".format(rank, len(arrs))
        ids = totalpage*per_page + scipy.arange(per_page, dtype=int)
        print "S{}: files fetched for iter {}".format(rank, iter)
        compacts = []
        for arr in arrs:
            compacts.append(pm.compactRepresentation(arr))
        arrvs = scipy.concatenate(arrs, axis=0)
        compactvs = scipy.concatenate(compacts, axis=0)

        print "S{}: len(compactvs) = {}, len(arrs) = {}".format(rank, len(compactvs), len (arrs))
        for i in range(len(compactvs)):
            compactv = compactvs[i]
            print "S{}: compactvs[{}]".format(rank, i), compactv.shape
        scraperResForPlacers = scipy.array(scipy.concatenate((ids.reshape((ids.size,1)), compactvs), axis=1), dtype='i')
        scraperResForMaster  = scipy.array(scipy.concatenate((ids.reshape((ids.size,1)), arrvs), axis=1), dtype='i')
        #print "S{}: res shape: ".format(rank), scraperResForPlacers.shape
        #print "S{}: res shape: ".format(rank), scraperResForMaster.shape
        #scraperResForPlacers = {'Compacts': Compacts, 'ids': ids}
        #scraperResForMaster  = {'arrs': arrs, 'ids': ids}
        print "S{}: broadcasting to Placer nodes".format(rank)
        for placer in range(1+NScrapers, 1+NScrapers+NPlacers):
            comm.Send([scraperResForPlacers, MPI.INT], dest=placer, tag=2)
        comm.Send([scraperResForMaster, MPI.INT], dest=0, tag=3)
        print "S{}: broadcasted ids at iter {}".format(rank, iter)

if __name__=="__main__":
    import photo_match_tinyimg2 as photo_match
	
    print "testing the scraper Pool"
    per_page = 100
    rank = 1
    NScrapers = 1
    pm = photo_match.photoMatch
    tag = 'Brugge'

    fs = flickr_scraper.flickrScraper()
    
    #%%
    for iter in range(1):
        urls = fs.scrapeTag(tag, per_page, iter=iter) 
        print "tag {} scraped for iter {}".format(tag, iter)

        poolsize = 20
        fp = FetcherPool(fs.fetchFileData, urls[rank-1 : per_page : NScrapers],
                         poolsize)
        arrs = fp.executeJobs()
