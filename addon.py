# -*- coding: utf-8 -*-
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import httplib
from urlparse import urlparse
import traceback
import json
import ivysilani
from datetime import datetime, timedelta
import time
import random
from xbmcplugin import addDirectoryItem
from collections import defaultdict
###############################################################################
REMOTE_DBG = False
# append pydev remote debugger
if REMOTE_DBG:
    try:
        sys.path.append(os.environ['HOME'] + r'/.kodi/system/python/Lib/pysrc')
        import pydevd
        pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)
    except ImportError:
        sys.stderr.write("Error: Could not load pysrc!")
        sys.exit(1)
###############################################################################

params = None
_addon_ = xbmcaddon.Addon('plugin.video.ivysilani')
_lang_ = _addon_.getLocalizedString
_scriptname_ = _addon_.getAddonInfo('name')
_version_ = _addon_.getAddonInfo('version')
_first_error_ = False
_send_errors_ = False
###############################################################################
def log(msg, level=xbmc.LOGDEBUG):
    if type(msg).__name__ == 'unicode':
        msg = msg.encode('utf-8')
    xbmc.log("[%s] %s" % (_scriptname_, msg.__str__()), level)

def logDbg(msg):
    log(msg, level=xbmc.LOGDEBUG)

def logErr(msg):
    log(msg, level=xbmc.LOGERROR)
###############################################################################

def _exception_log(exc_type, exc_value, exc_traceback):
    global _first_error_
    global _send_errors_
    logErr(traceback.format_exception(exc_type, exc_value, exc_traceback))
    xbmcgui.Dialog().notification(_scriptname_, _toString(exc_value), xbmcgui.NOTIFICATION_ERROR)
    if not _first_error_:
        if xbmcgui.Dialog().yesno(_scriptname_, _lang_(30500), _lang_(30501)):
            _addon_.setSetting("send_errors", "true")
            _send_errors_ = (_addon_.getSetting('send_errors') == "true")
        _addon_.setSetting("first_error", "true")
        _first_error_ = (_addon_.getSetting('first_error') == "true")
    if _send_errors_:
        if _sendError(params, exc_type, exc_value, exc_traceback):
            xbmcgui.Dialog().notification(_scriptname_, _lang_(30502), xbmcgui.NOTIFICATION_INFO)
        else:
            xbmcgui.Dialog().notification(_scriptname_, _lang_(30503), xbmcgui.NOTIFICATION_ERROR)

try:
    # First run
    if not (_addon_.getSetting("settings_init_done") == "true"):
        DEFAULT_SETTING_VALUES = {"quality" : "576p",
                                  "auto_quality" : "true",
                                  "quality_fallback" : "true",
                                  "player_fallback" : "true",
                                  "player_type" : "HLS",
                                  "audio_description" : "false",
                                  "auto_view_mode" : "true",
                                  "send_errors" : "false",
                                  "auto_unpause" : "false"}
        for setting in DEFAULT_SETTING_VALUES.keys():
            val = _addon_.getSetting(setting)
            if not val:
                _addon_.setSetting(setting, DEFAULT_SETTING_VALUES[setting])
        _addon_.setSetting("settings_init_done", "true")
    ###############################################################################
    _auto_quality_ = (_addon_.getSetting('auto_quality') == "true")
    _quality_ = _addon_.getSetting('quality')
    _quality_fallback_ = (_addon_.getSetting('quality_fallback') == "true")
    _player_fallback_ = (_addon_.getSetting('player_fallback') == "true")
    _audio_description_ = (_addon_.getSetting('audio_description') == "true")
    _player_type_ = _addon_.getSetting('player_type')
    _first_error_ = (_addon_.getSetting('first_error') == "true")
    _send_errors_ = (_addon_.getSetting('send_errors') == "true")
    _auto_view_mode_ = (_addon_.getSetting('auto_view_mode') == "true")
    _auto_unpause_ = (_addon_.getSetting('auto_unpause') == "true")
    _icon_ = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'icon.png'))
    _next_ = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'next.png'))
    _previous_ = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'previous.png'))
    _fanArt = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'fanart1.png'))
    _handle_ = int(sys.argv[1])
    _baseurl_ = sys.argv[0]


    well_known_error_messages = [('Programme not found!', 30550),
                                 ('Playlisturl is empty!', 30550),
                                 ('Non playable programme!', 30550),
                                 ('error_nonEncoded', 30551)]
    SKIN_DATA = defaultdict(list, {
        'skin.confluence': [
            {'name': 'List', 'id': 50},
            {'name': 'Big List', 'id': 51},
            {'name': 'Thumbnail', 'id': 500},
            {'name': 'Media info', 'id': 504},
            {'name': 'Media info 2', 'id': 503}
        ]
    })

    def _toString(text):
        if type(text).__name__ == 'unicode':
            output = text.encode('utf-8')
        else:
            output = str(text)
        return output

    def _fanart():
        fanartFolder = os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'fanart')
        listedDir = os.listdir(fanartFolder)
        r = random.randint(0, len(listedDir) - 1)
        selected = os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'fanart', listedDir[r])
        return xbmc.translatePath(selected)

    def _setViewMode(view_mode):
        if _auto_view_mode_:
            skin_dir = xbmc.getSkinDir()
            for sd in SKIN_DATA[skin_dir]:
                if sd['name'] == view_mode:
                    view_mode_id = sd['id']
                    xbmc.executebuiltin('Container.SetViewMode(%d)' % view_mode_id)

    def mainMenu():
        spotlight_labels = { "tipsMain": 30019,
                             "topDay": 30020,
                             "topWeek": 30021,
                             "tipsNote": 30022,
                             "tipsArchive": 30023,
                             "watching": 30024 }
        addDirectoryItem(_lang_(30015), _baseurl_ + "?menu=live")
        addDirectoryItem(_lang_(30016), _baseurl_ + "?menu=byDate")
        addDirectoryItem(_lang_(30017), _baseurl_ + "?menu=byLetter")
        addDirectoryItem(_lang_(30018), _baseurl_ + "?menu=byGenre")
        for spotlight in ivysilani.SPOTLIGHTS:
            addDirectoryItem(_lang_(spotlight_labels[spotlight.ID]), _baseurl_ + "?menu=" + spotlight.ID)
        xbmcplugin.endOfDirectory(_handle_, updateListing=True)

    def addDirectoryItem(label, url, ID=None, related=False, episodes=False, plot=None, title=None, date=None, duration=None,
                          icon=_icon_, image=None, fanart=None, isFolder=True):
        li = xbmcgui.ListItem(label)
        if not title:
            title = label
        liVideo = {'title': title}
        if duration:
            liVideo['duration'] = duration
        if plot:
            liVideo['plot'] = plot
        if date:
            dt = datetime.fromtimestamp(time.mktime(time.strptime(date, "%d. %m. %Y")))
            liVideo['premiered'] = dt.strftime("%Y-%m-%d")
        if image:
            li.setThumbnailImage(image)
        li.setIconImage(icon)
        li.setInfo("video", liVideo)
        if not fanart:
            fanart = _fanart()
        li.setProperty('fanart_image', fanart)
        if episodes:
            url = _baseurl_ + "?episodes=" + ID
        if ID:
            cm = []
            cm.append((_lang_(30013), "XBMC.Container.Update(" + _baseurl_ + "?play=" + ID + "&skip_auto=1)"))
            if related:
                cm.append((_lang_(30003), "XBMC.Container.Update(" + _baseurl_ + "?related=" + ID + ")"))
                cm.append((_lang_(30004), "XBMC.Container.Update(" + _baseurl_ + "?episodes=" + ID + ")"))
                cm.append((_lang_(30005), "XBMC.Container.Update(" + _baseurl_ + "?bonuses=" + ID + ")"))
            li.addContextMenuItems(cm)
        xbmcplugin.addDirectoryItem(handle=_handle_, url=url, listitem=li, isFolder=isFolder)

    def listProgrammelist(programmelist, episodes=False):
        xbmcplugin.setContent(_handle_, "episodes")
        pList = programmelist.list()
        for item in pList:
            plot = None
            date = None
            if hasattr(item, "synopsis") and item.synopsis:
                plot = item.synopsis
            url = _baseurl_ + "?play=" + item.ID
            title = item.title
            if hasattr(item, 'time'):
                title = "[" + item.time + "] " + title
            active = True
            if hasattr(item, 'active'):
                active = (item.active == '1')
            if active:
                addDirectoryItem(title, url, ID=item.ID, related=True, episodes=episodes, plot=plot, date=date, image=item.imageURL)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False , cacheToDisc=False)

    def playProgramme(ID, skipAutoQuality=False):
        programme = ivysilani.Programme(ID)
        if _auto_quality_ and not skipAutoQuality:
            u = autoSelectQuality(programme)
            if u:
                playUrl(_toString(programme.title), u, programme.imageURL)
                return
        for quality in programme.available_qualities():
            url = programme.url(quality)
            addDirectoryItem(quality.label(), url=url, title=_toString(programme.title), image=programme.imageURL, isFolder=False)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def autoSelectQuality(playable):
        player_type = _player_type_.lower()
        if player_type == "hls":
            player_type = "iPad"
        setting_quality = ivysilani.Quality(_quality_, player_type)
        setting_quality.ad = _audio_description_
        url = playable.url(setting_quality)
        if url or not _quality_fallback_:
            return url
        all_qualities = [ "720p", "576p", "404p", "288p", "144p" ]
        for q in all_qualities:
            quality = ivysilani.Quality(q, player_type)
            if  setting_quality.height < quality.height:
                continue
            url = playable.url(quality)
            if url and quality.ad == setting_quality.ad:
                return url
            else:
                if _player_fallback_:
                    all_players = [ "iPad", "rtsp"]
                    for p in all_players:
                        quality = ivysilani.Quality(q, p)
                        url = playable.url(quality)
                        if url and quality.ad == setting_quality.ad:
                            return url
        return None

    def listLiveChannels():
        xbmcplugin.setContent(_handle_, "episodes")
        for liveChannel in ivysilani.LIVE_CHANNELS:
            title = _toString(liveChannel.title)
            live_programme = liveChannel.programme()
            if hasattr(live_programme, "title") and live_programme.title:
                title += ": " + _toString(live_programme.title)
            plot = None
            if hasattr(live_programme, "time") and live_programme.time:
                plot = _toString(_lang_(30001)) + " " + _toString(live_programme.time)
            if hasattr(live_programme, "elapsedPercentage") and live_programme.elapsedPercentage:
                plot += " (" + _toString(live_programme.elapsedPercentage) + "%)"
            if hasattr(live_programme, "synopsis") and live_programme.synopsis:
                plot += "\n\n" + _toString(live_programme.synopsis)
            if live_programme.ID:
                try:
                    programme = ivysilani.Programme(live_programme.ID)
                    if programme.videoURL:
                            url = _baseurl_ + "?play=" + liveChannel.ID
                            addDirectoryItem(title, url, ID=liveChannel.ID, plot=plot, image=live_programme.imageURL)
                            continue
                except:
                    pass
            title += " [" + _toString(_lang_(30002)) + "]"
            url = _baseurl_ + "?menu=live"
            addDirectoryItem(title, url, image=live_programme.imageURL)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def playUrl(title, url, image):
        li = xbmcgui.ListItem(title)
        li.setThumbnailImage(image)
        if _auto_unpause_:
            import threading
            t = threading.Thread(target=playAsync, args=(xbmc, xbmc.Player()))
            t.start()
            xbmc.sleep(100)
        xbmc.Player().play(url, li)

    def playAsync(x, p):
        player = AutoUnpausePlayer()
        while not player.isPlaying():
            x.sleep(10)
        xbmc.abortRequested = True
        logErr("started")
        while player.isPlaying():
            xbmc.sleep(10)
        logErr("stopped")
        del player
    
    class AutoUnpausePlayer (xbmc.Player):
      
        def __init__(self, *args, **kwargs):
            xbmc.Player.__init__(self)
        
        def onPlayBackStarted(self):
            while not xbmc.Player().isPlaying():
                xbmc.sleep(10)
            xbmc.sleep(1000)
            self._temp_pause = True        
            xbmc.Player().pause()
            logErr("autostart")
              
        def onPlayBackPaused(self):
            if self._temp_pause:
                xbmc.Player().play()
            self._temp_pause = False
        
        def onPlayBackSeek(self, time, seekOffset):
            xbmc.sleep(1000)
            self._temp_pause = True
            xbmc.Player().pause()
            logErr("seek")

    def playPlayable(playable, skipAutoQuality=False):
        image = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'logo_' + playable.ID.lower() + '_400x225.png'))
        if isinstance(playable, ivysilani.Programme):
            image = playable.imageURL
        if _auto_quality_ and not skipAutoQuality:
            url = autoSelectQuality(playable)
            if url:
                playUrl(playable.title, url, image)
                return
        qualities = playable.available_qualities()
        for quality in qualities:
            url = playable.url(quality)
            addDirectoryItem(quality.label(), url=url, title=_toString(playable.title), image=image, isFolder=False)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def playLiveChannel(liveChannel, skipAutoQuality=False):
        image = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'logo_' + liveChannel.ID.lower() + '_400x225.png'))
        if _auto_quality_ and not skipAutoQuality:
            url = autoSelectQuality(liveChannel)
            if url:
                playUrl(liveChannel.title, url, image)
                return
        qualities = liveChannel.available_qualities()
        for quality in qualities:
            url = liveChannel.url(quality)
            addDirectoryItem(quality.label(), url=url, title=_toString(liveChannel.title), image=image, isFolder=False)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def selectLiveChannel(ID):
        for liveChannel in ivysilani.LIVE_CHANNELS:
            if liveChannel.ID == ID:
                return liveChannel

    def listAlphabet():
        for letter in ivysilani.alphabet():
            addDirectoryItem(letter.title, _baseurl_ + "?letter=" + urllib.quote_plus(_toString(letter.link)))
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def listGenres():
        for genre in ivysilani.genres():
            addDirectoryItem(genre.title, _baseurl_ + "?genre=" + urllib.quote_plus(_toString(genre.link)))
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def listDates():
        day_names = []
        for i in range(7):
            day_names.append(_lang_(31000 + i))
        dt = datetime.now();
        min_date = datetime.fromtimestamp(time.mktime(time.strptime(ivysilani.DATE_MIN, "%Y-%m-%d")))
        while dt > min_date:
            pretty_date = day_names[dt.weekday()] + " " + dt.strftime("%d.%m.%Y")
            formated_date = dt.strftime("%Y-%m-%d")
            addDirectoryItem(pretty_date, _baseurl_ + "?date=" + urllib.quote_plus(formated_date))
            dt = dt - timedelta(days=1)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)


    def listChannelsForDate(date):
        for channel in ivysilani.LIVE_CHANNELS:
            image = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'resources', 'media', 'logo_' + channel.ID.lower() + '_400x225.png'))
            url = _baseurl_ + "?date=" + urllib.quote_plus(date) + "&channel=" + channel.ID
            addDirectoryItem(_toString(channel.title), url, image=image)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False, cacheToDisc=False)

    def listContext(what, ID, page):
        xbmcplugin.setContent(_handle_, "episodes")
        programme = ivysilani.Programme(ID)
        l = []
        if what == "related":
            l = programme.related(page)
        elif what == "episodes":
            l = programme.episodes(page)
        elif what == "bonuses":
            l = programme.bonuses(page)
        if page > 1:
            addDirectoryItem('[B]<< ' + _lang_(30007) + '[/B]', _baseurl_ + "?" + what + "=" + ID + "&page=" + str(page - 1), image=_previous_)
        for item in l:
            plot = None
            if hasattr(item, "synopsis") and item.synopsis:
                plot = item.synopsis
            addDirectoryItem(item.title, _baseurl_ + "?play=" + item.ID, ID=item.ID, related=True, plot=plot, image=item.imageURL)
        if len(l) == ivysilani.PAGE_SIZE:
            addDirectoryItem('[B]' + _lang_(30006) + ' >>[/B]', _baseurl_ + "?" + what + "=" + ID + "&page=" + str(page + 1), image=_next_)
        _setViewMode("Media info")
        xbmcplugin.endOfDirectory(_handle_, updateListing=(page > 1), cacheToDisc=False)

    def _sendError(params, exc_type, exc_value, exc_traceback):
        status = "no status"
        try:
            conn = httplib.HTTPSConnection('script.google.com')
            req_data = urllib.urlencode({ 'addon' : _scriptname_, 'version' : _version_, 'params' : _toString(params), 'type' : exc_type, 'value' : exc_value, 'traceback' : _toString(traceback.format_exception(exc_type, exc_value, exc_traceback))})
            headers = {"Content-type": "application/x-www-form-urlencoded"}
            conn.request(method='POST', url='/macros/s/AKfycbyZfKhi7A_6QurtOhcan9t1W0Tug-F63_CBUwtfkBkZbR2ysFvt/exec', body=req_data, headers=headers)
            resp = conn.getresponse()
            while resp.status >= 300 and resp.status < 400:
                location = resp.getheader('Location')
                o = urlparse(location, allow_fragments=True)
                host = o.netloc
                conn = httplib.HTTPSConnection(host)
                url = o.path + "?" + o.query
                conn.request(method='GET', url=url)
                resp = conn.getresponse()
            if resp.status >= 200 and resp.status < 300:
                resp_body = resp.read()
                json_body = json.loads(resp_body)
                status = json_body['status']
                if status == 'ok':
                    return True
                else:
                    logErr(status)
        except:
            pass
        logErr(status)
        return False

    def get_params():
            param = []
            paramstring = sys.argv[2]
            if len(paramstring) >= 2:
                    params = sys.argv[2]
                    cleanedparams = params.replace('?', '')
                    if (params[len(params) - 1] == '/'):
                            params = params[0:len(params) - 2]
                    pairsofparams = cleanedparams.split('&')
                    param = {}
                    for i in range(len(pairsofparams)):
                            splitparams = {}
                            splitparams = pairsofparams[i].split('=')
                            if (len(splitparams)) == 2:
                                    param[splitparams[0]] = splitparams[1]
            return param

    def assign_params(params):
        for param in params:
            try:
                globals()[param] = urllib.unquote_plus(params[param])
            except:
                pass
    menu = None
    play = None
    play_live = None
    genre = None
    letter = None
    date = None
    channel = None
    related = None
    episodes = None
    bonuses = None
    skip_auto = None
    page = 1
    params = get_params()
    assign_params(params)
    page = int(page)

    try:
        if play:
            skip_auto = (skip_auto is not None and skip_auto != "0")
            playable = selectLiveChannel(play)
            if not playable:
                playable = ivysilani.Programme(play)
            playPlayable(playable, skip_auto)
        elif genre:
            for g in ivysilani.genres():
                if g.link == genre:
                    listProgrammelist(g, episodes=True)
                    _setViewMode("Media info")
                    break
        elif letter:
            for l in ivysilani.alphabet():
                if _toString(l.link) == _toString(letter):
                    listProgrammelist(l, episodes=True)
                    _setViewMode("Media info")
                    break
        elif date and channel:
            listProgrammelist(ivysilani.Date(date, selectLiveChannel(channel)))
            _setViewMode("Media info")
        else:
            if date:
                listChannelsForDate(date)
                _setViewMode('Media info 2')
            elif related:
                listContext("related", related, page)
                _setViewMode("Media info")
            elif episodes:
                listContext("episodes", episodes, page)
                _setViewMode("Media info")
            elif bonuses:
                listContext("bonuses", bonuses, page)
                _setViewMode("Media info")
            elif menu:
                _setViewMode('List')
                if menu == "live":
                    listLiveChannels()
                elif menu == "byDate":
                    listDates()
                elif menu == "byLetter":
                    listAlphabet()
                elif menu == "byGenre":
                    listGenres()
                else:
                    for spotlight in ivysilani.SPOTLIGHTS:
                        if spotlight.ID == menu:
                            listProgrammelist(spotlight)
                            break
            else:
                mainMenu()
    except Exception as ex:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logErr(traceback.format_exception(exc_type, exc_value, exc_traceback))
        found = False
        for wnm in well_known_error_messages:
            if ex.message == wnm[0]:
                xbmcgui.Dialog().notification(_scriptname_, _lang_(wnm[1]), xbmcgui.NOTIFICATION_ERROR)
                found = True
        if not found:
            _exception_log(exc_type, exc_value, exc_traceback)
except Exception as ex:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    _exception_log(exc_type, exc_value, exc_traceback)
