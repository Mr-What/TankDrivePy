# $Id$
#
# Potentiomenters on ADC pin with low-pass filter

# Pi Pico ADC on GP26, GP27, GP28, board pin 31,32,34, == ADC0,ADC1,ADC2

from machine import ADC

class FilteredADC() :
    def setGain(self,gain) :
        self.gain = gain
        self.gain1 = 1.0 - gain
    def setRange(self,in0,in1,out0,out1) :  # scale input counts in0..in1 to out0..out1
        self.in0 = in0
        self.out0 = out0
        self.out1 = out1
        self.scale = float(out1 - out0) / float(in1 - in0)
        
        # let a "large step" be this fraction of whole scale
        self.largeStep = round(0.2 * float(in1 - in0))
  
    def __init__(self,pinID,gain=0.5,out0=-255,out1=255,in0=500,in1=65000) :
        # default, some "flat zone" at extreme ends of the adc [tLo > 0, tHi < 65335]
        self.adc = ADC(pinID)
        self.v = 32767  # filtered ADC output
        self.outlierCount = 0
        self.setGain(gain)
        self.setRange(in0,in1,out0,out1)
        
    def update(self) : # Pi Pico is actually 12-bit ADC, but scaled to u16 in uPy
        val = self.adc.read_u16()
        if val == self.v : return  # no change
        dv = float(val - self.v)
        v = round(float(self.v) * self.gain1 + dv * self.gain)
        
        if dv < self.largeStep :
            # typical case, small reading change
            self.outlierCount = 0
            if self.v == v :
                # move by 1 count if readings not the same.
                # otherwise self.v can get stuck on small gains
                if   dv > 0 : self.v = v+1
                else        : self.v = v-1
            else            : self.v = v
        else :
            # reject transients, but reset filter if step detected
            if dv > 0 : self.outlierCount += 1
            else      : self.outlierCount -= 1
            if abs(self.outlierCount) > 2 :
                # not outlier.  step.  reset filter
                self.v = val
                self.outlierCount = 0
                
    def peek(self) : # convert current filtered input to output
        # scale input reading to output scale
        y = round(self.out0 + self.scale * float(self.v - self.in0))
        # when v is outside of in0..in1 range, y is out of range
        if y < self.out0 : return self.out0
        if y > self.out1 : return self.out1
        return y

    def read(self) :  # update and return resulting output. Most common used method
        self.update()
        return self.peek()

# $Log$
