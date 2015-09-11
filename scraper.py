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
        Compacts = []
        for arr in arrs:
            Compacts.append(pm.compactRepresentation(arr))
        scraperResForPlacers = {'Compacts': Compacts, 'ids': ids}
        scraperResForMaster  = {'Compacts': Compacts, 'arrs': arrs,
                                'ids': ids}
        for placer in range(NPlacers):
            #print "S{}: sending to Placer node {}".format(rank, 1+NScrapers+placer)
            comm.send(scraperResForPlacers, dest=1+NScrapers+placer, tag=2)
        comm.send(scraperResForMaster, dest=0, tag=3)
        print "S{}: sent ids at iter {}".format(rank, iter)

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
        arrs = fp.fetchUrls()
