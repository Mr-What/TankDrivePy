# $Id: TankDrive.py,v 1.3 2022/06/09 15:43:36 aaron Exp aaron $
#
# Main Tank-tread style drive control loop.
#
# Two H-bridge motor drives, on left and right side
#
#      Motor drives take speed commands from -255..255,
#              with negative numbers for reverse.
#      If commands are not updated reguarly, the
#               motors will be commanded to stop.


from machine import UART,Pin,Timer,ADC
from WordParser import WordParser
from FilteredADC import FilteredADC

# In C I had an abstract MotorDrive base class, which was passed around, and you
# instantiated it for the specific driver
# It seems like in uPython, this is overkill.
# As long as your class has all the required methods, it will work.
# You'll get a nice, informative run-time error if a method is missing.
# So, for uPython, I plan to copy-and-paste with minor mods for each controller

# instantiate (file) global Motor Controlers, and put in brake or coast state
from MotorDriveBoim import MotorDriveBoim

from MotorDriveIBT2 import MotorDriveIBT2
pinEnL = Pin(21,Pin.OUT,1)  # for test, set EN pins high
pinEnR = Pin(20,Pin.OUT,1)  
#def IBT2on(en=1) : # EN pins not in MotorDriveIBT2, assumed tied hi
#    Pin(20,Pin.OUT,en)
#    Pin(21,Pin.OUT,en)
#IBT2on()

class TankDriveHardware() :
    def __init__(self) :
        self.cs  = WordParser(UART(1,115200)) # command stream
        self.led = Pin(25, Pin.OUT) # hidden on-board LED pin

        self.MotL = MotorDriveBoim( 6, 7, 8,'L') # PWM,Fwd,Rev,ID,freq,switch_us,coast,maxPWM
        #self.MotR = MotorDriveBoim(10,11,12,'R')
        self.MotR = MotorDriveIBT2(18,19,'R')

        self.AnalogOverrideSwitch = Pin(16, Pin.IN, Pin.PULL_UP)

        self.PotL = FilteredADC(26,0.2)  # GPIO pin index in [26|27|28]
        self.PotR = FilteredADC(27,0.2)
        
        # use this switch only in analog override mode
        self.DeadmanSwitch  = Pin(17, Pin.IN, Pin.PULL_UP) # active LOW

        self.led2 = Pin(9,Pin.OUT)  # extra diagnostic LED

HW = TankDriveHardware()
HW.led.value(1)  # show HW initialized

########################### Pico board pin to GPIO index:
#pin GPIO
#  6   4      UART1 Tx
#  7   5      UART1 Rx
#  9   6
# 10   7
# 11   8
# 14  10
# 15  11
# 16  12

# Pi Pico ADC on GP26, GP27, GP28, board pin 31,32,34, == ADC0,ADC1,ADC2

        
class TankDriveSettings() :
    def __init__(self) :
       self.DeadmanTime = 20000  # ms without command before emergencyStop()
       self.tFlash = 2000  # LED13 status flash period (ms)

    def load(self,fnam="TankDrive.dat") :
        print("load not yet implemented")

    def save(self,fnam="TankDrive.dat") :
        print("save not yet implemented")

    def print(self) :
        #analogDesc  = "UART"
        #stoppedDesc = "Running"
        #AnalogOverride = not AnalogOverrideSwitch.value() # active LOW
        #if self.stopped   : stoppedDesc = "Stopped"
        #if AnalogOverride :  analogDesc = "Analog"
        #print("Mode",analogDesc,stoppedDesc,
        #      "\tTimeout",self.DeadmanTime,
        #      "\tFlash_Period",self.tFlash)
        print("\tTimeout",self.DeadmanTime,
              "\tFlash_Period",self.tFlash)
        
# load previous state from file
Settings = TankDriveSettings()
#State.load()
Settings.print()

import time
#import _thread

class TankDriveState() :
    def __init__(self) :
        self.stopped = True
        self.analogOverride = False

        # Diagnostics stop after a few messages so that they can remain
        # in production code, but not mess up performance in actual use
        self.nMsg = 9   # print this many messages before shutting down
        self.prevCommandTime = 0  # for digital command deadman timeout
        self.deadmanClosed = True
        self.tFlash = 0 # heartbeat
        #self.lockMotorUpdate = _thread.allocate_lock()
        
    def diag(self,items) : # print diagnostic message from tupple
        if self.nMsg <= 0 :
            return
        self.nMsg -= 1
        if isinstance(items, tuple) :
            print(time.ticks_ms(),"\t".join([str(a) for a in items]))
            return
        print(time.ticks_ms(),items)


State = TankDriveState()

def updateAnalogFilters() :
    HW.PotL.update()
    HW.PotR.update()

# extract command code char (as int), and decode value in command word
def parseCommand(w) :
    iCmd = w[0]
    bVal = w[1:]
    sVal = bVal.decode()
    #print("CommandWord",chr(iCmd),sVal)
    try :
        val = int(sVal)
    except :
        State.diag((bVal,"not a valid numeric parameter, defaulted to 0"))
        val = 0
    return iCmd,val

def emergencyStop(msg) :
    print(time.ticks_ms(),msg)
    HW.MotR.emergencyStop()
    HW.MotL.emergencyStop()
    State.stopped = True
    
def updateMotorSpeedFromAnalog() :
    HW.MotL.setSpeed(HW.PotL.read())
    HW.MotR.setSpeed(HW.PotR.read())
    State.stopped = False
    
def deadmanSwitchCB(pin) :
    if not State.analogOverride :
        return # only used in analogOverride mode
    if not State.stopped :
         emergencyStop("Deadman switch open")
         State.stopped = True

HW.DeadmanSwitch.irq(deadmanSwitchCB, Pin.IRQ_RISING)

######################################################### Main loops

def initAnalogUpdate () :
    #global AnalogReadingUpdate
    timAnalogUpdate.init(period=50, mode=Timer.PERIODIC, callback=updateMotorSpeedFromAnalog)

print("AnalogOverride",State.analogOverride,"\tstopped",State.stopped)
#print("AnalogOverrideSwitch.value",HW.AnalogOverrideSwitch.value())


def checkAnalogOverrideSwitch() :
    #global State, HW, AnalogReadingUpdate
    #if State.analogOverride :
    #    print("Analog Override ACTIVE")
    #else :
    #    print("Analog Override OFF")

    if HW.AnalogOverrideSwitch.value() : # active LOW
        #print("Analog Override Switch OPEN")
        if State.analogOverride :
            # switch just turned off
            print("Analog Override OFF")
            timAnalogUpdate.deinit()
            State.analogOverride = False
    else :
        print("Analog Override Switch ENGAGED")
        if not State.analogOverride :
            print("Analog Override Enabled")
            initAnalogUpdate()
            State.analogOverride = True
        updateMotorSpeedFromAnalog()

def TankDriveUpdate(myTimer) :   # poll for commands
    #checkAnalogOverrideSwitch()
    t = time.ticks_ms()
    while HW.cs.ready() :
        HW.led.value(1) # processing command
        State.prevCommandTime = t  # reset deadman timeout
        cmd,val = parseCommand(HW.cs.next())
        State.diag((" Cmd [",chr(cmd),val,"]"))
        if cmd == ord('d') :
            MotL.show(val)
            MotR.show(val)
        elif cmd == ord('q') :
            if val > 10 : State.DeadmanTime = val
            print("+ deadman timeout",val,"ms")
        else:
            if State.analogOverride :
                State.diag((cmd,val,"ignored in Analog Override Mode"))
            else :
                # convert speed commands from 8-bit speed to 16ish for Pico PWM
                if   cmd == ord('L') :
                    HW.MotL.setSpeed(val*257)
                    State.stopped = False
                elif cmd == ord('R') :
                    HW.MotR.setSpeed(val*257)
                    State.stopped = False
                elif cmd == ord('X') :
                    HW.MotL.stop()
                    HW.MotR.stop()
                    State.stopped = True
                else :
                    #MotL.setSpeed(0,t)
                    #MotR.setSpeed(0,t)
                    State.diag(("Cmd<",chr(cmd),val,"not recognized"))

        HW.led.value(0) # done processing command
        State.tFlash = t # note that LED flashed

    # if no commands coming in, show some sign that polling loop is running
    if time.ticks_diff(t,Settings.tFlash) > State.tFlash :
        State.tFlash = t
        HW.led.toggle()


    #if State.analogOverride :        # drive from analog inputs
    #    if not State.stopped :
            
    #    if not HW.DeadmanSwitch.value() : # active LOW
    #        if not State.stopped :
    #            emergencyStop("Deadman switch open")
    #    else : State.stopped = False
 
    #else : # digital command mode, check deadman
#        if not State.stopped :
    if not (State.stopped or State.analogOverride) :
        #State.diag("checking deadman timeout")
        if time.ticks_diff(t,State.prevCommandTime) > Settings.DeadmanTime :
            emergencyStop("Deadman command timeout")
            State.stopped = True

###################################################### Launch main loop(s):
#timMotorUpdate = Timer(period=31, mode=Timer.PERIODIC,callback=updateMotors)
State.prevCommandTime = time.ticks_ms()
timTankDrive   = Timer(period=50*2, mode=Timer.PERIODIC,callback=TankDriveUpdate)
###########################################################################

# debug :
def G(vL,vR) : # set motor speeds from console
    #t = time.ticks_ms()
    print('G',vL,vR)
    HW.MotR.setSpeed(vR)
    HW.MotL.setSpeed(vL)
def X() : # stop
    State.prevCommandTime -= Settings.DeadmanTime # trigger deadman too
    HW.MotR.stop()
    HW.MotL.stop()

#HW.led.toggle()
#TankDriveUpdate()
#time.sleep_ms(2000)
#TankDriveUpdate()
#checkMotors()

#HW.MotL.show(999)
#State.nMsg = 999
#time.sleep_ms(3000)
#G(65500,0)
#time.sleep_ms(2000)
#G(-44000,0)

# $Log: TankDrive.py,v $
# Revision 1.3  2022/06/09 15:43:36  aaron
# seems to be working with IBT2
#
