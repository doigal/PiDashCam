#! /usr/bin/python
# _______ __  ______               __     _______                
# |   _   |__||   _  \ .---.-.-----|  |--.|   _   .---.-.--------.
# |.  1   |  ||.  |   \|  _  |__ --|     ||.  1___|  _  |        |
# |.  ____|__||.  |    |___._|_____|__|__||.  |___|___._|__|__|__|
# |:  |       |:  1    /                  |:  1   |               
# |::.|       |::.. . /                   |::.. . |               
# `---'       `------'                    `-------'               
#
# Created by Lachlan Doig, September 2016.
#
# A Project to use a Raspberry Pi Zero (or any other Raspberry Pi 
#  that works with serial GPS) as a time lapse style dash cam with GPS
#  logging as well.
# 
# A single Neopixel is used for statusing. A long press (2s) of the shutdown 
#  button will safely shut the Pi down.
#
# 3D printed case can be found here:
#  !!!!! linko thingiverse
#
# STRONGLY recommended to check gpsd manually first. If there are permission
#   errors on the serial port, check /boot/cmdline.txt to make sure there are 
#   no references to the ttyAMA0 or any alias.
#
## With thanks to:
# https://github.com/karlexceed/PicturesAndPlaces/blob/master/gpstime.py
# http://exceedindustries.net/?q=projects/picturesandplaces
# http://www.danmandle.com/blog/getting-gpsd-to-work-with-python/
# https://github.com/pimoroni/internet-of-seeds/blob/master/internet-of-seeds.py
# https://learn.adafruit.com/raspberry-pi-wearable-time-lapse-camera/using-it?view=all
# https://github.com/RPi-Distro/python-gpiozero/blob/master/docs/examples/button_shutdown.py

# All depenencies can be installed with
# sudo apt-get install python-gpiozero gpsd gpsd-clients python-gps python-picamera build-essential python-dev git scons swig
# 

#Future Work:
# Video mode select switch
# Auto upload?
# Better GPX handling


# Import Frameworks & Libaries
import os
import datetime
import time
import shutil
import threading
from picamera import PiCamera
from gpiozero import Button
from neopixel import *
from gps import *

#import PIL
#from PIL import Image, ImageFont, ImageDraw

## GENERAL CONFIG
time_interval = 2              #Time between pictures in seconds. Not exact.
camera_res = (1280, 720)       #Resolution to take photos at
pin_Shutdown = 4               #Pin that shutdown switch is connected to

# LED strip configuration:
LED_COUNT      = 1       # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)


###########################################################################################
###                                   GPS FUNCTIONS                                     ###
###########################################################################################
class GpsPoller(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		global gpsd		        # Bring it in scope
		gpsd = gps(mode=WATCH_ENABLE)	# Starting the stream of info
		self.current_value = None
		self.running = True	        # Setting the thread running to true

	def run(self):
		global gpsd
		while gpsp.running:
			gpsd.next()	        # This will continue to loop and grab EACH set of gpsd info to clear the buffer	


def GpsSetTime():
#set pi clock with UTC 2013-03-16T00:37:55.000Z -> 16 MAR 2013 00:37:55
   if gpsd.utc != None and gpsd.utc != '':
      gpstime = gpsd.utc[0:4] + gpsd.utc[5:7] + gpsd.utc[8:10] + ' ' + gpsd.utc[11:13] + gpsd.utc[13:19]
      print 'Setting system time to GPS time...'
      # added -u to set clock to UTC time and not effect the timezone
      os.system('sudo date -u --set="%s"' % gpstime)
	
###########################################################################################
###                                  IMAGE FUNCTIONS                                    ###
###########################################################################################	
## Captures an image and copies to latest.jpg. 
## Needs to be passed a datetime object for the timestamped image, t.
def capture_image(t):
  ts = t.strftime('%Y-%m-%d-%H-%M-%S')
  filename = '/home/pi/DashCam/RawPhotos/image-' + ts + '.jpg'
  camera.capture('/home/pi/DashCam/RawPhotos/latest.jpg')
  shutil.copy2('/home/pi/DashCam/RawPhotos/latest.jpg',filename)
  print "Taken image at " + filename
  return filename
  
## Takes the latest.jpg and stamps the data on  
## Needs to be passed datetime object and GPS values dictionary
def timestamp_image(t, gpsdatavals):
  ts_read = t.strftime('%H:%M, %a. %d %b %Y')
  img = Image.open('/home/pi/DashCam/RawPhotos/latest.jpg')
  draw = ImageDraw.Draw(img)
  font = ImageFont.truetype('/home/pi/coding/DashCam/Roboto-Regular.ttf', 16)

  draw.text((10, 10), ts_read, (255, 255, 255), font=font)
  draw.text((10, 50), 'Lat: {0:.4f}, Long: {0:.4f}, Alt: {0:.0f}m, Spd: {0:.1f}kph, Hdg'.format(gpsdatavals['lat'],gpsdatavals['lon'],gpsdatavals['alt']), (255, 255, 255), font=font)

  img.save('/home/pi/DashCam/RawPhotos/latest_ts.jpg')
  filename = '/home/pi/DashCam/RawPhotos/ts_image-' + t.strftime('%Y-%m-%d-%H-%M') + '.jpg'
  shutil.copy2('/home/pi/DashCam/RawPhotos/latest_ts.jpg',filename)
  
  return filename

###########################################################################################
###                                        NEOPIX                                       ###
###########################################################################################	 
def colorWipe(strip, color, wait_ms=50):
	"""Wipe color across display a pixel at a time."""
	for i in range(strip.numPixels()):
		strip.setPixelColor(i, color)
		strip.show()
		time.sleep(wait_ms/1000.0)
	
def blink(strip, color, blink_ms, bright=LED_BRIGHTNESS):
	strip.setBrightness(bright)
	colorWipe(strip,color,blink_ms)
	colorWipe(strip,Color(0, 0, 0),blink_ms)
		
def fader(strip, color, startbright=0, endbright=255, iterations=255, fade_ms=250):		
    deltabright = endbright-startbright
    for i in range(iterations):
        currbright = int(float(i)/float(iterations)*deltabright)+startbright
        strip.setBrightness(currbright)
        colorWipe(strip,color,0)
        pausetime=(float(1)/float(iterations)*fade_ms)/float(1000)
        time.sleep(pausetime)		

def pulser(strip,color,bright,total_ms):
    fader(strip,color,0,bright,32,total_ms/2)
    fader(strip,color,bright,0,32,total_ms/2)
    colorWipe(strip, Color(0, 0, 0))


###########################################################################################
###                                        SYSTEM                                       ###
###########################################################################################
def checkinternets():
   #Function to check if an internet connection is up
   #Presumtion being that internet means time sync
   #No internet means that GPS time will be used instead
   
   #Ping Google
   hostname = "google.com" #example
   response = os.system("ping -c 1 " + hostname)
   #and then check the response...
   
   if response == 0:
     print hostname + ' is up!'
   else:
     print hostname + ' is down!'


def CleanClose():
   #Closes all the threads cleanly and shuts GPXlogger now
   #Flash orange 2 times
   print "\nKilling Thread..."
   gpsp.running = False	# Kill it!
   gpsp.join()		# Wait for the thread to finish
   print "Threads closed."
   os.system("sudo pkill gpxlogger") 
   print "gpxlogger closed cleanly"
   
	 
def ShuttingDown():
   CleanClose() 
   print "\nShutting down"
   #Flash medium red 5 times and hold
   blink(LED_Pix,Color(0,255,0),250,255)
   blink(LED_Pix,Color(0,255,0),250,255) 
   blink(LED_Pix,Color(0,255,0),250,255)
   blink(LED_Pix,Color(0,255,0),250,255)
   blink(LED_Pix,Color(0,255,0),250,255)
   colorWipe(LED_Pix, Color(0, 255, 0))
   time.sleep(2)
   os.system("sudo shutdown now")

###########################################################################################
###                                         MAIN                                        ###
###########################################################################################	 
#
os.system('clear')

#Initialise Neopixel
LED_Pix = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)
LED_Pix.begin()

#blink white twice
blink(LED_Pix,Color(255,255,255),250,255)
blink(LED_Pix,Color(255,255,255),250,255)


#Start GPSD 
print "Starting GPS"
os.system("sudo killall gpsd")
os.system("sudo rm /var/run/gpsd.sock")
os.system("sudo gpsd /dev/ttyAMA0 -F /var/run/gpsd.sock")

#Start GPS thread & GPX Logger
gpsp = GpsPoller()	# Create the thread
gpsp.start()	    # Start it up

print "Starting GPS Logger"
t = datetime.datetime.now()
os.system("sudo gpxlogger -d -f /home/pi/DashCam/TripLogs/trip_log_" + t.strftime('%Y-%m-%d-%H-%M') + ".gpx -m 25 -i 60") # GPX logger

#Check for IP. If an IP is present, then NTP time is presumed.
#Otherwise the time must come from the GPS signal
print "Checking for internet (and NTP)"
internetstatus = checkinternets()
if internetstatus == False:
   print 'NTP link not confirmed. Attempting to use GPS for time sync'
   GpsSetTime()
   print 'System Clock:  ' + t.strftime('%Y-%m-%d-%H-%M')
   print 'GPS UTC Clock: ' + gpsd.utc
else:
   print 'Assumed NTP link.'
   print 'System Clock:  ' + t.strftime('%Y-%m-%d-%H-%M')
   print 'GPS UTC Clock: ' + gpsd.utc
   
#Initialise Shutdown Switch
shutdown_btn = Button(pin_Shutdown, hold_time=2)
shutdown_btn.when_held = ShuttingDown  

#Initialise Camera
print "Initalising Camera"
camera = PiCamera()
camera.resolution = camera_res
camera.vflip = True
camera.hflip = True
#camera.led = False
time.sleep(1) # gives is all a second or two to stabalise before recording
#blink purple once
blink(LED_Pix,Color(0,255,255),500,255)

startstatus = True

try: 
  while True:
    # It may take a second or two to get good data
    if gpsd.fix.mode == 1:
      #Pulse Red Med
      pulser(LED_Pix,Color(0,255,0),80,500)	  
      startstatus = True
      time.sleep(1)

    if gpsd.fix.mode >= 2:
      if startstatus:
         print('GPS locked!')
         #blink blue 3 times to indicate GPS lock
         pulser(LED_Pix,Color(0,0,255),100,250)
         pulser(LED_Pix,Color(0,0,255),100,250)
         pulser(LED_Pix,Color(0,0,255),100,250)
         GpsSetTime() 
         startstatus = False
      
      #Gathers the GPS data, currently dosnt do much with this.
      gpsdata = {}
      gpsdata['lat'] = gpsd.fix.latitude
      gpsdata['lon'] = gpsd.fix.longitude
      gpsdata['alt'] = gpsd.fix.altitude
      gpsdata['spd'] = gpsd.fix.speed
      gpsdata['clm'] = gpsd.fix.climb
      gpsdata['trk'] = gpsd.fix.track
      
      t = datetime.datetime.now()
      img = capture_image(t)
      #latest = timestamp_image(t,gpsdata)
	  
	  #pulse LED green softly (25% bright)
      pulser(LED_Pix,Color(255,0,0),40,250)
      time.sleep(time_interval)
      
except (KeyboardInterrupt, SystemExit):	# When you press ctrl+c
  CleanClose()