# $Id: MotorDriveBoim.py,v 1.4 2022/06/09 16:56:04 aaron Exp aaron $
#Motor driver for Late 2021/early 2022 optoisolated H-Bridge
#board produced from JLCPCB.

#Aaron Birenboim, http://boim.com    13apr2022
#provided under LGPL license

#PWM  FWD  REV
# 0    X    X    coast
# X    1    1    coast
# 1    1    0    forward
# 1    0    1    reverse
# 1    0    0    brake

#----------------- summary of LGPL :
#You are free to use and/or alter this code as you need,
#but no guarantee of correctness/appropriateness is implied.
#If you do use this code please retain credit to above as originator.

# port to micropython 220518

from machine import PWM,Pin,Timer
import time
#import _thread
from MotorDrive import MotorDrive

class MotorDriveBoim(MotorDrive) :
    def __init__(self,
                 ppwm, # GP number for pwm (EN) pin
                 fwd, # GP number, forward pin
                 rev, # GP index, rev pin,
                 id,  # ID code, usually 'L' or 'R'
                 freq = 500,  # PWM freq
                 switch_us = 50, # switching time, us, to wait for MOSFET to switch
                 coast = MotorDrive.MAX_PWM // 100, # Below this PWM, just coast (set to 0)
                 maxPWM = MotorDrive.MAX_PWM) :
        # get into coast mode as fast as possible
        # get H-bridge to quiescent state
        self.iPWM = ppwm  # GPIO index of PWM (En) pin
        self.iFwd = fwd   # forward
        self.iRev = rev   # reverse, see logic table above
        
        self.PWM = PWM(Pin(self.iPWM))
        self.PWM.freq(freq)
        self.Fwd = Pin(self.iFwd,Pin.OUT,value=0)
        self.Rev = Pin(self.iRev,Pin.OUT,value=0)

        super().__init__(id,coast,maxPWM)
        
        self.switchTime = switch_us  # wait this long for MOSFETs to switch
        self.speed = 0         # current PWM command
        
#    def grab(self) :
#        print(time.ticks_ms(),self.ID,"locking")
#        self.lock.acquire()
#        print(time.ticks_ms(),self.ID,"locked")
#    def release(self) :
#        print(time.ticks_ms(),self.ID,"releasing")
#        self.lock.release()
#        print(time.ticks_ms(),self.ID,"released")
    
    # arbitrary stop delay.  may soft-code later
    def stopDelay(self) :
        d = self.PWM.duty_u16()
        #dt = abs(speed) // 2 # 8-bit speed
        dt = abs(d) // 512  # 16-bit speed
        if dt < 1 : return 1
        return dt

    # all public in python, so user can set data membner if desired
    #void setSwitchTime(const int us) { _switchTime = us; }

    def showState(self) :
        print(time.ticks_ms(),self.ID,
              self.PWM.duty_u16(),
              self.Fwd.value(),
              self.Rev.value(),MotorDrive.mode2str(self.mode),
              "\tcoast",self.coast,"counts ; switch ",
              self.switchTime,"us\tEn,Fwd,Rev:",
              self.iPWM,self.iFwd,self.iRev)

    def setEbrake(self) :  # internal.  set in e-braking state
        self.PWM.duty_u16(0)  # coast 
        time.sleep_us(self.switchTime) # wait until we know low MOSFETs are disabled
        self.Fwd.value(0)
        self.Rev.value(0)
        time.sleep_us(self.switchTime)
        self.PWM.duty_u16(MotorDrive.MAX_PWM) # set to hard-break state

    def stop(self) :
        self.setEbrake()
        self.speed = 0
        self.mode = MotorDrive.MODE_STOP

    def direction(self) :
        fwd = self.Fwd.value()
        rev = self.Rev.value()
        if fwd and (not rev) : return  1
        if rev and (not fwd) : return -1
        return 0
    
    def setDirection(self) :  # internal use. just direction, not speed
        #self.diag(("setting direction for",self.speed))
        if self.speed == 0 :
            return
        dctn = self.direction()
        toReverse = self.speed < 0
        #self.diag(("current direction",dctn,"toReverse",toReverse))
        if  ( (     toReverse  and (dctn < 0))  or
              ((not toReverse) and (dctn > 0))  ) :
            self.diag("direction OK")
            return
        self.diag(("Switching Direction toReverse :",toReverse))
        self.PWM.duty_u16(0)  # coast
        time.sleep_us(self.switchTime)  # make sure we are coasting
        self.Fwd.value(not toReverse)
        self.Rev.value(    toReverse)
        time.sleep_us(self.switchTime)  # make sure direction change has settled
        #self.diag(("reverse",toReverse))

    def currentSpeed(self) :
        pwm = self.PWM.duty_u16()
        sgn = self.direction()
        return pwm*sgn
    
    def restart_cb(self,tmr) : # internal only, for delay callback
        self.diag("restart")
        self.setDirection()
        #sgn = self.direction()
        self.PWM.duty_u16(abs(self.speed)) # resume commanded speed
        self.mode = MotorDrive.MODE_RUNNING
        self.speed = self.currentSpeed() # in case speed not retained EXACTLY
        self.diag(("resume",self.speed))
    
    # Set speed -MAX_PWM for max reverse, MAX_PWM for max forward
    # sets speed COMMAND, actual speed change happens only in update()
    def setSpeed(self, spdReq) :
        cmd = self.clipPWM(spdReq)  # check if spdReq is supported
        self.diag((MotorDrive.mode2str(self.mode),"setSpeed",cmd))
        self.speed = cmd  # remember current command, in case delay

        if self.mode == MotorDrive.MODE_STOPPING :
            self.diag("delayed.  stopping...")
            return

        #self.lock.acquire()  # protect command updates
        pwm = self.PWM.duty_u16()
        sgn = self.direction()
        self.diag(("current speed",sgn,pwm))
        
        # not a change in direction, but make sure we are set for the
        # desired future direction
        if sgn == 0 :
            self.setDirection()
            sgn = self.direction()
            
        # if RUNNING or STOP, and no change of direction, update PWM immediately
        spd = sgn * pwm # current
        self.diag(("cmd",cmd,"current",spd))
        if ( ( (cmd > 0) and (spd > 0) ) or
             ( (cmd < 0) and (spd < 0) ) or
             (cmd == 0) ) :
            self.PWM.duty_u16(abs(cmd))
            self.speed = sgn * self.PWM.duty_u16() # in case can't set EXACTLY
            self.mode = MotorDrive.MODE_RUNNING
            self.diag(("speed updated",self.speed))
            return
        
        if spd == 0 : #restart without delay.  already coasting
            self.restart_cb(0)

        # if we got here, there must be a direction change
        sd = self.stopDelay()  # estimated ms to stop from current speed
        self.setEbrake()
        self.mode = MotorDrive.MODE_STOPPING
        # set timer to go off when stop should be complete
        Timer(period=sd, mode=Timer.ONE_SHOT,
              callback=self.restart_cb)
        self.diag(("waiting",sd,"ms before direction change."))                    
        #self.release()

# test sequence
def testMotorDriveBoim() :
    a = MotorDriveBoim(6,7,8,'A')
    a.show(9999)
    a.setSpeed(33000)
    d = 100
    time.sleep_ms(d)
    a.setSpeed(-33000)
    time.sleep_ms(d)
    a.setSpeed(0)
    time.sleep_ms(d)
    a.setSpeed(11000)
    time.sleep_ms(d)
    a.setSpeed(22000)
    time.sleep_ms(d)
    a.setSpeed(44000)
    time.sleep_ms(d)
    a.setSpeed(-22000)
    time.sleep_ms(d)
    a.setSpeed(-44000)
    d=1000
    time.sleep_ms(d)
    
    # noted trouble with rev-coast-fwd staying rev from TankDrive
    # try to reproduce
    a.setSpeed(0)
    time.sleep_ms(d)
    print("should switch direction")
    a.setSpeed(22000)
    time.sleep_ms(d)
    a.stop()
#testMotorDriveBoim()

# $Log: MotorDriveBoim.py,v $
# Revision 1.4  2022/06/09 16:56:04  aaron
# refactor to inherit from MotorDrive.py
#
# Revision 1.3  2022/06/09 15:43:36  aaron
# Revision 1.2  2022/05/25 20:05:51  aaron
# got rid if update().  setSpeed will use timers as necessary to execute slow commands
# Revision 1.1  2022/05/25 17:25:59  aaron
# 220519 ab ported from MotorDriveBoim.h Arduino/C++
