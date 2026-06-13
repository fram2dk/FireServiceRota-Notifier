#!/usr/bin/env python3
import telebot
import json
import sqlite3
import paho.mqtt.client as mqtt
import ssl
import threading
import queue
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from base64 import b64encode
import time
import os
import logging
import random,string
import sys
import signal
import socket
import traceback
import requests
import shutil
import hashlib
import uuid
import copy

from timecheck import payCheck
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'telegramLogger'))
from telegramLogger import tgLog
from custom_functions import merge_with_mask

print("__telegram bot started__")

class TelegramUsers:
  def __init__(self,completeobj=None):
    self.stationname = stationname
    self.tguserdataobj = {'data':{'telegramusers':[]},'versionnode':{'stationname':self.stationname,'hash':'','parent':None,'branch':str(uuid.uuid1().hex),'timestamp':int(datetime.now(timezone.utc).timestamp())}}
    self.backupfolderpath = "../tmp/olduserfiles/"
    if isinstance(completeobj,dict):
      if 'data' in completeobj.keys() and 'versionnode' in completeobj.keys():
        if 'stationname' in completeobj['versionnode'].keys():
          if completeobj['versionnode']['stationname'] == self.stationname:
            self.tguserdataobj = completeobj

  def setHash(self):
    res = hashlib.md5(json.dumps(self.tguserdataobj['data']).encode())
    hashstr = str(res.hexdigest())
    if hashstr != self.tguserdataobj['versionnode']['hash']:
      self.tguserdataobj['versionnode']['hash'] = str(res.hexdigest())
      self.tguserdataobj['versionnode']['timestamp'] = int(datetime.now(timezone.utc).timestamp())
      filepath = os.path.join(str(self.backupfolderpath), str(self.tguserdataobj['versionnode']['hash'])+".json")
      try:
        os.makedirs(self.backupfolderpath)
      except: # folder already exists
        pass
      with open(tgusersjsonpath, "w") as outfile: #save users file of the new object
        json.dump(self.tguserdataobj, outfile, indent=2)
      if not os.path.exists(filepath):
        with open(filepath, "w") as outfile: #save backupfile and send it later
          json.dump(self.tguserdataobj, outfile, indent=2)
        return True
    return False

  def updateUser(self,userdata:dict,updatekeys=None):
    if 'chatid' in userdata.keys():
      for idx,tmpuserdata in enumerate(self.tguserdataobj['data']['telegramusers']):
        if 'chatid' in tmpuserdata.keys():
          if userdata['chatid'] == tmpuserdata['chatid']:
            if updatekeys is None:
              self.tguserdataobj['data']['telegramusers'][idx] = userdata
            elif isinstance(updatekeys,dict):
              #_LOGGER.debug("old userdata1:"+str(self.tguserdataobj['data']['telegramusers'][idx]))
              merged = merge_with_mask(copy.deepcopy(self.tguserdataobj['data']['telegramusers'][idx]), userdata, updatekeys)
              #_LOGGER.debug("old userdata2:"+str(self.tguserdataobj['data']['telegramusers'][idx]))
              #_LOGGER.debug("new userdata:"+str(userdata))
              if merged != self.tguserdataobj['data']['telegramusers'][idx]:
                merged['lastupdate'] = int(datetime.now(timezone.utc).timestamp())
                _LOGGER.debug("result userdata:"+str(merged))
                self.tguserdataobj['data']['telegramusers'][idx] = merged
              else:
                _LOGGER.debug("olddata was identical for chatid:"+str(tmpuserdata['chatid']))

            self.setHash()
            return True
      self.tguserdataobj['data']['telegramusers'].append(userdata)
      return True
    return False

  def get(self):
    return self.tguserdataobj
  def getJson(self):
    return json.dumps(self.tguserdataobj)
  def getUserData(self,search_chatid=None,alldata=None):
    if isinstance(search_chatid,int):
      try:
        for tguser in self.tguserdataobj['data']['telegramusers']:
          if tguser['chatid'] == search_chatid:
            if alldata is True:
              return tguser
            else:
              return {'roles':tguser['roles'],'state':tguser['state']}
      except:
        pass
  def getBackupfiles(self):
    toreturn = {'files':[]}
    try:
      backupfiles = os.listdir(self.backupfolderpath)
      if isinstance(backupfiles,list):
        if len(backupfiles) > 0:
          for file in backupfiles:
            filepath = os.path.join(str(self.backupfolderpath), str(file))
            if os.path.isfile(filepath):
             filename,fileext = os.path.splitext(filepath)
             if str(fileext).lower() == '.json':
               with open(str(filepath), 'r') as f:
                 toreturn['files'].append(str(f.read()).strip())
          return toreturn
    except:
      pass

  def deleteBackupFile(self, hashvalue):
    try:
      backupfiles = os.listdir(self.backupfolderpath)
      if isinstance(backupfiles,list):
        if len(backupfiles) > 0:
          for file in backupfiles:
            filepath = os.path.join(str(self.backupfolderpath), str(file))
            if os.path.isfile(filepath):
             filename,fileext = os.path.splitext(filepath)
             if str(fileext).lower() == '.json':
               with open(str(filepath), 'r') as f:
                 filedict = json.load(f)
                 if 'versionnode' in filedict.keys():
                   if 'hash' in filedict['versionnode'].keys():
                     if len(filedict['versionnode']['hash']) > 5 and str(filedict['versionnode']['hash']) == hashvalue:
                       os.remove(filepath)
                       _LOGGER.info("backup file"+str(filepath)+" deleted")
    except:
      pass

  def getUserCount(self):
    toreturn = {'users':0,'responders':0,'family':0,'message':{'first':0,'response':0}}
    for tmpusr in self.tguserdataobj['data']['telegramusers']:
      toreturn['users'] += 1
      if 'roles' in tmpusr:
        for roles in tmpusr['roles']:
          if 'role' in roles.keys():
            if roles['role'] == 1:
              toreturn['message']['response'] += 1
            elif roles['role'] == 2:
              toreturn['message']['first'] += 1
      if 'access_level' in tmpusr:
        if tmpusr['access_level'] == 1:
          toreturn['family'] += 1
        elif tmpusr['access_level'] == 2:
          toreturn['responders'] += 1
    return toreturn

  def checkUpdate(self,newversion):
    toreturn = {'oldversions':[],'updatestatus':0}
    try:
      if 'data' in newversion.keys() and 'versionnode' in newversion.keys():
        if 'branch' in newversion['versionnode'].keys() and 'hash' in newversion['versionnode'].keys() and self.stationname == newversion['versionnode']['stationname']:
          if newversion['versionnode']['branch'] != self.tguserdataobj['versionnode']['branch']: #backup version is different, we must use that one
            toreturn['updatestatus'] = 1 #need to run online version
          elif newversion['versionnode']['hash'] != self.tguserdataobj['versionnode']['hash']: #current version is different
            toreturn['updatestatus'] = 1 #need to run online version
          else:
            toreturn['updatestatus'] = 2 #same, nothing done

      if toreturn['updatestatus'] == 1: #must update
        if self.setHash():
          toreturn['updatestatus'] = 1 #saved old file
        else: #already had saved the old file
          pass
        self.tguserdataobj = newversion
        self.tguserdataobj['versionnode']['parent'] = self.tguserdataobj['versionnode']['hash'] #when saving from backup set parent to the hash of the recieved version.
        self.setHash() #recalculate hash for the new file (it should be correct from server)												#So even when a local version evolves it will still have the same parent.

    except:
      toreturn['updatestatus'] = -1
    return toreturn

  def getCallList(self,validusers=None):
    validuserids = None
    messagestructure = {'call':{},'update':{}} #  {"call":{chatid:messagetype},"update":{fsruserid:[{"chatid":None,"massagetype":0}]}} #messagetype:0=invalid,1=censored,2=full

    if isinstance(validusers,list):
      if len(validusers) > 0:
        validuserids = validusers

    for tguser in self.get()['data']['telegramusers']:
      if isinstance(tguser,dict):
        if 'roles' in tguser.keys() and 'chatid' in tguser.keys() and 'state' in tguser.keys() and 'access_level' in tguser.keys():
          chatid = tguser['chatid']
          if tguser['state'] in [1,2]:
            if isinstance(tguser['roles'],list):
              for role in tguser['roles']:
                if 'userid' in role.keys() and 'role' in role.keys():
                  fsruserid = role['userid']
                  validfsruserid = False
                  if validuserids is None:
                    validfsruserid = True
                  elif isinstance(validuserids,list):
                    if fsruserid in validuserids:
                      validfsruserid = True
                  if validfsruserid:
                    if fsruserid not in messagestructure['update'].keys():
                      messagestructure['update'][fsruserid] = []
                    if role['role'] == 1: #familie
                      messagestructure['update'][fsruserid].append({'chatid':chatid,'messagetype':1})
                    elif role['role'] == 2: #brandmand
                      messagestructure['call'][chatid] = 2
                  else:
                    print('FSR user was invalid: '+str(fsruserid)+'in chatid '+str(chatid))
                else:
                  print('role keys invalid for chatis: '+str(chatid))
            else:
              print('roles not a list for chatid: '+str(chatid))
            if 'settings' in tguser.keys():
              if 'initial_message' in tguser['settings'].keys():
                if tguser['settings']['initial_message'] is True:
                  messagestructure['call'][chatid] = tguser['access_level']
                else:
                  messagestructure['call'][chatid] = 0
            else:
              pass
          else:
            print("invalid access level for chatid"+str(chatid))
        else:
          print(str(tguser)+" dindt have proper keys")
      else:
        print(str(tguser)+" was not a dict")
    return messagestructure

  def __str__(self):
    return str(self.tguserdataobj)

def handle_stop(signum, frame):
    print("Received stop signal")
    stop_event.set()
signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)


appname = 'fsrtg'
workdir = os.path.dirname(os.path.abspath(__file__))

debugFlag = True
admins = []
exclude_users = []
include_groups = []
telegramusers = None
mqttLogin = {'username':None,'password':None}
basemqtttopic_list = ["unknown","fromTG"]
instanceid = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
stationname = instanceid
lastFsrHeartbeat = None

log1 = tgLog(appname)
_LOGGER = logging.getLogger(__name__)
if debugFlag:
  logging.basicConfig(level=logging.DEBUG)
else:
  try:
    os.makedirs('../tmp/logfiles/')
  except:
    pass
  logging.basicConfig(filename='../tmp/logfiles/telebot'+ datetime.now().strftime('%m%d%H%M')+'.log', level=logging.DEBUG,format=' %(asctime)s - %(levelname)s - %(message)s')   #debug
_LOGGER.info("telegram bot started")


configfilepath = '../data/config.json'
if os.path.isfile(configfilepath):
 with open(configfilepath) as config_file:
  config_content = config_file.read()
  config = json.loads(config_content)
  _LOGGER.debug(config)
  if 'mqtt' in config:
    if 'username' in config['mqtt'] and 'password' in config['mqtt']:
      mqttLogin = {'username':config['mqtt']['username'],'password':config['mqtt']['password']}
    if 'basetopic' in config['mqtt']:
      basemqtttopic_list[0] = str(config['mqtt']['basetopic'])
      stationname = basemqtttopic_list[0]
    if 'stationname' in config['mqtt']:
      stationname = config['mqtt']['stationname']
  if 'app' in config:
    if 'admin' in config['app']:
      admins = config['app']['admin']
  if 'telegram' in config:
    if 'token' in config['telegram']:
      tgtoken = config['telegram']['token']
  _LOGGER.info('config file found. it had '+str(len(config))+' keys')
  _LOGGER.debug('config content'+str(config_content))
else:
  _LOGGER.warning("no config file")

tgusersjsonpath = '../tmp/users.json'
if os.path.isfile(tgusersjsonpath):
  print('found old users file('+str(tgusersjsonpath)+')')
  with open(tgusersjsonpath, 'r') as f:
    contentdict = json.load(f)
    telegramusers = TelegramUsers(contentdict)
else:
  print("no telegramuser file found")
  telegramusers = TelegramUsers()

fsrusersjsonpath = '../tmp/fsrusers.json'
fsrusers = {}
if os.path.isfile(fsrusersjsonpath):
  _LOGGER.info('found old FSR users file('+str(fsrusersjsonpath)+')')
  with open(fsrusersjsonpath, 'r') as f:
    fsrusers_str = json.load(f) #userid is str in json
  fsrusers = {int(k): v for k, v in fsrusers_str.items()} #key(userid) skal være int
else:
  _LOGGER.warning("no FSR users file found")

sqlitefilepath = "../tmp/users.db"


if not 'tgtoken' in globals():
  if "TG_TOKEN" in os.environ:
    tgtoken = os.environ["TG_TOKEN"]
elif tgtoken is None:
  if "TG_TOKEN" in os.environ:
    tgtoken = os.environ["TG_TOKEN"] 

if debugFlag:
  _LOGGER.info('##### DEBUG IS ON #######')
  _LOGGER.info('tgtoken: ..'+tgtoken[-10:]+'')

incidentsQue = queue.SimpleQueue()
fromTgQue = queue.SimpleQueue()
toTgQue = queue.SimpleQueue()


_LOGGER.debug("telegramusers: "+str(telegramusers.getUserCount())+" version: "+str(telegramusers.get()['versionnode']))

loginPenalty = {}
bot = telebot.TeleBot(tgtoken)

#demo =
#{
#  "users":[
#    {"chatid":None,"roles":[{"userid":None,"role":1}],"userdata":{"fromTG":{}},"state":0,lastupdate:None}
#  ]
#  "history":[]
#}
incidents = {65432:{'starttime':None,'message':{'full':'','censured':''},'responses':{123:0,1234:1}}}



class ThreadMqttService(threading.Thread):
        def __init__(self,name,restart,stop):
          threading.Thread.__init__(self)
          self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
          self.name = name
          self.restart = restart
          self.stop = stop
          self.client = None
          self.instancetopic = basemqtttopic_list[0]+'/'+basemqtttopic_list[1]+'/'+'instance/'+str(instanceid)
          self.fsruserstopic = basemqtttopic_list[0]+'/fromFSR/users'
          self.tgchatstopic = basemqtttopic_list[0]+'/toTelegram/instance/'+str(instanceid)+'/tgusers'
          self.tgrequestbackuptopic = basemqtttopic_list[0]+'/fromTG/getUsers'
          self.tguserupdatetopic = basemqtttopic_list[0]+'/toTelegram/userupdate/+/+'
          self.tgincidentupdatetopic = basemqtttopic_list[0]+'/toTelegram/incidentupdate'
          self.tgbackupreceipttopic = basemqtttopic_list[0]+'/toTelegram/backupreceipt/'+str(instanceid)
          _LOGGER.debug("thread mqtt("+str(name)+") started")
        def connect(self):
          cafile = '../data/ssl/ca.crt'
          certfile = '../data/ssl/fsr.crt'
          keyfile = '../data/ssl/fsr.key'
          if os.path.isfile(cafile) and os.path.isfile(certfile) and os.path.isfile(keyfile) and mqttLogin['username'] is not None and mqttLogin['password'] is not None:
            self.client = mqtt.Client(client_id="FSRtelegram_"+str(instanceid),callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.client.on_connect= self.on_connect  #bind call back function
            self.client.on_disconnect= self.on_disconnect  #bind call back function
            self.client.on_message = self.on_message #bind call back function
            self.client.will_set(self.instancetopic,json.dumps({'message':'connection terminated abrupt'}),qos=2,retain=False)
            self.client.username_pw_set(mqttLogin['username'], mqttLogin['password'])
            self.client.tls_set(ca_certs=cafile, certfile=certfile, keyfile=keyfile, tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_REQUIRED)
            self.client.tls_insecure_set(True)
            self.client.connect("135.125.201.77", 8893, 60)
          else:
            _LOGGER.warning("mqtt ssl og login missing")
            time.sleep(300)
            self.restart = True

        def on_connect(self,client, userdata, flags, rc,properties=None):
          global newconnection
          if rc==0:
            _LOGGER.debug("mqtt connected ok")
            client.subscribe(self.tgchatstopic)
            client.subscribe(self.fsruserstopic)
            client.subscribe(self.tgincidentupdatetopic)
            client.subscribe(self.tguserupdatetopic)
            client.subscribe(self.tgbackupreceipttopic)
            client.publish(self.instancetopic,json.dumps({'message':'startup and initializing', \
            'hostname':str(socket.gethostname()),'localip':str(socket.gethostbyname(socket.gethostname()))}),)
            newconnection = True
          else:
            _LOGGER.warning("mqtt not connected")
        def on_disconnect(self,client, userdata, rc,properties=None,reasonCode=None, *args):
          _LOGGER.warning("mqtt disconnecting reason  "  +str(rc))
        def on_message(self,client, userdata, msg):
          print(str(msg.payload.decode()))
          if msg.topic == self.fsruserstopic:
            activeuserslist = None
            try:
              #con = sqlite3.connect(sqlitefilepath)
              #cur = con.cursor()
              tmpuserdata = json.loads(str(msg.payload.decode("utf-8","ignore")))
              if 'users' in tmpuserdata:
                tmpusers = tmpuserdata['users']
                if isinstance(tmpusers,list):
                  tmpusrlist = {}
                  for tmpusr in tmpusers:
                    tmpuserid = int(tmpusr['userid'])
                    if isinstance(tmpuserid,int):
                      tmpusrlist[tmpuserid] = tmpusr
                    #tmpusrlist.append(tmpusr['userid'])
                  with open(fsrusersjsonpath, 'w') as f: #write to file for backup
                    json.dump(tmpusrlist, f, indent=1)
                  fsrusers = tmpusrlist

            except Exception as e:
              print("bad mqtt userdata or sql insert "+str(e))
              print(traceback.format_exc())
          if msg.topic == self.tgchatstopic:
            try:
              con = sqlite3.connect(sqlitefilepath)
              cur = con.cursor()
              tmpuserdata = json.loads(str(msg.payload.decode("utf-8","ignore")))
              if 'data' in tmpuserdata and 'versionnode' in tmpuserdata:
                toTgQue.put({'topic':'tguserBackupFromServer','payload':tmpuserdata})

            except Exception as e:
              print("bad mqtt chatdata recieved"+str(e))
              print(traceback.format_exc())

          if msg.topic == self.tgbackupreceipttopic:
            try:
              tmpbackupreceipt = json.loads(str(msg.payload.decode("utf-8","ignore")))
              if 'backup_receipt' in tmpbackupreceipt.keys():
                print(tmpbackupreceipt['backup_receipt'])
                telegramusers.deleteBackupFile(tmpbackupreceipt['backup_receipt'])
            except Exception as e:
              print("bad mqtt chatdata recieved"+str(e))
              print(traceback.format_exc())

          if msg.topic == self.tgincidentupdatetopic:
            print("recieved incidentupdate")
            try:
              tmpincidentdata = json.loads(str(msg.payload.decode("utf-8","ignore")))
              if 'incidentid' in tmpincidentdata.keys():
                if not tmpincidentdata['incidentid'] in incidents.keys(): #new incident
                  incidents[int(tmpincidentdata['incidentid'])] = {'starttime':None,'message':{'full':'','censured':''},'responses':{}}
                  if 'starttime' in tmpincidentdata.keys():
                    incidents[int(tmpincidentdata['incidentid'])]['starttime'] = tmpincidentdata['starttime']
                  if 'melding' in tmpincidentdata.keys():
                    incidents[int(tmpincidentdata['incidentid'])]['message']['full'] = tmpincidentdata['melding']
                  if 'kort_melding' in tmpincidentdata.keys():
                    incidents[int(tmpincidentdata['incidentid'])]['message']['censured'] = tmpincidentdata['kort_melding']
                  if 'crew' in tmpincidentdata.keys():
                    incidents[int(tmpincidentdata['incidentid'])]['crew'] = tmpincidentdata['crew']
                  #print("mqtt will forward new incident:"+str(incidents[int(tmpincidentdata['incidentid'])]))
                  incidentsQue.put({'topic':'newincident','payload':incidents[int(tmpincidentdata['incidentid'])]})
                else:
                  print('recieved incident update on known incident')
                  print('old incidentdata:'+str(incidents))
                  print('new incidentdata:'+str(tmpincidentdata))
                  if 'crew' in tmpincidentdata.keys():
                    if 'minimum' in tmpincidentdata['crew'].keys() and 'assigned' in tmpincidentdata['crew'].keys():
                      if 'crew' in incidents[int(tmpincidentdata['incidentid'])].keys():
                        if 'minimum' in incidents[int(tmpincidentdata['incidentid'])]['crew'].keys() and 'assigned' in incidents[int(tmpincidentdata['incidentid'])]['crew'].keys():
                          before = (incidents[int(tmpincidentdata['incidentid'])]['crew']['assigned'] >= incidents[int(tmpincidentdata['incidentid'])]['crew']['minimum'])
                          now = (tmpincidentdata['crew']['assigned'] >= tmpincidentdata['crew']['minimum'])
                          print('incupdate status before/now '+str(before)+'/'+str(now))
                          if before != now:
                            if 'ts' in tmpincidentdata:
                              ts = datetime.fromtimestamp(tmpincidentdata['ts'], timezone.utc)
                            else:
                              ts = datetime.now(timezone.utc)
                            tmpmsg = ts.astimezone(ZoneInfo('Europe/Copenhagen')).strftime("%H:%M:%S")+' bemanding '+str(tmpincidentdata['crew']['minimum'])
                            if now:
                              tmpmsg += ' opfyldt'
                            else:
                              tmpmsg += ' ikke opfyldt'
                            incidentsQue.put({'topic':'assignedUpdate','payload':{'incidentid':int(tmpincidentdata['incidentid']),'message':tmpmsg}})

                      incidents[int(tmpincidentdata['incidentid'])]['crew'] = tmpincidentdata['crew']

            except Exception as e:
              print("bad mqtt incidentdata or sql insert "+str(e))
              print(traceback.format_exc())
          if msg.topic.split('/')[:-2] == self.tguserupdatetopic.split('/')[:-2]: #user update in incident
            try:
              userid = int(msg.topic.split('/')[-1])
              print("recieved incidentupdate on user "+str(userid))
              tmpuserpayload = json.loads(str(msg.payload.decode("utf-8","ignore")))
              tmpuserid = int(tmpuserpayload['userdata']['id'])
              tmpincidentid = int(tmpuserpayload['incidentid'])
              if tmpincidentid in incidents and tmpuserid > 0:
                if not tmpuserid in incidents[tmpincidentid]['responses'].keys():
                  incidents[tmpincidentid]['responses'][tmpuserid] = False
                #respons_danish = {'acknowledged':'kommer','pending':'afventer','rejected':'kommer IKKE'}
                tmpmessage = str(tmpuserpayload['kort_melding'])+' '+str(tmpuserpayload['userdata']['name'])
                tmpsend = False
                if not incidents[tmpincidentid]['responses'][tmpuserid] and tmpuserpayload['status'] == 'acknowledged':
                  tmpmessage += " kommer \u2705"
                  incidents[tmpincidentid]['responses'][tmpuserid] = True
                  tmpsend = True
                if incidents[tmpincidentid]['responses'][tmpuserid] and tmpuserpayload['status'] == 'rejected':
                  tmpmessage += " \uE333 kommer ikke \uE333"
                  incidents[tmpincidentid]['responses'][tmpuserid] = False
                  tmpsend = True
                if tmpsend:
                  incidentsQue.put({'topic':'userUpdate','payload':{'userid':tmpuserid,'message':tmpmessage}})
            except Exception as e:
              print("bad mqtt incidentdata or sql insert "+str(e))
              print(traceback.format_exc())
        def worker_loop(self):
          while not self.stop.is_set():
            while not fromTgQue.empty():
              quemes = fromTgQue.get()
              if isinstance(quemes,dict):
                if 'statusupdate' in quemes.keys():
                  sendmes = {'message':'status update'} | quemes['statusupdate']
                  self.client.publish(self.instancetopic,json.dumps(sendmes),)
                if 'tguserupdate' in quemes.keys():
                  sendmes = {'message':'telegram user update','returntopic':str(self.tgbackupreceipttopic)} | quemes['tguserupdate']
                  self.client.publish(self.instancetopic,json.dumps(sendmes),)
                if 'tguserupdaterequest' in quemes.keys():
                  sendmes = {'message':'telegram request user backup','returntopic':str(self.tgchatstopic)} | quemes['tguserupdaterequest']
                  self.client.publish(self.tgrequestbackuptopic,json.dumps(sendmes),)
            time.sleep(1)
          _LOGGER.info("mqtt worker shutingdown)")
          self.client.disconnect()
          time.sleep(1)
          _LOGGER.info("mqtt worker finished")

        def run(self):
          self.connect()
          self.worker_thread.start()
          self.client.loop_forever(retry_first_connection=True)
          _LOGGER.info("mqtt tread ended")


class ThreadTelebot(threading.Thread):
        def __init__(self, name,restart,stop):
                threading.Thread.__init__(self)
                self.name = name
                self.restart = restart
                self.stop = stop
                _LOGGER.debug("telegram thread started")
                con = sqlite3.connect(sqlitefilepath)
                cur = con.cursor()
                cur.execute('''CREATE TABLE IF NOT EXISTS tgfiles (rowid INTEGER PRIMARY KEY,file_unique_id STRING UNIQUE, base64 STRING)''')
                con.commit()
                con.close()

                # ⭐ HANDLERS SKAL LIGGE HER ⭐
                @bot.message_handler(commands=['start'])
                def send_welcome(message):
                        log1.connect()
                        log1.put([message])
                        msg = bot.reply_to(message, "Send mig kalde nummer til indentifikation?")
                        bot.register_next_step_handler(msg, process_identificer1)
                        log1.put([msg])
                        log1.disconnect()
                def process_identificer1(message):
                        log1.connect()
                        log1.put([message])
                        kaldenr = 0
                        chatid = message.chat.id
                        if chatid not in loginPenalty:
                                loginPenalty[chatid] = {'last_penaltytime':datetime.now(),'penaltyduration':timedelta(seconds=0)}
                        try:
                                if datetime.now() < loginPenalty[chatid]['last_penaltytime']+loginPenalty[chatid]['penaltyduration']:
                                        raise Exception('user', 'tried to login in penalty period')
                                for bmuserid,user in fsrusers.items():
                                        if user['kaldenr'] == int(message.text):
                                                kaldenr = user['kaldenr']
                                                userid = user['userid']
                                chatusrdata = telegramusers.getUserData(search_chatid=chatid)
                                if chatusrdata is None:
                                        if kaldenr>0:
                                                newuserdata = {'chatid': int(chatid),'roles':[{'userid':userid,'role':0}],'userdata':{'fromTG': message.from_user},'access_level':1,'state':1,'lastupdate':int(datetime.now(timezone.utc).timestamp())}
                                                updateres = telegramusers.updateUser(userdata=newuserdata)

                                                #create next question
                                                markup = telebot.types.ReplyKeyboardMarkup(row_width=2,one_time_keyboard=True)
                                                itembtn1 = telebot.types.KeyboardButton('brandmand')
                                                itembtn2 = telebot.types.KeyboardButton('familie')
                                                markup.add(itembtn1, itembtn2)
                                                msg = bot.send_message(chatid, "Hvilken rolle har du?:", reply_markup=markup)
                                                bot.register_next_step_handler(msg, process_identificer2)
                                        else:
                                                penaltydur = max(loginPenalty[chatid]['penaltyduration'].total_seconds(),10)*10
                                                print('previous penalty dur was:'+str(loginPenalty[chatid]['penaltyduration'].total_seconds())+' now it up to:'+str(penaltydur))

                                                loginPenalty[chatid] = {'last_penaltytime':datetime.now(),'penaltyduration':timedelta(seconds=penaltydur)}
                                                raise Exception('user', 'invalid')
                                else:
                                        msg = bot.send_message(chatid, "Du er allerede oprettet\r\nkontakt stationens telegram administrator hvis der er noget der skal ændres")

                        except Exception as e:
                                msg = bot.send_message(chatid, "ikke verificeret\r\nvent "+str(int(loginPenalty[chatid]['penaltyduration'].total_seconds()))+' sekunder og prøv igen')
                                print("Exeption indentifier stage 1 "+str(e))
                                print(traceback.format_exc())
                        log1.put([msg])
                        log1.disconnect()
                def process_identificer2(message):
                        log1.connect()
                        log1.put([message])
                        try:
                                want_level = 0
                                want_rolle = 0
                                if message.text == 'brandmand':
                                        want_level = 2
                                        want_rolle = 2
                                if message.text == 'familie':
                                        want_level=1
                                        want_rolle=1
                                if want_rolle==0:
                                        raise Exception('rolle', 'invalid')
                                #update some sql
                                userdata = telegramusers.getUserData(search_chatid=message.chat.id)
                                if isinstance(userdata,dict):
                                        for idx,role in enumerate(userdata['roles']):
                                                if role['role'] == 0:
                                                        userdata['roles'][idx]['role'] = want_rolle
                                userdata['access_level'] = want_level
                                updateres = telegramusers.updateUser(userdata=userdata)

                                botrepl = bot.send_message(message.chat.id, "Okay alt er ok nu..\r\nDu vil modtage relevante beskeder ved udkald")

                        except Exception as e:
                                botrepl = bot.send_message(message.chat.id, "Nej det lykkedes ikke.")
                        log1.put([botrepl])
                        log1.disconnect()

                @bot.message_handler(commands=['help'])
                def send_help(message):
                        log1.connect()
                        log1.put([message])
                        messageList = []
                        try:
                                userdata = telegramusers.getUserData(search_chatid=message.chat.id,alldata=True)
                                calllist = telegramusers.getCallList(validusers=fsrusers.keys()) # {"call":{chatid:messagetype},"update":{fsruserid:[{"chatid":None,"massagetype":0}]}} #messa>
                                bmuserid = None
                                print('userdata for user asking foir help: '+str(userdata))
                                if isinstance(userdata,dict):
                                        if 'access_level' in userdata.keys():
                                                if userdata['access_level']: # find evt. brandmands userid
                                                        for role in userdata['roles']:
                                                                if role['role'] == 2:
                                                                        bmuserid = role['userid']
                                        tmpmsg = "modtager førstemelding:"
                                        if userdata['chatid'] in calllist['call'].keys(): #tjek om får førstemelding
                                                tmpmsg += " Ja"
                                        else:
                                                tmpmsg += " Nej"
                                        messageList.append(str(tmpmsg))
                                        messageList.append("modtager tilmeldingsbesked:")
                                        if isinstance(bmuserid,int): #asking user is brandmand
                                                if bmuserid in calllist['update'].keys(): #tjek om får tilmeldings notifikation
                                                        tmpupdates = calllist['update'][bmuserid]
                                                        for tmpupd in tmpupdates:
                                                                tmpname = ""
                                                                guestuserdata = telegramusers.getUserData(search_chatid=tmpupd['chatid'],alldata=True)
                                                                if 'userdata' in guestuserdata:
                                                                        if 'fromTG' in guestuserdata['userdata']:
                                                                                if 'first_name' in guestuserdata['userdata']['fromTG']:
                                                                                        tmpname += str(guestuserdata['userdata']['fromTG']['first_name'])
                                                                                if 'last_name' in guestuserdata['userdata']['fromTG']:
                                                                                        tmpname += " "+str(guestuserdata['userdata']['fromTG']['last_name'])
                                                                messageList.append(str(tmpname))
                                        if True: #asking user might be family
                                                for tmpbmuserid,tmpupdusers in calllist['update'].items():
                                                        for tmpupduser in tmpupdusers:
                                                                if userdata['chatid'] == tmpupduser['chatid']:
                                                                        tmpname = "Du modtager besked når "
                                                                        guestuserdata = telegramusers.getUserData(search_chatid=tmpupduser['chatid'],alldata=True)
                                                                        print("leder efter "+str(type(tmpbmuserid))+" i:"+str(fsrusers.keys()))
                                                                        if tmpbmuserid in fsrusers.keys():
                                                                                if 'fornavn' in fsrusers[tmpbmuserid]:
                                                                                        tmpname += str(fsrusers[tmpbmuserid]['fornavn'])
                                                                                if 'efternavn' in fsrusers[tmpbmuserid]:
                                                                                        tmpname += " "+str(fsrusers[tmpbmuserid]['efternavn'])
                                                                        tmpname += " melder til/fra et udkald"
                                                                        messageList.append(str(tmpname))
                                else:
                                        raise Exception('user', 'invalid')
                                if len(messageList) > 0:
                                        msgreturn = '\r\n'.join(messageList)
                                else:
                                        msgreturn = "Der er noget galt. din profil er ikke koblet til en brandmand"
                                botrepl = bot.reply_to(message, msgreturn)

                        except Exception as e:
                                botrepl = bot.send_message(message.chat.id, "Nej det lykkedes ikke.")
                                print("bad /help response returned to user"+str(e))
                                print(traceback.format_exc())
                        finally:
                                log1.put([botrepl])
                                log1.disconnect()

                @bot.message_handler(commands=['paycheck'])
                def send_paycheck1(message):
                        log1.connect()
                        log1.put([message])
                        #con = sqlite3.connect('./storage/users.db')
                        #cur = con.cursor()
                        ##check user
                        #cur.execute("SELECT kaldenr FROM user WHERE chatid = ? AND rolle = 2 AND state = 2",(message.chat.id,))
                        #rows = cur.fetchall()
                        if False:
                                for kaldenr, in rows:
                                        payChk = payCheck(kaldenr)
                                        latest = payChk.getLatestMonths(4)
                                        #create next question
                                        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
                                        markup.add(telebot.types.KeyboardButton(latest[0]),telebot.types.KeyboardButton(latest[1]),telebot.types.KeyboardButton(latest[2]),telebot.types.KeyboardButton(latest[3]).telebot.types.KeyboardButton(latest[4]))
                                        msg = bot.send_message(message.chat.id, "Hvilken måned vil du se?:", reply_markup=markup)
                                        bot.register_next_step_handler(msg, send_paycheck2)
                        else:
                                msg = bot.reply_to(message, "ingen info")

                        log1.put([msg])
                        log1.disconnect()

                def send_paycheck2(message):
                        log1.connect()
                        log1.put([message])
                        if len(rows)==1:
                                for kaldenr, in rows:
                                        payChk = payCheck(kaldenr)
                                        dates = payChk.getMonth(message.text)
                                        test1 = payChk.getUdkald(dates['begin'],dates['end'])
                                        botrepl = bot.reply_to(message, test1,parse_mode='HTML')
                                        log1.put([botrepl])
                        log1.disconnect()

                @bot.message_handler(commands=['users'])
                def show_users(message):
                        log1.connect()
                        log1.put([message])
                        loginPenalty[message.chat.id] = {'last_penaltytime':datetime.now(),'penaltyduration':timedelta(seconds=123)}
                        userdata = []
                        #with open("./storage/users.json", "r") as read_file:
                        #       userdata = json.load(read_file)
                        #con = sqlite3.connect(sqlitefilepath)
                        #cur = con.cursor()
                        #cur.execute("SELECT roles,access_level FROM user WHERE chatid = ? AND state = 2",(message.chat.id,))
                        #rows = cur.fetchone()
                        #[{'userid': 37370, 'role': 2}]
                        if rows and False:
                                if rows[1] == 2: #admin
                                        pass
                                elif rows[1] == 1: #alm bruger
                                        pass


                                for roles,access_level,state in rows:
                                        if brRolle==2:
                                                if kaldenr in admins:
                                                        #get user list
                                                        rolleStr = {1:'F',2:'B'}
                                                        stateStr = {1:'V',2:'+',3:'-'}
                                                        cur.execute("SELECT kaldenr,rolle,state,userdata FROM user ORDER BY kaldenr ASC,rolle DESC")
                                                        rows2 = cur.fetchall()
                                                        toTelegram = ''
                                                        lastkaldenr=0
                                                        for kaldenr,rolle,state,userdataStr in rows2:
                                                                if kaldenr!=lastkaldenr and lastkaldenr!=0:
                                                                        pass
                                                                        #toTelegram += "\r\n......\r\n"
                                                                userdataStr2 = eval(userdataStr)
                                                                for user in userdata:
                                                                        if user['kaldenr'] == kaldenr:
                                                                                indentation =''
                                                                                if rolle==1:
                                                                                        indentation = '  '
                                                                                if rolle==2:
                                                                                        indentation = '     '
                                                                                if kaldenr!=lastkaldenr:
                                                                                        navn = user['fornavn']+' '+user['efternavn']+'\r\n'
                                                                                else:
                                                                                        navn = ''
                                                                                userStr = indentation+' '.join(filter(None,(userdataStr2['first_name'],userdataStr2['last_name']))) #      'username': None
                                                                                toTelegram += str(stateStr[state])+rolleStr[rolle]+navn+''+userStr+'\r\n'
                                                                lastkaldenr=kaldenr
                                                        #show penalty
                                                        for cid,penalty in loginPenalty.items():
                                                                print(penalty)
                                                                toTelegram += penalty['last_penaltytime'].strftime("%d/%m %H:%M:%S")+' ¤ '+str(penalty['penaltyduration'].total_seconds())+'s'
                                                        botrepl = bot.reply_to(message, toTelegram)
                                                        log1.put([botrepl])
                                                else: #alm brandmand
                                                        cur.execute("SELECT rolle,userdata FROM user WHERE kaldenr = ? AND rolle=1  AND state = 2",(kaldenr,))
                                                        rows2 = cur.fetchall()
                                                        toTelegram = 'Familie:\r\n'
                                                        for rolle,userdataStr in rows2:
                                                                userdataStr2 = eval(userdataStr)
                                                                userStr = ' '.join(filter(None,(userdataStr2['first_name'],userdataStr2['last_name'])))
                                                                toTelegram += userStr+'\r\n'
                                                        botrepl = bot.reply_to(message, toTelegram)
                                                        log1.put([botrepl])
                                        else: #alm familie
                                                for user in userdata:
                                                        if user['kaldenr'] == kaldenr:
                                                                navn = user['fornavn']+' '+user['efternavn']
                                                                botrepl = bot.reply_to(message, "familie til "+navn)
                                                                log1.put([botrepl])

                        log1.disconnect()
                        #con.commit()
                        #con.close()

                @bot.message_handler(func=lambda message: True)
                def echo_all(message):
                        if not incidentsQue.empty():
                                try:
                                        newmsg=simpleQue.get()
                                        print('New fire message'+str(newmsg))
                                except:
                                        print('did not recieve the Fire message')
                        else:
                                print('Køen er tom')
                        log1.connect()
                        log1.put([message])
                        msgreply = False
                        userinfo = self.getUserInfo(message.chat.id)
                        #check om det er strandnr
                        print(userinfo)
                        #fStrand = strandFunc.findStrandNr(message.text)
                        fStrand = False
                        if fStrand is not False:
                                botrepl = bot.reply_to(message, fStrand)
                                msgreply = True
                        else:
                                if 'roles' in userinfo:
                                        if isinstance(userinfo['roles'],list):
                                                if len(userinfo['roles']) >= 1:
                                                        if lastFsrHeartbeat is not None:
                                                                if lastFsrHeartbeat>datetime.now()-timedelta(seconds=10):
                                                                        FSRstatus = "FSR is online"
                                                                else:
                                                                        if userinfo['kaldenr'] in admins:
                                                                                FSRstatus = "FSR is offline since "+str(lastFsrHeartbeat.strftime("%d/%m %H:%M:%S"))
                                                                        else:
                                                                                FSRstatus = "FSR is offline"
                                                        else:
                                                                FSRstatus = "FSR status unknown"
                                                else:
                                                        FSRstatus = 'empty user setup'
                                        else:
                                                FSRstatus = 'bad user setup'
                                else:
                                        FSRstatus = 'invalid user'
                                botrepl = bot.reply_to(message, FSRstatus)
                        log1.put([botrepl])
                        log1.disconnect()
                        if not 'roles' in userinfo:
                                send_welcome(message)

                        print("færdig")


        def getUserInfo(self, chatid):
                toReturn = {}
                con = sqlite3.connect(sqlitefilepath)
                cur = con.cursor()
                #check user
                cur.execute("SELECT roles,state FROM user WHERE chatid = ? LIMIT 1",(chatid,))
                rows = cur.fetchone()
                tguserdata = telegramusers.getUserData() #{'roles':tguser['roles'],'state':tguser['state']}
		#[{'userid': 37370, 'role': 2}]
                try:
                  if isinstance(tguserdata,dict):
                    toReturn['roles'] = []
                    roles = json.loads(tguserdata['roles'])
                    if isinstance(roles,list) and tguserdata['state'] == 2:
                      if len(roles) >= 1:
                        for rolle in roles:
                          if 'userid' in rolle.keys() and 'role' in rolle.keys():
                            cur.execute("SELECT userid,kaldenr,fornavn || ' ' || efternavn AS navn FROM FSRusers WHERE userid = ? LIMIT 1",(rolle['userid'],))
                            fsruser = cur.fetchone()
                            print(fsruser)
                            if fsruser:
                              toReturn['roles'].append({'userid':int(fsruser[0]),'fsruserdata':{'kaldenr':fsruser[1],'navn':fsruser[2]},'role':rolle['role']})
                            else:
                              print("fsruser not found")
                          else:
                            print("role format invalid")
                      else:
                        print("role list empty")
                    else:
                      print("chatid disabled or role not list")
                  else:
                    print("chatid not known")
                except Exception as e:
                  print("bad user roles chat("+str(chatid)+") "+str(e))
                  print(traceback.format_exc())

		#.fetchall()
		#if len(rows)==1:
	#		for roles,state in rows:
#				toReturn = {'roles':json.loads(roles)}
                con.commit()
                con.close()
                if debugFlag:
                  print("chat:"+str(chatid)+" data:"+str(toReturn))
                return toReturn

	
        def run(self):
          _LOGGER.debug("telegram loop started")
          while not self.stop.is_set():
            try:
              bot.polling(non_stop=False, timeout=60,long_polling_timeout=60)
            except Exception as e:
              _LOGGER.debug("Telegram polling error:", e)
              time.sleep(1)
          _LOGGER.debug("telegram loop stopped")
          #bot.infinity_polling(interval=0,timeout=60)


reboot = threading.Event()
stop_event = threading.Event()

mqttServiceT = ThreadMqttService("mqttservice",reboot,stop_event)
teleT = ThreadTelebot("telbot1",reboot,stop_event)
mqttServiceT.daemon= True
teleT.daemon= True

mqttServiceT.start()
teleT.start()

nextreboot = datetime.now().replace(hour=1,minute=random.randrange(5,55))+timedelta(days=1)
time.sleep(0.65)
messagestructure = None

def sendTG(chatMessage,chatid,debug=False):
  msg = None
  try:
    if True:
      _LOGGER.info('sending message:$'+chatMessage+'$ to chatid('+str(chatid)+')')
      msg = bot.send_message(chatid, chatMessage)
      #self.sentMessages.append(msg)
    else:
      _LOGGER.info('no message is sent to chatid('+str(chatid)+')')
  except telebot.apihelper.ApiTelegramException:
    _LOGGER.info('will delete this user(chatid: '+str(chatid)+'')
  except Exception as e:
    _LOGGER.error('error when sending message '+str(e))
  finally:
    pass
  return msg




while nextreboot>datetime.now():
  #print('.',end='')
  while not incidentsQue.empty() and messagestructure is not None:
    try:
      if messagestructure is not None:
        newmsg=incidentsQue.get()
        _LOGGER.info('New fire message'+str(newmsg))
        #{'starttime': 1760611538, 'message': {'full': 'STR 8M 1289 2290 2291 BBVi - Bygningsbrand - Villa/Rækkehus Baunevænget 93 7600 Struer røg fra tag og flammer', 'censured': 'Bygning>
        if newmsg['topic'] == 'newincident':
          for chatid,role in messagestructure['call'].items():
            chatMessage = 'Brand'
            incidentdt = datetime.now(timezone.utc)
            if 'starttime' in newmsg['payload'].keys():
              incidentdt = datetime.fromtimestamp(int(newmsg['payload']['starttime']), tz=timezone.utc)
            brandbilemoji = ''
            if role == 1: #familie
              chatMessage = incidentdt.astimezone(ZoneInfo('Europe/Copenhagen')).strftime("%d %b %H:%M:%S ")+brandbilemoji+"\r\n"+newmsg['payload']['message']['censured']
            if role == 2: #brandmand
              chatMessage = incidentdt.astimezone(ZoneInfo('Europe/Copenhagen')).strftime("%d %b %H:%M:%S ")+brandbilemoji+"\r\n"+newmsg['payload']['message']['full']
            tmpsendtelegram = sendTG(chatMessage,chatid)

        if newmsg['topic'] == 'assignedUpdate': #send full/not full to firemen
         #'payload':{'incidentid':int(tmpincidentdata['incidentid']),'message':tmpmsg}}
         for chatid,role in messagestructure['call'].items():
           if role == 2:
             tmpsendtelegram = sendTG(newmsg['payload']['message'],chatid)

        if newmsg['topic'] == 'userUpdate': #send updated userdata to family
         #'payload':{'userid':tmpuserid,'message':tmpmessage}}
         tmpuserid = newmsg['payload']['userid']
         if tmpuserid in messagestructure['update'].keys():
           for chatdata in messagestructure['update'][tmpuserid]:
             tmpsendtelegram = sendTG(newmsg['payload']['message'],chatdata['chatid'])


    except Exception as e:
       _LOGGER.warn("failed to handle Fire message properly "+str(e))
       _LOGGER.warn(traceback.format_exc())
  time.sleep(0.8)
  if True:
    if not stop_event.is_set():
      if not mqttServiceT.is_alive():
        raise RuntimeError("MQTT thread died")
      if not teleT.is_alive():
        raise RuntimeError("Telegram thread died")
    else:
      if teleT.is_alive(): #try to stop telegram
        bot.stop_polling()
        bot.stop_bot()
        _LOGGER.info("tried to stop telegram connection/thread")
        time.sleep(3)

    if int(datetime.now(timezone.utc).timestamp()) % 116 == 0: #166 send status ping to nodered
      cntbrandmænd = None
      cntfamilie = None
      if isinstance(messagestructure,dict):
        if 'call' in messagestructure.keys():
          cntbrandmænd = len(messagestructure['call'])
        if 'update' in messagestructure.keys():
          cntfamilie = len(messagestructure['update'])
      botname = None
      try:
        botdetails = bot.get_me()
        if isinstance(botdetails,telebot.types.User):
          botname = botdetails.username
      except:
        _LOGGER.warn("failed to get bot details: "+str(traceback.format_exc()))
        pass 
      fromTgQue.put({'statusupdate':{'stationname':stationname,'instance':instanceid,'calls':cntbrandmænd,'updates':cntfamilie,'listens':str(mqttServiceT.tgincidentupdatetopic),'botname':str(botname)}})
    if int(datetime.now(timezone.utc).timestamp()) % 226 == 0: #send tg user backup files if i have any
      #print(telegramusers.getJson())
      chkbackupfiles = telegramusers.getBackupfiles()
      if isinstance(chkbackupfiles,dict):
        if 'files' in chkbackupfiles.keys():
          if isinstance(chkbackupfiles['files'],list):
            fromTgQue.put({'tguserupdate':{'files':chkbackupfiles['files']}})
          #print('backupfiles:_'+str(chkbackupfiles))

    if int(datetime.now(timezone.utc).timestamp()) % 3456 == 0: #3456 ask for userdata update from telegram
      #get info for current users
      try:
        users = telegramusers.get()
        con = sqlite3.connect(sqlitefilepath)
        cur = con.cursor()
        for tguser in users['data']['telegramusers']:
          time.sleep(0.2)
          try:
            usrdata = bot.get_chat(tguser['chatid'])
            if isinstance(usrdata,telebot.types.ChatFullInfo):
              usrdatadict = usrdata.__dict__
              usrdatadict.pop('accepted_gift_types')
              if 'photo' in usrdatadict.keys():
                if isinstance(usrdatadict['photo'],telebot.types.ChatPhoto):
                  #_LOGGER.debug("fileid: "+str(usrdatadict['photo'].big_file_id))
                  imgfileobj = bot.get_file(usrdatadict['photo'].big_file_id)
                  #_LOGGER.debug("fileobj: "+str(imgfileobj))

                  #_LOGGER.debug("filedata: "+imgfileobj.download_as_bytearray())
                  cur.execute("SELECT rowid FROM tgfiles WHERE file_unique_id = ? LIMIT 1",(str(imgfileobj.file_unique_id),))
                  rows = cur.fetchone()
                  if not rows: # some invalid result
                    cur.execute("INSERT INTO tgfiles (file_unique_id,base64) VALUES (?,?)", (str(imgfileobj.file_unique_id),str(b64encode(bot.download_file(imgfileobj.file_path)).decode("utf-8"))))

                  file_data = bot.download_file(imgfileobj.file_path)
                  #  r = requests.get("", timeout=20)
                  #  r.raise_for_status()  # fejler pænt hvis 404/500 osv.
                  b64 = b64encode(file_data).decode("utf-8")
                  #_LOGGER.debug("filedata: "+str(file_data))
                  #_LOGGER.debug("b64: "+str(b64))
                  usrdatadict['TgPhoto'] = str(imgfileobj.file_unique_id)
                usrdatadict.pop('photo')

              #print(dir(usrdata))
              filtered_usrdata = {k: v for k, v in usrdatadict.items() if v is not None}
              #_LOGGER.debug(filtered_usrdata)
              newuserdata = {'chatid': int(tguser['chatid']),'userdata':{'fromTG': filtered_usrdata}}
              keystoupdate = {'userdata':{'fromTG':True}}
              _LOGGER.debug("userdata:"+str(newuserdata)+" keys to update:"+str(keystoupdate))
              telegramusers.updateUser(userdata=newuserdata,updatekeys=keystoupdate)
            else:
              _LOGGER.warning("wrong chatdata for chat("+str(tguser['chatid'])+"): "+str(usrdata)+" type:"+str(type(usrdata)))
          except telebot.apihelper.ApiTelegramException:
            _LOGGER.warning("user with chatid: "+str(tguser['chatid'])+" not working") #+str(traceback.format_exc())) 
        con.commit()
        con.close()
      except:
        _LOGGER.warning("failed to get user details from tg: "+str(traceback.format_exc()))
        pass


    if int(datetime.now(timezone.utc).timestamp()) % 56 == 0: #56 ask for userdata update from nodered
      tmptgusers = telegramusers.get()
      request = False
      waittime = 3600 #3600
      if tmptgusers['versionnode']['parent'] is None:
        request = True
        _LOGGER.info('requesting tguser update from server, as this i orthaned')
      else:
        if int(datetime.now(timezone.utc).timestamp()) % (56*50)  == 0: #ask for userdata update from nodered
          if int(tmptgusers['versionnode']['timestamp'])+waittime < int(datetime.now(timezone.utc).timestamp()): # over 1 time siden seneste lokale ændring
            request = True
            _LOGGER.info('requesting tguser update from server, as current version timestamp is '+str(int(tmptgusers['versionnode']['timestamp']))+' and its time for update')
          else:
            _LOGGER.debug("local tguser has been changed "+str(int(tmptgusers['versionnode']['timestamp']))+" waiting for changed to settle ("+str(int(datetime.now(timezone.utc).timestamp())-int(tmptgusers['versionnode']['timestamp'])+waittime)+"s.) before requesting/updating server")
      if request is True:
        fromTgQue.put({'tguserupdaterequest':{'stationname':str(stationname),'current_hash':str(tmptgusers['versionnode']['hash'])}})


    if int(datetime.now(timezone.utc).timestamp()) % 222 == 0 or messagestructure is None: #create message structure with some interval to be prepared
      #_LOGGER.debug("3. FSR users:"+str(fsrusers))
      messagestructure = telegramusers.getCallList(validusers=fsrusers.keys())
      _LOGGER.debug(messagestructure)
  if True: 
    while not toTgQue.empty():
      try:
        newUpdate=toTgQue.get()
        if newUpdate['topic'] == 'tguserBackupFromServer': #userdata from nodered
          #check if it newer/better than current version
          _LOGGER.debug("#######new######"+str(newUpdate['payload']['versionnode']))
          _LOGGER.debug("#######old######"+str(telegramusers.get()['versionnode']))
          updateres = telegramusers.checkUpdate(newUpdate['payload'])
          _LOGGER.info('tguser update result:'+str(updateres))
          _LOGGER.debug(telegramusers.get()['versionnode'])
      except Exception as e:
        print("failed to handle update from server properly "+str(e))
        print(traceback.format_exc())



#send melding til brandmænd
    #                                    cur.execute("SELECT chatid FROM user WHERE access_level = 2 AND state = 2")
    #                                    rows = cur.fetchall()
    #                                    timestamps = [datetime.now().strftime('%d %b %H:%M:%S.%f')]
    #                                    for chatid, in rows:	
    #                                            brandbilemoji = ''
    #                                            timestamps.append(datetime.now().strftime('%H:%M:%S.%f'))
    #                                            chatMessage = time.strftime("%d %b %H:%M:%S ")+brandbilemoji+"\r\n"+incText
    #                                            tmpsendtelegram = self.sendTG(chatMessage,chatid,tmpdebug)


_LOGGER.debug("Complete service terminated")
