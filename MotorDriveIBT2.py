# $Id: MotorDriveIBT2.py,v 1.3 2022/06/09 15:43:36 aaron Exp aaron $
#Motor driver for IBT-2 H-Bridge module

#Aaron Birenboim, http://boim.com    3jun2022
#provided under LGPL license

#There are current sensor pins on the IBT-2, but this
# module does not support them... yet

# Many people tie the EN pins high, then drive using
# L_PWM and R_PWM for forward/reverse speed.

# I could try tieing the EN together to a pin, but I worry that
# a 3.3v ARM output might not pull these sufficiently high

# for this version, I assume that :
#    * EN pins are tied high, hence not mentioned
#    * current alarm pins are not used, hence not mentioned


from machine import PWM,Pin,Timer
import time

from MotorDrive import MotorDrive

class MotorDriveIBT2(MotorDrive) :
    def __init__(self,
                 ppwmL, # GP number for L pwm pin
                 ppwmR, # GP number for L pwm pin
                 id,  # ID code, usually 'L' or 'R'
                 freq = 1000,  # PWM freq
                 switch_us = 50, # switching time, us, to wait for MOSFET to switch
                 coast = MotorDrive.MAX_PWM // 100, # Below this PWM, just coast (set to 0)
                 maxPWM = MotorDrive.MAX_PWM) :
        super().__init__(id,coast,maxPWM)
        
        # get into coast mode as fast as possible
        # get H-bridge to quiescent state
        self.iLpwm = ppwmL  # GPIO index of L PWM pin
        self.iRpwm = ppwmR  # GPIO index of R PWM pin

        self.Lpwm = PWM(Pin(self.iLpwm))
        self.Rpwm = PWM(Pin(self.iRpwm))
        self.Lpwm.freq(freq)
        self.Rpwm.freq(freq)
        self.Lpwm.duty_u16(0)
        self.Rpwm.duty_u16(0)
        


        self.coast = coast # below this PWM command level, just coast
        self.switchTime = switch_us  # wait this long for MOSFETs to switch
        
        
    # arbitrary stop delay.  may soft-code later
    def stopDelay(self) :
        d  = self.Lpwm.duty_u16()
        dr = self.Rpwm.duty_u16()
        if (dr > d) :
            d = dr
        dt = abs(d) // 512  # 16-bit speed
        if dt < 1 : return 1
        return dt

    def showState(self) :
        if self.msgCount <= 0 : self.msgCount=1
        super().diag((self.Lpwm.duty_u16(),
             self.Rpwm.duty_u16(),
             MotorDrive.mode2str(self.mode),
             "\tcoast",self.coast,"counts ; switch ",
             self.switchTime,"us\tFwd,Rev Pins:",
             self.iLpwm,self.iRpwm))

    #def setEbrake(self) :  # internal.  set in e-braking state
    #    self.PWM.duty_u16(0)  # coast 
    #    time.sleep_us(self.switchTime) # wait until we know low MOSFETs are disabled
    #    self.Fwd.value(0)
    #    self.Rev.value(0)
    #    time.sleep_us(self.switchTime)
    #    self.PWM.duty_u16(MAX_PWM) # set to hard-break state

    def stop(self) :
        #self.setEbrake()
        self.Rpwm.duty_u16(0)
        self.Lpwm.duty_u16(0)
        self.speed = 0
        self.mode = MotorDrive.MODE_STOP
        
    def direction(self) :
        dL = self.Lpwm.duty_u16()
        dR = self.Rpwm.duty_u16()
        if (dL == 0) and (dR == 0) :
            return 0
        if (dL > 0) and (dR > 0) :
            self.emergencyStop()
            diag("Both L and R running, STOP")
            return 0
        if rev > 0 :
            return -1
        return 1
    
    #def setDirection(self) :  # internal use. just direction, not speed
    #    #self.diag(("setting direction for",self.speed))
    #    if self.speed == 0 :
    #        return
    #    dctn = self.direction()
    #    toReverse = self.speed < 0
    #    #self.diag(("current direction",dctn,"toReverse",toReverse))
    #    if  ( (     toReverse  and (dctn < 0))  or
    #          ((not toReverse) and (dctn > 0))  ) :
    #        self.diag("direction OK")
    #        return
    #    self.diag(("Switching Direction toReverse :",toReverse))
    #    self.PWM.duty_u16(0)  # coast
    #    time.sleep_us(self.switchTime)  # make sure we are coasting
    #    self.Fwd.value(not toReverse)
    #    self.Rev.value(    toReverse)
    #    time.sleep_us(self.switchTime)  # make sure direction change has settled
    #    #self.diag(("reverse",toReverse))

    def currentSpeed(self) :
        pwm = self.Lpwm.duty_u16()
        if pwm == 0 :
            pwm = -self.Rpwm.duty_u16()
        return pwm

    def restart_cb(self,tmr) : # internal only, for delay callback
        self.diag("restart")
        #self.setDirection()
        #sgn = self.direction()
        # resume commanded speed
        if self.speed < 0 :
            self.Lpwm.duty_u16(0)
            self.Rpwm.duty_u16(-self.speed)
        else :
            self.Rpwm.duty_u16(0)
            self.Lpwm.duty_u16(self.speed)
        
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

        spd = self.currentSpeed()
        
        # not a change in direction, but make sure we are set for the
        # desired future direction
        #if cmd * spd >= 0 :
        #    self.setDirection()
        #    sgn = self.direction()
            
        # if RUNNING or STOP, and no change of direction, update PWM immediately
        self.diag(("cmd",cmd,"current",spd))
        if ( ( (cmd <= 0) and (spd <= 0) ) or
             ( (cmd >= 0) and (spd >= 0) ) ) :
            if cmd < 0 :
                self.Lpwm.duty_u16(0)
                self.Rpwm.duty_u16(-cmd)
                self.speed = -self.Rpwm.duty_u16() # incase roundoff
            else:
                self.Rpwm.duty_u16(0)
                self.Lpwm.duty_u16(cmd)
                self.speed = self.Lpwm.duty_u16() # incase roundoff
            self.mode = MotorDrive.MODE_RUNNING
            self.diag(("speed updated",self.speed))
            return
        
        # if we got here, there must be a direction change
        sd = self.stopDelay()  # estimated ms to stop from current speed
        self.stop()
        self.speed = cmd # save command for re-start, other direction
        self.mode = MotorDrive.MODE_STOPPING
        # set timer to go off when stop should be complete
        Timer(period=sd, mode=Timer.ONE_SHOT,
              callback=self.restart_cb)
        self.diag(("waiting",sd,"ms before direction change."))

# test code
#a = MotorDriveIBT2(18,19,'A')
#a.show(9999)
#
#a.setSpeed(22000)
#time.sleep_ms(2000)
#a.setSpeed(0)
#time.sleep_ms(1000)
#a.setSpeed(-22000)
#time.sleep_ms(1000)
#
## I have had failures switching direction, but not reproducing now
#a.setSpeed(22000) ; time.sleep_ms(1000) ; a.setSpeed(-22000)
#time.sleep_ms(1000)
#a.setSpeed(0)

# $Log: MotorDriveIBT2.py,v $
# Revision 1.3  2022/06/09 15:43:36  aaron
# seems to be working with IBT2
#
# Revision 1.2  2022/06/07 13:57:00  aaron
# at least partially working, by hand.  Not as member of HW in TankDrive.py

