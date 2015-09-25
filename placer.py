import scipy
from mpi4py import MPI
from scipy import misc, ndimage, signal
from skimage import color

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
        self.mosaic = None
        self.mosaicTiles = []
        self.matchMap = {}
        self.tilesToPlace = []
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
        self.splitTargetChunk()
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

    def splitTargetChunk(self):
        ## create mosaic data-structure + list of 'pointers' to the tiles in
        ## this structure
        self.mosaic = scipy.zeros((self.sliceDim[1]*self.Tiles[1]/self.NPlacers,
                                self.sliceDim[0]*self.Tiles[0], 3), dtype='i')
        VertSplitFinalArrs = scipy.split(self.mosaic, self.Tiles[0], axis=1)
        for VertSplitFinalArr in VertSplitFinalArrs:
            SplitFinalArrs = scipy.split(VertSplitFinalArr,
                                         self.Tiles[1]/self.NPlacers, axis=0)
            for SplitFinalArr in SplitFinalArrs:
                self.mosaicTiles.append(SplitFinalArr)

    
    def getTiles(self):
        print "P{}: > listening".format(self.rank)
        
        scraperRes = scipy.empty((self.per_page,)+self.tileDim, dtype=scipy.uint8)
        self.tiles = scipy.zeros((self.NScrapers*self.per_page,)+self.tileDim,
                                 dtype='i')
        # listen for the NScrapers scrapers, in the correct order!
        for scraper in range(1, 1+self.NScrapers):
            self.comm.Bcast(scraperRes, root=scraper)
            i0 = (scraper-1)*self.per_page
            i1 =  scraper   *self.per_page
            self.tiles[i0:i1,...] = scraperRes.reshape((self.per_page,)+self.tileDim)
        print "P{}: < listening".format(self.rank)
        self.resizedTiles = self.resizeTiles(self.tiles)

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
            bestMatch = self.compare(piece, self.resizedTiles)
            if (idx in self.matchMap):
                if (bestMatch[2] < self.matchMap[idx][2]):
                    self.matchMap[idx] = bestMatch
                    self.tilesToPlace.append(idx)
            else:
                self.matchMap[idx] = bestMatch
                self.tilesToPlace.append(idx)
        print "P{}: < processing".format(self.rank)
    
    def resizeTiles(self, arrs):
        N = self.compareTileSize
        result = scipy.zeros((arrs.shape[0], N,N, 3))
        for i in range(arrs.shape[0]):
            result[i,...] = color.rgb2lab(scipy.misc.imresize(arrs[i], (N,N)))
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
        ## Writes all 'tilesToPlace' to the final data structure.
        ## On the first iteration all tiles are placed, on the next iterations
        ## only some tiles maybe re-placed
        for idx in range(len(self.mosaicTiles)):
            if (len(self.tilesToPlace) != 0 and self.tilesToPlace[0] == idx):
                self.tilesToPlace.pop(0)
            else:
                continue
            match = self.matchMap[idx]
            # print match
            self.mosaicTiles[idx][...] = self.cutout(self.tiles[match[0]],
                                                     match[1])
        return self.mosaic
    
    def compare(self, chunk, tiles):
        raise NotImplementedError


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


