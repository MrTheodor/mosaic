import scipy
from mpi4py import MPI
from scipy import misc, ndimage, signal, linalg
from photo_match_labimg import *

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def surf(Z):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    X,Y = scipy.meshgrid(range(Z.shape[0]),range(Z.shape[1]))
    ax.plot_surface(X,Y,Z)
    plt.show()


class Placer(object):
    def __init__(self, pars):
        # --- tile size parameters
        self.chunkDim = None
        self.tileDim = None
        self.shiftDim = None
        # --- data structures for image data and correlation results
        self.targetPieces = []
        self.tiles = []
        self.resizedTiles = []
        self.matchMap = {}
        # --- parameters for communication
        self.NPlacers = pars['NPlacers']
        self.NScrapers = pars['NScrapers']
        self.per_page = pars['per_page']
        self.iters = pars['iters']
        # --- MPI stuff
        self.comm = MPI.COMM_WORLD
        self.rank = self.comm.Get_rank()
        size = self.comm.Get_size()
        self.status = MPI.Status()
        # --- identify oneself
        print "Placer, node {} out of {}".format(self.rank, size) 
        print "P{} > init".format(self.rank)
    
    def process(self): ## Not tested yet
        self.listenForParameters()
        self.getTargetChunk()
        for i in range(self.iters):
            self.getTiles()
            self.matchPieces()
            self.sendToMaster()
        # --- signal completion
        self.comm.barrier()
        print "P{}: reached the end of its career".format(self.rank)
    
    def listenForParameters(self):
        placerPars = self.comm.recv(source=0, tag=0, status=self.status)
        print "P{}: received the placer parameters".format(self.rank)
        self.Tiles         = placerPars['Tiles']
        self.TilesPerNode  = placerPars['TilesPerNode']
        PixPerTile    = placerPars['PixPerTile']
        self.TileSize = 3*scipy.prod(PixPerTile)
        
        ratio = 2.0 / 3.0
        self.tileDim = (PixPerTile[0], PixPerTile[1], 3)
        self.sliceDim = (int(self.tileDim[0]*ratio),
                         int(self.tileDim[1]*ratio), 3)
        
        self.compareTileSize = placerPars['ComparePixPerTile'][0]
        assert (self.compareTileSize % 3 == 0) ## multiple of 3
        self.compareChunkSize = int(self.compareTileSize*ratio)
        shiftSize = self.compareTileSize - self.compareChunkSize + 1
        self.shiftDim = (shiftSize,shiftSize)
        print "P{} < init".format(self.rank) 

    def getTargetChunk(self):
        print "P{} > listening".format(self.rank) 
        NodeArr = self.comm.recv(source=0, tag=1, status=self.status)
        print "P{} < listening".format(self.rank) 
        
        #%% Divide the NodeArr into tiles
        print "P{} > dividing".format(self.rank) 
        VertSplitArrs = scipy.split(NodeArr, self.Tiles[0], axis=1)
        for VertSplitArr in VertSplitArrs:
            SplitArrs = scipy.split(VertSplitArr,self.Tiles[1]/self.NPlacers,
                                    axis=0)
            for splitArr in SplitArrs:
                self.targetPieces.append(splitArr)
        print "P{}: < dividing image".format(self.rank)
    
    def getTiles(self):
        print "P{}: > listening".format(self.rank)
        
        # Received Data : 1+... for the ids!
        scraperRes = scipy.empty((self.per_page, 1+self.TileSize), dtype='i')
        self.tiles = scipy.zeros((self.NScrapers*self.per_page,)+self.tileDim,
                                 dtype='i')
        ids  = scipy.zeros((self.NScrapers*self.per_page), dtype='i')
        # listen for the NScrapers scrapers, but not necessarilly in that order!
        for scraper in range(self.NScrapers):
            self.comm.Recv([scraperRes, MPI.INT], source=MPI.ANY_SOURCE, tag=2,
                           status=self.status)
            i0 =  scraper*self.per_page
            i1 = (scraper+1)*self.per_page
            ids[i0:i1]      = scraperRes[:,0]
            print "P{}: received ids {}--{} from the {}th scraper".format(self.rank, ids[i0], ids[i1-1], scraper)
            self.tiles[i0:i1,...] = scraperRes[:,1:].reshape((self.per_page,)+self.tileDim)
        self.resizedTiles = self.resizeTiles(self.tiles)
        print "P{}: < listening".format(self.rank)

    def sendToMaster(self):
        result = self.buildMosaic()
        print "P{}: > sending".format(self.rank)
        self.comm.Send([result, MPI.INT], dest=0, tag=4)
        print "P{}: < sending".format(self.rank)
        
    def pack(self, img, ID):
        data = scipy.reshape(img, (-1,))
        return scipy.concatenate((scipy.array([ID]), data))
    
    def unpack(self, data, dim):
        ID = data[0] ## Note: not using ID anymore, no need ...
        img = scipy.reshape(data[1:], dim)
        return img
    
    def matchPieces(self):
        print "P{}: > processing {} target pieces".format(self.rank,
                                                        len(self.targetPieces))
        for idx, piece in enumerate(self.targetPieces):
            print "P{}: {}/{}".format(self.rank, idx, len(self.targetPieces))
            self.matchMap[idx] = self.compare(piece, self.resizedTiles)
        print "P{}: < processing".format(self.rank)

    def resizeTiles(self, arrs):
        N = self.compareTileSize
        result = scipy.zeros((len(arrs), N,N, 3))
        for i in range(len(arrs)):
            result[i,...] = scipy.misc.imresize(arrs[i], (N,N))
        return result
            
    def translatePos(self, pos):
        ratio = self.compareTileSize / float(self.tileDim[0])
        pX = int(round(pos[0] / ratio))
        pY = int(round(pos[1] / ratio))
        return (pX, pY)

    def cutout(self, tiledata, pos):
        assert (tiledata.shape == self.tileDim)
        
        return tiledata[pos[0]:pos[0]+self.sliceDim[0],\
                        pos[1]:pos[1]+self.sliceDim[1],:]
    
    def buildMosaic(self):
        tileFinalArrs = []            
        
        finalArr = scipy.zeros((self.sliceDim[1]*self.Tiles[1]/self.NPlacers,
                                self.sliceDim[0]*self.Tiles[0], 3), dtype='i')
        VertSplitFinalArrs = scipy.split(finalArr, self.Tiles[0], axis=1)
        for VertSplitFinalArr in VertSplitFinalArrs:
            SplitFinalArrs = scipy.split(VertSplitFinalArr,
                                         self.Tiles[1]/self.NPlacers, axis=0)
            for SplitFinalArr in SplitFinalArrs:
                tileFinalArrs.append(SplitFinalArr)

        for idx in range(len(tileFinalArrs)):
            match = self.matchMap[idx]
            print match
            tileFinalArrs[idx][...] = self.cutout(self.tiles[match[0]], match[1])
        # for idx, piece in enumerate(tileFinalArrs):
        #     match = self.matchMap[idx]
        #     print self.cutout(self.tiles[match[0]], match[1])
        #     piece = self.cutout(self.tiles[match[0]], match[1])
        return finalArr
    
    def compare(self, chunk, tiles):
        raise NotImplementedError


class OldMinDistPlacer(Placer):
    def dist(self, arr1, arr2):
        assert (arr1.shape[0] < arr2.shape[0])
        
        S = arr1.shape[0]
        diff = scipy.zeros(self.shiftDim)
        for i in range(self.shiftDim[0]):
            for j in range(self.shiftDim[1]):
                diff[i,j] = linalg.norm(abs(arr1 - arr2[i:i+S,j:j+S]))
        return diff
    
    def compare(self, chunk, tiles):
        assert (chunk.shape[0] == self.compareChunkSize)
        
        print tiles.shape
        
        chunk = scipy.int_(chunk)
        minDist = (-1,0,999999999)
        for ID, tile in enumerate(tiles):
            assert (tile.shape[0] == self.compareTileSize)
            tile = scipy.int_(tile)
            diff = scipy.zeros(self.shiftDim)
            colorComps = tile.shape[2] # usually 3 RGB color components
            for i in range(colorComps):
                diff = diff + self.dist(chunk, tile)
            diff = diff / colorComps
            min_idx = scipy.unravel_index(scipy.argmin(diff), self.shiftDim)
            if (diff[min_idx] < minDist[2]):
                # print diff[min_idx]
                minDist = (ID, self.translatePos(min_idx), diff[min_idx])
        return minDist


class MinDistPlacer(Placer):
    def distance(self, target, candidates):
        self.weights = scipy.ones(3) # might want to change this in Lab space
        return scipy.sum((candidates - target)**2*self.weights, axis=(1,2,3))
    
    def compare(self, chunk, tiles):
        assert (chunk.shape[0] == self.compareChunkSize)
        
        chunk = scipy.int_(chunk)
        S = chunk.shape[0]
        # distance will contain the distance for each tile, for each position
        distances = scipy.zeros((self.shiftDim[0], self.shiftDim[1], tiles.shape[0]))
        for i in range(self.shiftDim[0]):
            for j in range(self.shiftDim[1]):
                distances[i,j,:] = self.distance(chunk, tiles[:,i:i+S,j:j+S,:])
        combinedIndex = scipy.unravel_index(scipy.argmin(distances), distances.shape)
        idx  = combinedIndex[-1]
        pos  = self.translatePos(combinedIndex[:-1])
        dist = distances[combinedIndex]
        return (idx, pos, dist)
    

class CorrelationPlacer(Placer):
    def compare(self, chunk, tiles):
        chunk = self.normalize(chunk)
        for i in range(chunk.shape[2]):
            chunk[:,:,i] = chunk[:,:,i] - scipy.mean(chunk[:,:,i])
            chunk[:,:,i] = chunk[:,:,i] / scipy.amax(abs(chunk[:,:,i]))
        maxCorr = (-1, 0, 0)
        for ID, tile in enumerate(tiles):
            tile = self.normalize(tile)
            corr = scipy.zeros(self.shiftDim)
            colorComps = tile.shape[2] # usually 3 RGB color components
            for i in range(colorComps):
                corr = corr + signal.correlate(tile[:,:,i],chunk[:,:,i],
                                               mode='valid')
            corr = corr / colorComps
            max_idx = scipy.unravel_index(scipy.argmax(corr), self.shiftDim)
            if (corr[max_idx] > maxCorr[2]):
                print corr[max_idx]
                maxCorr = (ID, self.translatePos(max_idx), corr[max_idx])
        return maxCorr
    
    def normalize(self, data):
        return scipy.float64(data)/255 - 0.5


class TestPlacer(MinDistPlacer):
    def __init__(self):
        # --- tile size parameters
        self.tileDim = None
        self.shiftDim = None
        # --- data structures for image data and correlation results
        self.targetPieces = []
        self.tiles = []
        self.resizedTiles = []
        self.matchMap = {}
        
    def listenForParameters(self):
        ratio = 2.0 / 3.0
        self.tileDim = (75, 75, 3)
        self.compareTileSize = 45
        assert (self.compareTileSize % 3 == 0) ## multiple of 3
        self.compareChunkSize = int(self.compareTileSize*ratio)
        shiftSize = self.compareTileSize - self.compareChunkSize + 1
        self.shiftDim = (shiftSize,shiftSize)


        
def process(pars):
#%% load the parameters that CAN be specified from the command line
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    per_page = pars['per_page']
    iters = pars['iters']
    UsedPenalty = float(pars['UsedPenalty'])/10.

#%% MPI stuff
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()
   
#%% identify oneself
    print "Placer, node {} out of {}".format(rank, size) 
    print "P{} > init".format(rank) 

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
    print "P{} < init".format(rank) 

#%% Receive its bit of the target image
    print "P{} > listening".format(rank) 
    NodeArr = comm.recv(source=0, tag=1, status=status)
    #print "P{}: received its part of the image with shape ".format(rank), NodeArr.shape
    print "P{} < listening".format(rank) 

    print "P{} > dividing".format(rank) 
#%% Divide the NodeArr into tiles
    TileArrs = [] # each tile in the image
    whichSources = scipy.zeros((TotalTilesPerNode), dtype=int)
    distances = scipy.ones((TotalTilesPerNode))*scipy.Inf # the quality of the current fit for each tile (put at infinity to start with)

    print "Tiles = ", Tiles
    print "NodeArr = ",  NodeArr.shape
    VertSplitArrs = scipy.split(NodeArr, Tiles[0], axis=1)
    print "VertSplitArrs = ", scipy.array(VertSplitArrs).shape
    for VertSplitArr in VertSplitArrs:
        SplitArrs = scipy.split(VertSplitArr, Tiles[1]/NPlacers, axis=0)
        print "SplitArrs = ", scipy.array(SplitArrs).shape
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
    print "P{}: < dividing image".format(rank) 

#%% listen to the scrapers for images place
    scraperRes = scipy.empty((per_page, 1+TileSize), dtype='i') # 1+... for the ids!
    for it in range(iters):
        print "P{}: > listening".format(rank)
        ids  = scipy.zeros((NScrapers*per_page), dtype='i')
        arrs = scipy.zeros((NScrapers*per_page, PixPerTile[0],PixPerTile[1],3), dtype='i')
        for scraper in range(NScrapers): # listen for the NScrapers scrapers, but not necessarilly in that order!
            #print "P{}: waiting for the {}th scraper at iter {}".format(rank, scraper, it)
            #print "P{}: scraperRes has shape and type ".format(rank), scraperRes.shape, type(scraperRes[0,0])
            comm.Recv([scraperRes, MPI.INT], source=MPI.ANY_SOURCE, tag=2, status=status)
            #print "P{}: stuff received with shape and type ".format(rank), scraperRes.shape, type(scraperRes[0,0])
            i0 =  scraper*per_page
            i1 = (scraper+1)*per_page
            ids[i0:i1]      = scraperRes[:,0]
            arrs[i0:i1,...] = scraperRes[:,1:].reshape((per_page,PixPerTile[0],PixPerTile[1],3))
#            arrs[:,:,:,1:] = 0
            #print "P{}: received ids {}--{} at iter {} from the {}th scraper".format(rank, ids[i0], ids[i1-1], it, scraper)
        print "P{}: < listening".format(rank)

        print "P{}: > placing".format(rank)
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
                trialDistances[i]*= (1+UsedPenalty) # add a penalty to an image that has already been used
                tileFinalArrs[t][:,:,:] = arrs[i,:,:,:]
                #print "P{}: placed photo {} at position {}".format(rank, whichSources[t],t)
        #print "P{}: last photo vs. target: ".format(rank), arrs[i,:15,:15,:], compacts[i,0,0,:], TileArrs[t][:15,:15,:]
        #print "P{}: placed photos: ".format(rank), whichSources
        print "P{}: < placing".format(rank)
            
        #print "P{}: finalArr has shape ".format(rank), finalArr.shape
        #print "P{}: finalArr has type ".format(rank), type(finalArr[0,0,0])
        print "P{}: > sending".format(rank)
        if it > 0:
            isReceived = False
            while isReceived == False:
                isReceived = MPI.Request.Test(req)
        req = comm.Isend([finalArr, MPI.INT], dest=0, tag=4)
        #print "P{}: sent results after iter {} to Master".format(rank, it)
        print "P{}: < sending".format(rank)

#%% signal completion
    comm.barrier()
    print "P{}: reached the end of its career".format(rank)
    
if __name__ == "__main__":
    import os 
    
    pars = {'NScrapers': 1, 'NPlacers': 1, 'iters': 2, 'per_page': 10, 'MaxTilesVert': 8, 'fidelity': 1, 'poolSize': 20, 'UsedPenalty': 0.}

    placer_obj = Placer(pars)

    imagePaths = os.listdir('test_imgs')    
    K = 10
    Images = scipy.zeros(K, )
