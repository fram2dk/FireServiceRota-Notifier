#!/usr/bin/env python3
import sqlite3
import json
import time
import paho.mqtt.client as paho
import ssl
import os, pyaes
#from Crypto.PublicKey import RSA
#from Crypto.Cipher import PKCS1_OAEP
from base64 import b64decode
import socket



class tgLog():
   def __init__(self, name):
      self.name = name
      self.path = 'logger.db'
      self.mqttclient = paho.Client()

   def connect(self):
      print("connecting logger: "+str(self.name))
      self.con = sqlite3.connect(self.path,check_same_thread=False)
      self.cur = self.con.cursor()
   def disconnect(self):
      print("disconnecting logger: "+str(self.name))
      self.con.commit()
      self.con.close()

   def put(self, tgMessage):
       self.cur.execute('''CREATE TABLE IF NOT EXISTS chats
               (time INTEGER, chatid INTEGER NOT NULL, way INTEGER, message TEXT)''')
       for mesg in tgMessage:
          if mesg.from_user.is_bot:
            way=2
          else:
            way=1
#          print('date:'+str(mesg.date)+', chatid:'+str(mesg.chat.id)+' text: '+str(mesg.text)+', way: '+str(mesg.from_user.is_bot))
          self.cur.execute("INSERT INTO chats (time,chatid,way,message) VALUES (?,?,?,?)", (int(mesg.date),int(mesg.chat.id),way,str(mesg.text)))
          self.sendincidentMqtt(json.dumps({'name':str(mesg.from_user.username),'chat':mesg.chat.id,'logger':self.name,'msg':mesg.text}))
       try:
         self.con.commit()
       except:
         pass
   def incidents(self,incId,messages=None):
       self.cur.execute('''CREATE TABLE IF NOT EXISTS incidents (rowid INTEGER PRIMARY KEY,incidentId INTEGER UNIQUE, handledtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,messages INTEGER NOT NULL DEFAULT 0)''')
       self.cur.execute("INSERT OR REPLACE INTO incidents (incidentId,messages) VALUES (?,(select IFNULL(messages,0) from incidents WHERE incidentId = ?))", (int(incId),int(incId)))
       if isinstance(messages, int):
           print('has sent'+str(messages)+' messages')
           self.cur.execute("UPDATE incidents SET messages = messages + ? WHERE incidentId = ?", (int(messages),int(incId)))
       self.con.commit()
   def sendLocalMqtt(self,incidentObj):
       pass

   def sendincidentMqtt(self,incident):
       pass
