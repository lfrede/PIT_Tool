import cv2
from tkinter import *
from PIL import ImageTk, Image, ImageOps
import random
import threading
import queue
import math
import numpy as np
import sys


class VideoPlayer:
    def __init__(self, window, video_source, width, height, alpha, debug):
        self.window = window
        self.video_source = video_source
        self.width = width
        self.height = height
        self.debug = debug
        self.alpha = alpha

        # Setting up the canvas (thread2)
        self.initThread2()
        # Starting up OpenCV (thread1) and starting up the threads
        self.initThread1()

    # Function to generate our frame references from pictures
    def callPicture(self, name, color, t=0, b=100, l=0, r=100):
        pic = cv2.imread(name)
        # Upscaling to match the source
        pic = cv2.resize(pic, (width, height), interpolation=cv2.INTER_LANCZOS4)
        # Changing brighness to match the source
        pic = cv2.convertScaleAbs(pic, alpha=self.alpha, beta=0)
        # Optional : Croping
        pic = pic[int(t / 100.0 * self.height):int(b / 100.0 * self.height), int(l / 100.0 * self.width):int(r / 100.0 * self.width), :]
        # Optional : Changing color
        pic = cv2.cvtColor(pic, color)
        return pic

    # THREAD 1
    # Capture card reader
    def initThread1(self):

        # Open the video source
        self.video_capture = cv2.VideoCapture(self.video_source)

        if not self.video_capture.isOpened():
            print("Cannot read capture card")
        else:
            print("Capture card is fine")

        # Create a queue to hold captured images
        self.image_queue = queue.Queue()

        # Start the thread to read the video
        self.thread = threading.Thread(target=self.read, args=())
        self.thread.daemon = True
        self.thread.start()

        # Start the thread to display the layout
        self.display_thread = threading.Thread(target=self.display, args=())
        self.display_thread.daemon = True
        self.display_thread.start()

        # Start the main loop
        self.window.mainloop()


    # THREAD 2
    # Tkinter, layout generation
    def initThread2(self):

        ################################
        # Loading pictures for the layout

        # Generatin layout
        self.window.title("PIT Layout")
        self.PITLayout = ImageTk.PhotoImage(Image.open("Frames/Background.png"))
        self.Mover = ImageTk.PhotoImage(Image.open("Frames/Mover.png"))
        self.PITLayoutSize = Image.open("Frames/Background.png").size

        self.canvas = Canvas(self.window, width=self.PITLayoutSize[0], height=self.PITLayoutSize[1])
        #self.canvas = Canvas(self.window, width=720, height=480)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=NW, image=self.PITLayout)

        # Generating layout pictures
        self.etageTK = []
        for i in range(10):
            currentPicture = Image.open("Frames/{}.png".format(i))
            pictureResized = currentPicture.resize((currentPicture.width * 3, currentPicture.height * 3))
            currentTK = ImageTk.PhotoImage(pictureResized)
            self.etageTK.append(currentTK)  # Ajoute la sous-liste remplie à la liste principale

        self.tabMovers = []

        self.charteTK = []
        for i in range(11):
            currentTK = ImageTk.PhotoImage(Image.open("Frames/Stages{}.png".format(i)))
            self.charteTK.append(currentTK)  # ajoute la sous-liste remplie à la liste principale

        self.moverTK = []
        self.moverTK.append(ImageTk.PhotoImage(Image.open("Frames/Mover.png")))
        self.moverTK.append(ImageTk.PhotoImage(ImageOps.mirror(Image.open("Frames/Mover.png"))))

        self.nbMovers = 0
        self.currentStage = 0


        ##########################
        # Loading frame references

        # Image comparison for the PIT
        self.PITFrame = self.callPicture("Frames/EnterPIT.png", cv2.COLOR_BGR2GRAY)

        # for stages
        self.STG1 = self.callPicture("Frames/NextStage1.png", cv2.COLOR_BGR2GRAY)
        self.STG2 = self.callPicture("Frames/NextStage2.png", cv2.COLOR_BGR2GRAY)
        self.STG3 = self.callPicture("Frames/NextStage3.png", cv2.COLOR_BGR2GRAY)
        self.STG4 = self.callPicture("Frames/NextStage4.png", cv2.COLOR_BGR2GRAY)

        # Frames of reference for Tier rooms with / wo charlie
        self.TierGrayFrame = self.callPicture("Frames/Tier.png", cv2.COLOR_BGR2GRAY)
        self.TierChGrayFrame = self.callPicture("Frames/TierCharlie.png", cv2.COLOR_BGR2GRAY)

        # Rideau
        self.GrayCurtain = self.callPicture("Frames/Rideau.png", cv2.COLOR_BGR2GRAY)
        # Black Frame
        self.GrayBFrame = self.callPicture("Frames/Blackframe.png", cv2.COLOR_BGR2GRAY)

        # Pounies
        # Frame reference presence pounie a l'étage superieur
        self.Pounies = self.callPicture("Frames/Pounies.png", cv2.COLOR_BGR2GRAY, t=64, b=72, l=17, r=22)

        # Tier : Crop on Charlieton
        self.charlietonGray = self.callPicture("Frames/TierStage.png", cv2.COLOR_BGR2GRAY, t=54, b=73, l=74, r=88)
        self.chestGray = self.callPicture("Frames/TierStage.png", cv2.COLOR_BGR2GRAY, t=37, b=58, l=42, r=57)

        # Variable that track player pounies choices
        self.pouniesChoice = 0
        self.isChoiceMade = False
        # Charlieton tracker
        self.isCharlieton = False
        # Chest tracker
        self.isChest = False
        # Pounies tracker
        self.currentMover = False
        # Pipe tracker pounies rooms
        self.pipeTaken = False

        # Variables that track sequences of the game (Bein in the pit, in a fight, with a pounie, ...)
        self.isBaseLayout = False
        self.PitRoom = False
        self.isInPIT = False
        #self.sequences = ["EndPipe", "BeginFight", "EndFight", "Pounies"]
        self.sequence = ""

        # Black pixel count for pounies
        self.pLcount = 0
        self.pCcount = 0


        self.canvas.update()


    # THREAD 1
    # Capture card reader
    def read(self):
        while True:
            # Capture an image from the video source
            # ret : Boolean set to true if a frame has been captured
            # frame : numpy.ndarray object wich is a pixel array of actual the frame
            ret, frame = self.video_capture.read()

            if ret:
                # Add the image to the queue
                self.image_queue.put(frame)


    # THREAD 2
    # Tkinter, layout generation
    def display(self):

        ########### TESTS ##################
        self.isBaseLayout = False
        self.isInPIT = True
        self.sequence = "NextStage"
        self.currentStage = 1
        ####################################

        while True:

            ######################
            ## Frame Processing ##
            ######################

            # Get an image from the queue
            self.currentFrame = self.image_queue.get()
            if self.sequence != "Pounies":
                self.currentGrayFrame = cv2.cvtColor(self.currentFrame, cv2.COLOR_BGR2GRAY)

            # We detect if player is about to enter pit
            if not self.PitRoom:

                # Frames comparisons via MSE method (Mean Squared Error)
                mse = ((self.currentGrayFrame - self.PITFrame) ** 2).mean()
                print("Not in PIT : ", mse) if self.debug == True else None

                if mse < 40:
                    self.PitRoom = True
                    print("In pit room.") if self.debug == True else None

            ######################
            ## ENTERING STAGE 1 ##
            ######################

            # Then we detect if Mario is entering the pipe
            if self.PitRoom:
                # First pipe handled differently because different from the ones on the pit
                mse1 = ((self.currentGrayFrame - self.STG1) ** 2).mean()
                mse2 = ((self.currentGrayFrame - self.STG2) ** 2).mean()
                print("Takin pipe ? MSE1:", mse1, "MSE2: ", mse2) if self.debug == True else None
                if mse1 < 60 or mse2 < 60:
                    self.currentStage = 1
                    self.display_updateLayout()
                    self.sequence = "NextStage"
                    self.isInPIT = True
                    # We stop checking for PIT
                    self.PitRoom = False
                    print("In PIT Stage 1") if self.debug == True else None

            # We now start tracking the PIT
            if self.isInPIT:
                ## SETUP LAYOUT one time when entering PIT
                if not self.isBaseLayout:
                    self.display_baseLayout()


                ############################################
                ############################################
                ################## STATES ##################
                ############################################
                ############################################

                # In the PIT the script track the current state of the game, when we enter a level, a fight, or get a mover
                print(self.sequence) if self.debug == True else None

                #################
                ## NEXT STAGE  ##
                if self.sequence == "NextStage":
                    # Three possible events
                    # A mover : t=64, b=72, l=17, r=22
                    currentFrame = self.currentFrame[int(64 / 100.0 * self.height):int(72 / 100.0 * self.height), int(17 / 100.0 * self.width):int(22 / 100.0 * self.width), :]
                    currentFrame = cv2.cvtColor(currentFrame, cv2.COLOR_BGR2GRAY)
                    PouniesMSE = ((currentFrame - self.Pounies) ** 2).mean()
                    print("Pounie MSE:", PouniesMSE) if self.debug == True else None
                    if PouniesMSE < 40:
                        self.sequence = "Pounies"
                    # Rideau signifiant début de combat
                    CurtainMSE = ((self.currentGrayFrame - self.GrayCurtain) ** 2).mean()
                    print("Curtain MSE:", CurtainMSE) if self.debug == True else None
                    if CurtainMSE < 40:
                        self.sequence = "Fight"


                ################
                ## NEXT TIER  ##
                if self.sequence == "NextTier":

                    # A tier room is where reside charlieton and the chest

                    # Waitin for room to be fully generated before comparing :
                    if not self.isChest:
                        # By tracking the chest
                        currentFrameChest = self.currentFrame[int(37 / 100.0 * self.height):int(58 / 100.0 * self.height), int(42 / 100.0 * self.width):int(57 / 100.0 * self.width), :]
                        currentFrameChest = cv2.cvtColor(currentFrameChest, cv2.COLOR_BGR2GRAY)
                        ChestMSE = ((currentFrameChest - self.chestGray) ** 2).mean()
                        print("Is chest ? :", ChestMSE) if self.debug == True else None
                        if ChestMSE < 30:
                            print("CHEST") if self.debug == True else None
                            #Now we stop tracking chest
                            self.isChest = True
                        # Charlieton track for futures updates:
                        currentFrameCharlie = self.currentFrame[int(54 / 100.0 * self.height):int(73 / 100.0 * self.height), int(74 / 100.0 * self.width):int(88 / 100.0 * self.width), :]
                        currentFrameCharlie = cv2.cvtColor(currentFrameCharlie, cv2.COLOR_BGR2GRAY)
                        CharlietonMSE = ((currentFrameCharlie - self.charlietonGray) ** 2).mean()
                        print("Is charlie  ?:", CharlietonMSE) if self.debug == True else None
                        if CharlietonMSE < 50:
                            self.isCharlieton = True
                            print("CHARLI") if self.debug == True else None
                            # For future update
                            # self.display_updateLayout()

                    # PIPE

                    # Comparison starting when the room is fully loaded (meaning we see the chest correctly)
                        # We do so because the code could match a pipe entering when mario enter the tier room by leaving the ceiling pipe
                        # Or we want to trigger the next sequence only when mario leave the tier room
                    # We look for Mario entering the pipe (leaving the room),
                    # Two possible comparisons for more precisions, with and without charlie

                    # For now if no movers we monitor pipe this way
                    if self.isChest == True and self.currentMover == False:
                        if self.isCharlieton == True:
                            mse = ((self.currentGrayFrame - self.TierChGrayFrame) ** 2).mean()
                            print("Charlie PIPE", mse) if self.debug == True else None
                        else:
                            mse = ((self.currentGrayFrame - self.TierGrayFrame) ** 2).mean()
                            print("No Charlie PIPE", mse) if self.debug == True else None

                        if mse < 20:
                            print("PIPE CHOOSEN") if self.debug == True else None
                            self.currentStage = self.currentStage + 1
                            self.display_updateLayout()
                            self.sequence = "NextStage"
                            self.isChoiceMade = False
                            self.isCharlieton = False
                            self.isChest = False
                            self.currentMover = False


                    # MOVER
                    # We look for the presence of a pounie, we stop tracking if we found one
                    if not self.currentMover:
                        currentFramePounies = self.currentFrame[int(64 / 100.0 * self.height):int(72 / 100.0 * self.height), int(17 / 100.0 * self.width):int(22 / 100.0 * self.width), :]
                        currentFramePounies = cv2.cvtColor(currentFramePounies, cv2.COLOR_BGR2GRAY)
                        PouniesMSE = ((currentFramePounies - self.Pounies) ** 2).mean()
                        print("Is pounie ? :", PouniesMSE) if self.debug == True else None
                        # If mover,
                        if PouniesMSE < 20:
                            print("Pounies here") if self.debug == True else None
                            self.currentMover = True

                    #If we found a pounie, we track player choice and pipe entrance in a specific way (fastest method implemented lately)
                    if self.isChest == True and self.currentMover == True:
                        print("GO TO Pounies") if self.debug == True else None
                        self.sequence = "Pounies"

                ###########
                ##POUNIES##
                if self.sequence == "Pounies":

                    # Check for hand white pixel
                    # We need the closest coordinate casted in integer
                    pixel2 = self.currentFrame[int(round((48.958 * self.height) / 100)),
                             int(round((13.055 * self.width) / 100)), :]

                    pixel5 = self.currentFrame[int(round((55.625 * self.height) / 100)),
                             int(round((13.055 * self.width) / 100)), :]

                    # Check also for text box pixel to prevent maching white hand pixel with pounie/menu
                    pixelTB = self.currentFrame[int(round((5 * self.height) / 100)), int(round((32 * self.width) / 100)), :]

                    if np.mean(pixel2) > 196 and np.mean(pixelTB) > 230:
                        print("Choosing 2") if self.debug == True else None
                        self.pouniesChoice = 2
                        self.isChoiceMade = True

                    if np.mean(pixel5) > 196 and np.mean(pixelTB) > 230:
                        print("Choosing 5") if self.debug == True else None
                        self.pouniesChoice = 5
                        self.isChoiceMade = True

                    # Pour chacun compter de black frame à la suite
                    # Si lorsque les deux le sont depuis + de 4 frames et qu'il y a un diff de plus de deux frames d'écard alors c'est PIPE sinon c'est POUNIE

                    pixelUp = self.currentFrame[int(round((10.625 * self.height) / 100)),
                                int(round((50 * self.width) / 100)), :]
                    pixelCenter = self.currentFrame[int(round((59.583 * self.height) / 100)),
                                  int(round((50.555 * self.width) / 100)), :]

                    if np.mean(pixelUp) == 0:
                        self.pLcount = self.pLcount + 1
                    else:
                        self.pLcount = 0

                    if np.mean(pixelCenter) == 0:
                        self.pCcount = self.pCcount + 1
                    else:
                        self.pCcount = 0

                    if self.pCcount > 4 and self.pLcount > 4:
                        print("##############") if self.debug == True else None
                        print("## 4 FRAMES ##") if self.debug == True else None
                        print("##############") if self.debug == True else None
                        # PIPE
                        if abs(self.pLcount - self.pCcount) > 6:
                            self.currentStage = self.currentStage + 1
                            print("###  PIPE  ###") if self.debug == True else None

                        # POUNIES
                        else:
                            self.nbMovers = self.nbMovers + 1
                            if self.isChoiceMade:
                                print("## POUNIE ", self.pouniesChoice, " ##") if self.debug == True else None
                                self.currentStage = self.currentStage + self.pouniesChoice
                            else:
                                # In the case the program didnt had the time to see the player choice (e.g. sway exec is too fast), we will have to guess the player choice
                                print("Guessing the choice") if self.debug == True else None
                                self.nbMovers = self.nbMovers + 1
                                if self.currentStage in range(16, 18) or self.currentStage in range(46, 48):
                                    # The player is not likely to skip Fire Drive or Strange Sack
                                    self.currentStage = self.currentStage + 2
                                else:
                                    # We do not track coins so we assume the player has enough
                                    self.currentStage = self.currentStage + 5
                        # ANY
                        if self.currentStage % 10 == 0:
                            self.sequence = "NextTier"
                            print("NextTier : ", self.pouniesChoice) if self.debug == True else None
                        else:
                            self.sequence = "NextStage"
                            print("NextStage : ", self.pouniesChoice) if self.debug == True else None
                        self.display_updateLayout()
                        self.isChoiceMade = False
                        self.isCharlieton = False
                        self.isChest = False
                        self.currentMover = False
                        self.pLcount = 0
                        self.pCcount = 0

                ###########
                ## FIGHT ##
                if self.sequence == "Fight":
                    #Comparaison black frames, signifiant fin de combat
                    bframeMSE = ((self.currentGrayFrame - self.GrayBFrame) ** 2).mean()
                    print("black frame ?", bframeMSE) if self.debug == True else None
                    if bframeMSE < 2:
                        self.sequence = "Pipe"
                        print("Waiting for pipe") if self.debug == True else None



                ###########
                ## PIPE  ##
                if self.sequence == "Pipe":
                    mse3 = ((self.currentGrayFrame - self.STG3) ** 2).mean()
                    mse4 = ((self.currentGrayFrame - self.STG4) ** 2).mean()
                    print("MSE4", mse4, "MSE3", mse3)
                    if mse3 < 60 or mse4 < 60:
                        print("MSE1", mse3)
                        print("MSE2", mse4)
                        self.currentStage = self.currentStage + 1
                        self.display_updateLayout()
                        if self.currentStage % 10 == 0:
                            self.sequence = "NextTier"
                            print("NextTier")
                        else:
                            self.sequence = "NextStage"
                            print("NextStage")
                    #rideau signifiant début de combat
                    CurtainMSE = ((self.currentGrayFrame - self.GrayCurtain) ** 2).mean()
                    if CurtainMSE < 20:
                        self.sequence = "Fight"
                        print("Fight")





    def display_baseLayout(self):
        self.currentStage = 1
        self.isBaseLayout = True
        self.canvas.create_image(410, 150, image=self.charteTK[0], tags="pallierTag")
        self.canvas.create_image(150, 174, image=self.etageTK[0], tag="uniteTag")
        self.canvas.update()


        ##TEST
        self.currentStage = 1
        #self.display_updateLayout()


    def display_updateLayout(self):

        # UPDATE DES INFORMATIONS DANS LE LAYOUT
        # In this function i load a font depending on the value of the incremented var
        dizaine = math.floor(self.currentStage // 10)

        if self.nbMovers > 0:
            for i in range(self.nbMovers):
                currentMover = self.canvas.find_withtag("Mover{}".format(i))
                if not currentMover:
                    # Creating Mover
                    # Adding gone because its shifted by one
                    horizontalCoord = random.randint(0, 27) * 20 + 1
                    verticalCoord = random.randint(0, 3) * 20 + 275 + 1
                    moverTKFacing = random.choice(self.moverTK)
                    self.canvas.create_image(horizontalCoord, verticalCoord, image=moverTKFacing,
                                             tags="Mover{}".format(i), anchor="nw")
                    self.tabMovers.append(moverTKFacing)
                else:
                    self.canvas.itemconfigure(currentMover, image=self.tabMovers[i])

        if self.currentStage < 100:
            # STAGES 1-99
            unite = math.floor(self.currentStage % 10)
            etageC = self.canvas.find_withtag("uniteTag")
            self.canvas.itemconfigure(etageC, image=self.etageTK[unite])

            if dizaine > 0 and dizaine < 10:
                pallierC = self.canvas.find_withtag("dizaineTag")
                if not pallierC:
                    self.canvas.create_image(100, 174, image=self.etageTK[dizaine], tags="dizaineTag")
                else:
                    self.canvas.itemconfigure(pallierC, image=self.etageTK[dizaine])

            if dizaine < 10:
                charteC = self.canvas.find_withtag("pallierTag")
                self.canvas.itemconfigure(charteC, image=self.charteTK[dizaine])

        else:
            # BONETAIL
            etageC = self.canvas.find_withtag("uniteTag")
            pallierC = self.canvas.find_withtag("dizaineTag")
            charteC = self.canvas.find_withtag("pallierTag")
            self.canvas.itemconfigure(etageC, image=self.etageTK[0])
            self.canvas.itemconfigure(pallierC, image=self.etageTK[0])
            self.canvas.itemconfigure(charteC, image=self.charteTK[10])

        #if self.isCharlieton == True:
            # Add Charlie to the layout

        self.canvas.update()



def which_video_source():
    print('Hello') if debug == True else None

    # Testing each potential video sources, player must be in saves menu on main menu or start menu (mario tab) in game
    for i in range(10):
        cap = cv2.VideoCapture(i)

        #If not a video source, we skip this occurrence
        if not cap.isOpened():
            continue

        # H/W of the current source
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Load frames reference (saves screen on the menu or start menu in game).

        # Scaling to match the source
        saves = cv2.resize(cv2.imread("Saves.png"), (width, height), interpolation=cv2.INTER_LANCZOS4)
        # Crop to compare a static part (image[top:bottom left:right])
        saves = saves[0:int(8 / 100.0 * height), 0:width]
        cv2.imwrite("testSave.png", saves) if debug == True else None

        start = cv2.resize(cv2.imread("Start.png"), (width, height), interpolation=cv2.INTER_LANCZOS4)
        start = start[int(53 / 100.0 * height):int(74 / 100.0 * height), int(23 / 100.0 * width):int(28 / 100.0 * width)]
        cv2.imwrite("testStart.png", start) if debug == True else None

        # Load source frames
        ret, frame = cap.read()
        frameSaves = frame[0:int(8 / 100.0 * height), 0:width]
        frameStart = frame[int(53 / 100.0 * height):int(74 / 100.0 * height), int(23 / 100.0 * width):int(28 / 100.0 * width)]

        cv2.imwrite("testFrameSaves.png", frameSaves) if debug == True else None
        cv2.imwrite("testFrameStart.png", frameStart) if debug == True else None

        # Make the reference frames match the brighness of the source
        # Because it can differ based on the capture card decoder, we record it to update futures frames references
        # Otherwise MSE lead to a huge diff even with low brighness diff

        # Gray means of the picture
        meanSaveFrame = cv2.mean(cv2.cvtColor(frameSaves, cv2.COLOR_BGR2GRAY))[0]
        meanSave = cv2.mean(cv2.cvtColor(saves, cv2.COLOR_BGR2GRAY))[0]
        # Getting the ratio of brightness
        alphaSave = meanSaveFrame / meanSave

        meanStartFrame = cv2.mean(cv2.cvtColor(frameStart, cv2.COLOR_BGR2GRAY))[0]
        meanStart = cv2.mean(cv2.cvtColor(start, cv2.COLOR_BGR2GRAY))[0]
        alphaStart = meanStartFrame / meanStart

        # Changing brighness
        saves = cv2.convertScaleAbs(saves, alpha=alphaSave, beta=0)
        start = cv2.convertScaleAbs(start, alpha=alphaStart, beta=0)

        # MSE Diff
        mseStart = ((frameStart - start) ** 2).mean()
        mseSaves = ((frameSaves - saves) ** 2).mean()

        print("Saves:", mseSaves, "Start :", mseStart) if debug == True else None

        # If it return 0.0 its because of a null array (0**2=0)
        if mseSaves < 40 and mseSaves != 0.0:
            return i, width, height, alphaSave
        elif mseStart < 40 and mseStart != 0.0:
            return i, width, height, alphaStart

    print("No capture found")
    return -1

# Fonction Main called at the beginning of the script
if __name__ == '__main__':

    try:
        if sys.argv[1]:
            debug = True
    except:
        debug = False

    debug = True
    index, width, height, alpha = which_video_source()
    if index == -1:
        print("Cannot match, verify you are either on the saves screen on the main menu or the START menu (Mario page) in game") if debug == True else None
        exit(0)

    print(index, width, height, alpha) if debug == True else None

    #Window creation
    window = Tk()

    # Create the video player
    player = VideoPlayer(window, index, width, height, alpha, debug)

    # Release the video source
    player.video_capture.release()


