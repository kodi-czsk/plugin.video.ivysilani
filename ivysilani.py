#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper pro iVysílání České televize
"""

import httplib
import urllib2
import urllib
import xml.etree.ElementTree as ET
import time

__author__ = "Štěpán Ort"
__license__ = "MIT"
__version__ = "1.0.1"
__email__ = "stepanort@gmail.com"

# Abstraktní třída pro výpisy
class _ProgrammeList:

	def _programmeListFetch(self, params):
		data = _fetch(PROGRAMMELIST_URL, params)
		programmes = ET.fromstring(data)
		output = []
		for item in programmes:				
			programme = Programme()
			for child in item:
				setattr(programme, child.tag, child.text)
			output.append(programme)
		return output
	
	def list(self):
		params = self._identifier()
		params["imageType"] = IMAGE_WIDTH
		return self._programmeListFetch(params)

# Výběry
class Spotlight(_ProgrammeList):

	def __init__(self, ID, label):
		self.ID = ID
		self.label = label
		
	def _identifier(self):
		return { "spotlight" : self.ID }

# Přehled pro datum a kanál
class Date(_ProgrammeList):
	
	def _validate_date(self, date_text):
		date_format = '%Y-%m-%d'
		date = None
		try:
			date = time.strptime(date_text, date_format)
		except ValueError:
			raise ValueError("Incorrect data format, should be YYYY-MM-DD")
		min_date = time.strptime(DATE_MIN, date_format)
		if date < min_date:
			raise ValueError("Must be after " + DATE_MIN)
		
	def __init__(self, date, live_channel):
		self._validate_date(date)
		self.date = date
		self.live_channel = live_channel
		
	def _identifier(self):
		return { "date" : self.date,
				"channel" : self.live_channel.channel }

# Přehled pro písmeno		
class Letter(_ProgrammeList):
	
	def __init__(self, title, link):
		self.title = title
		self.link = link
		
	def _identifier(self):
		return { "letter": _toString(self.link) }
	
# Přehled pro žánr
class Genre(_ProgrammeList):
	_identifier_name = "genre"
	
	def __init__(self, title, link):
		self.title = title
		self.link = link
		
	def _identifier(self):
		return { "genre": self.link }

class Quality():
	
	def __init__(self, quality, playerType=None):
		if not playerType:
			parts = quality.split('_')
			playerType = parts[0]
			quality = parts[1]
		self.height = self._height(quality)
		self.playerType = self._properPlayerType(playerType)
		self.ad = False
		if quality == "AD":
			self.ad = True

	def _height(self, quality):
		if quality == "web":
			return 576
		if quality == "mobile":
			return 288
		if quality == "AD":
			return -1
		return int(quality[0:-1])
	
	def quality(self):
		if self.ad:
			return "AD"
		if self.playerType == "iPad":
			if self.height == 576:
				return "web"
			if self.height == 288:
				return "mobile"
		return str(self.height) + "p"

	def label(self):
		out = ""
		if self.playerType == "iPad":
			out += "HLS"
		else:
			out += "RTSP"
		out += ": "
		if self.ad:
			out += "AD"
		else:
			out += str(self.height) + "p"
		return out
	
	def __eq__(self, obj):
		return isinstance(obj, Quality) and obj.__str__() == self.__str__()
	
	def __hash__(self):
		return self.__str__().__hash__()
		
	def __repr__(self):
		return self.__str__()
			
	def __str__(self):
		return self.playerType + "_" + self.quality()
	
	def _properPlayerType(self, playerType):
		if playerType == "flash":
			return "rtsp"
		return playerType

# Abstraktní třída zprostředkovává přístup ke kvalitě a odkazu na video
class _Playable:
	
	def available_qualities(self):
		params = { "playerType": "flash",
			   "quality": "web",
			   "ID": self.ID }
		data = _fetch(PLAYLISTURL_URL, params)
		playlisturl = ET.fromstring(data)
		data = urllib2.urlopen(playlisturl.text).read()
		root = ET.fromstring(data)
		switchItem = root.find("smilRoot/body/switchItem")
		videos = switchItem.findall("video")
		for video in videos:
			label = video.get("label")
			quality = Quality(label, "flash")
			if quality not in self._links():
				url = switchItem.get("base") + "/" + video.get("src")
				self._links()[quality] = url
			hls_quality = Quality(label, "iPad")
			self.url(hls_quality)
		qualities = self._links().keys()
		return sorted(qualities, key=lambda quality: quality.height + (0.5 if quality.playerType == "iPad" else 0), reverse=True)
	
	def _links(self):
		try:
			if not self.__links__:
				self.__links__ = {}
		except:
			self.__links__ = {}
		return self.__links__

	def url(self, quality):
		url = None
		quality = Quality(str(quality))			
		if quality in self._links():
			url = self._links()[quality]
			return url
		params = { "ID": self.ID,
				   "playerType": quality.playerType }
		if quality.playerType == "rtsp":
			params["playerType"] = "flash"
			params["quality"] = "web"
		else:
			params["quality"] = quality.quality()
		data = None
		try:
			data = _fetch(PLAYLISTURL_URL, params)
		except:
			return None
		root = ET.fromstring(data)
		if root.tag == "errors":
			raise Exception(', '.join([e.text for e in root]))
		playlist_url = root.text
		playlist_data = urllib2.urlopen(playlist_url).read()
		root = ET.fromstring(playlist_data)
		videos = root.findall("smilRoot/body//video")
		for video in videos:
			if 'label' not in video.attrib or video.get("label") == quality.quality():
				url = video.get("src")
				break
		if not url:
			return None
		switchItem = root.find("smilRoot/body/switchItem")
		if switchItem:
			url = switchItem.get("base") + "/" + url
		if quality.playerType == "iPad":
			try:
				if urllib2.urlopen(url).getcode() == 200:
						self._links()[quality] = url
			except urllib2.HTTPError:
				return None
		return url

# Kanál
class LiveChannel(_Playable):
	
	_programme = None
	
	def __init__(self, channel, ID, title):
		self.channel = channel
		self.ID = ID
		self.title = title
		
	def programme(self):
		if self._programme is None:
			self._refresh()
		return self._programme
	
	def _refresh(self):
		params = { "imageType": IMAGE_WIDTH,
			   "current": 1,
			   "channel": self.channel }
		data = _fetch(PROGRAMMELIST_URL, params)
		if data is None:
			return None
		root = ET.fromstring(data)
		if root.tag == "errors":
			raise Exception(', '.join([e.text for e in root]))
		self._programme = Programme()
		programme = root[0][0][0]
		for child in programme:
			setattr(self._programme, child.tag, child.text)
			
# Program
class Programme(_Playable):
	

	def __init__(self, ID=None):
		if ID is None:
			return
		params = { "imageType": IMAGE_WIDTH,
			   	   "ID":  ID}
		data = _fetch(PROGRAMMEDETAIL_URL, params)
		if data is None:
			return None
		root = ET.fromstring(data)
		if root.tag == "errors":
			raise Exception(', '.join([e.text for e in root]))
		programme = root
		for child in programme:
			setattr(self, child.tag, child.text)
	
	def _list(self, name, current_page, page_size):
		if page_size is None:
			page_size = PAGE_SIZE
		params = { "ID": self.ID,
				   "paging[" + name + "][currentPage]": current_page,
				   "paging[" + name + "][pageSize]": page_size,
				   "imageType": IMAGE_WIDTH,
				   "type[0]": name }
		data = _fetch(PROGRAMMELIST_URL, params)
		if data is None:
			return None
		root = ET.fromstring(data)
		if root.tag == "errors":
			raise Exception(', '.join([e.text for e in root]))
		output = []
		for item in root.findall(name + "/programme"):
			programme = Programme()
			for child in item:
				setattr(programme, child.tag, child.text)
			output.append(programme)
		return output
	
	def related(self, current_page=1, page_size=None):
		return self._list("related", current_page, page_size)
	
	def episodes(self, current_page=1, page_size=None):
		return self._list("episodes", current_page, page_size)
		
	def bonuses(self, current_page=1, page_size=None):
		return self._list("bonuses", current_page, page_size)
		

## --- privátní metody - začátek --- ###

def _toString(text):
	if type(text).__name__ == 'unicode':
		output = text.encode('utf-8')
	else:
		output = str(text)
	return output

def _https_ceska_televize_fetch(url, params):
	headers = { "Content-type": "application/x-www-form-urlencoded",
				"Accept-encoding": "gzip",
				"Connection": "Keep-Alive",
            	"User-Agent": "Dalvik/1.6.0 (Linux; U; Android 4.4.4; Nexus 7 Build/KTU84P)" }
	conn = httplib.HTTPSConnection("www.ceskatelevize.cz")
	conn.request("POST", url, urllib.urlencode(params), headers)
	response = conn.getresponse()
	if response.status == 200:
		data = response.read()
		conn.close()
		return data
	return None

_token = None
def _token_refresh():
	params = { "user": "iDevicesMotion" }
	data = _https_ceska_televize_fetch(TOKEN_URL, params)
	global _token
	_token = ET.fromstring(data).text

def _fetch(url, params):
	if _token is None:
		_token_refresh()
	params["token"] = _token
	data = _https_ceska_televize_fetch(url, params)
	root = ET.fromstring(data)
	if root.tag == "errors":
		if root[0].text == "no _token sent" or root[0].text == "wrong _token":
			_token_refresh()
			data = _https_ceska_televize_fetch(url, params)
		else:
			raise Exception(', '.join([e.text for e in root]))
	return data

def _fetch_list(url, output, cls):
	if output is not None:
		return output
	data = _fetch(url, {})
	genres = ET.fromstring(data)
	output = []
	for child in genres:
		title = child.find("title").text
		link = child.find("link").text
		output.append(cls(title, link))
	return output

## --- privátní metody - konec --- ###

# výpis žánrů
_genres = None
def genres():
	global _genres
	_genres = _fetch_list(GENRELIST_URL, _genres, Genre)
	return _genres

# výpis písmen abecedy
_alphabet = None
def alphabet():
	global _alphabet
	_alphabet = _fetch_list(ALPHABETLIST_URL, _alphabet, Letter)
	return _alphabet

DATE_MIN = "2005-02-01"
TOKEN_URL = "/services/ivysilani/xml/token/"
PROGRAMMELIST_URL = "/services/ivysilani/xml/programmelist/"
PROGRAMMEDETAIL_URL = "/services/ivysilani/xml/programmedetail/"
GENRELIST_URL = "/services/ivysilani/xml/genrelist/"
PLAYLISTURL_URL = "/services/ivysilani/xml/playlisturl/"
ALPHABETLIST_URL = "/services/ivysilani/xml/alphabetlist/"

IMAGE_WIDTH = 400  # doporučeno na TheTvDB Wiki
PLAYER_TYPES = ["iPad", "rtsp", "flash"]
PLAYER_TYPE = "iPad"

# Audio Descrition není dostupné pomoci HLS (playerType=iPad)
QUALITIES = ["AD", "mobile", "web", "144p", "288p", "404p", "576p", "720p"]  # mobile=288p web=576p


PAGE_SIZE = 25

# Živě
LIVE_CHANNELS = [ LiveChannel(1, "CT1", "ČT1"),
				  LiveChannel(2, "CT2", "ČT2"),
				  LiveChannel(24, "CT24", "ČT24"),
				  LiveChannel(4, "CT4", "ČT Sport"),
				  LiveChannel(5, "CT5", "ČT :D"),
				  LiveChannel(6, "CT6", "ČT art") ]

# Výběry
SPOTLIGHTS = [ Spotlight("tipsMain", "Tipy"),
			   Spotlight("topDay", "Nejsledovanější dne"),
			   Spotlight("topWeek", "Nejsledovanější týdne"),
			   Spotlight("tipsNote", "Nepřehlédněte"),
			   Spotlight("tipsArchive", "Z našeho archivu"),
			   Spotlight("watching", "Ostatní právě sledují")]
