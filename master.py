from mpi4py import MPI
from PIL import Image
import scipy
import photo_match_tinyimg as photo_match

def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    pages = pars['pages']
    MaxTilesVert = pars['MaxTilesVert']
    fidelity = pars['fidelity']
    for key, value in pars.iteritems():
        print "{} is now {}".format(key, value)

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    print "Master, node {} out of {}".format(rank, size) 

    pmPars = {'fidelity': fidelity}
    pm = photo_match.photoMatch(pmPars)
    
#%% call the scrapers right at the beginning, as it is probably the slowest
# TODO make multiple tags possible, and let the scrapers deal with them properly
    scraperPars = {'pm': pm, 'tag': 'Art'}
    for scraper in range(1,1+NScrapers):
	comm.send(scraperPars, dest=scraper, tag=0)

#%% adjust the image to have the correct shape (aspect ratio) for turning it into a mosaic
    PixPerTile = scipy.array((75,75))
    TilesVert = int(MaxTilesVert/NPlacers) * NPlacers
    
    TargetImg = Image.open('./KWM18333.JPG')
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
    placerPars = {'TilesPerNode': TilesPerNode, 'UnscaledWidth': UnscaledWidth, 'Tiles': Tiles, 'pm': pm, 'pages': pages}
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

#%% listen to the placers' INTERMEDIATE results
# this will be NPlacers*NScrapers*pages communications,
# but all these communications require the same handling
# i.e. it is required that the master node keeps a list of
# the files that are needed in the final image
# alternatively, we might want to use the iteration over the pages
# as an outer loop, showing an updated intermediate result after each page
# or possibly after a numer of pages, of course this loop could also go around 
# the actual calling of the scraper and placers, to give some control
    arrsKeep = {}
    for page in range(pages):
        print "page: ", page, " out of ", pages
###
### The stuff below is not necessarily in the correct order
###
        for scraper in range(NScrapers):
            print "Master node waiting for the {}th scraper".format(scraper)
            # apparently all nodes in comm need to pay attention to bcast
            comm.bcast(None, root=1+scraper) 
            scraperRes = comm.recv(source=MPI.ANY_SOURCE, tag=3, status=status) # N.B. This is "scraperResForMaster" and NOT "scraperResForPlacer"
            arrs = scraperRes['arrs'] 
            Compacts = scraperRes['Compacts'] 
            ids   = scraperRes['ids'] 
            print "Master node received {} files from a Scraper node (it does not need to know which), but the id of the first file is {}".format(len(arrs), ids[0])
            for i in range(len(arrs)):
                arrsKeep[ids[i]] = arrs[i]
        for step in range(NPlacers*NScrapers):
            print "Master waiting for the {}th block of results (out of {}, one per Scraper per Placer)".format(step, NPlacers*NScrapers)
            placerRes = comm.recv(source=MPI.ANY_SOURCE, tag=4, status=status)
            whichSources = placerRes['whichSources']
            placer = placerRes['placer']-(1+NScrapers)
            print "Master received result from placer node {}".format(placer)
            for t in range(len(whichSources)):
                #print Compacts[whichSources[t]]
                #print arrsKeep[whichSources[t]]
                NodeTiless[placer][t][:,:,:] = arrsKeep[whichSources[t]].copy()
            
#            print "Master node received from {} the following list of Sources to use \n".format(placerRes['placer']), placerRes['whichSources']
        print "Master received results from all nodes"
        FinalImg = Image.fromarray(FinalArr, 'RGB')
        FinalImg.save('mosaic{}.png'.format(page))
        print "Image saved after page {}".format(page)

    print "The master node reached the end of its career"
