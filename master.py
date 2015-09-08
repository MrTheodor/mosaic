from mpi4py import MPI
from PIL import Image
import scipy
import photo_match_tinyimg as photo_match

def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    pages = pars['pages']

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    print "Master node {} out of {}".format(rank, size) 
    pm = photo_match.photoMatch()
    
#%% call the scrapers right at the beginning, as it is probably the slowest
    scraperPars = {'pm': pm, 'tag': 'Art'}
    for scraper in range(1,1+NScrapers):
	comm.send(scraperPars, dest=scraper, tag=0)

#%% adjust the image to have the correct shape (aspect ratio) for turning it into a mosaic
    PixPerTile = scipy.array((75,75))
    MaxTilesVert = 20
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
    NodeArrs = scipy.split(CroppedArr, sections, axis=0) # each tile in the image

#%% send each of the placers a piece of the picture
    for placer in range(NPlacers):
        comm.send(NodeArrs[placer], dest=1+NScrapers+placer, tag=1)

#%% listen to the placers' INTERMEDIATE results
# this will be NPlacers*NScrapers*pages communications,
# but all these communications require the same handling
# i.e. it is required that the master node keeps a list of
# the files that are needed in the final image
# alternatively, we might want to use the iteration over the pages
# as an outer loop, showing an updated intermediate result after each page
# or possibly after a numer of pages, of course this loop could also go around 
# the actual calling of the scraper and placers, to give some control
    for page in range(pages):
        scraperRes = comm.recv(source=MPI.ANY_SOURCE, tag=3, status=status) # N.B. This is "scraperResForMaster" and NOT "scraperResForPlacer"
        for step in range(NPlacers*NScrapers):
            placerRes = comm.recv(source=MPI.ANY_SOURCE, tag=4, status=status)
            print "Master node received from {} the following list of Sources to use \n".format(placerRes['placer']), placerRes['whichSources']

    print "The master node reached the end of its career"