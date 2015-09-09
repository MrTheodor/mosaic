from mpi4py import MPI
import flickr_scraper
from PIL import Image
import scipy, threading, time

class FetcherThread(threading.Thread):
    def __init__(self, threadID, fetcher, result_buf, result_lock):
        threading.Thread.__init__(self)
        self.my_id = threadID
        self.fetcher = fetcher
        self.results = result_buf
        self.results_lock = result_lock
        self.url = None
        self.urlLock = threading.Condition()
        self.stopped = False
    
    def stopThread(self):
        self.stopped = True
        self.urlLock.acquire()
        self.urlLock.notify()
        self.urlLock.release()
    
    def getUrl(self):
        return self.url
    
    def setUrl(self, url):
        self.urlLock.acquire()
        self.url = url
        self.urlLock.notify()
        self.urlLock.release()
    
    def run(self):
        while (not self.stopped):
            self.urlLock.acquire()
            while (self.url == None):
                if (self.stopped):
                    return
                self.urlLock.wait()
            # print "Thread %d : downloading %s" % (self.my_id, self.url[-30:])
            data = self.fetcher(self.url)
            if (data == None):
                continue
            self.results_lock.acquire()
            self.results.append(data)
            self.results_lock.release()
            # print "Thread %d : finished downloading" % (self.my_id)
            self.url = None
            self.urlLock.release()
        return


class FetcherPool(object):
    def __init__(self, fetcher, urls, poolsize):
        self.fetcher = fetcher
        self.urls = urls
        self.nbthreads = poolsize
        if (len(self.urls) < self.nbthreads):
            self.nbthreads = len(self.urls)
        self.results = []
        self.res_lock = threading.Lock()
        self.threads = []
        for i in range(self.nbthreads):
            tic = time.time()
            t = FetcherThread(i, self.fetcher, self.results, self.res_lock)
            t.start()
            self.threads.append(t)
    
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
                #print "Downloading: %d left ..." % (len(self.urls))
        print "Cleaning up threads ..."
        self.freeThreads()
        print "Deleted all download threads"
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
   
    print "Scraper, node {} out of {}".format(rank, size) 

    scraperPars = comm.recv(source=0, tag=0, status=status)
    print "Node {} received params from Master".format(rank)
    pm = scraperPars['pm']
    tag = scraperPars['tag']

    fs = flickr_scraper.flickrScraper()
    
    #%%
    for page in range(pages):
        urls = fs.scrapeTag(tag, per_page, page=page) 
        print "tag {} scraped for page {}".format(tag, page)

        poolsize = 20
        fp = FetcherPool(fs.fetchFileData, urls[rank-1 : per_page : NScrapers],
                         poolsize)
        arrs = fp.fetchUrls()
        ids = page*per_page + scipy.arange(rank-1, per_page,  NScrapers, dtype=int)
        print "files fetched for page {}".format(page)
        Compacts = []
        for arr in arrs:
            Compacts.append(pm.compactRepresentation(arr))
        scraperResForPlacers = {'Compacts': Compacts, 'ids': ids}
        scraperResForMaster  = {'Compacts': Compacts, 'arrs': arrs,
                                'ids': ids}
        for placer in range(NPlacers):
            print "Scraper, node {} sending to Placer {}".format(rank, placer)
            comm.send(scraperResForPlacers, dest=1+NScrapers+placer, tag=2)
        comm.send(scraperResForMaster, dest=0, tag=3)
        print "Scraper node {} sent ids at page {}".format(rank, page)
