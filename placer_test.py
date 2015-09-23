from placer import *
import scipy, Image, os

def resize_chunk(data, dim):
    N = dim
    return scipy.misc.imresize(data, (N,N)).reshape(N,N,3)

## Try converting an image to an array and back
def test_img_reconstr(placer):
    img_obj = Image.open("Matilda.JPG")
    img = scipy.array(img_obj)
    img_obj.show()
    
    data = placer.pack(img, 0)
    img_r = placer.unpack(data, img.shape)
    img_recon = Image.fromarray(scipy.uint8(img_r))
    img_recon.show()

def test_compare_single(placer):
    tile = scipy.array(Image.open("./eye.jpg"))
    resizedTile = resize_chunk(tile, placer.compareChunkSize)
    expanded = 128*scipy.ones((75,75,3))
    pos = (8, 12)
    expanded[pos[0]:pos[0]+50, pos[1]:pos[1]+50] = tile

    cands = placer.resizeTiles(scipy.array([expanded]))
    ID, best_pos, bestCorr = placer.compare(resizedTile, cands)
    if (pos == best_pos):
        print "tile correctly discovered: %r, %r, %r" % (ID, best_pos, bestCorr)
        return True
    else:
        print "ERROR: Tile was not correctly discovered! %r, %r, %r" % (ID, best_pos, bestCorr)
        return False
    
def test_compare_two(placer):
    tile = scipy.array(Image.open("./eye.jpg"))
    tile = resize_chunk(target, placer.compareChunkSize)
    cand = scipy.array(Image.open("./imgs0/img_0gxHKNvoka.jpg"))
    ID, best_pos, bestCorr = placer.compare(tile, [cand])
    idx = best_pos
    
    result = scipy.zeros(cand.shape)
    result[idx[0]:idx[0]+50, idx[1]:idx[1]+50] = tile
    Image.fromarray(scipy.uint8(result)).show()
    Image.fromarray(scipy.uint8(cand)).show()

def test_compare_many(placer, target_fn, cnt):
    target = scipy.array(Image.open(target_fn))
    resizedTarget = resize_chunk(target, placer.compareChunkSize)
    
    cand_names = os.listdir("./imgs0/")
    cands = []
    for i in range(cnt):
        cands.append(scipy.array(Image.open("./imgs0/" + cand_names[i])))
        if (cands[i].ndim == 2):
            csh = cands[i].shape
            cands[i] = scipy.reshape(cands[i], (csh[0], csh[1], 1))
    resizedCands = placer.resizeTiles(scipy.array(cands))
    ID, best_pos, bestCorr = placer.compare(resizedTarget, resizedCands)
    cand = cands[ID]
    idx = best_pos
    
    result = scipy.zeros((75,75,3))
    result[idx[0]:idx[0]+50, idx[1]:idx[1]+50] = target
    Image.fromarray(scipy.uint8(result)).show()
    Image.fromarray(scipy.uint8(cand)).show()


#placer = CorrelationPlacer()
placer = MinDistPlacer()
placer.listenForParameters()

# test_img_reconstr(placer)
# test_compare_two(placer)
# test_compare_single(placer)
test_compare_many(placer, "./eye.jpg", 100)
