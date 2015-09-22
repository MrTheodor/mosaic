import scipy
from mpi4py import MPI
from scipy import misc, ndimage

def process(pars):
#%% load the parameters that CAN be specified from the command line
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    iters = pars['iters']

#%% MPI stuff
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
#%% identify oneself
    print "Placer, node {} out of {}".format(rank, size) 

#%% receive parameters from the master
    placerPars = comm.recv(source=0, tag=0, status=status)
    print "P{}: received the placer parameters".format(rank)
    Tiles         = placerPars['Tiles']
    TilesPerNode  = placerPars['TilesPerNode']
    pm            = placerPars['pm']
    iters         = placerPars['iters']
    PixPerTile    = placerPars['PixPerTile']
    
    # derived parameters
    TileSize = 3*scipy.prod(PixPerTile)
    TotalTilesPerNode = scipy.prod(TilesPerNode)

#%% Receive its bit of the target image
    NodeArr = comm.recv(source=0, tag=1, status=status)
    print "P{}: received its part of the image with shape ".format(rank), NodeArr.shape

#%% Divide the NodeArr into tiles
    TileArrs = [] # each tile in the image
    whichSources = scipy.zeros((TotalTilesPerNode), dtype=int)
    distances = scipy.ones((TotalTilesPerNode))*scipy.Inf # the quality of the current fit for each tile (put at infinity to start with)
    
    VertSplitArrs = scipy.split(NodeArr, Tiles[0], axis=1)
    for VertSplitArr in VertSplitArrs:
        SplitArrs = scipy.split(VertSplitArr, Tiles[1]/NPlacers, axis=0)
        for SplitArr in SplitArrs:
            TileArrs.append(SplitArr.reshape(scipy.insert(SplitArr.shape, 0, 1)))
    TileCompacts = pm.compactRepresentation(scipy.concatenate(TileArrs, axis=0))

#%% Create output array
    tileFinalArrs = []            
        
    finalArr = scipy.zeros((PixPerTile[1]*Tiles[1]/NPlacers, PixPerTile[0]*Tiles[0], 3), dtype='i')
    VertSplitFinalArrs = scipy.split(finalArr, Tiles[0], axis=1)
    for VertSplitFinalArr in VertSplitFinalArrs:
        SplitFinalArrs = scipy.split(VertSplitFinalArr, Tiles[1]/NPlacers, axis=0)
        for SplitFinalArr in SplitFinalArrs:
            tileFinalArrs.append(SplitFinalArr)
    #print "P{} shapes of SplitArr and SplitFinalArr: ".format(rank), SplitArr.shape, SplitFinalArr.shape

#%% listen to the scrapers for images place
    scraperRes = scipy.empty((per_page, 1+TileSize), dtype='i') # 1+... for the ids!
    for it in range(iters):
        ids  = scipy.zeros((NScrapers*per_page), dtype='i')
        arrs = scipy.zeros((NScrapers*per_page, PixPerTile[0],PixPerTile[1],3), dtype='i')
        for scraper in range(NScrapers): # listen for the NScrapers scrapers, but not necessarilly in that order!
            print "P{}: waiting for the {}th scraper at iter {}".format(rank, scraper, it)
            #print "P{}: scraperRes has shape and type ".format(rank), scraperRes.shape, type(scraperRes[0,0])
            comm.Recv([scraperRes, MPI.INT], source=MPI.ANY_SOURCE, tag=2, status=status)
            print "P{}: stuff received with shape and type ".format(rank), scraperRes.shape, type(scraperRes[0,0])
            i0 =  scraper*per_page
	    i1 = (scraper+1)*per_page
            ids[i0:i1]      = scraperRes[:,0]
            arrs[i0:i1,...] = scraperRes[:,1:].reshape((per_page,PixPerTile[0],PixPerTile[1],3))
#            arrs[:,:,:,1:] = 0
            print "P{}: received ids {}--{} at iter {} from the {}th scraper".format(rank, ids[i0], ids[i1-1], it, scraper)

        # compact each of the arrays
        compacts = pm.compactRepresentation(arrs)
        # for each set of received files, see if any are better matches to the existing ones
        for t in range(TotalTilesPerNode):
            trialDistances = pm.compactDistance(TileCompacts[t], compacts)
            i = scipy.argmin(trialDistances)
            #print "P{}: at tile {} found minimum distance to be {} at index {}, photo id {}".format(rank, t, trialDistances[i], i, ids[i])
            if trialDistances[i] < distances[t]:
                whichSources[t] = ids[i]
                distances[t] = trialDistances[i]
                tileFinalArrs[t][:,:,:] = arrs[i,:,:,:]
                #print "P{}: placed photo {} at position {}".format(rank, whichSources[t],t)
        #print "P{}: last photo vs. target: ".format(rank), arrs[i,:15,:15,:], compacts[i,0,0,:], TileArrs[t][:15,:15,:]
        #print "P{}: placed photos: ".format(rank), whichSources
            
        #print "P{}: finalArr has shape ".format(rank), finalArr.shape
        #print "P{}: finalArr has type ".format(rank), type(finalArr[0,0,0])
        if it > 0:
            isReceived = False
            while isReceived == False:
                isReceived = MPI.Request.Test(req)
        req = comm.Isend([finalArr, MPI.INT], dest=0, tag=4)
        print "P{}: sent results after iter {} to Master".format(rank, it)

#%% signal completion
    comm.barrier()
    print "P{}: reached the end of its career".format(rank)
