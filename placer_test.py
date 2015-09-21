from placer import *
import scipy, Image, os

## Try converting an image to an array and back
def test_img_reconstr(placer):
    img_obj = Image.open("Matilda.JPG")
    img = scipy.array(img_obj)
    img_obj.show()
    
    data = placer.pack(img, 0)
    img_r = placer.unpack(data, img.shape)[1]
    img_recon = Image.fromarray(scipy.uint8(img_r))
    img_recon.show()

def test_compare_single(placer):
    tile = scipy.array(Image.open("./eye.jpg"))
    expanded = scipy.zeros((75,75,3))
    pos = (8, 12)
    expanded[pos[0]:pos[0]+50, pos[1]:pos[1]+50] = tile
    
    ID, best_pos, bestCorr = placer.compare(tile, {0 : expanded})
    if (pos == best_pos):
        print "tile correctly discovered"
        return True
    else:
        print "ERROR: Tile was not correctly discovered!"
        return False
    
def test_compare_two(placer):
    tile = scipy.array(Image.open("./eye.jpg"))
    cand = scipy.array(Image.open("./imgs0/img_0gxHKNvoka.jpg"))
    ID, best_pos, bestCorr = placer.compare(tile, {0 : cand})
    idx = best_pos
    
    result = scipy.zeros(cand.shape)
    result[idx[0]:idx[0]+50, idx[1]:idx[1]+50] = tile
    Image.fromarray(scipy.uint8(result)).show()
    Image.fromarray(scipy.uint8(cand)).show()

def test_compare_many(placer, target_fn, cnt):
    target = scipy.array(Image.open(target_fn))
    
    cand_names = os.listdir("./imgs0/")
    cands = {}
    for i in range(cnt):
        cands[i] = scipy.array(Image.open("./imgs0/" + cand_names[i]))
        if (cands[i].ndim == 2):
            csh = cands[i].shape
            cands[i] = scipy.reshape(cands[i], (csh[0], csh[1], 1))
        
    ID, best_pos, bestCorr = placer.compare(target, cands)
    cand = cands[ID]
    idx = best_pos
    
    result = scipy.zeros(cand.shape)
    result[idx[0]:idx[0]+50, idx[1]:idx[1]+50] = target
    Image.fromarray(scipy.uint8(result)).show()
    Image.fromarray(scipy.uint8(cand)).show()

    
placer = TestPlacer()
#test_img_reconstr(placer)
# test_compare_two(placer)
# test_compare_single(placer)
test_compare_many(placer, "./eye.jpg", 500)
