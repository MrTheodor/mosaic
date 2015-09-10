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
    print "Node {} received params from Master".format(rank)
    pm = scraperPars['pm']
    tag = scraperPars['tag']

    fs = flickr_scraper.flickrScraper()
    
    #%%
    for iter in range(iters):
        urls = fs.scrapeTag(tag, per_page, page=iter) 
        print "tag {} scraped for iter {}".format(tag, iter)

        poolsize = 50
        fp = FetcherPool(fs.fetchFileData, urls[rank-1 : per_page : NScrapers],
                         poolsize)
        arrs = fp.executeJobs()
        #print "arrs has length {}".format(len(arrs))
        ids = iter*per_page + scipy.arange(rank-1, per_page,  NScrapers, dtype=int)
        print "files fetched for iter {}".format(iter)
        Compacts = []
        for arr in arrs:
            Compacts.append(pm.compactRepresentation(arr))
        scraperResForPlacers = {'Compacts': Compacts, 'ids': ids}
        scraperResForMaster  = {'Compacts': Compacts, 'arrs': arrs,
                                'ids': ids}
        for placer in range(NPlacers):
            #print "Scraper, node {} sending to Placer node {}".format(rank, 1+NScrapers+placer)
            comm.send(scraperResForPlacers, dest=1+NScrapers+placer, tag=2)
        comm.send(scraperResForMaster, dest=0, tag=3)
        print "Scraper node {} sent ids at iter {}".format(rank, iter)

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
