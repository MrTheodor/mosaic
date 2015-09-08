import scipy
from mpi4py import MPI
from scipy import misc, ndimage

def process(pars):
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    pages = pars['pages']

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
    print "Placer node {} out of {}".format(rank, size) 

#%% Receive some parameters
    placerPars = comm.recv(source=0, tag=0, status=status)
    print "Placer {} received the placer parameters".format(rank)
    Tiles = placerPars['Tiles']
    TilesPerNode = placerPars['TilesPerNode']
    UnscaledWidth = placerPars['UnscaledWidth']
    pm = placerPars['pm']
    pages = placerPars['pages']
    TotalTilesPerNode = scipy.prod(TilesPerNode)

#%% Receive its bit of the target image
    NodeArr = comm.recv(source=0, tag=1, status=status)
    print "Placer {} received its part of the image".format(rank)

#%% Divide the NodeArr into tiles
    TileArrs = [] # each tile in the image
    TileCompacts = [] # each tile in the image
    whichSources = scipy.zeros((TotalTilesPerNode), dtype=int)
    Distances = scipy.ones((TotalTilesPerNode))*scipy.Inf # the quality of the current fit for each tile (put at infinity to start with)
    
    TileWidthInCroppedArr = float(UnscaledWidth)/Tiles[0]
    vertSections = scipy.array(scipy.arange(TileWidthInCroppedArr, UnscaledWidth-.5*TileWidthInCroppedArr, TileWidthInCroppedArr), dtype=int)
    VertSplitArrs = scipy.split(NodeArr, vertSections, axis=1)
    for VertSplitArr in VertSplitArrs:
        TileHeightInCroppedArr = float(VertSplitArr.shape[0])/Tiles[1]*NPlacers
        horSections = scipy.array(scipy.arange(TileHeightInCroppedArr, VertSplitArr.shape[0]-.5*TileHeightInCroppedArr, TileHeightInCroppedArr), dtype=int)
        SplitArrs = scipy.split(VertSplitArr, horSections, axis=0)
        for SplitArr in SplitArrs:
            TileArrs.append(SplitArr)
            TileCompacts.append(pm.compactRepresentation(SplitArr))

#%% listen to the scrapers for images place
    for page in range(pages):
        for scraper in range(NScrapers): # listen for the NScrapers scrapers, but not necessarilly in that order!
            scraperRes = comm.recv(source=MPI.ANY_SOURCE, tag=2, status=status) # N.B. This is "scraperResForPlacer" and NOT "scraperResForMaster"
            #print "Placer node {} received ids at page {}".format(rank, page), scraperRes['ids']
            Compacts = scraperRes['Compacts']
            newSources = []

	    # for each set of received files, see if any are better matches to the existing ones
            for f in range(len(Compacts)):
                Compact = Compacts[f]
                for t in range(TotalTilesPerNode):
                    Distance = pm.compactDistance(TileCompacts[t], Compact)
                    if Distance < Distances[t]:
                        whichSources[t] = page*per_page + f
                        newSources.append(whichSources[t])
                        Distances[t] = Distance
                        print "placed photo {} at position {}".format(whichSources[t],t)
            placerRes = {'whichSources': whichSources, 'newSources': newSources, 'placer': rank}
	    # send the master node the result
            comm.send(placerRes, dest=0, tag=4)