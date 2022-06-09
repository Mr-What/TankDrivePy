# Parse whitespace delimited ASCII commands coming in on an input stream.
#
# Constructed with the stream to parse

#from machine import Pin,UART
#from machine import UART
import time

# there has been trouble using bytes const.  put in int variable
def asc2int(a) :
    b = int.from_bytes(a,"big")
    #print('asc2int',type(a),a,'-->',type(b),b,'<')
    return b

# A few convenient constants
iSPC = asc2int(b' ')
iTLD = asc2int(b'~')

# consider anything not a printable character as whitespace
def isWhitespace(b) : # works for whitespace in byte
    #print(type(b),b)  # seems to convert bytes to int on passing
    if (b <= iSPC) or (b > iTLD) :
        return True
    return False


def cleanWhitespace(buf) :
    #print('cleaning:',type(buf),buf,'<')
    x = bytearray(buf)
    #print('copied',type(x),x,'<')
    n = len(x)
    for k in range(0,n) :
        if isWhitespace(x[k]) : # x[k] seems to be int, not bytes
            x[k] = iSPC
    print('cleaned input stream',x)
    return x

def trimLeadingSpace(buf) :
    k = 0
    nb = len(buf)
    while (nb > k) and (buf[k] == iSPC) :
        k=k+1
    #print("Spaces til",k)
    if k==0:
        return buf
    if k >= nb:
        return str("")
    return bytearray(buf[k:])

def firstSpace(b) :
    for k in range (0,len(b)) :
        if b[k] == iSPC :
            return k
    return -1 # no whitespace in string


class WordParser() :
    def __init__(self,s) :   # provide stream to parse
        self.stream = s
        self.buf = bytearray()  # to accumulate bytes
        self.cmd = []           # list of completed commands received

    def parse(self) : # check for next command in buffer (internal use only)
        buf = trimLeadingSpace(self.buf)
        #print('parsing',type(buf),buf,'<')
        k = firstSpace(buf)
        #print('first space at',k)
        if k <= 0 :
            return
        nextCmd=buf[:k]
        #print('next cmd:',nextCmd,'<')
        if len(self.cmd) > 0 :
            self.cmd.append(nextCmd)
        else:
            self.cmd = [nextCmd]
        #print(len(self.cmd),'commands in queue')
        #print(self.cmd)
        self.buf = buf[k+1:]
        #print('unparsed buffer remaining',type(self.buf),self.buf,'<')

    def update(self) : # check for new bytes on command line (internal use only)
        if (self.stream.any() <= 0) :
            return
        while self.stream.any():  # load any new bytes
            newBytes = self.stream.read()
            self.buf += str(cleanWhitespace(newBytes),'UTF-8')
            #print('updated buf',type(self.buf),self.buf,'<')

        while True:  # parse any new commands received
            nq = len(self.cmd)
            #print(nq,'commands in queue')
            self.parse()
            if nq==len(self.cmd) :
                return
            #else :
                #print('remaining buf:',self.buf,'<')
                            
    def ready(self) : # returns True if a complete command is ready to be retrieved
        self.update()
        return len(self.cmd) > 0  # True if a complete command was received
        
    def next(self) : # get next command.  will block.  use ready() to avoid blocking
        #n=0
        while not self.ready() :
            #print(n,'waiting...')
            #n=n+1
            time.sleep_ms(100)

        cmd = self.cmd[0]
        if len(self.cmd) > 1 :  self.cmd = self.cmd[1:]
        else                 :  self.cmd = []
        return cmd
