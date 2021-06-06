#!/usr/bin/env python3

import os, re, sys, requests, subprocess, itertools, configparser, pickle, json, time, csv, logging
from datetime import date, datetime, timedelta, timezone

#Get episode ids, dates and start times for seven days (single token):
def getICalEpisodes(token,utcoffset):
    url = 'https://api.tvmaze.com/ical/followed?token=' + token
    try:
        iCalIcs = requests.get(url).text
    except requests.exceptions.RequestException as e:
        logging.info(e)
        sys.exit(1)
    today = date.today()
    days = [today.strftime("%Y%m%d")]
    for i in range(1, 7):
        day = today + timedelta(days=i)
        days.append(day.strftime("%Y%m%d"))
    episodes = []
    for i in range(len(iCalIcs)-200):
        episode = []
        if iCalIcs[i : i + 8] == 'DTSTART:':
            day = iCalIcs[i+8 : i+16]
            time = iCalIcs[i+17 : i+21]
            if day in days:
                stime = datetime.strptime(day+time, '%Y%m%d%H%M') + utcoffset
                day = stime.strftime("%Y%m%d")
                time = stime.strftime("%H%M")
                if day == days[0] and int(datetime.now().strftime("%H%M")) > int(time):
                    break
                episode.append(day)
                episode.append(time)
                for j in range(1, 200):
                    if iCalIcs[i+j : i+j+8] == 'episodes' and len(episode) > 0:
                        for k in range(25,10,-1):
                            if iCalIcs[i+j+9 : i+j+k].isdigit():
                                episode.append(iCalIcs[i+j+9 : i+j+k])
                                episodes.append(episode)
                                break
                        break
    return episodes

#Get episode ids, dates and start times for seven days (all tokens):
def getICalsEpisodes(tokens):
    if len(tokens) == 0:
        logging.info(' Error in getICalsEpisodes (no API key provided)')
        sys.exit(1)
    ts = time.time()
    utcoffset = (datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts))
    episodes = []
    for i in range(len(tokens)):
        episodes = episodes + getICalEpisodes(tokens[i],utcoffset)
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
        logging.info(e)
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

def main():
    homepath = os.path.expanduser('~')
    if os.path.isfile(homepath+'/.mythrecmaze/mythrecmaze0.log'):
        os.rename(homepath+'/.mythrecmaze/mythrecmaze0.log',homepath+'/.mythrecmaze/mythrecmaze1.log')
    if not os.path.isdir(homepath + '/.mythrecmaze'):
        os.mkdir(homepath + '/.mythrecmaze')
    try:
        logging.basicConfig(format='%(levelname)s:%(message)s', filename=homepath+'/.mythrecmaze/mythrecmaze0.log', filemode='w', level=logging.INFO)
    except IOError:
        logging.basicConfig(format='%(levelname)s:%(message)s', filename='/tmp/mythrecmaze0.log', filemode='w', level=logging.INFO)
    logging.info(" " + str(datetime.now()) + " Starting mythrecmaze.py")
    if not os.path.isfile("/opt/mythrecmaze/userhomepath.dat"):
        logging.info(" Aborting (Required file userhomepath.dat not found)")
        sys.exit(0)
    config = configparser.RawConfigParser()
    config.read('/opt/mythrecmaze/userhomepath.dat')
    uhomepath = config.get('userhomepath', 'uhp')
    mythlanip = False
    #Display GUI if ran by user:
    if not 'mythtv' in homepath:
        while True:
            try:
                option = subprocess.check_output("zenity --list --title='Mythrecmaze' --text='Select Option' --column='0' \
                'Change settings' \
                'Check for shows to record now' \
                'View log' \
                'Exit Mythrecmaze' --hide-header \
                --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
                option = option.strip().decode('utf-8')
            except subprocess.CalledProcessError:
                logging.info(' Exiting (Options dialog canceled)')
                sys.exit(0)
            if option == 'Exit Mythrecmaze':
                logging.info(' Exiting (User selected exit)')
                sys.exit(0)
            if option == 'Change settings':
                try:
                    cfg = subprocess.check_output("zenity --forms --title='Mythrecmaze' --text='Configuration' \
                    --add-entry='MythTV backend server IP address (example: 192.168.1.50)' \
                    --add-entry='MythTV backend web server port (default: 6544)' \
                    --add-entry='MythTV channel source id (default: 1)' \
                    --add-entry='TVmaze API key (enter single API key)' \
                    --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
                    cfg = cfg.strip().decode('utf-8').split("|")
                except subprocess.CalledProcessError:
                    continue
                mythlanip = cfg[0]
                if isbadipv4(mythlanip):
                    logging.info(' Aborting (invalid MythTV backend server IP address)')
                    sys.exit(0)
                mythport = cfg[1]
                if len(mythport) == 0:
                    mythport = '6544'
                elif not mythport.isdigit():
                    logging.info(' Aborting (invalid MythTV backend web server port number)')
                    sys.exit(0)
                mythsourceid = cfg[2]
                if len(mythsourceid) == 0:
                    mythsourceid = '1'
                elif not mythsourceid.isdigit():
                    logging.info(' Aborting (invalid MythTV channel source id number)')
                    sys.exit(0)
                mazetokens = [cfg[3]]
                if len(mazetokens) == 0:
                    logging.info(' Aborting (TVmaze API key is required)')
                    sys.exit(0)
                while True:
                    try:
                        mazetoken = subprocess.check_output("zenity --forms --title='Mythrecmaze' \
                        --text='Enter additional TVmaze API key or leave blank if none' \
                        --add-entry='TVmaze API key (enter single API key)' \
                        --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
                        mazetoken = mazetoken.strip().decode('utf-8')
                    except subprocess.CalledProcessError:
                        break
                    if len(mazetoken) == 0:
                        break
                    else:
                        mazetokens.append(mazetoken)
                config.add_section('mythrecmazesettings')
                config.set('mythrecmazesettings', 'mythlanip', mythlanip)
                config.set('mythrecmazesettings', 'mythport', mythport)
                config.set('mythrecmazesettings', 'mythsourceid', mythsourceid)
                config.set('mythrecmazesettings', 'mazetokens', ','.join(mazetokens))
                config.set('mythrecmazesettings', 'showdetails', 'False')
                showdetails = False
                with open(homepath + '/.mythrecmaze/mythrecmaze.cfg', 'w') as configfile:
                    config.write(configfile)
            if option == 'View log':
                viewedlog = False
                if os.path.isfile(homepath + '/.mythrecmaze/mythrecmaze1.log'):
                    subprocess.call("zenity --text-info --title='Mythrecmaze Previous Manual Run Log' --width=600 \
                    --height=500 --filename=" + homepath + "/.mythrecmaze/mythrecmaze1.log \
                    --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
                    viewedlog = True
                if os.path.isfile('/home/mythtv/.mythrecmaze/mythrecmaze0.log'):
                    subprocess.call("zenity --text-info --title='Mythrecmaze Previous Automatic Run Log' --width=600 \
                    --height=500 --filename=/home/mythtv/.mythrecmaze/mythrecmaze0.log \
                    --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
                    viewedlog = True
                if not viewedlog:
                    subprocess.call("zenity --info --title='Mythrecmaze' --text='No log file found' --width=150 \
                    --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
            if option == 'Check for shows to record now':
                break
    if os.path.isfile(uhomepath + '/.mythrecmaze/mythrecmaze.cfg') and not mythlanip:
        config.read(uhomepath + '/.mythrecmaze/mythrecmaze.cfg')
        mythlanip = config.get('mythrecmazesettings', 'mythlanip')
        mythport = config.get('mythrecmazesettings', 'mythport')
        mythsourceid = config.get('mythrecmazesettings', 'mythsourceid')
        mazetokens = config.get('mythrecmazesettings', 'mazetokens').split(',')
        showdetails = config.getboolean('mythrecmazesettings', 'showdetails')
    if not mythlanip:
        logging.info(" Aborting (Required file mythrecmaze.cfg not found)")
        if not 'mythtv' in homepath:
            subprocess.call("zenity --info --title='Mythrecmaze' --text='Aborting (Unable to retreive settings)' --width=300 \
            --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
        sys.exit(0)
    logging.info(' Opening TVmaze connection')
    episodes = getICalsEpisodes(mazetokens)
    newepisodes = episodes
    if len(episodes) > 0:
        if os.path.isfile(homepath + '/.mythrecmaze/mythrecmaze.pickle'):
            with open(homepath + '/.mythrecmaze/mythrecmaze.pickle', 'rb') as f:
                prevepisodes = pickle.load(f)
            #Episodes not in previous episodes list:
            newepisodes = list(itertools.compress(newepisodes, (not x in prevepisodes for x in newepisodes)))
        if os.path.isfile(homepath + '/home/mythtv/.mythrecmaze/mythrecmaze.pickle'):
            with open(homepath + '/home/mythtv/.mythrecmaze/mythrecmaze.pickle', 'rb') as f:
                prevepisodes = pickle.load(f)
            newepisodes = list(itertools.compress(newepisodes, (not x in prevepisodes for x in newepisodes)))
        with open(homepath + '/.mythrecmaze/mythrecmaze.pickle', 'wb') as f:
            pickle.dump(episodes, f, pickle.HIGHEST_PROTOCOL)
    else:
        newepisodes = []
    logging.info(' Downloading TVmaze schedule')
    noschedule = True
    usingNonMazeChIds = False
    if os.path.isfile(uhomepath + '/xmltvidmap.csv'):
        usingNonMazeChIds = True
        with open(uhomepath + '/xmltvidmap.csv', 'r') as f:
            reader = csv.reader(f)
            channelsMap = list(reader)
        channelsMazeInclude = []
        for i in range(len(channelsMap)):
            channelsMazeInclude = channelsMazeInclude + [channelsMap[i][1]]
    #Write out schedule for each unique day in newepisodes and add network id and start time to new episodes list:
    if 'mythtv' in homepath:
        tmp_xml_file = '/tmp/xmltvmrm_m.xml'
    else:
        tmp_xml_file = '/tmp/xmltvmrm.xml'
    with open(tmp_xml_file, 'w') as xml_file:
        xml_file.write('<?xml version="1.0" encoding="ISO-8859-1"?>'+'\n')
        xml_file.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">'+'\n')
        xml_file.write('\n')
        xml_file.write('<tv source-info-name="TVmaze" generator-info-name="mythrecmaze.py">'+'\n')
        schedule_dicts = getSchedule('https://api.tvmaze.com/schedule')#Always get today's schedule
        daysdone = []
        channelsMazeSkipped = []
        torecord = 'To be recorded: \n'
        for i in range(len(newepisodes)+1):
            overlapcheck = []
            if i > 0:
                day = newepisodes[i-1][0]
                if not day in daysdone:
                    scheduleday = day
                    schedule_dicts = getSchedule('https://api.tvmaze.com/schedule?date='+day[0:4]+'-'+day[4:6]+'-'+day[6:8])
            else:
                day = date.today().strftime("%Y%m%d")
                scheduleday = day
            for j in range(len(schedule_dicts)):
                skip = False
                episodeid = schedule_dicts[j]['id']
                name = schedule_dicts[j]['show']['name']
                try:
                    ch_id = str(schedule_dicts[j]['show']['network']['id'])
                    tm = schedule_dicts[j]['airstamp']
                    start = tm[0:4]+tm[5:7]+tm[8:10]+tm[11:13]+tm[14:16]+tm[17:19]+' '+tm[19:22]+tm[23:25]
                    start_time = datetime.strptime(start[0:14], "%Y%m%d%H%M%S")
                except:
                    logging.info(' Incomplete schedule information for ' + name)
                    logging.info(' Skipping EPG entry for ' + name)
                    skip = True
                    if i > 0:
                        if str(episodeid) == newepisodes[i-1][2]:
                            logging.info(' Error in mythrecmaze.py (Incomplete schedule information for show to be recorded)')
                            sys.exit(1)
                if usingNonMazeChIds and not skip:
                    if ch_id in channelsMazeInclude:
                        ch_id = channelsMap[channelsMazeInclude.index(ch_id)][0]
                    else:
                        if not ch_id in channelsMazeSkipped:
                            if showdetails:
                                logging.info(' Skipping TVmaze network id ' + ch_id + ' (not included in xmltvidmap.csv)')
                            channelsMazeSkipped = channelsMazeSkipped + [ch_id]
                        continue
                if i > 0 and not skip:
                    if str(episodeid) == newepisodes[i-1][2]:
                        if day != scheduleday:
                            logging.info(' Error in mythrecmaze.py (unexpected schedule sort order)')
                            sys.exit(1)
                        torecord = torecord+name+' on '+newepisodes[i-1][0][4:6]+'/'+newepisodes[i-1][0][6:9]+'/'+newepisodes[i-1][0][0:4]+'\n'
                        newepisodes[i-1] = newepisodes[i-1] + [ch_id] + [tm]
                if not day in daysdone and not skip:
                    runtime = schedule_dicts[j]['runtime']
                    try:
                        description = re.sub('<[^<]+?>', '', schedule_dicts[j]['summary'])
                    except:
                        description = ''
                    try:
                        stop_time = start_time + timedelta(minutes=runtime)
                    except TypeError:
                        logging.info(' Unable to determine runtime for: ' + name + ' ' + start_time.strftime("%Y-%m-%d %H:%M"))
                        logging.info(' Guessing 60 minutes runtime for ' + name)
                        stop_time = start_time + timedelta(minutes=60)
                    stop = stop_time.strftime("%Y%m%d%H%M%S")+' '+tm[19:22]+tm[23:25]
                    for k in range(len(overlapcheck)):
                        if start_time < overlapcheck[k][2] and stop_time > overlapcheck[k][1] and ch_id == overlapcheck[k][0]:
                            if i > 0:
                                if str(episodeid) == newepisodes[i-1][2]:
                                    logging.info('Warning: Uncorrected time overlap detected for ' + name + ' at ' + start_time.strftime("%Y-%m-%d %H:%M"))
                                    time.sleep(1)
                                    break
                            if stop_time <= overlapcheck[k][2]:
                                skip = True
                                break
                            else:
                                start_time = overlapcheck[k][2]
                                try:
                                    start = start_time.strftime("%Y%m%d%H%M%S")+' '+time[19:22]+time[23:25]
                                except:
                                    logging.info(' Overlap detected for ' + name + ' ' + start_time.strftime("%Y-%m-%d %H:%M"))
                                    logging.info(' Skipping EPG entry for ' + name + ' ' + start_time.strftime("%Y-%m-%d %H:%M"))
                                    skip = True
                                    break
                                logging.info(' Overlap detected and start time adjusted for ' + name + ' ' + start_time.strftime("%Y-%m-%d %H:%M"))
                    overlapcheck.append([ch_id, start_time, stop_time])
                    if not skip:
                        xml_file.write('  <programme start="'+start+'" stop="'+stop+'" channel="'+ch_id+'">'+'\n')
                        xml_file.write('    <title lang="en">'+name+'</title>'+'\n')
                        xml_file.write('    <sub-title lang="en">'+schedule_dicts[j]['name']+'</sub-title>'+'\n')
                        xml_file.write('    <desc lang="en">'+description+'</desc>'+'\n')
                        genres = schedule_dicts[j]['show']['genres']
                        if len(genres) > 0:
                            for l in range(len(genres)):
                                xml_file.write('    <category lang="en">'+genres[l]+'</category>'+'\n')
                        xml_file.write('    <category lang="en">Show</category>'+'\n')
                        xml_file.write('  </programme>'+'\n')
                        if noschedule:
                            noschedule = False
            daysdone = daysdone + [day]
        xml_file.write('</tv>')
    if noschedule:
        logging.info(' Error in mythrecmaze.py (no schedule data)')
        sys.exit(1)
    if not 'mythtv' in homepath:
        if len(torecord) > 17:
            subprocess.call("zenity --info --title='Mythrecmaze' --text='" + torecord + "' --width=300 \
            --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
        else:
            subprocess.call("zenity --info --title='Mythrecmaze' --text='Nothing new found to record' --width=300 \
            --window-icon=/opt/mythrecmaze/mythrecmaze.svg", shell=True)
    else:
        if len(torecord) > 17:
            logging.info(' ' + torecord)
    #Run mythfilldatabase:
    logging.info(' Running mythfilldatabase')
    subprocess.call('mythfilldatabase --quiet --refresh 1 --file --sourceid ' + mythsourceid + ' --xmlfile ' + tmp_xml_file, shell=True)
    pym = mythRecord(mythlanip, mythport)
    chaninfo = pym.GetChannelInfoList(SourceID=mythsourceid, Details='true')
    if chaninfo:
        chaninfo = chaninfo['ChannelInfoList']['ChannelInfos']
    else:
        logging.info(' Error in mythrecmaze.py (unable to fetch channel information)')
        sys.exit(1)
    for i in range(len(chaninfo)):
        for j in range(len(newepisodes)):
            if len(newepisodes[j]) > 3:
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
                        logging.info(' Error: No record schedule found')

if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception("Fatal error in main function")
