from mpi4py import MPI
import flickr_scraper
from PIL import Image
import scipy, threading

class FetcherThread(threading.Thread):
    def __init__(self, fetcher, result_buf, result_lock):
        threading.Thread.__init__(self)
        self.fetcher = fetcher
        self.results = result_buf
        self.results_lock = result_lock

    def run(self):
        data = self.fetcher()
        self.results_lock.acquire()
        self.results.append(data[0])
        self.results_lock.release()
        return

def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    pages = pars['pages']

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    print "Scraper node {} out of {}".format(rank, size) 

    scraperPars = comm.recv(source=0, tag=0, status=status)
    print "Node {} received params from Master".format(rank)
    pm = scraperPars['pm']
    tag = scraperPars['tag']

    fs = flickr_scraper.flickrScraper()
    
    filesKeep = {} # the files that actually need to be kept, will be filled after each search, 
    # to keep certain files before they are disregarded in the new search
    
    #%%
    for page in range(pages):
        arrs = []
        Compacts = []
        urls = fs.scrapeTag(tag, per_page, page=page) 
        #print "tag {} scraped for page {}".format(tag, page)

        files = []
        files_lock = threading.Lock()
        threads = []
        for url in urls:
            func = lambda: fs.fetchFiles([url])
            t = FetcherThread(func, files, files_lock)
            threads.append(t)
            t.start()
        while len(threads) != 0:
            threads[0].join()
            threads.pop(0)
        # files = fs.fetchFiles(urls[rank-1 : per_page : NScrapers])
        ids = page*per_page + scipy.arange(rank-1, per_page,  NScrapers, dtype=int)
        #print "files fetched for page {}".format(page)
        for f in range(len(files)):
            arr = scipy.array(Image.open(files[f]))
            arrs.append(arr)
            Compacts.append(pm.compactRepresentation(arr))
        scraperResForPlacers = {'Compacts': Compacts, 'ids': ids}
        scraperResForMaster  = {'Compacts': Compacts, 'arrs': arrs, 'ids': ids}
        #print "Scraper node {} sent ids at page {}".format(rank, page), ids
        for placer in range(NPlacers):
            comm.send(scraperResForPlacers, dest=1+NScrapers+placer, tag=2)
        comm.send(scraperResForMaster, dest=0, tag=3)
