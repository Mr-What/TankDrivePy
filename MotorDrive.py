# $Id: MotorDrive.py,v 1.2 2022/06/09 15:43:36 aaron Exp aaron $
#Motor driver abstract base

#Aaron Birenboim, http://boim.com    3jun2022
#provided under LGPL license


from machine import Timer
import time

class MotorDrive() :

    MODE_STOP     = 0
    MODE_RUNNING  = 1
    MODE_STOPPING = 2

    MAX_PWM = 65535 #255  // system PWM for "1" state

    @staticmethod
    def mode2str(m) :
        if m == MotorDrive.MODE_STOP    : return "STOP"
        if m == MotorDrive.MODE_RUNNING : return "RUNNING"
        if m == MotorDrive.MODE_STOPPING: return "STOPPING"
        return "UNK"

    def __init__(self,id,
                 coast = MAX_PWM // 100, # Below this PWM, just coast (set to 0)
                 maxPWM = MAX_PWM) :
        self.ID = id

        self.coast = coast # below this PWM command level, just coast
        self.speed = 0         # current PWM command
        self.msgCount = 11 # issue this many diagnostic messages before going quiet
        self.mode = MotorDrive.MODE_STOP

        
        # some drivers can't do 100% duty cycle.  Default settings for drivers that can
        self.maxPWM = maxPWM # don't go over this PWM level
        self.fullPWM = 255 * 256 - 8  # top command from 8-bit converted, - fuzz
        if self.fullPWM > self.maxPWM :
            self.fullPWM = self.maxPWM  # limit if full-power disabled

    # enforce "coast" zone near zero, and saturation zone near max
    def clipPWM(self,pwm) :
        if pwm > 0 :
            if pwm >  self.fullPWM : return  self.maxPWM
            if pwm <  self.coast   : return   0
        else :
            if pwm < -self.fullPWM : return -self.maxPWM
            if pwm > -self.coast   : return   0
        return pwm

    def diag(self,items) : # print diagnostic message from string or tupple
        if self.msgCount <= 0 :
            return
        self.msgCount -= 1
        if isinstance(items, tuple) :
            print(time.ticks_ms(),self.ID,"\t".join([str(a) for a in items]))
            return
        print(time.ticks_ms(),self.ID,items)
        
    def showState(self) :
        print("Child of MotorDrive needs to override showState() method")

    def show(self, n) :
        self.msgCount = n+1
        self.diag(("Show next",n,"messages"))
        self.showState()

    def stop(self) :    # polymorph needs to do actual stopping, then call this
        self.speed = 0
        self.mode = MODE_STOP
        
    def emergencyStop(self) :
        self.stop()
        self.diag("Emergency stop")
        self.show(11)

    # most drivers set up in __init__, but provide this to override just in case
    def begin(self) : self.emergencyStop()

    # Set speed -MAX_PWM for max reverse, MAX_PWM for max forward
    # sets speed COMMAND, actual speed change happens only in update()
    def setSpeed(self, spdReq) :
        cmd = self.clipPWM(spdReq)  # check if spdReq is supported
        self.diag((MotorDrive.mode2str(self.mode),"setSpeed",cmd))
        prevSpeed = self.speed
        self.speed = cmd  # remember current command, in case delay
                
        if self.mode == MODE_STOPPING :
            self.diag("delayed.  stopping...")
            return

        if cmd * float(spd) < 0 :
            # direction change

            sd = self.stopDelay()  # estimated ms to stop from current speed
            self.stop()
            self.speed = cmd # save command for re-start, other direction
            self.mode = MODE_STOPPING
            # set timer to go off when stop should be complete
            Timer(period=sd, mode=Timer.ONE_SHOT,
                  callback=self.restart_cb)
            self.diag(("waiting",sd,"ms before direction change."))                    

    def coast(self) : self.setSpeed(0)  # same as speed 0 most controllers

# $Log: MotorDrive.py,v $
# Revision 1.2  2022/06/09 15:43:36  aaron
# seems to be working with IBT2
#
# Revision 1.1  2022/06/07 13:56:44  aaron
# Initial revision
#
