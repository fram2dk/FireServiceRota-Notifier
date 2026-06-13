import json
import datetime
import math
import calendar
import pytz
from dateutil.relativedelta import *

class payCheck:
   def __init__(self,lonnummer):
     # Opening JSON file
     self.userid=0
     self.months = ['None','januar','februar','marts','april','maj','juni','juli','august','september','oktober','november','december']
     f = open('./storage/users.json')
     mandliste = json.load(f) 
     for mand in mandliste:
       if mand['kaldenr'] == lonnummer:
          self.userid = mand['userid']

   def split_melding(self,melding):
      meld1 = melding.split(',GPS')[0] #fjern GPS data
      meld2 = meld1.split('\r\n') #split til linjer
      if len(meld2)>=2:
         meld2.pop(0)
      return meld2
   def getMonth(self,month):
      monthnumber = 0
      now = datetime.datetime.now().astimezone(pytz.timezone('Europe/Copenhagen'))
      if isinstance(month, int):
         monthnumber = month
      else:
         if month in self.months:
            monthnumber = self.months.index(month)
      if monthnumber in range(1,13):
         if monthnumber>now.month:
           year = now.year-1
         else:
           year = now.year
         #print('month:'+str(monthnumber)+' year:'+str(year))
         #nu = datetime.datetime.now().astimezone(pytz.timezone('Europe/Copenhagen'))
         begin = datetime.datetime(year,monthnumber,1,0,0,1).astimezone(pytz.timezone('Europe/Copenhagen'))
         monthrange = calendar.monthrange(year,monthnumber)
         end = datetime.datetime(year,monthnumber,monthrange[1],23,59,59).astimezone(pytz.timezone('Europe/Copenhagen'))
      else:
         begin = now
         end = now
      return {'begin':begin,'end':end}

   def getLatestMonths(self,number):
      now = datetime.datetime.now().astimezone(pytz.timezone('Europe/Copenhagen'))
      returnMonths = []
      for offs in range(0,number):
         print('look at '+str(offs))
         offsm = now-relativedelta(months=offs)
         returnMonths.append(self.months[offsm.month])
      return returnMonths

   def getUdkald(self,begin,end):
      # Opening JSON file
      toReturn = self.months[begin.month]+' '+str(begin.year)
      with open('./latest_incidents.json') as json_file:
         data = json.load(json_file)
         meldCounter = 0
         for p in reversed(data): #opgave
            melding = p['body']
            print('data type:'+str(melding))
            splMeld = self.split_melding(melding)
            if splMeld[0] != 'RADIOPRØVE':
               print('data type1:')

               meldTime = datetime.datetime.strptime(p['start_time'],'%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.timezone('Europe/Copenhagen'))
               print('meld:'+str(meldTime)+' before:'+str(begin)+' after:'+str(end))
               if begin <= meldTime <= end:
                  print('data type2:')

                  meldCounter += 1
                  meldTimeTxt = ''
                  repstatus = None
                  for q in p['incident_responses']:
                     #print(json.dumps(q, indent=4, sort_keys=True))
                     if all (k in q for k in ('start_time','end_time','user_id','reported_status')):
                        resp_start = datetime.datetime.strptime(q['start_time'],'%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.timezone('Europe/Copenhagen'))
                        resp_end = datetime.datetime.strptime(q['end_time'],'%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.timezone('Europe/Copenhagen'))
                        diff = resp_end-resp_start
                        printDiff = round(diff.total_seconds()/3600,2)
                        diffHours,diffremain = divmod(diff.total_seconds(),3600)
                        diffMinutes,diffSeconds = divmod(diffremain,60)
                        payedHours = max(2,int(math.ceil(printDiff)))
                        if self.userid == q['user_id']:
                           repstatus = q['reported_status']
                           if q['reported_status'] == 'shown_up':
                              meldTimeTxt = '\r\n'+str(resp_start.strftime("%H:%M"))+' til '+str(resp_end.strftime("%H:%M")) + "(" + str(int(diffHours)) +"t"+str(round(diffremain/60))+"m løn:"+str(payedHours)+"t)"
                  if meldTimeTxt != '':
                     toReturn += '\r\n<b>'+str(meldTime.strftime("d.%d"))+' '+splMeld[0]+':</b>'
                     toReturn += meldTimeTxt
                  else:
                     if repstatus is None:
                        toReturn += '\r\n<s>'+str(meldTime.strftime("d.%d"))+''+splMeld[0]+'</s>'
                     else:
                        toReturn += '\r\n<s> '+str(meldTime.strftime("d.%d"))+' '+splMeld[0]+'</s>'

         if meldCounter==0:
            toReturn += '\r\n ingen udkald'
      return toReturn
