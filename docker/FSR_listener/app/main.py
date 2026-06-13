#!/usr/bin/env python3
from pyfireservicerota import FireServiceRota, FireServiceRotaIncidents, ExpiredTokenError, InvalidTokenError, InvalidAuthError
import paho.mqtt.client as mqtt
from datetime import datetime,timedelta,timezone
import os
import ssl
import queue
import logging
import random
import string
import sys
import json
import time
import socket

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def handleFSrtoken(tmpapi, renew=False):
  #example {'access_token': 'sB48pF6lQktR0nL1vOIAko-UuVaM0Vj793igyw9zaq8C-ohZHY', 'token_type': 'Bearer', 'expires_in': 1209600,
  #         'refresh_token': 'AjXcvERlQM0Vj793igIlcJL_-1ak2ZxN0at5-HpJnYI', 'created_at': 1759344156}
  oldtokendata = api._token_info
  tmprenew = True
  renewtoken = None
  newtoken_info = None
  if isinstance(oldtokendata,dict):
    if 'access_token' in oldtokendata.keys() and 'expires_in' in oldtokendata.keys() and 'created_at' in oldtokendata.keys():
      if datetime.now(timezone.utc).timestamp() < oldtokendata['created_at']+(oldtokendata['expires_in']*0.5) and not renew:
        _LOGGER.debug("Token was ok - no need to refresh")
        tmprenew = False
    if tmprenew:
      if 'refresh_token' in oldtokendata.keys():
        _LOGGER.info("Trying to refresh Token")
        try:
          newtoken_info = api.refresh_tokens()
        except InvalidAuthError:
          newtoken_info = None
        if not token_info:
          _LOGGER.error("Failed to get renew access tokens with refresh token")
        if isinstance(newtoken_info,dict):
          if 'access_token' in newtoken_info.keys() and 'expires_in' in newtoken_info.keys() and 'created_at' in newtoken_info.keys():
            if datetime.now(timezone.utc).timestamp() < newtoken_info['created_at']+(newtoken_info['expires_in']*0.5):
              tmprenew = False
  if tmprenew:
    _LOGGER.info("Trying to get a new Token with credential")
    try:
      newtoken_info = api.request_tokens()
    except InvalidAuthError:
      newtoken_info = None
    if not newtoken_info:
      _LOGGER.error("Failed to get access tokens with credentials")
  else:
    return oldtokendata
  if newtoken_info is not None and isinstance(newtoken_info,dict):
    if 'access_token' in newtoken_info.keys() and 'expires_in' in newtoken_info.keys() and 'created_at' in newtoken_info.keys():
      with open('../tmp/FSRtoken.json', 'w') as f:
        json.dump(newtoken_info, f)
    return newtoken_info


service_priority = random.randrange(10,100)
exclude_users = []
include_groups = []
fsrLogin = {'username':'','password':''}
mqttLogin = {'username':None,'password':None}
basemqtttopic_list = ["unknown","fromFSR"]
instanceid = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
token_info = None


configfilepath = '../data/config.json'
if os.path.isfile(configfilepath):
 with open(configfilepath) as config_file:
  config_content = config_file.read()
  config = json.loads(config_content)
  if 'priority' in config:
    try:
      service_priority = max(1,int(config['priority']))
    except:
      print("unable to set app priority")
  if 'mqtt' in config:
    if 'stationname' in config['mqtt']:
      basemqtttopic_list[0] = str(config['mqtt']['stationname'])
    if 'username' in config['mqtt'] and 'password' in config['mqtt']:
      mqttLogin = {'username':config['mqtt']['username'],'password':config['mqtt']['password']}
    if 'server' in config['mqtt']:
      mqttLogin['host'] = str(config['mqtt']['server'])
    if 'port' in config['mqtt']:
      mqttLogin['port'] = str(config['mqtt']['port'])
  if 'fireservicerota' in config:
    if 'username' in config['fireservicerota'] and 'password' in config['fireservicerota']:
       fsrLogin = {'username':config['fireservicerota']['username'],'password':config['fireservicerota']['password']}
    if 'exclude_user' in config['fireservicerota']:
       exclude_users = config['fireservicerota']['exclude_user']
    if 'include_groups' in config['fireservicerota']:
       include_groups = config['fireservicerota']['include_groups']
  _LOGGER.info('config file found. it had '+str(len(config))+' keys')
  _LOGGER.debug('config content'+str(config_content))

incidenttopic = "/".join(basemqtttopic_list)+"/"

tokenfilepath = '../tmp/FSRtoken.json'
if os.path.isfile(tokenfilepath):
  try:
    with open(tokenfilepath) as tokenfile:
      tokencontent = tokenfile.read()
      tokenjson = json.loads(tokencontent)
    if isinstance(tokenjson,dict):
      token_info = tokenjson
      _LOGGER.info('reusing old token info:'+str(token_info))
  except:
    _LOGGER.error('failed to get tokenfile or content')


simpleQue = queue.SimpleQueue()

api = FireServiceRota(base_url="www.fireservicerota.co.uk",username=fsrLogin['username'],password=fsrLogin['password'],token_info=token_info)


token_info = handleFSrtoken(api, renew=False)

#try:
#  token_info = api.request_tokens()
#except InvalidAuthError:
#  token_info = None
#if not token_info:
#  _LOGGER.error("Failed to get access tokens")
#wsurl = f"wss://www.fireservicerota.co.uk/cable?access_token={token_info['access_token']}"
#_LOGGER.debug("got FSR access token:"+str(token_info['access_token']))

print('######')
print(token_info)
# Get user availability (duty)
try:
   #print(api.get_availability('Europe/Amsterdam'))
   pass
except ExpiredTokenError:
   _LOGGER.debug("Tokens are expired, refreshing")
   try:
       token_info = api.refresh_tokens()
   except InvalidAuthError:
       _LOGGER.debug("Invalid refresh token, you need to re-login")
except InvalidTokenError:
   _LOGGER.debug("Tokens are invalid")
   try:
       token_info = api.refresh_tokens()
   except InvalidAuthError:
       _LOGGER.debug("Invalid refresh token, you need to re-login")

# Get incident response status for incident with id 123456

incident_id = 123456

try:
   #print(api.get_incident_response(incident_id))
   pass
except ExpiredTokenError:
   _LOGGER.debug("Tokens are expired, refreshing")
   try:
       token_info = api.refresh_tokens()
   except InvalidAuthError:
       _LOGGER.debug("Invalid refresh token, you need to re-login")
except InvalidTokenError:
   _LOGGER.debug("Tokens are invalid")
   try:
       token_info = api.refresh_tokens()
   except InvalidAuthError:
       _LOGGER.debug("Invalid refresh token, you need to re-login")


# Set incident response to acknowlegded (False = 'rejected')
try:
   #api.set_incident_response(id, True)
   pass
except ExpiredTokenError:
   _LOGGER.debug("Tokens are expired, refreshing")
   try:
       token_info = api.refresh_tokens()
   except InvalidAuthError:
       _LOGGER.debug("Invalid refresh token, you need to re-login")
except InvalidTokenError:
   _LOGGER.debug("Tokens are invalid")
   try:
       token_info = api.refresh_tokens()
   except InvalidAuthError:
       _LOGGER.debug("Invalid refresh token, you need to re-login")

def getUsers(tmpapi):
  #create list of users
  users = tmpapi._request("GET","users","get users",{"page": 1,"per_page":1000},None,False)
  users_list = []
  admins_list = []
  for user in users:
    if 'personnel_number' in user:
      if user['personnel_number'] not in {'',' '}:
        memberok = False
        if 'memberships' in user.keys():
          for membership in user['memberships']:
            if membership['group_id'] in include_groups:
              memberok = True
              #self.membershipids[user['id']] = {'name':user['first_name']+' '+user['last_name'],'membership':membership['id']}
        if memberok:
          if not user['id'] in exclude_users:
            users_list.append({'kaldenr':int(user['personnel_number']),'userid':int(user['id']),'fornavn':user['first_name'],'efternavn':user['last_name']})
            #print("//////"+str(user['id'])+": "+user['first_name']+" "+user['last_name'])
          else:
            #print("####excluded "+str(user['id'])+": "+user['first_name']+" "+user['last_name'])
            pass
  loginuserdata = tmpapi.get_user()
  if isinstance(loginuserdata,dict):
    if 'id' in loginuserdata.keys():
      admins_list.append(int(loginuserdata['id']))
  #with open('./storage/users.json', 'w') as outfile:
  #  json.dump(users_dict, outfile, indent=2)
  return {'users':users_list,'admins':admins_list}



# Connect to websocket channel for incidents
if isinstance(token_info,dict):
  if 'access_token' in token_info.keys():
    wsurl = f"wss://www.fireservicerota.co.uk/cable?access_token={token_info['access_token']}"
  else:
    time.sleep(60)
    sys.exit('No access_token obtained')
else:
  time.sleep(230)
  sys.exit('No token info obtained')

class FireService():
    def __init__(self, url):
        self._data = None
        self.listener = None
        self.url = url
        self.incidents_listener()
    def on_message(self, data):
        _LOGGER.debug("info Mesg: %s", data)
        simpleQue.put({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'source':'message','payload':data})

    def on_incident(self, data):
        _LOGGER.debug("INCIDENT: %s", data)
        simpleQue.put({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'source':'incident','payload':data})
        self._data = data
    def on_statechange(self,data):
        simpleQue.put({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'source':'connection','payload':data})

    def incidents_listener(self):
        """Spawn a new Listener and links it to self.on_incident."""
        self.listener = FireServiceRotaIncidents(on_incident=self.on_incident,on_message=self.on_message,on_statechange=self.on_statechange)
        _LOGGER.debug("Starting incidents listener")
        self.listener.start(url=self.url)

newconnection = False
runninginstance = {'instance':None,'ts':None,'priority':None,'expiresAt':None}
takeover = datetime.now(timezone.utc)+timedelta(seconds=service_priority+30)

def on_connect(client, userdata, flags, rc, properties):
   global newconnection
   if rc==0:
      _LOGGER.debug("mqtt connected ok")
      client.subscribe(incidenttopic+'active')
      client.publish(incidenttopic+'instance/'+str(instanceid),json.dumps({'message':'startup and initializing', \
'hostname':str(socket.gethostname()),'localip':str(socket.gethostbyname(socket.gethostname())), \
'user':str(fsrLogin['username'])}),)
      newconnection = True
   else:
      _LOGGER.warning("mqtt not connected")
def on_disconnect(client, userdata, rc, properties):
   _LOGGER.warning("mqtt disconnecting reason  "  +str(rc))
   newconnection = False
def on_message(client, userdata, msg):
   global runninginstance
   global takeover
   print(str(msg.payload.decode()))
   if msg.topic.split("/")[-1] == "active":
     try:
       addseconds = 0
       tmpactive = json.loads(str(msg.payload.decode("utf-8","ignore")))
       if all(key in tmpactive for key in ('instance', 'expiresAt')):
         if 'ts' in tmpactive.keys():
           activebeat = datetime.fromtimestamp(tmpactive['ts'], tz=timezone.utc)
           runninginstance['ts'] = tmpactive['ts']
           if activebeat < datetime.now(timezone.utc)-timedelta(seconds=1):
             addseconds += 10
             if activebeat < datetime.now(timezone.utc)-timedelta(seconds=10):
               addseconds += 60
         takeover = datetime.fromtimestamp(tmpactive['expiresAt'], tz=timezone.utc)+timedelta(seconds=addseconds+service_priority*0.1)
         runninginstance = tmpactive

     except:
       print("active mqtt instance invalid")

cafile = '../data/ssl/ca.crt'
certfile = '../data/ssl/fsr.crt'
keyfile = '../data/ssl/fsr.key'
if mqttLogin['username'] is not None and mqttLogin['password'] is not None:
  client = mqtt.Client(client_id="FSRlistener_"+str(instanceid),callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
  client.on_connect=on_connect  #bind call back function
  client.on_disconnect=on_disconnect  #bind call back function
  client.on_message = on_message #bind call back function
  client.will_set(incidenttopic+'instance/'+str(instanceid),json.dumps({'message':'connection terminated abrupt'}),qos=2,retain=False)
  client.username_pw_set(mqttLogin['username'], mqttLogin['password'])

  mqtthost = mqttLogin.get('host', 'mosquitto')
  if os.path.isfile(cafile) and os.path.isfile(certfile) and os.path.isfile(keyfile):
    _LOGGER.info("mqtt ssl is used")
    mqttport = mqttLogin.get('port', 8883)
    client.tls_set(ca_certs=cafile, certfile=certfile, keyfile=keyfile, tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_REQUIRED)
    client.tls_insecure_set(True)
    client.connect(mqtthost, mqttport, 60)
  else:
    _LOGGER.info("mqtt no TLS is used")
    mqttport = mqttLogin.get('port', 1883)
    client.connect(mqtthost, mqttport, 60)
else:
  _LOGGER.warning("mqtt login missing")

incupc_interval = {'current':411,'live':171,'sleeping':1876}
heartbeat = 0
latestfsrping = -1

waiting = True
while not newconnection:
  client.loop_start()
  time.sleep(1)
  client.loop_stop()
  time.sleep(1)

time.sleep(0.5)

print("now:"+str(datetime.now(timezone.utc))+" takeover:"+str(takeover)+" waiting for permission: "+str(runninginstance))
while waiting:
  client.loop_start()
  if takeover < datetime.now(timezone.utc):
    client.publish(incidenttopic+'active',json.dumps({'instance':str(instanceid),'ts':int(round(datetime.now(timezone.utc).timestamp())),'priority':service_priority,'expiresAt':int(round(datetime.now(timezone.utc).timestamp()))+60}),retain=True)
    if takeover+timedelta(seconds=random.randrange(10,100)) < datetime.now(timezone.utc):
      waiting = False
  if runninginstance['instance'] is not None:
    if str(runninginstance['instance']) == str(instanceid):
      waiting = False
  time.sleep(1)
  client.loop_stop()
  if int(datetime.now(timezone.utc).timestamp()) % 956 == 0:
    handleFSrtoken(api, renew=False) # check and update token if needed
  if int(datetime.now(timezone.utc).timestamp()) % 29 == 0:
    tmptoken = None
    if isinstance(api._token_info,dict):
      if 'access_token' in api._token_info.keys() and 'expires_in' in api._token_info.keys() and 'created_at' in api._token_info.keys():
        tmptoken = api._token_info['created_at']+api._token_info['expires_in']

    client.publish(incidenttopic+'instance/'+str(instanceid),json.dumps({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'message':{'instancestate':'standby'}, \
'hostname':str(socket.gethostname()),'instance_name':os.getenv("INSTANCENAME",None),'localip':str(socket.gethostbyname(socket.gethostname())), \
'user':str(fsrLogin['username']),'token_valid_until':tmptoken}),)
  time.sleep(1)
print(str(datetime.now(timezone.utc))+" - activated")
time.sleep(1)


ws = FireService(wsurl)
lastinc_upd = datetime.now(timezone.utc).timestamp()
while True:
    client.loop_start()
    time.sleep(1)
    client.loop_stop()
    heartbeat += 1
    if heartbeat > 30:
      if runninginstance['instance'] == str(instanceid):
        client.publish(incidenttopic+'active',json.dumps({'instance':str(instanceid),'ts':int(round(datetime.now(timezone.utc).timestamp())),'priority':service_priority,'expiresAt':int(round(datetime.now(timezone.utc).timestamp()))+60}),retain=True)
      heartbeat = 0
    if int(datetime.now(timezone.utc).timestamp()) % 156 == 0:
      tmptoken = None
      if isinstance(api._token_info,dict):
        if 'access_token' in api._token_info.keys() and 'expires_in' in api._token_info.keys() and 'created_at' in api._token_info.keys():
          tmptoken = api._token_info['created_at']+api._token_info['expires_in']
      client.publish(incidenttopic+'instance/'+str(instanceid),json.dumps({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'message':{'instancestate':'still alive','latestpingrecieved':latestfsrping},'token_valid_until':tmptoken,'hostname':str(socket.gethostname()),'instance_name':os.getenv("INSTANCENAME",None)}))

 
    if int(datetime.now(timezone.utc).timestamp()) % 656 == 0:
      handleFSrtoken(api, renew=False) # check and update token if needed
    if int(datetime.now(timezone.utc).timestamp()) % 2672 == 0:
      userlist = getUsers(api)
      client.publish(incidenttopic+'users',json.dumps(userlist),retain=True)

    messages = []
    incidents = []
    while not simpleQue.empty():
      quemes = simpleQue.get()
      sendmes = True
      if quemes['source'] == 'message':
        if 'payload' in quemes.keys():
          if 'type' in quemes['payload'].keys():
            if quemes['payload']['type'] == "ping":
              sendmes = False
              latestfsrping = quemes['payload']['message']
        if sendmes:
          messages.append(quemes)
      elif quemes['source'] == 'incident':
        incidents.append(quemes)
      elif quemes['source'] == 'connection':
        client.publish(incidenttopic+'instance/'+str(instanceid),json.dumps({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'message':quemes['payload']}))

      time.sleep(0.01)
    if len(incidents) > 0:
      client.publish(incidenttopic+'incidents',json.dumps(incidents),)
    if len(messages) > 0:
      print("fra køen:"+str(messages))
      client.publish(incidenttopic+'messages',json.dumps(messages),)
    if not newconnection:
      time.sleep(60) #apparently no mqtt connect, wait some time
    if datetime.now(timezone.utc).timestamp() > lastinc_upd+incupc_interval['current']:
      incidents_json = api._request("GET","incidents","get incidents",{"page": 1,"per_page":4},None,False)
      lastinc_upd = datetime.now(timezone.utc).timestamp()
      incidents_dict = incidents_json
      incupc_interval['current'] = incupc_interval['sleeping']
      if isinstance(incidents_dict,list):
        incidentsToMqtt = []
        for incd in incidents_dict:
          incidentsToMqtt.append({'timestamp':datetime.now(timezone.utc).timestamp(),'instance':str(instanceid),'source':'incidentList','payload':incd})
          if 'state' in incd.keys():
            if not (incd['state'] == "finished" or "end_time" in incd.keys()) and incupc_interval['current'] > incupc_interval['live']:
              incupc_interval['current'] = incupc_interval['live']
   
          print("###########")
          print(incd)
        if len(incidentsToMqtt) > 0:
          client.publish(incidenttopic+'incidents',json.dumps(incidentsToMqtt),retain=True)
