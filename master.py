from mpi4py import MPI
from PIL import Image
import scipy
import photo_match_tinyimg2 as photo_match
import os

def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    iters = pars['iters']
    tags = ('Bussum','Football','PSV','Minimalism','urbex')

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    MaxTilesVert = pars['MaxTilesVert']
    fidelity = pars['fidelity']
    for key, value in pars.iteritems():
        print "M{}: {} is now {}".format(rank, key, value)

    print "Master, node {} out of {}".format(rank, size) 

    pmPars = {'fidelity': fidelity}
    pm = photo_match.photoMatch(pmPars)
    
#%% call the scrapers right at the beginning, as it is probably the slowest
    scraperPars = {'pm': pm, 'tags': tags }
    for scraper in range(1,1+NScrapers):
	comm.send(scraperPars, dest=scraper, tag=0)

#%% adjust the image to have the correct shape (aspect ratio) for turning it into a mosaic
    PixPerTile = scipy.array((75,75))
    TilesVert = int(MaxTilesVert/NPlacers) * NPlacers
    
    TargetImg = Image.open('./KWM24489.JPG')
    TargetSize = TargetImg.size
    TilesHor = (TargetSize[0]*PixPerTile[1]*TilesVert)/(TargetSize[1]*PixPerTile[0])
    Tiles = scipy.array((TilesHor, TilesVert), dtype=int)
    TilesPerNode = scipy.array((TilesHor, TilesVert/NPlacers), dtype=int)
    TotalTilesPerNode = scipy.prod(TilesPerNode)
    Pixels = Tiles*PixPerTile
    UnscaledWidth = (TargetSize[1]*Tiles[0])/Tiles[1]# the width of the original size image to yield the correct aspect ratio
    CropMargin = (TargetSize[0] - UnscaledWidth)/2
    #TargetImg.crop((0,0,))
    #TargetImg.resize(Pixels)
    CroppedImg = TargetImg.transform((UnscaledWidth,TargetSize[1]), Image.EXTENT, (CropMargin,0, CropMargin+UnscaledWidth,TargetImg.size[1]))
    CroppedArr = scipy.array(CroppedImg)

#%% send each placer some parameters
    placerPars = {'TilesPerNode': TilesPerNode, 'UnscaledWidth': UnscaledWidth, 'Tiles': Tiles, 'pm': pm, 'iters': iters}
    for placer in range(NPlacers):
        comm.send(placerPars, dest=1+NScrapers+placer, tag=0)
    
#%% reduce CroppedArr to NPlacers NodeArrs
    NodeHeightInCroppedArr = float(TargetSize[1])/NPlacers
    sections = scipy.array(scipy.arange(NodeHeightInCroppedArr, TargetSize[1], NodeHeightInCroppedArr), dtype=int)
    NodeArrs = scipy.split(CroppedArr, sections, axis=0) 

#%% send each of the placers a piece of the picture
    for placer in range(NPlacers):
        comm.send(NodeArrs[placer], dest=1+NScrapers+placer, tag=1)

#%% create the final image and divide it into pieces for the placers to     FinalArr = CroppedArr.copy()
# now the division has to be accurate!
    FinalArr = scipy.zeros((Tiles[1]*PixPerTile[1], Tiles[0]*PixPerTile[0], 3), dtype=scipy.uint8)
    NodeFinalArrs = scipy.split(FinalArr, NPlacers, axis=0)

    NodeTiless = []
    for NodeFinalArr in NodeFinalArrs:
        NodeTiles = []
        VertSplitArrs = scipy.split(NodeFinalArr, Tiles[0], axis=1) 
        for VertSplitArr in VertSplitArrs:
            SplitArrs = scipy.split(VertSplitArr, Tiles[1]/NPlacers, axis=0)
            for SplitArr in SplitArrs:
                NodeTiles.append(SplitArr)
        NodeTiless.append(NodeTiles)
#%% TODO: delete all existing mosaic files while the guys are busy

#%% listen to the placers' INTERMEDIATE results
# this will be NPlacers*NScrapers*iters communications,
# but all these communications require the same handling
# i.e. it is required that the master node keeps a list of
# the files that are needed in the final image
# alternatively, we might want to use the iteration over the iters
# as an outer loop, showing an updated intermediate result after each iter
# or possibly after a numer of iters, of course this loop could also go around 
# the actual calling of the scraper and placers, to give some control
    arrsKeep = {}
    for iter in range(iters):
        print "M{}: iter: {} out of {} ".format(rank, iter,iters)
        for scraper in range(NScrapers):
            print "M{}:  waiting for the {}th scraper".format(rank, scraper)
            scraperRes = scipy.empty((per_page, 1+75*75*3), dtype='i') # 1 for the ids!
            #print "M{}: res shape: ".format(rank), scraperRes.shape
            comm.Recv([scraperRes, MPI.INT], source=MPI.ANY_SOURCE, tag=3) # N.B. This is "scraperResForMaster" and NOT "scraperResForPlacers"
            #arrs = scraperRes['arrs'] 
            #ids   = scraperRes['ids'] 
            ids = scraperRes[:,0]
            arrvs = scraperRes[:,1:]
            print "M{}: received {} files from a Scraper node".format(rank, ids.shape[0], ids[0])
            #print "M{}: received {} files from a Scraper node (it does not need to know which), but the id of the first file is {}".format(rank, arrvs.shape[0], ids[0])
            for i in range(arrvs.shape[0]):
                arrsKeep[ids[i]] = arrvs[i,:].reshape((75,75,3))
        print "M{}: now listening for placer results".format(rank)
        for step in range(NPlacers*NScrapers):
            print "M{}: waiting for the {}th block of results (out of {}, one per Scraper per Placer)".format(rank, step, NPlacers*NScrapers)
            placerRes = comm.recv(source=MPI.ANY_SOURCE, tag=4, status=status)
            whichSources = placerRes['whichSources']
            placer = placerRes['placer']-(1+NScrapers)
            print "M{}: received result from placer node {}".format(rank, placer)
            #print "M{}: received from {} the following list of Sources to use \n".format(rank, placerRes['placer']), placerRes['whichSources']
            for t in range(len(whichSources)):
                #print "M{}: At {} use source {}".format(rank, t, whichSources[t])
                NodeTiless[placer][t][:,:,:] = arrsKeep[whichSources[t]].copy()
            
        print "M{}: finished listening to placer results".format(rank)
        FinalImg = Image.fromarray(FinalArr, 'RGB')
        FinalImg.save('mosaic{}.png'.format(iter))
        print "M{}: Image saved after iter {}".format(rank, iter)

    print "The master node reached the end of its career"
