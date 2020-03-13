"""
Copyright (c) 2020 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""
#!/usr/bin/env python3

# web application GUI
from flask import Flask, render_template, request, jsonify, url_for, json, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_googlecharts import GoogleCharts
from config import READING_INTERVAL
import requests
import random
import time
import re
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import xmltodict
from base64 import b64encode
import json


app = Flask(__name__)
charts = GoogleCharts(app)

#SQLAlchemy

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

db = SQLAlchemy(app)

#Setup Table
class Setup(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     start_stamp = db.Column(db.DateTime)
     end_stamp = db.Column(db.DateTime)
     deviceIDfilter = db.Column(db.String(50))
     date_created = db.Column(db.DateTime, default=datetime.now)

#peopleCont Table
class peopleCountTbl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deviceID = db.Column(db.String(20))
    timestamp = db.Column(db.Integer)
    reading = db.Column(db.Integer)


#query setup DB
print('Performing Initial Setup')

setupEntry = Setup.query.order_by(Setup.id.desc()).first().__dict__
print(setupEntry)
START_STAMP = setupEntry.get('start_stamp')
END_STAMP = setupEntry.get('end_stamp')
DEVICE_ID_FILTER = setupEntry.get('deviceIDfilter')

# load list of devices to query
with open('devices.json' , 'r') as f:
    devices_list = json.load(f)

def getPeopleCount():
    for device in devices_list:
        #replace following line with FQDN or IP address of endpoint
        fqdnEndpoint = device['ipAddress']
        username = device['username']
        password = device['password']
        authTokenBytes = b64encode(bytes(username + ':' + password, "utf-8"))
        authToken = authTokenBytes.decode('utf-8')

        url = "http://%s/status.xml" % fqdnEndpoint


        headers = {"Accept": "text/xml",
               "Authorization": "Basic %s" % authToken
               }

        resp = requests.get(url, headers=headers)

        if(resp.status_code == 200):
            xmlData = xmltodict.parse(resp.text)
            peopleCount = int(xmlData['Status']['RoomAnalytics']['PeopleCount']['Current'])
            print(f"Device {device['id']} current people count: {peopleCount} ")
            if peopleCount>0:
                # update DB with form input
                peopleCountEntry = peopleCountTbl(deviceID=device['id'], timestamp=int(time.time()),
                              reading=peopleCount)
                db.session.add(peopleCountEntry)
                db.session.commit()
#            else:
#                #add random data for now to populate the DB
#                peopleCountEntry = peopleCountTbl(deviceID=device['id'], timestamp=int(time.time()),
#                              reading=random.randint(1,9))
#                db.session.add(peopleCountEntry)
#                db.session.commit()
        else:
            print(f"Error occured on device {device['id']} with status code: ",resp.status_code)




#POST config data to DB
@app.route('/commit', methods=['POST'])
def setup_post():
    #get data from html form via name
    theDevIDFilter = request.form.get('DeviceIDFilter')

    testStart=request.form.get('start-time')
    #if you do not modify the datetime field in the form after setting from DB, it adds seconds
    #which we need to remove
    if testStart[-3:]==":00" and len(testStart)>16:
        testStart=testStart[:-3]

    testEnd=request.form.get('end-time')
    #if you do not modify the datetime field in the form after setting from DB, it adds seconds
    #which we need to remove
    if testEnd[-3:]==":00" and len(testEnd)>16:
        testEnd=testEnd[:-3]

    theStartStamp = datetime.strptime(testStart,"%Y-%m-%dT%H:%M")
    theEndStamp = datetime.strptime(testEnd,"%Y-%m-%dT%H:%M")
    #update DB with form input
    setup = Setup(deviceIDfilter=theDevIDFilter, start_stamp=theStartStamp, end_stamp=theEndStamp)
    db.session.add(setup)
    db.session.commit()

    return render_template("success.html",device_id_filter=theDevIDFilter, start_stamp=theStartStamp, end_stamp=theEndStamp)

@app.route('/currentconfig', methods=['GET'])
def current_config():
    #query setup DB
    print('Query Setup')
    setupEntry = Setup.query.order_by(Setup.id.desc()).first().__dict__
    print(setupEntry)
    theStartStamp = setupEntry.get('start_stamp')
    theEndStamp = setupEntry.get('end_stamp')
    theDevIDFilter = setupEntry.get('deviceIDfilter')
    return render_template("currentConfig.html",device_id_filter=theDevIDFilter, start_stamp=theStartStamp, end_stamp=theEndStamp)

@app.route('/pcountActivity',methods=['GET','POST'])
def pcountActivity():
    # open cmx data
    data = []
    reader = peopleCountTbl.query.all()

    if request.method == 'POST':

        theChoiceStr=request.form.get('dropdown_choice')
        # theDevIDFilter should contain either nothing (if they selected --All--)
        # or the exact name of the device as selected from the dropdown
        print(theChoiceStr)
        if theChoiceStr=="--All--":
            theDevIDFilter=""
        else:
            theDevIDFilter=theChoiceStr

        # now we extract the start end stamps detected
        testStart = request.form.get('start-time')
        # if you do not modify the datetime field in the form after setting from DB, it adds seconds
        # which we need to remove
        if testStart[-3:] == ":00" and len(testStart) > 16:
            testStart = testStart[:-3]

        testEnd = request.form.get('end-time')
        # if you do not modify the datetime field in the form after setting from DB, it adds seconds
        # which we need to remove
        if testEnd[-3:] == ":00" and len(testEnd) > 16:
            testEnd = testEnd[:-3]

        theStartStamp = datetime.strptime(testStart, "%Y-%m-%dT%H:%M")
        theEndStamp = datetime.strptime(testEnd, "%Y-%m-%dT%H:%M")
        #put the time stamps in the same format as they come back from the DB
        #to re-use the code that processes them between the GET and POST
        theStartStamp = str(theStartStamp).replace("T", " ")
        theEndStamp = str(theEndStamp).replace("T", " ")
    else:
        setupEntry = Setup.query.order_by(Setup.id.desc()).first().__dict__
        print(setupEntry)
        theStartStamp = str(setupEntry.get('start_stamp'))
        theEndStamp = str(setupEntry.get('end_stamp'))
        theDevIDFilter = setupEntry.get('deviceIDfilter')

    count = 0
    arrayCount=0
    flag=0

    newData=[]
    numReadings=[]
    deviceIDs=[]
    fullListDeviceIDs=[]

    for row in reader:
        # retrieve each row and create data structures in memory to keep the last
        # 24 hours of readings and create an average for each to be ready to show in graph
        #print(row.deviceID)
        #print(row.timestamp)
        #print(row.reading)

        #first populate the entire list of devices to be able to have a functional dropdown selector
        if row.deviceID not in fullListDeviceIDs:
            fullListDeviceIDs.append(row.deviceID)

        # second check to see if the timestamp from the DB is in the time period we are interested in calculating
        # average for
        posixStartStamp=time.mktime(datetime.strptime(theStartStamp, "%Y-%m-%d %H:%M:%S").timetuple())
        posixEndStamp=time.mktime(datetime.strptime(theEndStamp, "%Y-%m-%d %H:%M:%S").timetuple())
        regex=re.compile(theDevIDFilter)
        matches=re.findall(regex,row.deviceID)
        if (row.timestamp >= posixStartStamp) and (row.timestamp <= posixEndStamp) and (matches!=[]):
            #if it is, figure out which hour of the day the reading belongs to, using local timezone
            theLocalTimeStruct=time.localtime(row.timestamp)
            theHour=theLocalTimeStruct.tm_hour
            #print("theHour=",theHour)
            #if we have not seen this device before, add it to the list
            if row.deviceID not in deviceIDs:
                deviceIDs.append(row.deviceID)
                newData.append([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
                numReadings.append([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
            #now accumulate readings and number of readings
            newData[deviceIDs.index(row.deviceID)][theHour]+=row.reading
            numReadings[deviceIDs.index(row.deviceID)][theHour] += 1

     #once all records are read from DB, calculate averages
    for idx,val in enumerate(newData):
        for idx2, val2 in enumerate(newData[idx]):
            #only average for where there is at least one reading
            if (numReadings[idx][idx2])>0:
                newData[idx][idx2]=newData[idx][idx2]/numReadings[idx][idx2]


    #dynamically generate graph colors
    graphColors = []
    for x in range(0,25):
        randomColor = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        graphColors.append(randomColor)
    #fix timestamps so selection widget can correctly read them
    theStartStamp=str(theStartStamp).replace(" ","T")
    theEndStamp=str(theEndStamp).replace(" ","T")
    return render_template("pcountActivity.html",x=newData,dIDs=deviceIDs, fullDIDs=fullListDeviceIDs ,start_stamp=theStartStamp, end_stamp=theEndStamp, colors=graphColors)



# this is for the GET to show the overview
@app.route('/',methods=['GET'])
def index():

    return render_template("pleasewait.html", theReason='Initializing... ')


#API Configuration GUI
@app.route('/setup',methods=['GET','POST'])
def apiSetup():
    print('Query Setup')
    setupEntry = Setup.query.order_by(Setup.id.desc()).first().__dict__
    print(setupEntry)
    aStartStamp = setupEntry.get('start_stamp')
    aEndStamp = setupEntry.get('end_stamp')
    theStartStamp=str(aStartStamp).replace(" ","T")
    theEndStamp=str(aEndStamp).replace(" ","T")
    theDevIDFilter = setupEntry.get('deviceIDfilter')
    return render_template("setup.html",device_id_filter=theDevIDFilter, start_stamp=theStartStamp, end_stamp=theEndStamp)



if __name__ == "__main__":
    
    app.jinja_env.cache = {}
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=getPeopleCount, trigger="interval", seconds=READING_INTERVAL)
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    app.run(host='0.0.0.0', port=5003, debug=True, threaded=True)