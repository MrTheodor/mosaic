from mpi4py import MPI
import plogger
from PIL import Image
from skimage import color
import scipy
import sys, os, shutil
import photo_match_labimg as photo_match
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import time

execfile('./params.par')

def process(pars, data=None):   
        
#%% load the parameters that CAN be specified from the command line
    NPlacers = pars['NPlacers']
    NScrapers = pars['NScrapers']
    iters = pars['iters']
    MaxTilesVert = pars['MaxTilesVert']
    per_page = pars['per_page']
    fidelity = pars['fidelity']
    poolSize = pars['poolSize']

    if (data != None):
        tags = data['search'].split(', ')
    else:
        #tags = ('Minimalism',)
        tags = ('Face','Leuven','Belgium','Computer')
        #tags = ('Bussum','Football','PSV','Minimalism','urbex')
    
#%% MPI stuff
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    status = MPI.Status()

#%% initiate plogger   
    #execfile('../mosaic_gui/daemon/params.par')
    logger = plogger.PLogger(rank, host_url=LOGGER_HOST)

#%% print the values of those parameters that CAN be specified via the command line
    #for key, value in pars.iteritems():
        #print "M{}: {} is now {}".format(rank, key, value)

#%% identify oneself
    #print "Master, process {} out of {}".format(rank, size)
    #print "M{}: > init".format(rank) 
    logger.write('Initializing', status=plogger.INIT)

#%% initialize the photo matcher
    pmPars = {'fidelity': fidelity}
    pm = photo_match.photoMatch(pmPars)

    # create empty save-path
    if not pars['useDB']:
        if (os.path.exists(pars['savepath'])):
            shutil.rmtree(pars['savepath'], ignore_errors=True)
        os.mkdir(pars['savepath'])
    
#%% call the scrapers right at the beginning, as it is probably the slowest
    PixPerTile = scipy.array((75,75))
    ComparePixPerTile = scipy.array((fidelity,fidelity))
    scraperPars = {'pm': pm, 'tags': tags, 'PixPerTile': PixPerTile, 'poolSize': poolSize}
    for scraper in range(1,1+NScrapers):
	comm.send(scraperPars, dest=scraper, tag=0)

    TilesVert = int(MaxTilesVert/NPlacers) * NPlacers

    TargetImg = Image.open('./output/doesnotmatter.jpg')
    #TargetImg = Image.open('./Matilda.JPG')
    #TargetImg = Image.open('./rainbow_flag_by_kelly.jpg')
    #TargetImg = Image.open('./korneel_test.jpg')
    TargetSize = TargetImg.size
    TilesHor = (TargetSize[0]*PixPerTile[1]*TilesVert)/(TargetSize[1]*PixPerTile[0])
    Tiles = scipy.array((TilesHor, TilesVert), dtype=int)
    TilesPerNode = scipy.array((TilesHor, TilesVert/NPlacers), dtype=int)
    Pixels        = Tiles*PixPerTile
    ratio = 2.0 / 3.0
    TargetChunkPixels = Tiles*scipy.int_(PixPerTile*ratio)
    ComparePixels = Tiles*scipy.int_(ComparePixPerTile*ratio)
    
#%% adjust the image to have the correct shape (aspect ratio) for turning it into a mosaic
    UnscaledWidth = (TargetSize[1]*Tiles[0])/Tiles[1]# the width of the original size image to yield the correct aspect ratio
    CropMargin = (TargetSize[0] - UnscaledWidth)/2
    #TargetImg.crop((0,0,))
    #TargetImg.resize(Pixels)
    CroppedImg = TargetImg.transform((ComparePixels[0],ComparePixels[1]), Image.EXTENT, (CropMargin,0, CropMargin+UnscaledWidth,TargetImg.size[1]))
    CroppedArr = color.rgb2lab(scipy.array(CroppedImg))

#%% send each placer some parameters
    placerPars = {'TilesPerNode': TilesPerNode, 'UnscaledWidth': UnscaledWidth, 
                  'Tiles': Tiles, 'pm': pm, 'iters': iters, 'PixPerTile': PixPerTile, 'ComparePixPerTile' : ComparePixPerTile}
    for placer in range(NPlacers):
        comm.send(placerPars, dest=1+NScrapers+placer, tag=0)
    #print "M{}: < init".format(rank) 
    
    #print "M{}: > dividing image".format(rank) 
#%% reduce CroppedArr to NPlacers NodeArrs
    NodeArrs = scipy.split(CroppedArr, NPlacers, axis=0) 

#%% send each of the placers its piece of the picture
    for placer in range(NPlacers):
        comm.send(NodeArrs[placer], dest=1+NScrapers+placer, tag=1)

    #%% create the final image and divide it into pieces for the placers to FinalArr = CroppedArr.copy()
    # now the division has to be accurate!
    FinalArr = scipy.zeros((TargetChunkPixels[1], TargetChunkPixels[0], 3), dtype='i')
    # FinalArr = scipy.zeros((Tiles[1]*PixPerTile[1], Tiles[0]*PixPerTile[0], 3), dtype='i')
    NodeFinalArrs = scipy.split(FinalArr, NPlacers, axis=0)
    #print "M{}: < dividing image".format(rank) 
    

#%% listen to the placers' intermediate results
    tempNodeFinalArr = NodeFinalArrs[0].copy() # for receiving the data, before it is known whence it came
    for it in range(iters):
        #print "M{}: > not listening to the placer to scraper broadcast".format(rank) 
        dummy_arrs = scipy.zeros((per_page, PixPerTile[1], PixPerTile[0], 3), dtype=scipy.uint8)
        for scraper in range(1, 1+NScrapers):
            #print "M{}: not listening to scraper {}".format(rank, scraper)
            comm.Bcast(dummy_arrs, root=scraper)
        #print "M{}: < not listening to the placer to scraper broadcast".format(rank) 
        
        #print "M{}: now listening for placer results at iter {} out of {}".format(rank, it, iters)
        #print "M{}: > listening for results".format(rank) 
        logger.write('Listening for placers', status=plogger.RECEIVING)
        for p in range(NPlacers): # listen for the placers
            #print "M{}: NodeFinalArrs[{}] has shape ".format(rank, placer), NodeFinalArrs[placer].shape
            #print "M{}: NodeFinalArrs[{}] has type ".format(rank, placer), type(NodeFinalArrs[placer][0,0,0])
            comm.Recv([tempNodeFinalArr, MPI.INT], source=MPI.ANY_SOURCE, tag=4, status=status)
            placer = status.Get_source()
            NodeFinalArrs[placer-(1+NScrapers)][:,:,:] = tempNodeFinalArr
        #print "M{}: < listening for results".format(rank) 
            
        #print "M{}: > writing image".format(rank) 
        partial_filename = 'output/mosaic_{}.png'.format(it)
        FinalImg = Image.fromarray(scipy.array(FinalArr, dtype=scipy.uint8), 'RGB')
        FinalImg.save(partial_filename) # for fewer output images
        # Notify gui
        logger.emit_partial(partial_filename)
        #print "M{}: < writing image at iter {}".format(rank, it)
    writepars = pars.copy()
    del(writepars['savepath'])

    strrep = '_'.join(['{}{:d}'.format(item, value) for item, value in sorted(writepars.items())])
    final_filename = 'output/final{}_{}.png'.format(strrep, int(time.time()))
    FinalImg.save(final_filename)
    os.chmod(final_filename, 0744)
    print "M{}: Final image saved".format(rank)

    shutil.copy('log', 'output/log_'+strrep)

    # email result
    if (data != None):
        if len(data['email']) > 0:
          try:
            msg = MIMEMultipart()
            msg['Subject'] = "Opendeurdag Faculteit Wetenschappen - uw mozaiek"
            msg['From'] = "SuperPi <superpi@cs.kuleuven.be>"
            msg['To'] = data['email']
            fp = open(final_filename, 'rb')
            img = MIMEImage(fp.read())
            fp.close()
            img.add_header('Content-Disposition', 'attachment; filename="mosaic.jpeg"')
            msg.attach(img)
        
            s = smtplib.SMTP('mail4.cs.kuleuven.be')
            s.sendmail('superpi@cs.kuleuven.be', [msg['To']], msg.as_string())
            s.quit()
          except: pass

        logger.emit_finished(final_filename)
    else:
        print "Data was None. This should not happen."
        logger.emit_finished(final_filename)
    
#%% signal completion
    logger.write('Finished', status=plogger.FINISHED)
    comm.barrier()
    #print "M{}: reached the end of its career".format(rank)
