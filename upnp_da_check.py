#!/usr/bin/env python
#coding: utf-8

import socket
import sys
import fcntl
import re  
from httplib import HTTPResponse
from StringIO import StringIO
import re
from xml.etree import ElementTree
from urlparse import urlparse
import urllib
import urllib2
import threading
from enum import Enum
import select
from sys import argv
import inspect
import datetime
import locale
import signal
from threading import Condition, Thread 
import time
import itertools
import copy
import os


NAMESPACE_UPNP_DEVICE   = "urn:schemas-upnp-org:device-1-0"
NAMESPACE_UPNP_SERVICE  = "urn:schemas-upnp-org:service-1-0"
NAMESPACE_DLNA_DEVICE   = "urn:schemas-dlna-org:device-1-0"          # prefix="dlna"
NAMESPACE_SPTV_DEVICE   = "urn:schemas-skyperfectv-co-jp:device-1-0" # prefix="sptv"
NAMESPACE_HDLINK_DEVICE = "urn:schemas-hdlnk-org:device-1-0"         # prefix="hdlnk"
NAMESPACE_SONY_AV       = "urn:schemas-sony-com:av"                  # prefix="av"
NAMESPACE_JLABS_DEVICE  = "urn:schemas-jlabs-or-jp:device-1-0"       # prefix="jlabs"

#NAMESPACE_DIDL          = "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
#NAMESPACE_DC_ELEMENT    = "http://purl.org/dc/elements/1.1/"            # prefix="dc"
#NAMESPACE_UPNP_METADATA = "urn:schemas-upnp-org:metadata-1-0/upnp/"     # prefix="upnp"
#NAMESPACE_DLNA_METADATA = "urn:schemas-dlna-org:metadata-1-0/"          # prefix="dlna"
#NAMESPACE_ARIB_METADATA = "urn:schemas-arib-or-jp:elements-1-0/"        # prefix="arib"
#NAMESPACE_SPTV_METADATA = "urn:schemas-skyperfectv-co-jp:elements-1-0/" # prefix="sptv"
#NAMESPACE_XSRS_METADATA = "urn:schemas-xsrs-org:metadata-1-0/x_srs/"    # prefix="xsrs"
#NAMESPACE_DTCP_METADATA = "urn:schemas-dtcp-com:metadata-1-0/"          # prefix="dtcp"

NAMESPACE_XMLSOAP_ENV   = "http://schemas.xmlsoap.org/soap/envelope/"

ENCODING_STYLE_XMLSOAP  = "http://schemas.xmlsoap.org/soap/encoding/"

SIOCGIFADDR = 0x8915

MSEARCH_TTL = 4
MSEARCH_TIMEOUT = 5


gDeviceInfoMap = {}
gCmdList = []
gBeforeCmd = "" 
gChunkedRemain = 0
gIfAddr = ""
gIfName = ""
gIsCatchSigInt = False
gIsDebugPrint = False
gBaseQue = None
gWorkerThread = None
gMRThread = None
gTimerThread = None
gLockDeviceInfoMap = threading.Lock()


class State(Enum):
	INIT      = 0
	ANALYZING = 1
	ANALYZED  = 2
	ERROR     = 3

class Priority(Enum):
	LOW  = 0
	MID  = 1
	HIGH = 2

class DeviceInfo():
	def __init__(self, idx, content, addr, loc, usn, age):
		# discovery
		self.__idx = idx
		self.__content = content
		self.__addr = addr
		self.__loc = loc
		self.__usn = usn # key in map
		self.__age = age

		# from location
		self.__locBody = ""
		self.__urlBase = ""
		self.__udn = ""
		self.__friendlyName = ""
		self.__deviceType = ""
		self.__manufactureName = ""
		self.__dlnaType = ""
		self.__serviceListMap = {}

		# state
		self.__state = State.INIT
		self.__successPerGetScpd = " -/-"


	def clearForModMap(self):
		self.__friendlyName = ""
		self.__manufactureName = ""
		self.__state = State.INIT
		self.__successPerGetScpd = " -/-"


	# discovery
	def getIdx(self):
		return self.__idx

	def setIdx(self, idx):
		self.__idx = idx

	def getContent(self):
		return self.__content

	def setContent(self, content):
		self.__content = content

	def getIpAddr(self):
		return self.__addr

	def setIpAddr(self, addr):
		self.__addr = addr

	def getLocUrl(self):
		return self.__loc

	def setLocUrl(self, loc):
		self.__loc = loc

	def getUsn(self):
		return self.__usn

	def setUsn(self, usn):
		self.__usn = usn

	def getAge(self):
		return self.__age

	def setAge(self, age):
		self.__age = age

	def decAge(self):
		if self.__age > 0:
			self.__age = self.__age - 1

	def getLocUrlBase(self):
		debugPrint("DeviceInfo.getLocUrlBase")
		if len(self.__loc) > 0:
			o = urlparse(self.__loc)
			if o is not None:
				locUrlBase = o.scheme + "://" + o.netloc + "/"
			else:
				locUrlBase = ""
		else:
			locUrlBase = ""

		return locUrlBase


	# from location
	def setLocBody(self, body):
		self.__locBody = body

	def setUrlBase(self, urlBase):
		self.__urlBase = urlBase

	def getUrlBase(self):
		return self.__urlBase

	def setUdn(self, udn):
		self.__udn = udn

	def getFriendlyName(self):
		return self.__friendlyName

	def setFriendlyName(self, name):
		self.__friendlyName = name

	def setDeviceType(self, _type):
		self.__deviceType = _type

	def setManufactureName(self, name):
		self.__manufactureName = name

	def setDlnaType(self, _type):
		self.__dlnaType = _type

	def setServiceListMap(self, _map):
		self.__serviceListMap = _map

	def getServiceListMap(self):
		return self.__serviceListMap


	# state
	def getState(self):
		return self.__state

	def setState(self, state):
		self.__state = state

	def setSuccessPerGetScpd(self, arg):
		self.__successPerGetScpd = arg


	def printListFormat(self):
		print "%s %5d %s [%s] [%s] %s" % (self.__usn.ljust(45)[:45], self.__age, self.__successPerGetScpd,
												self.__friendlyName.ljust(20)[:20], self.__manufactureName.ljust(20)[:20], self.__loc)

	def printInfo(self):
		print "==============================="
		print "====      Detail Info      ===="
		print "==============================="
		print ""
		print "---- Discover Packet ----"
		print ""
		print self.__content
		print ""
		print "---- Location Info ----"
		print ""
		print "LocUrlBase:[%s]" % self.getLocUrlBase()
		print "UrlBase:[%s]" % self.__urlBase
		print "UDN:[%s]" % self.__udn
		print "FriendlyName:[%s]" % self.__friendlyName
		print "DeviceType:[%s]" % self.__deviceType
		print "ManufactureName:[%s]" % self.__manufactureName
		if len (self.__dlnaType) > 0:
			print "Dlna:[%s]" % self.__dlnaType
		print ""
#		debugPrint(self.__locContent)
		print "---- Service List ----"
		print ""
		if len(self.__serviceListMap) > 0:
			for key in self.__serviceListMap:
				serviceInfo = self.__serviceListMap[key]

				print "---------------------------------------------------------------------------------"
				print "ServiceType:[%s] ScpdUrl:[%s]" % (serviceInfo.getType(), serviceInfo.getScpdUrl())
				print ""
#				debugPrint(serviceInfo.getScpdContent())
#				debugPrint(str(serviceInfo.getServiceStateTableMap().items()))
				if len(serviceInfo.getActionListMap()) > 0:
					for key in serviceInfo.getActionListMap():
						actlm = serviceInfo.getActionListMap()[key]
						print " - action:[%s]" % actlm.getName()
						if len(actlm.getArgumentList()) > 0:
							for argl in iter(actlm.getArgumentList()):
								stateInfo = None
								dataType = ""
								valueList = ""
								range = ""
								if len(argl.getRelatedStateVariable()) > 0:
									if len(serviceInfo.getServiceStateTableMap()) > 0:
										if serviceInfo.getServiceStateTableMap().has_key(argl.getRelatedStateVariable()):
											stateInfo = serviceInfo.getServiceStateTableMap()[argl.getRelatedStateVariable()]
											dataType = stateInfo.getDataType()

											if len(stateInfo.getAllowedValueList()) > 0:
#												debugPrint(str(stateInfo.getAllowedValueList()))
												listNum = len(stateInfo.getAllowedValueList())
												valueList = "(allowedValue: "
												for si_it in iter(stateInfo.getAllowedValueList()):
													valueList += si_it
													listNum = listNum -1
													if listNum > 0:
														valueList += ", "
												valueList += ")"

											if len(stateInfo.getAllowedValueRange()) > 0:
#												debugPrint(str(stateInfo.getAllowedValueRange()))
												range = "(range: "
												range += stateInfo.getAllowedValueRange()[0]
												range += "~"
												range += stateInfo.getAllowedValueRange()[1]

												if len(stateInfo.getAllowedValueRange()[2]) > 0:
													range += ", step"
													range += stateInfo.getAllowedValueRange()[2]

												range += ")"
												
								print "       [(%s)%s] ...(type: %s) %s%s" % (argl.getDirection(), argl.getName(), dataType, valueList, range)


				else:
					print " - action is none."

				print "---------------------------------------------------------------------------------"
				print ""
		else:
			print "none."

class ServiceInfo():
	def __init__(self, _type, scpdUrl, controlUrl, eventSubUrl):
		self.__type = _type
		self.__scpdUrl = scpdUrl
		self.__controlUrl = controlUrl
		self.__eventSubUrl = eventSubUrl
		self.__scpdBody = ""
		self.__actionListMap = {}
		self.__serviceStateTableMap = {}

	def getType(self):
		return self.__type

	def getScpdUrl(self):
		return self.__scpdUrl

	def getControlUrl(self):
		return self.__controlUrl

	def getEventSubUrl(self):
		return self.__eventSubUrl

	def setScpdBody(self, body):
		self.__scpdBody = body

	def getScpdContent(self):
		return self.__scpdContent

	def setActionListMap(self, map):
		self.__actionListMap = map

	def getActionListMap(self):
		return self.__actionListMap

	def setServiceStateTableMap(self, map):
		self.__serviceStateTableMap = map

	def getServiceStateTableMap(self):
		return self.__serviceStateTableMap

class ActionInfo():
	def __init__(self, name, argumentList, serviceType):
		self.__name = name
		self.__argumentList = argumentList
		self.__serviceType = serviceType

	def getName(self):
		return self.__name

	def getArgumentList(self):
		return self.__argumentList

	def getServiceType(self):
		return self.__serviceType

class ArgumentInfo():
	def __init__(self, name, direction, relatedStateVariable):
		self.__name = name
		self.__direction = direction
		self.__relatedStateVariable = relatedStateVariable

	def getName(self):
		return self.__name

	def getDirection(self):
		return self.__direction

	def getRelatedStateVariable(self):
		return self.__relatedStateVariable

class ServiceStateInfo():
	def __init__(self, name, dataType, defaultValue, allowedValueList, allowedValueRange, isSendEvents):
		self.__name = name
		self.__dataType = dataType
		self.__defaultValue = defaultValue
		self.__allowedValueList = allowedValueList

		# tuple[0]: range min
		# tuple[1]: range max
		# tuple[2]: step
		self.__allowedValueRange = allowedValueRange

		self.__isSendEvents = isSendEvents

	def getName(self):
		return self.__name

	def getDataType(self):
		return self.__dataType

	def getDefaultValue(self):
		return self.__defaultValue

	def getAllowedValueList(self):
		return self.__allowedValueList

	# return tuple
	#     tuple[0]: range min
	#     tuple[1]: range max
	#     tuple[2]: step
	def getAllowedValueRange(self):
		return self.__allowedValueRange

	def isSendEvents(self):
		return self.__isSendEvents

class HttpResponse(HTTPResponse):
	def __init__(self, response):
		self.fp = StringIO(response)
		self.debuglevel = 0
		self.strict = 0
		self.msg = None
		self._method = None
		self.begin()

# singleton
class BaseQue():
	def __init__(self):
		self.__queHi = []
		self.__queMi = []
		self.__queLo = []
		self.__cond = Condition()

	# msg is MessageObject()
	def enQue(self, msg):
		self.__cond.acquire()
		debugPrint(str(msg));

		if msg.priority is Priority.HIGH:
			self.__queHi.append(msg)
		elif msg.priority is Priority.MID:
			self.__queMi.append(msg)
		else:
			self.__queLo.append(msg)

		self.__cond.notify()
		self.__cond.release()

	def waitQue(self):
		self.__cond.acquire()
		debugPrint("");
		self.__cond.wait()
		self.__cond.release()

	def deQue(self):
		self.__cond.acquire()
		debugPrint("que num:[Hi:%d,Mid:%d,Lo:%d]" % (len(self.__queHi), len(self.__queMi), len(self.__queLo)))
		popObj = None
		if len(self.__queHi) > 0:
			popObj = self.__queHi.pop(0)
		elif len(self.__queMi) > 0:
			popObj = self.__queMi.pop(0)
		elif len(self.__queLo) > 0:
			popObj = self.__queLo.pop(0)
		self.__cond.release()
		return popObj

	# return tuple
	#     tuple[0]: queue list
	#     tuple[1]: condition object
	def get(self, priority):
		if priority is Priority.HIGH:
			return (self.__queHi, self.__cond)
		elif priority is Priority.MID:
			return (self.__queMi, self.__cond)
		else:
			return (self.__queLo, self.__cond)

# reply object for Message().sendSync()
class UniqQue():
	def __init__(self):
		self.__cond = Condition()
		self.__isAlreadyReply = False
		self.__replyMsg = None

	def reply(self, msg):
		self.__cond.acquire()
		self.__replyMsg = msg
		self.__isAlreadyReply = True;
		self.__cond.notify()
		self.__cond.release()

	def receive(self):
		if self.__isAlreadyReply:
			return self.__replyMsg
		else:
			self.__cond.acquire()
			self.__cond.wait()
			self.__cond.release()
			return self.__replyMsg

class MessageObject():
	def __init__(self, cbFunc, isNeedArg, arg, replyObj, isNeedRtnVal, priority, opt):
		self.cbFunc = cbFunc
		self.isNeedArg = isNeedArg
		self.arg = arg
		self.replyObj = replyObj
		self.isNeedRtnVal = isNeedRtnVal
		self.priority = priority
		self.opt = opt
		self.isEnable = True

class Message():
	@staticmethod
	def sendSync (cbFunc, isNeedArg, arg, isNeedRtnVal, priority):
		if cbFunc is None or\
			isNeedArg is None or\
			isNeedRtnVal is None or\
			priority is None or\
			gBaseQue is None:
			return

		uniqQue = UniqQue()
		msg = MessageObject (cbFunc, isNeedArg, arg, uniqQue, isNeedRtnVal, priority, None)
		gBaseQue.enQue (msg)
		return uniqQue.receive()

	@staticmethod
	def sendAsync (cbFunc, isNeedArg, arg, priority):
		if cbFunc is None or\
			isNeedArg is None or\
			priority is None or\
			gBaseQue is None:
			return

		msg = MessageObject (cbFunc, isNeedArg, arg, None, False, priority, None)
		gBaseQue.enQue (msg)

	# for msearch
	@staticmethod
	def sendAsyncFromMsearch (cbFunc, isNeedArg, arg, priority):
		if cbFunc is None or\
			isNeedArg is None or\
			priority is None or\
			gBaseQue is None:
			return

		msg = MessageObject (cbFunc, isNeedArg, arg, None, False, priority, "by_msearch")
		gBaseQue.enQue(msg)

#class Message():
#	def __init__(self, cbFunc, isNeedArg, arg, priority):
#		self.__cbFunc = cbFunc
#		self.__isNeedArg = isNeedArg
#		self.__arg = arg
#		self.__priority = priority
#
#	# cbFunc need return
#	def sendSync (self):
#		if self.__cbFunc is None or\
#			self.__isNeedArg is None or\
#			self.__priority is None or\
#			gBaseQue is None:
#			return
#
#		uniqQue = UniqQue()
#		msg = MessageObject (self.__cbFunc, self.__isNeedArg, self.__arg, uniqQue, True, self.__priority, None)
#		gBaseQue.enQue (msg)
#		return uniqQue.receive()
#
#	def sendAsync (self):
#		if self.__cbFunc is None or\
#			self.__isNeedArg is None or\
#			self.__priority is None or\
#			gBaseQue is None:
#			return
#
#		msg = MessageObject (self.__cbFunc, self.__isNeedArg, self.__arg, None, False, self.__priority, None)
#		gBaseQue.enQue (msg)
#
#	# for msearch
#	def sendAsyncFromMsearch (self):
#		if self.__cbFunc is None or\
#			self.__isNeedArg is None or\
#			self.__priority is None or\
#			gBaseQue is None:
#			return
#
#		msg = MessageObject (self.__cbFunc, self.__isNeedArg, self.__arg, None, False, self.__priority, "by_msearch")
#		gBaseQue.enQue(msg)

class WorkerThread (threading.Thread):
	def __init__(self):
		super(WorkerThread, self).__init__()
		self.daemon = True
		self.__nowExecQue = None

	def run(self):
		while True:
			rtnVal = None

			# que is MessageObject()
			que = gBaseQue.deQue()
			if que is None:
				gBaseQue.waitQue()
			else:
				if not que.isEnable:
					debugPrint("this queue is ignore")
					continue

				self.__nowExecQue = que

				debugPrint("worker thread exec")

				if que.isNeedRtnVal:
					if que.isNeedArg:
						rtnVal = que.cbFunc(que.arg)
					else:
						rtnVal = que.cbFunc()
				else:
					if que.isNeedArg:
						que.cbFunc(que.arg)
					else:
						que.cbFunc()

				if que.replyObj is not None:
					# que.replyObj is UniqQue()
					que.replyObj.reply(rtnVal)

				self.__nowExecQue = None

	# reference only
	def getNowExecQue(self):
		return copy.deepcopy(self.__nowExecQue)

class MulticastReceiveThread(threading.Thread):
	def __init__(self):
		super(MulticastReceiveThread, self).__init__()
		self.daemon = True
		self.__cond = Condition()
		self.__isEnable = True

	def run(self):
		# server address = "" --> INADDR_ANY
		serverAddr = ("", 1900)
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.bind(serverAddr)
		mreq = socket.inet_aton("239.255.255.250") + socket.inet_aton(gIfAddr)
		sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

		while True:
			try:
				if not self.__isEnable:
					self.__cond.acquire()
					self.__cond.wait()
					self.__cond.release()

				buff, addr = sock.recvfrom(4096)
#				debugPrint(str(addr))
#				debugPrint(buff)
				strAddr = addr[0]

				loc = self.__getHeader(buff, "Location")
				usn = self.__getHeader(buff, "USN")
				nts = self.__getHeader(buff, "NTS")
				cc = self.__getHeader(buff, "Cache-Control")

				if (loc is not None) and (usn is not None) and (nts is not None):

					spUsn = usn.split("::")
					keyUsn = spUsn[0]
					debugPrint("key:[%s]" % keyUsn)

					ageNum = -1
					if re.search("max-age *=", cc, re.IGNORECASE):
						spCc = cc.split("=")
						age = spCc[1].strip()
						if age.isdigit():
							ageNum = long(age)

					# lock
					gLockDeviceInfoMap.acquire()

					if re.match("ssdp *: *alive", nts, re.IGNORECASE):
						if gDeviceInfoMap.has_key(keyUsn):
							# mod hash map
							gDeviceInfoMap[keyUsn].clearForModMap()
							gDeviceInfoMap[keyUsn].setContent(buff)
							gDeviceInfoMap[keyUsn].setIpAddr(strAddr)
							gDeviceInfoMap[keyUsn].setLocUrl(loc)
							gDeviceInfoMap[keyUsn].setUsn(keyUsn)
							gDeviceInfoMap[keyUsn].setAge(ageNum)

						else:
							# add hash map
							gDeviceInfoMap[keyUsn] = DeviceInfo(0, buff, strAddr, loc, keyUsn, ageNum)


						##################################
						# not queuing if there is piled in that queue at the same [usn]
						if not self.__checkAlreadyQueuing(keyUsn):
							Message.sendAsync(analyze, True, gDeviceInfoMap[keyUsn], Priority.LOW)
#							msg = Message (analyze, True, gDeviceInfoMap[keyUsn], Priority.LOW)
#							msg.sendAsync()
						else:
							debugPrint("not queuing")
						##################################


					elif re.match("ssdp *: *byebye", nts, re.IGNORECASE):
						if gDeviceInfoMap.has_key(keyUsn):

							# delete in timerThread
							gDeviceInfoMap[keyUsn].setAge(0)

					# unlock
					gLockDeviceInfoMap.release()

			except:
				putsExceptMsg()

		sock.close()

	def toggle(self):
		if self.__isEnable:
			self.__isEnable = False
			print "[UPnP multicast receive stop]"
		else:
			self.__isEnable = True
			self.__cond.acquire()
			self.__cond.notify()
			self.__cond.release()
			print "[UPnP multicast receive start]"

	def isEnable(self):
		return self.__isEnable

	def __checkAlreadyQueuing(self, keyUsn):
		isFound = False
		# Priority.LOW is multicast receive
		q = gBaseQue.get(Priority.LOW)
		qList = q[0]
		qCond = q[1]
		qCond.acquire()
		if len(qList) > 0:
			for it in iter(qList):
				if it.arg.getUsn() == keyUsn:
					isFound = True
		qCond.release()
		return isFound

	def __getHeader(self, content, pattern):
		if content is None or content == "" or\
			pattern is None or pattern == "":
			return None

		regPattern = "^ *%s *:" % pattern

		term = "\r\n"
		while True:
			contentArray = content.split(term)
			if len(contentArray) > 0:
				for i in iter(contentArray):
					if re.search(regPattern, i, re.IGNORECASE):
						n = 0
						for j in iter(i):
							if str(j) == ":":
								out = str(i[n+1:])
								out = out.strip()
								return out
							n = n + 1

				if term == "\r\n":
					term = "\n"
					continue
				else:
					break
			else:
				if term == "\r\n":
					term = "\n"
					continue
				else:
					break

		return None

class TimerThread(threading.Thread):
	def __init__(self):
		super(TimerThread, self).__init__()
		self.daemon = True
		self.__cond = Condition()
		self.__isEnable = True

	def run(self):
		while True:
			if not self.__isEnable:
				self.__cond.acquire()
				self.__cond.wait()
				self.__cond.release()

			time.sleep(1)
			self.__refreshAge()

	def __refreshAge(self):
		gLockDeviceInfoMap.acquire() # lock

		delKeyList = []
		if len(gDeviceInfoMap) > 0:
			for key in gDeviceInfoMap:
				info = gDeviceInfoMap[key]
				info.decAge()
				if info.getAge() <= 0:
					debugPrint("age is 0. [%s]" % key)

					# disable queue @ this usn
					self.__disableAnalyzeQueue(key)

					nowExecQue = gWorkerThread.getNowExecQue()
					if nowExecQue is not None:
						if (nowExecQue.cbFunc != analyze) or (nowExecQue.arg.getUsn() != key):
							delKeyList.append(key)
						else:
							debugPrint("[%s] is analyzing. don't detele." % key)
					else:
						delKeyList.append(key)

			if len(delKeyList) > 0:
				for itKey in iter(delKeyList):
					# delete hash map
					del gDeviceInfoMap[itKey]
					debugPrint("delete hash map:[%s]" % itKey)

		gLockDeviceInfoMap.release() # unlock

	def __disableAnalyzeQueue (self, usn):
		q = gBaseQue.get(Priority.HIGH)
		qList = q[0]
		qCond = q[1]
		qCond.acquire()
		if len(qList) > 0:
			for it in iter(qList):
				if it.cbFunc == analyze and it.arg.getUsn() == usn:
					it.isEnable = False
		qCond.release()

		q = gBaseQue.get(Priority.MID)
		qList = q[0]
		qCond = q[1]
		qCond.acquire()
		if len(qList) > 0:
			for it in iter(qList):
				if it.cbFunc == analyze and it.arg.getUsn() == usn:
					it.isEnable = False
		qCond.release()

		q = gBaseQue.get(Priority.LOW)
		qList = q[0]
		qCond = q[1]
		qCond.acquire()
		if len(qList) > 0:
			for it in iter(qList):
				if it.cbFunc == analyze and it.arg.getUsn() == usn:
					it.isEnable = False
		qCond.release()

	def toggle(self):
		if self.__isEnable:
			self.__isEnable = False
			print "[cache-control(max-age) disable]"
		else:
			self.__isEnable = True
			self.__cond.acquire()
			self.__cond.notify()
			self.__cond.release()
			print "[cache-control(max-age) enable]"

	def isEnable(self):
		return self.__isEnable

class BaseFunc():
	def __recvSocket(self, sock):
		debugPrint("recvSocket")
		totalData = ""
		isContinue = False

		while True:
			data = sock.recv(65536)
			if not data:
				debugPrint("disconnected from server")
				# TODO
				if len(totalData) > 0:
					return totalData
				else:
					return None

			debugPrint("sock.recv size " + str(len(data)))
			totalData += data

			# timeout 50mS
			readfds = set([sock])
			rList, wList, xList = select.select(readfds, [], [], 0.05)
			for r in iter(rList):
				if r == sock:
					debugPrint("sock in rList")
					isContinue = True

			if isContinue:
				isContinue = False
				continue
			else:
				break

		return totalData

	# return tuple
	#     tuple[0]: return code
	#               0: ok (all received)
	#               1: still the rest of the data
	#               2: error
	#               3: header is not able to receive all
	#               4: chuked body
	#     tuple[1]: remain size (return code is valid only when the 1)
	#     tuple[2]: HTTP status code
	def __checkHttpResponse(self, buff):
		isHeaderReceived = False
		term = ""
		httpStatus = ""

		# check whether it has header reception completion
		if buff.find("\r\n\r\n") >= 0:
			isHeaderReceived = True
			term = "\r\n"
		else:
			if buff.find("\n\n") >= 0:
				isHeaderReceived = True
				term = "\n"
			else:
				isHeaderReceived = False

		debugPrint("is all header received ? --> " + str(isHeaderReceived))
		if isHeaderReceived:
			res = HttpResponse(buff)
			debugPrint("res status %d %s" % (res.status, res.reason))
			httpStatus = "%d %s" % (res.status, res.reason)
#			if res.status != 200:
#				# error
#				return (2, 0, httpStatus)

			cl = res.getheader("Content-Length")
			debugPrint("content length ------- " + str(cl))
			if cl is not None:
				spBuff = buff.split(term+term)
				if len(spBuff) >= 2:

					# check spBuff data
					length = 0
					for i in range(0, len(spBuff)):
						if i != 0:
							length = length + len(spBuff[i])
							if i >= 2:
								length = length + len(term+term)
					debugPrint("current content length %d" % length)

					if long(cl) == length:
						# all received
						debugPrint("all received")
						return (0, 0, httpStatus)
					elif long(cl) > length:
						# still the rest of the data
						debugPrint("still the rest of the data")
						return (1, long(cl) - length, httpStatus)
					else:
						# error
						debugPrint("error")
						return (2, 0, httpStatus)
				else:
					# unexpected
					debugPrint("term split is unexpected.  len(spBuff) " + str(len(spBuff)))
					debugPrint("[" + buff + "]")
					return (2, 0, httpStatus)

			else:
				te = res.getheader("Transfer-Encoding")
				debugPrint("transfer encoding ------- " + str(te))
				if te is not None:
					if re.match("chunked", te, re.IGNORECASE):
						# chunked
						return (4, 0, httpStatus)
					else:
						#TODO
						# only chunked
						return (2, 0, httpStatus)
				else:
					debugPrint("[" + buff + "]")
					#TODO
					# Content-Length, Transfer-Encoding can not both exist
					# And it can be received for the time being all
					return (0, 0, httpStatus)

		else:
			# header is not able to receive all
			debugPrint("header is not able to receive all")
			debugPrint("[" + buff + "]")
			return (3, 0, httpStatus)

	def __checkChunkedData(self, data, isFirst):
		debugPrint("checkChunkedData")

		global gChunkedRemain
		chu = ""
		if isFirst:
			gChunkedRemain = 0

			spData = data.split("\r\n\r\n")
			if len(spData) >= 2:
				chu = spData[1];
			else:
				# unexpected
				return 2
		else:
			chu = data


		spChu = chu.split("\r\n")
#		debugPrint("spChu num:[%d]" % len(spChu))
		if len(spChu) == 1:
			# still the rest of the data @1line
			return 1

		elif len(spChu) > 1:
			i = 0
			rtn = 1 # init 1
			length = 0
			while len(spChu) > i:
#				debugPrint("[%s]" % str(spChu[i]))

				if len(spChu[i]) != 0:
					if self.__isHexCharOnly(spChu[i]):
						gChunkedRemain = long(spChu[i], 16)
						debugPrint("gChunkedRemain " + str(gChunkedRemain))
						if gChunkedRemain == 0:
							debugPrint("chunked data complete")
							return 0
					else:
						if len(spChu[i]) == gChunkedRemain:
							rtn = 1
						elif len(spChu[i]) < gChunkedRemain:
							gChunkedRemain = gChunkedRemain - len(spChu[i])
							rtn = 1
						else:
							# unexpected error
							return 2

				i = i + 1

		return rtn

	def __isHexCharOnly(self, st):
		if st is None or len(st) == 0:
			debugPrint("isHexCharOnly false")
			return False

		i = 0
		while len(st) > i:
			if (not re.search(r'[0-9]', st[i])) and (not re.search(r'[a-f]', st[i], re.IGNORECASE)):
				debugPrint("isHexCharOnly false")
				return False
			i = i + 1

		debugPrint("isHexCharOnly true")
		return True

	# return tuple
	#     tuple[0]: HTTP response body
	#     tuple[1]: HTTP status code
	def __sendrecv(self, addr, port, msg):
		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(5)
			sock.connect((addr, port))
			sock.send(msg)

			buffTotal = ""
			kind = -1
			remain = 0
			httpStatus = ""
			crtn = 0

			while True:
				buff = self.__recvSocket(sock)
				if buff is None:
					break

#				debugPrint("[" + buff + "]")
				buffTotal = buffTotal + buff

				if kind == -1 or kind == 3:
					rtn = self.__checkHttpResponse(buffTotal)
					debugPrint("checkHttpResponse " + str(rtn))
					kind = rtn[0]
					remain = rtn[1]
					httpStatus = rtn[2]

					if kind == 0:
						# ok (all received)
						break
					elif kind == 1:
						# still the rest of the data
						continue
					elif kind == 2:
						# error
						return (None, httpStatus)
					elif kind == 3:
						# header is not able to receive all
						continue
					elif kind == 4:
						# chuked body
						crtn = self.__checkChunkedData(buffTotal, True)
						if crtn == 0:
							# chunked data complete
							break
						elif crtn == 1:
							# still the rest of the data @1line
							continue
						else:
							# unexpected
							return (None, httpStatus)

				elif kind == 1:
					if remain == len(buff):
						debugPrint("remain == len(buff)")
						break
					elif remain > len(buff):
						debugPrint("remain > len(buff)")
						remain = remain - len(buff)
						continue
					else:
						return (None, httpStatus)

				elif kind == 4:
					crtn = self.__checkChunkedData(buff, False)
					if crtn == 0:
						break
					elif crtn == 1:
						continue
					else:
						return (None, httpStatus)

			sock.close()

			if len(buffTotal) > 0:
				res = HttpResponse(buffTotal)
#				debugPrint(buffTotal)
				body = res.read()
				res.close()
				return (body, httpStatus)
			else:
				return (None, httpStatus)

		except socket.timeout:
			sock.close()
			debugPrint("tcp socket timeout")
			return (None, "")

		except:
			sock.close()
			putsExceptMsg()
			return (None, "")

	def getHttpContent(self, addr, url):
		if addr is None or len(addr) == 0 or\
			url is None or len(url) == 0:
			return None

		debugPrint(url)

		port = 0
		rtn = urlparse(url)
		if rtn.port is None:
			port = 80
		else:
			port = rtn.port
		debugPrint("dst %s %d" % (addr, port))

		compPath = ""
		if len(rtn.query) > 0:
			compPath = rtn.path + "?" + rtn.query
		else:
			compPath = rtn.path

		compPath = re.sub("^/+", "/", compPath)

		if len(compPath) == 0:
			compPath = "/"

		msg  = "GET " + compPath + " HTTP/1.1\r\n"
		msg += "Host: %s:%s\r\n" % (addr, port)
#		msg += "Connection: close\r\n"
#		msg += "Connection: keep-alive\r\n"
		msg += "\r\n"
		debugPrint(msg)

		return self.__sendrecv(addr, port, msg)

	def postSoapAction(self, addr, url, actionInfo, reqArgList):
		if addr is None or len(addr) == 0 or\
			url is None or len(url) == 0 or\
			reqArgList is None or\
			actionInfo is None:
			return None

		debugPrint(url)

		port = 0
		rtn = urlparse(url)
		if rtn.port is None:
			port = 80
		else:
			port = rtn.port
		debugPrint("dst %s %d" % (addr, port))

		compPath = ""
		if len(rtn.query) > 0:
			compPath = rtn.path + "?" + rtn.query
		else:
			compPath = rtn.path

		compPath = re.sub("^/+", "/", compPath)


		nameSpaceServiceType = actionInfo.getServiceType()
		actionName = actionInfo.getName()

		contentHeader        = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n"
		contentHeader       += "<s:Envelope s:encodingStyle=\"%s\" xmlns:s=\"%s\">\r\n" % (ENCODING_STYLE_XMLSOAP, NAMESPACE_XMLSOAP_ENV)
		contentBody          = "  <s:Body>\r\n"
		contentBody         += "    <u:%s xmlns:u=\"%s\">\r\n" % (actionName, nameSpaceServiceType)
		for ai in iter(actionInfo.getArgumentList()):
			if ai.getDirection() == "in":
				contentBody += "      <%s>%s</%s>\r\n" % (ai.getName(), reqArgList.pop(0), ai.getName())
		contentBody         += "    </u:%s>\r\n" % (actionName)
		contentBody         += "  </s:Body>\r\n"
		contentFooter        = "</s:Envelope>\r\n"

		contentLength = len(contentHeader) + len(contentBody) + len(contentFooter)

		msg  = "POST " + compPath + " HTTP/1.1\r\n"
		msg += "Host: %s:%s\r\n" % (addr, port)
		msg += "Content-Type: text/xml; charset=\"utf-8\"\r\n"
		msg += "Content-Length: %d\r\n" % contentLength
		msg += "SOAPACTION: \"%s#%s\"\r\n" % (nameSpaceServiceType, actionName)
		msg += "\r\n"

#		msg  = "M-POST " + compPath + " HTTP/1.1\r\n"
#		msg += "Host: %s:%s\r\n" % (addr, port)
#		msg += "Content-Type: text/xml; charset=\"utf-8\"\r\n"
#		msg += "Content-Length: %d\r\n" % contentLength
#		msg += "MAN: \"%s\"; ns=01\r\n", NAMESPACE_XMLSOAP_ENV
#		msg += "01-SOAPACTION: \"%s#%s\"\r\n" % (nameSpaceServiceType, actionName)
#		msg += "\r\n"

		msg += contentHeader
		msg += contentBody
		msg += contentFooter

		debugPrint(msg)

		return self.__sendrecv(addr, port, msg)

	def getSoapResponse(self, xml, actionInfo):
		resArgList = []

		if xml is None or len(xml) == 0 or actionInfo is None:
			return resArgList

		if len(actionInfo.getArgumentList()) <= 0:
			return resArgList

		argList = actionInfo.getArgumentList()

		#TODO
#		xml = xml.replace("&quot;", "\"")
#		xml = xml.replace("&amp;", "&")
#		xml = xml.replace("&lt;", "<")
#		xml = xml.replace("&gt;", ">")
#		xml = xml.replace("&nbsp;", " ")
#		debugPrint("[%s]" % xml)

		rtn = ""
		nameSpaceServiceType = actionInfo.getServiceType()
		responseTagName = actionInfo.getName() + "Response"

		try:
			root = ElementTree.fromstring(xml)
			if root is not None:
				body = root.find(".//{%s}Body" % NAMESPACE_XMLSOAP_ENV)
				if body is not None:
					response = body.find(".//{%s}%s" % (nameSpaceServiceType, responseTagName))
					if response is not None:

						for ai in iter(argList):
							if ai.getDirection() == "out":
								debugPrint("find " + ai.getName())
								val = response.find(".//%s" % ai.getName())
								if val is not None:
									resArgList.append(val.text)

					else:
						debugPrint("%s is none." % responseTagName)
				else:
					debugPrint("Body is none.")
			else:
				debugPrint("root is none.")

			return resArgList

		except:
			putsExceptMsg()
			return resArgList

	def getSingleElement(self, xml, tag, namespace):
		if xml is None or len(xml) == 0:
			return ""
		if tag is None or len(tag) == 0:
			return ""

		form = ".//{%s}%s" % (namespace, tag)
		try:
			root = ElementTree.fromstring(xml)
			if root is not None:
				rtn = root.find(form)
				if rtn is not None:
					debugPrint("getSingleElement:[%s]" % rtn.text)
					return rtn.text

			return ""

		except:
			putsExceptMsg()
			return ""

	# return tuple
	#     tuple[0]: map
	#     tuple[1]: status True/False 
	def getServiceListMap(self, xml):
		if xml is None or len(xml) == 0:
			return ({}, False)

		serviceListMap = {}

		try:
			root = ElementTree.fromstring(xml)
			if root is not None:
				listRoot = root.find(".//{%s}serviceList" % NAMESPACE_UPNP_DEVICE)
				if listRoot is not None:
					list = listRoot.findall(".//{%s}service" % NAMESPACE_UPNP_DEVICE)
					if list is not None:
						for i in iter(list):
							type = i.find(".//{%s}serviceType" % NAMESPACE_UPNP_DEVICE).text
							scpdUrl = i.find(".//{%s}SCPDURL" % NAMESPACE_UPNP_DEVICE).text
							controlUrl = i.find(".//{%s}controlURL" % NAMESPACE_UPNP_DEVICE).text
							eventSubUrl = i.find(".//{%s}eventSubURL" % NAMESPACE_UPNP_DEVICE).text

							debugPrint("type:[" + str(type) + "]")
							debugPrint("scpdUrl:[" + str(scpdUrl) + "]")
							debugPrint("controlUrl:[" + str(controlUrl) + "]")
							debugPrint("eventSubUrl:[" + str(eventSubUrl) + "]")

							if type is not None and len(type) != 0:
								# add hash map
								serviceListMap[type] = ServiceInfo(type, scpdUrl, controlUrl, eventSubUrl)

					else:
						debugPrint("service is none.")
				else:
					debugPrint("serviceList is none.")
			else:
				debugPrint("root is none.")

			return (serviceListMap, True)

		except:
			putsExceptMsg()
			return (serviceListMap, False)

	def getActionListMap(self, xml, type):
		if xml is None or len(xml) == 0 or\
			type is None or len(type) == 0:
			return {}

		actionListMap = {}

		try:
			root = ElementTree.fromstring(xml)
			if root is not None:
				listRoot = root.find(".//{%s}actionList" % NAMESPACE_UPNP_SERVICE)
				if listRoot is not None:
					list = listRoot.findall(".//{%s}action" % NAMESPACE_UPNP_SERVICE)
					if list is not None:
						for i in iter(list):
							name = i.find(".//{%s}name" % NAMESPACE_UPNP_SERVICE).text
							debugPrint("name:[" + str(name) + "]")

							#------------ argument list ------------#
							argumentList = []
							argListRoot = i.find(".//{%s}argumentList" % NAMESPACE_UPNP_SERVICE)
							if argListRoot is not None:
								argList = argListRoot.findall(".//{%s}argument" % NAMESPACE_UPNP_SERVICE)
								if argList is not None:
									for ai in iter(argList):
										argName = ai.find(".//{%s}name" % NAMESPACE_UPNP_SERVICE).text
										argDirection = ai.find(".//{%s}direction" % NAMESPACE_UPNP_SERVICE).text
										argRelatedStateVariable = ai.find(".//{%s}relatedStateVariable" % NAMESPACE_UPNP_SERVICE).text
										argumentList.append(ArgumentInfo(argName, argDirection, argRelatedStateVariable))
								else:
									debugPrint("argument is none.")
							else:
								debugPrint("argumentList is none.")
							#---------------------------------------#

							if name is not None and len(name) != 0:
								# add hash map
								actionListMap[name] = ActionInfo(name, argumentList, type)

					else:
						debugPrint("action is none.")
				else:
					debugPrint("actionList is none.")
			else:
				debugPrint("root is none.")

			return actionListMap

		except:
			putsExceptMsg()
			return actionListMap

	def __checkKeyNameDuplication(self, name, map, sp):
		if map.has_key(name):
			sp = sp + 1
			name += "-%d" % sp
			return self.__checkKeyNameDuplication(name, map, sp)
		else:
			return name

	def getServiceStateTableMap(self, xml):
		if xml is None or len(xml) == 0:
			return {}

		serviceStateTableMap = {}

		try:
			root = ElementTree.fromstring(xml)
			if root is not None:
				listRoot = root.find(".//{%s}serviceStateTable" % NAMESPACE_UPNP_SERVICE)
				if listRoot is not None:
					list = listRoot.findall(".//{%s}stateVariable" % NAMESPACE_UPNP_SERVICE)
					if list is not None:
						for i in iter(list):

							isSendEvents = False
							if i.attrib.has_key("sendEvents"):
								debugPrint("attrib sendEvents:" + str(i.attrib["sendEvents"]))
								if re.match(i.attrib["sendEvents"], "yes", re.IGNORECASE):
									isSendEvents = True
							else:
								debugPrint("attrib does not have [sendEvents]")

							name = i.find(".//{%s}name" % NAMESPACE_UPNP_SERVICE).text
							dataType = i.find(".//{%s}dataType" % NAMESPACE_UPNP_SERVICE).text

							defaultValue = ""
							defaultValueRoot = i.find(".//{%s}defaultValue" % NAMESPACE_UPNP_SERVICE)
							if defaultValueRoot is not None:
								defaultValue = defaultValueRoot.text

							#------------ allowed value list ------------#
							allowedValueList = []
							valueListRoot = i.find(".//{%s}allowedValueList" % NAMESPACE_UPNP_SERVICE)
							if valueListRoot is not None:
								valueList = valueListRoot.findall(".//{%s}allowedValue" % NAMESPACE_UPNP_SERVICE)
								if valueList is not None:
									for vl in iter(valueList):
										allowedValueList.append(vl.text)
								else:
									debugPrint("allowedValue is none.")
							else:
								debugPrint("allowedValueList is none.")
							#--------------------------------------------#

							#------------ allowed value range ------------#
							allowedValueRange = ()
							allowedValueRangeMin = ""
							allowedValueRangeMax = ""
							allowedValueRangeStep = ""
							valueRangeRoot = i.find(".//{%s}allowedValueRange" % NAMESPACE_UPNP_SERVICE)
							if valueRangeRoot is not None:
								valueMin = valueRangeRoot.find(".//{%s}minimum" % NAMESPACE_UPNP_SERVICE)
								valueMax = valueRangeRoot.find(".//{%s}maximum" % NAMESPACE_UPNP_SERVICE)
								valueStep = valueRangeRoot.find(".//{%s}step" % NAMESPACE_UPNP_SERVICE)
								if valueMin is not None:
									allowedValueRangeMin = valueMin.text
								if valueMax is not None:
									allowedValueRangeMax = valueMax.text
								if valueStep is not None:
									allowedValueRangeStep = valueStep.text

								allowedValueRange = (allowedValueRangeMin, allowedValueRangeMax, allowedValueRangeStep)
							else:
								debugPrint("allowedValueRange is none.")
							#---------------------------------------------#

							if name is not None and len(name) != 0:
								# add hash map
								serviceStateTableMap[name] = ServiceStateInfo(name, dataType, defaultValue, allowedValueList, allowedValueRange, isSendEvents)

					else:
						debugPrint("stateVariable is none.")
				else:
					debugPrint("serviceStateTable is none.")
			else:
				debugPrint("root is none.")

			return serviceStateTableMap

		except:
			putsExceptMsg()
			return serviceStateTableMap

class ControlPoint (BaseFunc):
	def __init__(self, arg0=None, arg1=None, arg2=None, arg3=None):
		self.__arg0 = arg0
		self.__arg1 = arg1
		self.__arg2 = arg2
		self.__arg3 = arg3

	def msearch (self):
		ipAddr = self.__arg0

		dstAddr = ""
		isMulticast = False

		if ipAddr is None:
			dstAddr = "239.255.255.250"
			isMulticast = True
		else:
			dstAddr = ipAddr
			isMulticast = False

		print "M-SEARCH start."

		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(MSEARCH_TIMEOUT)
		if isMulticast:
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(gIfAddr))
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MSEARCH_TTL)

		req  = "M-SEARCH * HTTP/1.1\r\n"
		req += "HOST: 239.255.255.250:1900\r\n"
		req += "MAN: \"ssdp:discover\"\r\n"
		req += "MX: %d\r\n" % MSEARCH_TIMEOUT
		req += "ST:upnp:rootdevice\r\n"
		req += "\r\n"

		sock.sendto(req, (dstAddr, 1900))

		queuingList = []
		while True:
			try:
				buff, addr = sock.recvfrom(4096)
#				debugPrint(addr)
#				debugPrint(buff)
				strAddr = addr[0]

				res = HttpResponse(buff)
				if res is not None:
					loc = res.getheader("Location")
					usn = res.getheader("USN")
					cc = res.getheader("Cache-Control")
					if loc is None:
						loc = ""
					if usn is None:
						usn = ""
					if cc is None:
						cc = ""

					spUsn = usn.split("::")
					keyUsn = spUsn[0]
					debugPrint("key:[%s]" % keyUsn)

					ageNum = -1
					if re.search("max-age *=", cc, re.IGNORECASE):
						spCc = cc.split("=")
						age = spCc[1].strip()
						if age.isdigit():
							ageNum = long(age)

					debugPrint(loc)

					# lock
					gLockDeviceInfoMap.acquire()

					if gDeviceInfoMap.has_key(keyUsn):
						# mod hash map
						gDeviceInfoMap[keyUsn].clearForModMap()
						gDeviceInfoMap[keyUsn].setContent(buff)
						gDeviceInfoMap[keyUsn].setIpAddr(strAddr)
						gDeviceInfoMap[keyUsn].setLocUrl(loc)
						gDeviceInfoMap[keyUsn].setUsn(keyUsn)
						gDeviceInfoMap[keyUsn].setAge(ageNum)

					else:
						# add hash map
						gDeviceInfoMap[keyUsn] = DeviceInfo(0, buff, strAddr, loc, keyUsn, ageNum)

					# unlock
					gLockDeviceInfoMap.release()

					# queuing list
					queuingList.append(gDeviceInfoMap[keyUsn])

				if not isMulticast:
					print "M-SEARCH end."
					break

			except socket.timeout:
				print "M-SEARCH end."
				break

			except:
				putsExceptMsg()
				break

		sock.close()

		if len(queuingList) > 0:
			for it in iter(queuingList):
				Message.sendAsyncFromMsearch(analyze, True, it, Priority.MID)
#				msg = Message (analyze, True, it, Priority.MID);
#				msg.sendAsyncFromMsearch();
		else:
			print "M-SEARCH not responding..."

		del queuingList

	def analyze (self):
		if self.__arg0 is None:
			return

		deviceInfo = self.__arg0

		if deviceInfo.getState() is State.ANALYZING:
			return

		debugPrint("----------------------------------------------- analyze start. usn:[%s]" % deviceInfo.getUsn())
		deviceInfo.setState(State.ANALYZING)

		response = self.getHttpContent(deviceInfo.getIpAddr(), deviceInfo.getLocUrl())
		responseLocBody = response[0]
		responseStatusCode = response[1]

		if responseLocBody is not None:
			deviceInfo.setLocBody(responseLocBody)

			urlBase = self.getSingleElement(responseLocBody, "URLBase", NAMESPACE_UPNP_DEVICE)
			udn = self.getSingleElement(responseLocBody, "UDN", NAMESPACE_UPNP_DEVICE)
			flName = self.getSingleElement(responseLocBody, "friendlyName", NAMESPACE_UPNP_DEVICE)
			devType = self.getSingleElement(responseLocBody, "deviceType", NAMESPACE_UPNP_DEVICE)
			manuName = self.getSingleElement(responseLocBody, "manufacturer", NAMESPACE_UPNP_DEVICE)
			dlnaType = self.getSingleElement(responseLocBody, "X_DLNADOC", NAMESPACE_DLNA_DEVICE)

			deviceInfo.setUrlBase(urlBase)
			deviceInfo.setUdn(udn)
			deviceInfo.setFriendlyName(flName)
			deviceInfo.setDeviceType(devType)
			deviceInfo.setManufactureName(manuName)
			deviceInfo.setDlnaType(dlnaType)

			numSuccessGetScpd = 0

			result = self.getServiceListMap(responseLocBody)
			serviceListMap = result[0]
			status = result[1]
			if len(serviceListMap) > 0:
				deviceInfo.setServiceListMap(serviceListMap)

				base = ""
				if len(urlBase) > 0:
					base = urlBase
				else:
					base = deviceInfo.getLocUrlBase()

				base = re.sub("/$", "", base)

				for key in serviceListMap:
					serviceInfo = serviceListMap[key]
					url = ""

					if serviceInfo.getScpdUrl() is None or len(serviceInfo.getScpdUrl()) == 0:
						continue

					o = urlparse(serviceInfo.getScpdUrl())
					if len(o.scheme) == 0:
						scpd = ""
						if not re.search("^/", serviceInfo.getScpdUrl()):
							scpd = "/" + serviceInfo.getScpdUrl()
						else:
							scpd = serviceInfo.getScpdUrl()
						url = base + scpd
					else:
						url = serviceInfo.getScpdUrl()

					responseScpd = self.getHttpContent(deviceInfo.getIpAddr(), url)
					responseScpdBody = responseScpd[0]
					responseScpdStatus = responseScpd[1]
#					debugPrint(str(responseScpdBody))
					if responseScpdBody is not None:
						serviceInfo.setScpdBody(responseScpdBody)

						actListMap = self.getActionListMap(responseScpdBody, serviceInfo.getType())
						if len(actListMap) > 0:
							serviceInfo.setActionListMap(actListMap)

						sstm = self.getServiceStateTableMap(responseScpdBody)
						if len(sstm) > 0:
							serviceInfo.setServiceStateTableMap(sstm)

						numSuccessGetScpd = numSuccessGetScpd + 1

			if status:
				deviceInfo.setState(State.ANALYZED)

				if numSuccessGetScpd == len(serviceListMap):
					rsltSuccessPerTotal = " %d/%d" % (numSuccessGetScpd, len(serviceListMap))
				else:
					rsltSuccessPerTotal = "*%d/%d" % (numSuccessGetScpd, len(serviceListMap))
				deviceInfo.setSuccessPerGetScpd(rsltSuccessPerTotal)
			else:
				# getServiceListMap() error
				deviceInfo.setState(State.ERROR)
		else:
			# location content HTTP error
			deviceInfo.setState(State.ERROR)

	# return tuple
	#     tuple[0]: resArgList
	#     tuple[1]: HTTP status code
	#     tuple[2]: HTTP response body
	def action (self):
		if self.__arg0 is None or\
			self.__arg1 is None or\
			self.__arg2 is None or\
			self.__arg3 is None:
			return (None, None, None)

		deviceInfo = self.__arg0
		serviceInfo = self.__arg1
		actionInfo = self.__arg2
		reqArgList = self.__arg3

		base = ""
		if len(deviceInfo.getUrlBase()) > 0:
			base = deviceInfo.getUrlBase()
		else:
			base = deviceInfo.getLocUrlBase()

		base = re.sub("/$", "", base)

		url = ""
		o = urlparse(serviceInfo.getControlUrl())
		if len(o.scheme) == 0:
			ctrlUrl = ""
			if not re.search("^/", serviceInfo.getControlUrl()):
				ctrlUrl = "/" + serviceInfo.getControlUrl()
			else:
				ctrlUrl = serviceInfo.getControlUrl()
			url = base + ctrlUrl
		else:
			url = serviceInfo.getControlUrl()

		response = self.postSoapAction(deviceInfo.getIpAddr(), url, actionInfo, reqArgList)
		responseBody = response[0]
		responseStatus = response[1]
		debugPrint("[%s]" % responseBody)

		resArgList = []
		if re.match("200 +OK", responseStatus, re.IGNORECASE):
			resArgList = self.getSoapResponse(responseBody, actionInfo)

		return (resArgList, responseStatus, responseBody)

def msearch (arg):
	cp = ControlPoint (arg)
	cp.msearch()

def sendMsearch (arg=None):
	if arg is None:
		nowExecQue = gWorkerThread.getNowExecQue()
		if (nowExecQue is not None) and (nowExecQue.cbFunc == msearch):
			print "now running..."
		else:
			q = gBaseQue.get(Priority.MID)
			qList = q[0]
			qCond = q[1]
			qCond.acquire()
			if len(qList) > 0:
				for it in iter(qList):
					if it.opt == "by_msearch":
						it.isEnable = False
			qCond.release()

			Message.sendAsync(msearch, True, None, Priority.HIGH)
#			msg = Message (msearch, True, None, Priority.HIGH);
#			msg.sendAsync();
	else:
		if checkStringIPv4 (arg):
			Message.sendAsync(msearch, True, arg, Priority.HIGH)
#			msg = Message (msearch, True, arg, Priority.HIGH);
#			msg.sendAsync();
		else:
			print "invalid argument..."

# args is tupple. for Message().sendSync()
#
# return tuple
#     tuple[0]: resArgList
#     tuple[1]: HTTP status code
#     tuple[2]: HTTP response body
def actionInnerWrapper(args):
	deviceInfo = args[0]
	serviceInfo = args[1]
	actionInfo = args[2]
	reqArgList = args[3]

	cp = ControlPoint (deviceInfo, serviceInfo, actionInfo, reqArgList)
	return cp.action()

def actionInner(deviceInfo, serviceType):
	if deviceInfo is None or\
		serviceType is None or len(serviceType) == 0:
		return False

	serviceInfo = deviceInfo.getServiceListMap()[serviceType]
	if len(serviceInfo.getActionListMap()) > 0:

		print "    Select action."
		num = 1
		numMap = {}
		tmpKey = 0
		for key in serviceInfo.getActionListMap():
			actlm = serviceInfo.getActionListMap()[key]
			print "      %d. %s" % (num, actlm.getName())
			numMap[num] = actlm.getName()
			num = num + 1
		print ""

		act = ""
		while True:
			sys.stdout.write("        Enter No. --> ")
			inStr = raw_input().strip()
			if gIsCatchSigInt:
				return False

			if checkStringNumber(inStr, 1, num-1):
				tmpKey = long(inStr)
				print "          action is [%s].\n" % numMap[tmpKey]
				break
			else:
				if inStr == "q":
					return True
				else:
					if len(inStr) > 0:
						print "          invalid value..."
					continue

		act = numMap[tmpKey]
		reqArgList = []
		if len(serviceInfo.getActionListMap()[act].getArgumentList()) > 0:
			for argl in iter(serviceInfo.getActionListMap()[act].getArgumentList()):
				if argl.getDirection() == "in":
					sys.stdout.write("        Enter argument:[%s] --> " % argl.getName())
					arg = raw_input().strip()
					if gIsCatchSigInt:
						return False

					reqArgList.append(arg)
		print ""

		argTuple = (deviceInfo, serviceInfo, serviceInfo.getActionListMap()[act], reqArgList)
		rtn = Message.sendSync(actionInnerWrapper, True, argTuple, True, Priority.HIGH)
#		msg = Message (actionInnerWrapper, True, argTuple, Priority.HIGH)
#		rtn = msg.sendSync()
		resArgList = rtn[0]
		responseStatus = rtn[1]
		responseBody = rtn[2]

		print "    Response.  >>>status:[%s]" % responseStatus
		if responseBody is not None and len(responseBody) > 0:
			print "               >>>body: %s" % responseBody

		print ""
		for argl in iter(serviceInfo.getActionListMap()[act].getArgumentList()):
			if argl.getDirection() == "out":
				res = ""
				if resArgList is not None and len(resArgList) > 0:
					res = resArgList.pop(0)
				print "     --- %s:[%s] ---" % (argl.getName(), res)


		sys.stdout.write("\n    Hit Enter. (return to -Select service type.-)")
		raw_input().strip()
		if gIsCatchSigInt:
			return False

		return True

	else:
		print "    action is none."
		return True

def action(arg):
	gLockDeviceInfoMap.acquire() # lock
	dcpMap = copy.deepcopy(gDeviceInfoMap)
	gLockDeviceInfoMap.release() # unlock

	if dcpMap.has_key(arg):
		info = dcpMap[arg]
		if info.getState() is State.ANALYZED:

			if len(info.getServiceListMap()) == 0:
				print "Service is none."
				del dcpMap
				return

			while True:
				print "  ____________________"
				print "  Select service type."
				print "  --------------------"
				num = 1
				numMap = {}
				tmpKey = 0
				for key in info.getServiceListMap():
					serviceInfo = info.getServiceListMap()[key]
					print "    %d. %s" % (num, serviceInfo.getType())
					numMap[num] = serviceInfo.getType()
					num = num + 1
				print ""

				while True:
					sys.stdout.write("      Enter No. --> ")
					inStr = raw_input().strip()
					if gIsCatchSigInt:
						del dcpMap
						return

					if checkStringNumber(inStr, 1, num-1):
						tmpKey = long(inStr)
						print "        service type is [%s].\n" % numMap[tmpKey]
						break
					else:
						if inStr == "q":
							del dcpMap
							return
						else:
							if len(inStr) > 0:
								print "        invalid value..."
							continue

				serviceType = numMap[tmpKey]
				if actionInner(info, serviceType):
					print ""
					continue
				else:
					break

			del dcpMap
			return
		else:
			print "Not yet analysis."
			del dcpMap
			return

	else:
		print "not found..."

	del dcpMap

def checkStringNumber(val, min, max):
	if not val.isdigit():
		return False

	if long(val) < min or long(val) > max:
		return False

	return True

def checkStringIPv4(val):
	spVal = val.split(".")
	if len(spVal) != 4:
		return False

	for i in iter(spVal):
		if not i.isdigit():
			return False

	return True

def listDevice (arg=None):
	gLockDeviceInfoMap.acquire() # lock
	dcpMap = copy.deepcopy(gDeviceInfoMap)
	gLockDeviceInfoMap.release() # unlock

	if len(dcpMap) == 0:
		print "none."
		del dcpMap
		return

	print "UDN                                           AGE    S/S FriendlyName           ManufactureName        LocationUrl"
	print "--------------------------------------------- ----- ---- ---------------------- ---------------------- -------------------------------------"

	if arg is None:
		n = 0
		for key in dcpMap:
			n = n + 1
			info = dcpMap[key]
			info.printListFormat()
		print "---------"
		print "%d items." % n

	else:
		if checkStringIPv4(arg):
			isFound = False
			n = 0
			for key in dcpMap:
				info = dcpMap[key]
				if arg == info.getIpAddr():
					n = n + 1
					info.printListFormat()
					isFound = True
			if isFound:
				print "---------"
				print "%d items." % n
			else:
				print "none."

		else:
			if dcpMap.has_key(arg):
				info = dcpMap[arg]
				info.printListFormat()
			else:
				# wild card
				arg = re.sub("\?", ".", arg)
				arg = re.sub("\*", ".*", arg)
				arg = "^" + arg + "$"
				isFound = False
				n = 0
				for key in dcpMap:
					info = dcpMap[key]
					if re.search(arg, info.getFriendlyName()):
						n = n + 1
						info.printListFormat()
						isFound = True
				if isFound:
					print "---------"
					print "%d items." % n
				else:
					print "none."

	del dcpMap

def info(arg):
	gLockDeviceInfoMap.acquire() # lock
	dcpMap = copy.deepcopy(gDeviceInfoMap)
	gLockDeviceInfoMap.release() # unlock

	if dcpMap.has_key(arg):
		info = dcpMap[arg]
		if info.getState() is State.ANALYZED:
			info.printInfo()
		else:
			print "Not yet analysis."
	else:
		print "not found..."

	del dcpMap

def analyze(deviceInfo):
	if deviceInfo is None:
		return

	if deviceInfo.getState() is State.ANALYZING:
		return

	cp = ControlPoint (deviceInfo)
	cp.analyze()

def manualAnalyze (arg):
	if gDeviceInfoMap.has_key(arg):
		info = gDeviceInfoMap[arg]
		Message.sendAsync(analyze, True, info, Priority.HIGH)
#		msg = Message (analyze, True, info, Priority.HIGH)
#		msg.sendAsync()
	else:
		print "not found..."

def downloadAtHttp (url):
	rtn = urlparse(url)
	if len(rtn.scheme) == 0:
		print "invalid url."
		return

	if not re.match("http$", rtn.scheme, re.IGNORECASE):
		print "%s is not support.  HTTP only..." % rtn.scheme
		return

	if rtn.hostname is None:
		print "invalid url."
		return

	dlName = ""
	if len(rtn.path) > 0:
		spPath = rtn.path.split("/");
		if len(spPath) > 0:
			if len (spPath[len(spPath) -1]) > 0:
				dlName = spPath[len(spPath) -1]
			else:
				dlName = "download.data"
		else:
			dlName = "download.data"
	else:
		dlName = "download.data"
#	print "dlName[%s]" % dlName
	dlFullPath = "%s/%s" % (os.path.abspath(os.path.dirname(__file__)), dlName)

	bf = BaseFunc ()
	response = bf.getHttpContent (rtn.hostname, url)
	if len (response[1]) == 0:
		print "can not download...  maybe GET request is abnormal."
	else:
		if re.match("200 OK", response[1], re.IGNORECASE):
			print "downloaded  (status=%s) (%d bytes)" % (response[1], len(response[0]))

			if os.path.exists (dlFullPath):
				n = 1
				while True:
					if not os.path.exists ("%s.%d" % (dlFullPath, n)):
						break
					n = n + 1

				dlFullPath = "%s.%d" % (dlFullPath, n)

			f = open (dlFullPath, "w")
			try:
				f.write (response[0])
			finally:
				f.close ()
				print "save %s" % dlFullPath

		else:
			print "can not download...  (status=%s)" % response[1]

def getIfAddr(ifName):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		#TODO
		# The third argument is requesting a 32byte ???
		result = fcntl.ioctl(s.fileno(), SIOCGIFADDR, (ifName+"\0"*32)[:32])
	except IOError:
		return None

	# The purpose of the data is entered from the results obtained 20byte in ioctl to 23byte th
	return socket.inet_ntoa(result[20:24])

def putsGlobalState():
	print "--------------------------------"
	print "interface: [%s (%s)]" % (gIfName, gIfAddr)

	q = gBaseQue.get(Priority.HIGH)
	qList = q[0]
	qCond = q[1]
	qCond.acquire()
	h = len(qList)
	qCond.release()

	q = gBaseQue.get(Priority.MID)
	qList = q[0]
	qCond = q[1]
	qCond.acquire()
	m = len(qList)
	qCond.release()

	q = gBaseQue.get(Priority.LOW)
	qList = q[0]
	qCond = q[1]
	qCond.acquire()
	l = len(qList)
	qCond.release()

	print ("workerThread queue: [Hi:%d, Mid:%d, Lo:%d]" % (h, m, l))

	if gMRThread.isEnable():
		print "UPnP multicast receive: [running]"
	else:
		print "UPnP multicast receive: [stop]"

	if gTimerThread.isEnable():
		print "cache-control(max-age): [enable]"
	else:
		print "cache-control(max-age): [disable]"

	if gIsDebugPrint:
		print "debug print: [on]"
	else:
		print "debug print: [off]"

	print "--------------------------------"

def showHistory():
	it = iter(gCmdList)
	n = 0
	for i in it:
		n += 1
		print " %s %s" % (n, i)

def showHelp():
	print "  -- usage --"
	print "  upnp_da_check.py ifname"
	print ""
	print "  -- cli command --"
	print "  ls  [UDN|ipaddr|friendlyName]  - show device list (friendlyName can be specified by wildcard.)"
	print "  an  UDN                        - analyze device (connect to device and get device info.)"
	print "  info  UDN                      - show device info"
	print "  act  UDN                       - send action to device"
	print "  r                              - join UPnP multicast group (toggle on(def)/off)"
	print "  t                              - cache-control(max-age) (toggle enable(def)/disable)"
	print "  sc  [ipaddr]                   - send SSDP M-SEARCH"
	print "  sd  http-url                   - simple HTTP downloader"
	print "  ss                             - show status"
	print "  c                              - show command hitory"
	print "  h                              - show command referense"
	print "  d                              - debug log (toggle on/off(def))"
	print "  q                              - exit from console"

def cashCommand(cmd):
	global gBeforeCmd

	if (cmd != gBeforeCmd):
		gCmdList.append(cmd)

	gBeforeCmd = cmd

def checkCommand(cmd):
	global gIsDebugPrint

	if cmd is None:
		return True

	if cmd == "r":
		if gMRThread is not None:
			gMRThread.toggle()
		cashCommand(cmd)

	elif cmd == "t":
		if gTimerThread is not None:
			gTimerThread.toggle()
		cashCommand(cmd)

	elif cmd == "ss":
		putsGlobalState()
		cashCommand(cmd)

	elif cmd == "c":
		showHistory()
		cashCommand(cmd)

	elif cmd == "d":
		if gIsDebugPrint:
			gIsDebugPrint = False
			print "[debug print off]"
		else:
			gIsDebugPrint = True
			print "[debug print on]"
		cashCommand(cmd)

	elif cmd == "h":
		showHelp()
		cashCommand (cmd)

	elif cmd == "q":
		return False

	elif cmd == "!!":
		if checkCommand(gBeforeCmd):
			return True
		else:
			return False

	elif len(cmd) == 0:
		sys.stdout.flush()

	else:
		#------------------------------
		if re.search("^an ", cmd):
			spCmd = cmd.split()
			if len(spCmd) == 2:
				try:
					manualAnalyze(spCmd[1])
				except:
					putsExceptMsg()
			elif len(spCmd) > 2:
				print "invalid argument.\nargument is valid only one."
			else:
				print "Please set argument."
		elif re.search("^an$", cmd):
			print "Please set argument."


		#------------------------------
		elif re.search("^sc ", cmd):
			spCmd = cmd.split()
			if len(spCmd) == 2:
				try:
					sendMsearch (spCmd[1]);
				except:
					putsExceptMsg()
			elif len(spCmd) > 2:
				print "invalid argument.\nargument is valid only one."
			else:
				sendMsearch (None);				
		elif re.search("^sc$", cmd):
			sendMsearch ();


		#------------------------------
		elif re.search("^info ", cmd):
			spCmd = cmd.split()
			if (len(spCmd) == 2):
				try:
					info(spCmd[1])
				except:
					putsExceptMsg()
			elif len(spCmd) > 2:
				print "invalid argument.\nargument is valid only one."
			else:
				print "Please set argument."
		elif re.search("^info$", cmd):
			print "Please set argument."


		#------------------------------
		elif re.search("^ls ", cmd):
			spCmd = cmd.split()
			if (len(spCmd) == 2):
				try:
					listDevice(spCmd[1])
				except:
					putsExceptMsg()
			elif len(spCmd) > 2:
				print "invalid argument.\nargument is valid only one."
			else:
				print "Please set argument."
		elif re.search("^ls$", cmd):
			listDevice ()


		#------------------------------
		elif re.search("^act ", cmd):
			spCmd = cmd.split()
			if (len(spCmd) == 2):
				try:
					action(spCmd[1])
				except:
					putsExceptMsg()
			elif len(spCmd) > 2:
				print "invalid argument.\nargument is valid only one."
			else:
				print "Please set argument."
		elif re.search("^act$", cmd):
			print "Please set argument."


		#------------------------------
		elif re.search("^sd ", cmd):
			spCmd = cmd.split()
			if (len(spCmd) == 2):
				try:
					downloadAtHttp (spCmd[1])
				except:
					putsExceptMsg()
			elif len(spCmd) > 2:
				print "invalid argument.\nargument is valid only one."
			else:
				print "Please set argument."
		elif re.search("^sd$", cmd):
			print "Please set argument."


		#------------------------------
		else:
			print "%s: command not found" % cmd

		cashCommand(cmd)

	return True

def mainLoop():

	while True:
		sys.stdout.write(argv[0])
		sys.stdout.write(" > ")

		cmd = raw_input().strip()
		if gIsCatchSigInt:
			return

		if not checkCommand(cmd):
			return

def putsExceptMsg():
#	print "catch exception: (%d) %s" % (inspect.stack()[1][2], sys.exc_info())
	debugPrint("catch exception: %s" % str(sys.exc_info()))

def debugPrint(msg):
	if not gIsDebugPrint:
		return

	d = datetime.datetime.now()

	kind = 0
	term = ""
	if re.search("\r\n", msg):
		kind = 1
		term = "\r\n"
	elif re.search("\n", msg):
		kind = 1
		term = "\n"


	if kind == 0:
		compMsg = "[%s.%03d](%s(),%d) " % (d.strftime("%Y-%m-%d %H:%M:%S"), d.microsecond/1000, inspect.stack()[1][3], inspect.stack()[1][2])
		compMsg += msg
		print compMsg
	else:
		spMsg = msg.split(term)
		for i in spMsg:
			compMsg = "[%s.%03d](%s(),%d) " % (d.strftime("%Y-%m-%d %H:%M:%S"), d.microsecond/1000, inspect.stack()[1][3], inspect.stack()[1][2])
			compMsg += i
			print compMsg

def usage(arg):
	print "Usage: %s ifname" % arg

def sigHandler(signum, frame):
	debugPrint("catch signal %d %s" % (signum, frame))

	global gIsCatchSigInt
	if signum == signal.SIGINT:
		gIsCatchSigInt = True

def main(ifName):
	global gIfAddr
	global gIfName
	global gBaseQue
	global gWorkerThread
	global gMRThread
	global gTimerThread

	addr = getIfAddr(ifName)
	if addr is None:
		print "%s is not existed." % ifName
		return
	else:
		gIfAddr = addr
		gIfName = ifName

	#--  set signal handler
	signal.signal(signal.SIGINT, sigHandler)

	#--  create instance
	gBaseQue = BaseQue()
	gWorkerThread = WorkerThread()
	gMRThread = MulticastReceiveThread()
	gTimerThread = TimerThread()

	#--  start sub thread
	gWorkerThread.start()
	gMRThread.start()
	gTimerThread.start()

	print ""
	print "== UPnP DA checktool (sniffer) =="
	putsGlobalState()
	print ""

	print "console start..."
	mainLoop()
	print "console end..."

	#TODO  finish sub thread
#	gWorkerThread.join()
#	gMRThread.join()
#	timerThread.join()

if __name__ == "__main__":

	if len(sys.argv) == 2:
		main(sys.argv[1])
	else:
		usage(sys.argv[0])

