from mpi4py import MPI
import flickr_scraper
from PIL import Image
import scipy, threading

class FetcherThread(threading.Thread):
    def __init__(self, threadID, fetcher, result_buf, result_lock):
        threading.Thread.__init__(self)
        self.my_id = threadID
        self.fetcher = fetcher
        self.results = result_buf
        self.results_lock = result_lock
        self.url = None
        self.urlLock = threading.Lock()
        self.stopped = False
    
    def stopThread(self):
        self.stopped = True
    
    def getUrl(self):
        return self.url
    
    def setUrl(self, url):
        self.urlLock.acquire()
        self.url = url
        self.urlLock.release()
    
    def run(self):
        while (not self.stopped):
            if (self.url == None):
                continue
            # print "Thread %d : downloading %s" % (self.my_id, self.url[-30:])
            data = self.fetcher([self.url])
            self.results_lock.acquire()
            self.results.append(data[0])
            self.results_lock.release()
            # print "Thread %d : finished downloading" % (self.my_id)
            self.urlLock.acquire()
            self.url = None
            self.urlLock.release()
        return


class FetcherPool(object):
    def __init__(self, fetcher, urls, poolsize):
        self.fetcher = fetcher
        self.urls = urls
        self.nbthreads = poolsize
        if (len(self.urls) < self.nbthreads):
            self.nbthreads = len(self.urls))
        self.results = []
        self.res_lock = threading.Lock()
        self.threads = []
        for i in range(self.nbthreads):
            t = FetcherThread(i, self.fetcher, self.results, self.res_lock)
            t.start()
            self.threads.append(t)
        # print "Thread pool length = %d" % (len(self.threads))

    def getFreeThread(self):
        for t in self.threads:
            if (t.getUrl() == None):
                return t
        return None

    def freeThreads(self):
        while len(self.threads) != 0:
            self.threads[0].stopThread()
            self.threads[0].join()
            self.threads.pop(0)
    
    def fetchUrls(self):
        while (len(self.urls) != 0):
            url = self.urls[0]
            t = self.getFreeThread()
            if (t != None):
                t.setUrl(url)
                self.urls.pop(0)
        self.freeThreads()
        # print "Deleted all download threads"
        return self.results
    
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

        poolsize = 10
        fp = FetcherPool(fs.fetchFiles, urls[rank-1 : per_page : NScrapers],
                         poolsize)
        files = fp.fetchUrls()
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
