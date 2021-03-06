#!/usr/bin/python3
# -*- coding: utf-8 -*-
VEERSION = "20210306_1537"

'''
This python program running on a laptop connects to two remote headless controllers (Raspberry Pis) each operating a SSH server checking periodically for
IP connection to a router and whether the SSH connection is good. 
The status is displayed graphically using https://pysimplegui.readthedocs.io/en/latest/
Function sendMesage keeps an audit trail of events in memory and is able to send messages to the user via Telegram app and email.
Disable/comment this out initially to see basic operation.
Other features are a lock to prevent it being run more than once on the same device and the ability to restart that proves useful when making changes and testing.
zSamplePeriod locates where the sample periodicity can be changed.
zMidnight locates actions to happen at midnight
Run with:
  cd ~/Ref/pythonBC (example)
  python3 alarm2RPi.py
'''
#zMidnight zSamplePeriod
#zsh sh command
#Note 2m15 to start RPi3 HAL2

import subprocess,os,sys,re,datetime
def abortIfAlreadyRunning():
  #Prevent a python application being started more than once
  #Needs import subprocess,os,sys,re,datetime
  sProgNom = os.path.basename(sys.argv[0])
  sProgCall ="python3 {}".format(sProgNom) #eg python3 PSGtestBed.py
  sPsOp = subprocess.check_output(['ps', '-aux'])
  sPsOp = str(sPsOp)
  iNumTimesRunng = sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(sProgCall), sPsOp))
  if iNumTimesRunng > 1:
    print("Aborting as already running") #Log
    #with open("abort.txt", 'a') as fkj: fkj.write("{} Aborted as already running".format(datetime.datetime.now()))    
    sys.exit()
  return sProgNom #Normally return the name of the python script being run  
THISAPPFILENAME = abortIfAlreadyRunning()

import PySimpleGUI20201011 as sg

igChPerLin = 45
FONTHEL = 'Helvetica 10'
form = sg.FlexForm('colors',auto_size_text=True,font=('Helvetica',14))
layoot=[
         [sg.B('2 PING',key='KYPNG2'),sg.B('2 SSH',key='KYSSH2'),sg.T('',size=(6,1),key='KYT2'),
          sg.B('3 PING',key='KYPNG3'),sg.B('3 SSH',key='KYSSH3'),sg.T('',size=(6,1),key='KYT3')],
         [sg.Multiline(size=(igChPerLin,6),font=FONTHEL,key='KYMRESLT')],
         [sg.B('About',key='KYAB'),sg.B('Events',key='KYEVT'),
           sg.B('Restart',key='KYKLBR',enable_events=True,button_color=('black','orange')),
            sg.B('eXit',key='KYKLBX',enable_events=True,button_color=('black','pink'))]
       ]   

wiindow = sg.Window('Monitor 2xRPi {}'.format(THISAPPFILENAME),layoot,
                   return_keyboard_events=True,finalize=True)

import shlex,sys,time
import urllib,requests,configparser
#Ours
import emailImap

lEveents = []
MAXTOTGPERDAY = 50 #Acts like a fuse in case send to TG runs amok. Reset at midnight
iCtDn2TG = MAXTOTGPERDAY
coenfig = configparser.ConfigParser()
coenfig.read(".config.ini")
URXL = "https://api.telegram.org/bot{}/".format(coenfig['Telegram']['botno'])
igCtToday2 = 0
igCtToday3 = 0

def piing(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    https://stackoverflow.com/questions/2953462/pinging-servers-in-python
    Needs import subprocess (For executing a shell command)
    """
    # Option for the number of packets as a function of
    #  import platform    # For getting the operating system name
    ##param = '-n' if platform.system().lower()=='windows' else '-c'
    #param = '-c' #Cnt of number packets Linux
    # Building the Linux command. Ex: "ping -c 1 google.com"
    command = ['ping','-c','1',host]
    return subprocess.call(command) == 0

def iinstrX(sLong,sShort,iStart=0):
  """If sShort is found in sLong searching from left to right this returns its position
  else -1. iStart is optional and if omitted taken as position 0 (0 is first column)"""
  return sLong.find(sShort,iStart) #returns -1 if not matched

def testSSHserver(sArrg):
  #INPUT sArrg as either '2' or '3'
  #print("Testing {}".format(sArrg))
  #  zsh One can test below command on command line
  cmd = "ssh -o BatchMode=yes -o ConnectTimeout=5 andymc@192.168.0.{} echo ok 2>&1".format(sArrg)
  bRp = True #Assume is ok
  try:
    byAns = subprocess.check_output(shlex.split(cmd))
    sAns = byAns.decode("utf-8") #Convert from bytes to string 
    sAns = sAns.rstrip() #remove return at end
    iAns = iinstrX(sAns,"ok")
    if iAns == -1:
      bRp = False #No ok
  except:
    bRp = False
  return bRp

def restartProgram():
  pzython = sys.executable #20200808 
  os.execl(pzython, pzython, * sys.argv)
  
def notifyMobile(botMsg):
  #Notify Telegram Bot on mobile phone(s)
  global iCtDn2TG
  botMsg = urllib.parse.quote_plus(botMsg) #NEW 20201207
  iCtDn2TG -= 1 #decrement
  if iCtDn2TG == 0:
    print("Aborting no more sending to TG today")
    return
  if iCtDn2TG == 1:
    botMsg = "{}\nLAST TX!".format(botMsg)
  #See https://github.com/python-telegram-bot/python-telegram-bot/issues/131  Markdown expects matching special chars.
  #it throws an error if it sees an odd number of * or _
  st="{}sendMessage?chat_id=1090944657&text={}".format(URXL,botMsg)
  try:
    sRespnse = requests.get(st) #1/3 Good is <Response [200]>
    return sRespnse.json()
  except:
    print("not sent to mobile ({})".format(botMsg))
    return ""
    
def sendMesage(sNot,sDev2or3=" "):
  #INPUT sNot is a brief note
  #INPUT sDev2or3 can be string 2 or 3 else blank
  sNow = datetime.datetime.now()
  sDatestamp = sNow.strftime("%Y%m%d_%H%M")
  sMeesg = "SSH{} {} {}".format(sDev2or3,sDatestamp,sNot) # >>SSH3 20210218_1600 FAIL
  print(sMeesg)
  lEveents.insert(0,sMeesg) #Keep copy of the event in memory. At top of list
  if len(lEveents) > 50:
    del lEveents[-1] #Remove last in list
  notifyMobile(sMeesg) #HAL to Telegram (sci igi.clInCmmnd.notifyMobile(sMeesg))
  emailImap.send_email(sMeesg, "") #Send email with subject filled but empty body 

def showCt():
  wiindow['KYT2'].Update(str(igCtToday2))
  wiindow['KYT3'].Update(str(igCtToday3))
  wiindow.Refresh()

class clTest:
  #Test each SSH Server
  def __init__(self, si2or3, siSHOPNG, siSHOSSH):
    self.s2or3 = si2or3 #'2' or '3' indicates device under test  
    self.sSHOPNG = siSHOPNG #Show Ping state   
    self.sSHOSSH = siSHOSSH #Show SSH Server state
    self.bGudPNG = True #Assume good on startup
    self.bGudSSH = True #Assume good on startup

  def doTest(self):
    #---Test Ping
    global igCtToday2,igCtToday3
    wiindow[self.sSHOPNG].Update(button_color=('black','gray'))
    wiindow.Refresh()
    sIP = "192.168.0.{}".format(self.s2or3)
    if piing(sIP) == True:
      wiindow[self.sSHOPNG].Update(button_color=('black','green'))
      if self.bGudPNG == False:
        sendMesage("PNG OKAY",self.s2or3) #Was bad but recovered
        self.bGudPNG = True
    else:  
      wiindow[self.sSHOPNG].Update(button_color=('black','red'))
      if self.bGudPNG == True:
        sendMesage("PNG FAIL",self.s2or3) #Was good
        self.bGudPNG = False
        if self.s2or3 == '2':
          igCtToday2 += 1
        else:  
          igCtToday3 += 1
        showCt() #Bad 
    #---Test SSH Server
    wiindow[self.sSHOSSH].Update(button_color=('black','gray'))
    wiindow.Refresh()
    if testSSHserver(self.s2or3) == True:
      wiindow[self.sSHOSSH].Update(button_color=('black','green')) #Good SSH server
      if self.bGudSSH == False:
        sendMesage("SSH OKAY",self.s2or3) #Was bad but recovered
        self.bGudSSH = True
    else:  
      wiindow[self.sSHOSSH].Update(button_color=('black','red'))
      if self.bGudSSH == True:
        sendMesage("SSH FAIL",self.s2or3) #Was good
        self.bGudSSH = False
        if self.s2or3 == '2':
          igCtToday2 += 1
        else:  
          igCtToday3 += 1
        showCt() #Bad 2

testInst2 = clTest('2','KYPNG2','KYSSH2')
testInst3 = clTest('3','KYPNG3','KYSSH3')

bGudSSH2 = True #Assume ok to start with
bGudSSH3 = True
def periodicWorkerFunction():
  #===================================
  # Timed function Here every x seconds (clock time)
  #===================================
  testInst2.doTest()
  testInst3.doTest()

#=======================================================
wiindow['KYMRESLT'].Update("")
wiindow.Refresh()
sendMesage("Startup {}".format(sys.argv[0])) #Name of pyton script
showCt() #Startup

iSecOld = 99
iHrOld2 = -1
iHrOld3 = -1
igHoour = -1
while True:  # Event Loop zEventLoop
  sWithHMS = os.popen('date +"%Y %b %m %d %H %M %S %Z"').read() #2021 Feb 02 15 17 10 28 GMT
  #Above is like: 2020 Aug 08 26 15 16 45 BST
  lItms = sWithHMS.split(' ')
  iHrNowTemp = int(lItms[4]) #hrs 0 to 23
  iMins = int(lItms[5]) #Mins 0 to 59
  iSecNow = int(lItms[6]) #secs 0 to 59
  
  #Check if zMidnight
  if igHoour == 23 and iHrNowTemp == 0:
    #Midnight reset tasks
    iCtDn2TG = MAXTOTGPERDAY #Reset at midnight max msgs that can be sent to TG
    sendMesage("2:{} 3:{} FAILURES".format(str(igCtToday2),str(igCtToday3))) #Daily summary
    igCtToday2 = 0
    igCtToday3 = 0
    showCt() #update display
  igHoour = iHrNowTemp #as iHrNowTemp was only a temporary store
    
  if iSecNow != iSecOld:
    #Here at start of every new second
    iSecOld = iSecNow #Keep current second
    #zSamplePeriod
    #n % k == 0 evaluates true if and only if n is an exact multiple of k
    #print("{} {}".format(str(iSecNow),str(iSecNow % 10)))
    #if (iSecNow % 10) == 0: (test with 10 else 59 hourly)
    if (iSecNow % 30) == 0:
      periodicWorkerFunction()

  #Calls to read block until an event. 
  eveent, valuues = wiindow.read(timeout=100) # zEventLoop 29Oct2020 https://www.reddit.com/r/learnpython/comments/fpve1e/pysimplegui_problem_with_event_loop/
  if eveent == sg.WIN_CLOSED or eveent == 'Exit':    # always,  always give a way out!
    break
      
  if eveent == 'KYSSH2':
    print("Pressed 2")
  if eveent == 'KYSSH3':
    print("Pressed 3")
  if eveent == 'KYAB':
    #About
    wiindow['KYMRESLT'].Update("sshAlarm.py RPi Tester V.{}".format(VEERSION))
  if eveent == 'KYEVT':
    sTs = ""
    for sIteam in lEveents:
      sTs += "{}\n".format(sIteam)
    wiindow['KYMRESLT'].Update(sTs)

  #CLose
  if eveent == 'KYKLBX':
    break #User selected exit
  if eveent == 'KYKLBR':
    restartProgram()
    break #exit program

wiindow.Close()
