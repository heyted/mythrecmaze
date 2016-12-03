#!/usr/bin/env python3

import os, re, sys, requests, subprocess, itertools, configparser, pickle, json, time
from datetime import date, datetime, timedelta, timezone

#Get episode ids, dates and end times for seven days (single token):
def getICalEpisodes(token):
    url = 'http://api.tvmaze.com/ical/followed?token=' + token
    try:
        iCalIcs = requests.get(url).text
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    today = date.today()
    days = [today.strftime("%Y%m%d")]
    for i in range(1, 7):
        day = today + timedelta(days=i)
        days.append(day.strftime("%Y%m%d"))
    episodes = []
    for i in range(len(iCalIcs)-200):
        episode = []
        if iCalIcs[i : i + 5] == 'DTEND':
            for j in range(1, 200):
                if iCalIcs[i+j] == ':':
                    day = iCalIcs[i+j+1 : i+j+9]
                    if day in days:
                        time = iCalIcs[i+j+10 : i+j+14]
                        if day == days[0] and int(datetime.now().strftime("%H%M")) > int(time):
                            break
                        episode.append(day)
                        episode.append(time)
                if iCalIcs[i+j : i+j+8] == 'episodes' and len(episode) > 0:
                    for k in range(25,10,-1):
                        if iCalIcs[i+j+9 : i+j+k].isdigit():
                            episode.append(iCalIcs[i+j+9 : i+j+k])
                            episodes.append(episode)
                            break
                    break
    return episodes

#Get episode ids, dates and end times for seven days:
def getICalsEpisodes(tokens):
    if len(tokens) == 0:
        print('Error in getICalsEpisodes (no token provided)')
        sys.exit(1)
    episodes = []
    for i in range(len(tokens)):
        episodes = episodes + getICalEpisodes(tokens[i])
    episodes.sort()
    episodes = list(episodes for episodes,_ in itertools.groupby(episodes)) #Remove any duplicates
    return episodes

def removeNonAscii(s):
    s = s.replace("&", "and")
    return "".join([x if ord(x) < 128 else '_' for x in s])

def getSchedule(url):
    try:
        schedule_json_wa = requests.get(url).text
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    schedule_json = removeNonAscii(schedule_json_wa)
    return json.loads(schedule_json)

class mythRecord:
    def __init__(self, host, port):
        self.baseAddr = 'http://{}:{}/'.format(host, port)
        self.headers = {'Accept':'application/json'}
    def GetChannelInfoList(self, **params):
        cInfo = requests.get('{}Channel/GetChannelInfoList'.format(self.baseAddr), params = params, headers = self.headers)
        if cInfo:
            return cInfo.json()
    def GetRecordSchedule(self, **params):
        recSchedule = requests.get('{}Dvr/GetRecordSchedule'.format(self.baseAddr), params = params, headers = self.headers)
        if recSchedule:
            return recSchedule.json()
    def AddRecordSchedule(self, params):
        return requests.post('{}Dvr/AddRecordSchedule'.format(self.baseAddr), params = params, headers = self.headers).text

def isbadipv4(s):
    pieces = s.split('.')
    if len(pieces) != 4: return True
    try: return not all(0<=int(p)<256 for p in pieces)
    except ValueError: return True

if __name__ == '__main__':
    print('Visit www.tvmaze.com')
    #Read settings from file or prompt user:
    homepath = os.path.expanduser('~')
    config = configparser.RawConfigParser()
    if os.path.isfile(homepath + '/mythrecmaze.cfg'):
        config.read(homepath + '/mythrecmaze.cfg')
        mythlanip = config.get('mythrecmazesettings', 'mythlanip')
        mythport = config.get('mythrecmazesettings', 'mythport')
        mythsourceid = config.get('mythrecmazesettings', 'mythsourceid')
        mazetokens = config.get('mythrecmazesettings', 'mazetokens').split(',')
    else:
        mythlanip = input('Enter MythTV backend server IP address (example: 192.168.1.50) --> ')
        if isbadipv4(mythlanip):
            print('Aborting (invalid MythTV backend server IP address)')
            sys.exit(1)
        mythport = input('Enter MythTV backend web server port (default: 6544) --> ')
        if len(mythport) == 0:
            mythport = '6544'
        elif not mythport.isdigit():
            print('Aborting (invalid MythTV backend web server port number)')
            sys.exit(1)
        mythsourceid = input('Enter MythTV channel source id (default: 1) --> ')
        if len(mythsourceid) == 0:
            mythsourceid = '1'
        elif not mythsourceid.isdigit():
            print('Aborting (invalid MythTV channel source id number)')
            sys.exit(1)
        mazetokens = [input('Enter single TVmaze token --> ')]
        if len(mazetokens) == 0:
            print('Aborting (TVmaze token is required)')
            sys.exit(1)
        while True:
            mazetoken = input('Enter another TVmaze token or press enter if done --> ')
            if len(mazetoken) == 0:
                break
            else:
                mazetokens.append(mazetoken)
        config.add_section('mythrecmazesettings')
        config.set('mythrecmazesettings', 'mythlanip', mythlanip)
        config.set('mythrecmazesettings', 'mythport', mythport)
        config.set('mythrecmazesettings', 'mythsourceid', mythsourceid)
        config.set('mythrecmazesettings', 'mazetokens', ','.join(mazetokens))
        with open(homepath + '/mythrecmaze.cfg', 'w') as configfile:
            config.write(configfile)
    print('Opening TVmaze connection')
    episodes = getICalsEpisodes(mazetokens)
    if len(episodes) > 0:
        if os.path.isfile(homepath + '/.mythrecmaze.pickle'):
            with open(homepath + '/.mythrecmaze.pickle', 'rb') as f:
                prevepisodes = pickle.load(f)
            with open(homepath + '/.mythrecmaze.pickle', 'wb') as f:
                pickle.dump(episodes, f, pickle.HIGHEST_PROTOCOL)
            #Episodes not in previous episodes list:
            newepisodes = list(itertools.compress(episodes, (not x in prevepisodes for x in episodes)))
        else:
            with open(homepath + '/.mythrecmaze.pickle', 'wb') as f:
                pickle.dump(episodes, f, pickle.HIGHEST_PROTOCOL)
            if not os.path.isfile(homepath + '/.mythrecmaze.pickle'):
                print('Error in mythrecmaze.py (unable to save episodes list)')
                sys.exit(1)
            newepisodes = episodes
    else:
        newepisodes = []
    print('Downloading TVmaze schedule')
    noschedule = True
    with open('xmltv.xml', 'w') as xml_file:
        xml_file.write('<?xml version="1.0" encoding="ISO-8859-1"?>'+'\n')
        xml_file.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">'+'\n')
        xml_file.write('\n')
        xml_file.write('<tv source-info-name="TVmaze" generator-info-name="mythrecmaze.py">'+'\n')
        schedule_dicts = getSchedule('http://api.tvmaze.com/schedule')#Always get today's schedule
        daysdone = []
        #Write out schedule for each unique day in newepisodes and add network id and start time to new episodes list:
        for i in range(len(newepisodes)+1):
            overlapcheck = []
            if i > 0:
                day = newepisodes[i-1][0]
                if not day in daysdone:
                    scheduleday = day
                    schedule_dicts = getSchedule('http://api.tvmaze.com/schedule?date='+day[0:4]+'-'+day[4:6]+'-'+day[6:8])
            else:
                day = date.today().strftime("%Y%m%d")
                scheduleday = day
            for j in range(len(schedule_dicts)):
                episodeid = schedule_dicts[j]['id']
                ch_id = str(schedule_dicts[j]['show']['network']['id'])
                tm = schedule_dicts[j]['airstamp']
                if i > 0:
                    if str(episodeid) == newepisodes[i-1][2]:
                        if day != scheduleday:
                            print('Error in mythrecmaze.py (unexpected schedule sort order)')
                            sys.exit(1)
                        newepisodes[i-1] = newepisodes[i-1] + [ch_id] + [tm]
                if not day in daysdone:
                    name = schedule_dicts[j]['show']['name']
                    runtime = schedule_dicts[j]['runtime']
                    try:
                        description = re.sub('<[^<]+?>', '', schedule_dicts[j]['summary'])
                    except:
                        description = ''
                    if name and tm and runtime and ch_id:
                        start = tm[0:4]+tm[5:7]+tm[8:10]+tm[11:13]+tm[14:16]+tm[17:19]+' '+tm[19:22]+tm[23:25]
                        start_time = datetime.strptime(start[0:14], "%Y%m%d%H%M%S")
                        stop_time = start_time + timedelta(minutes=runtime)
                        stop = stop_time.strftime("%Y%m%d%H%M%S")+' '+tm[19:22]+tm[23:25]
                        skip = False
                        for k in range(len(overlapcheck)):
                            if start_time < overlapcheck[k][2] and stop_time > overlapcheck[k][1] and ch_id == overlapcheck[k][0]:
                                if i > 0:
                                    if str(episodeid) == newepisodes[i-1][2]:
                                        print('Warning: Uncorrected time overlap detected for ' + name + ' at ' + start_time.strftime("%Y-%m-%d %H:%M"))
                                        time.sleep(1)
                                        break
                                if stop_time <= overlapcheck[k][2]:
                                    skip = True
                                    break
                                else:
                                    start_time = overlapcheck[k][2]
                                    start = start_time.strftime("%Y%m%d%H%M%S")+' '+time[19:22]+time[23:25]
                                    print('Overlap detected and start time adjusted for ' + name + ' at ' + start_time.strftime("%Y-%m-%d %H:%M"))
                        overlapcheck.append([ch_id, start_time, stop_time])
                        if not skip:
                            xml_file.write('  <programme start="'+start+'" stop="'+stop+'" channel="'+ch_id+'">'+'\n')
                            xml_file.write('    <title lang="en">'+name+'</title>'+'\n')
                            xml_file.write('    <desc lang="en">'+description+'</desc>'+'\n')
                            xml_file.write('  </programme>'+'\n')
                            if noschedule:
                                noschedule = False
            daysdone = daysdone + [day]
        xml_file.write('</tv>')
    if noschedule:
        print('Error in mythrecmaze.py (no schedule data)')
        sys.exit(1)
    #Run mythfilldatabase:
    subprocess.call('mythfilldatabase --refresh 1 --file --sourceid ' + mythsourceid + ' --xmlfile ./xmltv.xml', shell=True)
    pym = mythRecord(mythlanip, mythport)
    chaninfo = pym.GetChannelInfoList(SourceID=mythsourceid, Details='true')
    if chaninfo:
        chaninfo = chaninfo['ChannelInfoList']['ChannelInfos']
    else:
        print('Error in mythrecmaze.py (unable to fetch channel information)')
        sys.exit(1)
    for i in range(len(chaninfo)):
        for j in range(len(newepisodes)):
            if newepisodes[j][3] == chaninfo[i]['XMLTVID']:
                time = newepisodes[j][4]
                time = datetime.strptime (time[0:22]+time[23:25], "%Y-%m-%dT%H:%M:%S%z")
                time = datetime.strftime(time.astimezone(timezone.utc), "%Y-%m-%dT%H:%M:%S")
                mythchid = chaninfo[i]['ChanId']
                recRule = pym.GetRecordSchedule(ChanId=mythchid, StartTime=time)
                if recRule:
                    recRule = recRule['RecRule']
                    recRule['Type'] = 'Single Record'
                    recRule['Station'] = recRule['CallSign']
                    pym.AddRecordSchedule(recRule)
                else:
                    print('Error: No record schedule found')
