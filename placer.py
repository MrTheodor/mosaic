import scipy
from mpi4py import MPI
from scipy import misc, ndimage

def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    iters = pars['iters']

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    #print "Placer, node {} out of {}".format(rank, size) 

#%% Receive some parameters
    placerPars = comm.recv(source=0, tag=0, status=status)
    print "P{}: received the placer parameters".format(rank)
    Tiles = placerPars['Tiles']
    TilesPerNode = placerPars['TilesPerNode']
    UnscaledWidth = placerPars['UnscaledWidth']
    pm = placerPars['pm']
    iters = placerPars['iters']
    TotalTilesPerNode = scipy.prod(TilesPerNode)

#%% Receive its bit of the target image
    NodeArr = comm.recv(source=0, tag=1, status=status)
    print "P{}: received its part of the image".format(rank)

#%% Divide the NodeArr into tiles
    TileArrs = [] # each tile in the image
    TileCompactvs = [] # each tile in the image
    whichSources = scipy.zeros((TotalTilesPerNode), dtype=int)
    Distances = scipy.ones((TotalTilesPerNode))*scipy.Inf # the quality of the current fit for each tile (put at infinity to start with)
    
    TileWidthInNodeArr = float(UnscaledWidth)/Tiles[0]
    vertSections = scipy.array(scipy.arange(TileWidthInNodeArr, UnscaledWidth-.5*TileWidthInNodeArr, TileWidthInNodeArr), dtype=int)
    VertSplitArrs = scipy.split(NodeArr, vertSections, axis=1)
    for VertSplitArr in VertSplitArrs:
        TileHeightInNodeArr = float(VertSplitArr.shape[0])/Tiles[1]*NPlacers
        horSections = scipy.array(scipy.arange(TileHeightInNodeArr, VertSplitArr.shape[0]-.5*TileHeightInNodeArr, TileHeightInNodeArr), dtype=int)
        SplitArrs = scipy.split(VertSplitArr, horSections, axis=0)
        for SplitArr in SplitArrs:
            TileArrs.append(SplitArr)
            TileCompactvs.append(pm.compactRepresentation(SplitArr))

#%% listen to the scrapers for images place
    for iter in range(iters):
        for scraper in range(NScrapers): # listen for the NScrapers scrapers, but not necessarilly in that order!
            print "P{}: waiting for ids at iter {}".format(rank, iter)
            scraperRes = scipy.empty((per_page, 1+3*scipy.prod(pm.compareSize)), dtype='i') # 1 for the ids!
            #print "P{}: res shape: ".format(rank), scraperRes.shape
            comm.Recv([scraperRes, MPI.INT], source=MPI.ANY_SOURCE, tag=2) # N.B. This is "scraperResForPlacers" and NOT "scraperResForMaster"
            print "P{}: received ids at iter {}".format(rank, iter)
            #Compacts = scraperRes['Compacts']
            #ids = scraperRes['ids']
            ids = scraperRes[:,0]
            compactvs = scraperRes[:,1:]
            newSources = []

	    # for each set of received files, see if any are better matches to the existing ones
            for f in range(compactvs.shape[0]):
                compactv = compactvs[f,:]
                for t in range(TotalTilesPerNode):
                    Distance = pm.compactDistance(TileCompactvs[t], compactv)
                    if Distance < Distances[t]:
                        whichSources[t] = ids[f]
                        newSources.append(whichSources[t])
                        Distances[t] = Distance
#                        print "P{}: placed photo {} at position {}".format(rank, whichSources[t],t)
            placerRes = {'whichSources': whichSources, 'newSources': newSources, 'placer': rank}
	    # send the master node the result
            comm.isend(placerRes, dest=0, tag=4)
            print "P{}: sent results after {}th scraper in iter {} to Master".format(rank, scraper, iter)
