UPnP DA checktool (sniffer)
===============

The tool is intended to perform control for devices that perform user with various functions as a UPnP Device Architecture is a control point.


Usage
--------

	$ ./upnp_da_check.py ifname

on the command line. Execution path you are free.


Examples
--------

	$ ./upnp_da_check.py eth0
	
	== UPnP DA checktool (sniffer) ==
	--------------------------------
	interface: [eth0 (43.3.177.96)]
	workerThread queue: [Hi:0, Mid:0, Lo:0]
	Multicast receive: [running]
	Cache-Control: [enable]
	debug print: [off]
	--------------------------------

	console start...
	./upnp_da_check.py >
	./upnp_da_check.py >
	./upnp_da_check.py >

Console will rise when you start the program.


	./upnp_da_check.py > ls
	uuid:55076f6e-6b79-1d65-a497-xxxxxxxxxxxx [ 1808]  3/3 [TomServer] PacketVideo  http://43.3.183.246:9000/dev0/desc.xml
	uuid:af75600b-2db7-428a-968a-xxxxxxxxxxxx [ 1797]  2/2 [KDL-50W800C] Sony Corporation  http://43.31.111.140:34278/sony/webapi/ssdp/dd.xml
	uuid:13814000-8752-1052-bfff-xxxxxxxxxxxx [ 1799]  -/- []   http://43.2.18.222:52323/upnp_description.xml
	uuid:434c8e6b-44ea-439a-81a4-xxxxxxxxxxxx [ 1791]  2/2 [KDL-GN2] Sony Corporation  http://43.31.109.4:12725/sony/webapi/ssdp/dd.xml
	uuid:4326e843-52e7-43d8-9e61-xxxxxxxxxxxx [ 1797]  1/1 [KDL-50W800C] Sony Corporation  http://43.31.111.140:43733/dd.xml
	uuid:5D076f6e-6b79-1d65-a497-xxxxxxxxxxxx [ 1808]  0/0 [Twonky NMC Queue Handler [JPC20313410]] PacketVideo  http://43.3.183.246:9000/dev1/desc.xml
	uuid:cfe92100-67c4-11d4-a45f-xxxxxxxxxxxx [ 1797]  2/2 [EPSON52DBB0] EPSON  http://43.2.60.163/DEVICE/PRINTER1.XML
	uuid:23456789-1234-1010-8000-xxxxxxxxxxxx [ 1791]  3/3 [KD-65S8505C] Sony Corporation  http://43.3.173.179:52323/MediaRenderer.xml
	uuid:4D454930-0100-1000-8000-xxxxxxxxxxxx [ 1799]  -/- []   http://43.31.111.141:60606/A81374451162/Server0/ddd
	uuid:5B076f6e-6b79-1d65-a497-xxxxxxxxxxxx [ 1808]  0/0 [TwonkyProxy [JPC20313410]] PacketVideo  http://43.3.183.246:9000/dev2/desc.xml
	uuid:a36e2757-2f7f-491b-8b4a-xxxxxxxxxxxx [  899]  3/3 [JPC00141623: 0000131404:] Microsoft Corporation  http://43.31.105.114:2869/upnphost/udhisapi.dll?content=uuid:a36e2757-2f7f-491b-8b4a-b4ae5dfbe4f8
	---------
	11 items.
	./upnp_da_check.py >

as long as it receives the discover packet and keeps the information to the device list.  
You have to display a list with the ls command.  
This is when there is some upnp enabled devices on the LAN if.


	./upnp_da_check.py > info uuid:cfe92100-67c4-11d4-a45f-xxxxxxxxxxxx
	uuid:cfe92100-67c4-11d4-a45f-xxxxxxxxxxxx [ 1771]  2/2 [EPSON52DBB0] EPSON  http://43.2.60.163/DEVICE/PRINTER1.XML
	====      Detail Info      ====
	.
	.
	.

If you pass the argument UDN to info command, detailed information for that device appears.  
(Display content here it will omitted.)  
\- Discover the contents of the packet  
\- Location overview of the content of  
\- The Published service list  
\- In-service there is what kind of action, and information of the argument to pass to the action  
etc...


	./upnp_da_check.py > act uuid:cfe92100-67c4-11d4-a45f-xxxxxxxxxxxx
	uuid:cfe92100-67c4-11d4-a45f-xxxxxxxxxxxx [ 1596]  2/2 [EPSON52DBB0] EPSON  http://43.2.60.163/DEVICE/PRINTER1.XML
	  ____________________
	  Select service type.
	  --------------------
	    1. urn:schemas-upnp-org:service:PrintBasic:1
	    2. urn:schemas-upnp-org:service:PrintEnhanced:1
	
	      Enter No. --> 

If you pass the argument UDN to act command, you can perform the action of the public service for the equipment.  
You choose whether first how to service.


	      Enter No. --> 2
	        service type is [urn:schemas-upnp-org:service:PrintEnhanced:1].
	
	    Select action.
	      1. GetPrinterAttributesV2
	      2. X_GetPrinterStatusString
	      3. CreateJob
	      4. GetJobAttributes
	      5. CreateJobV2
	      6. GetMargins
	      7. CancelJob
	      8. CreateURIJob
	      9. GetMediaList
	      10. GetPrinterAttributes
	
	        Enter No. --> 

After selecting the service, you will select the action.


	        Enter No. --> 2
	          action is [X_GetPrinterStatusString].
	
	
	    Response.  >>>status:[200 OK]
	               >>>body: <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:X_GetPrinterStatusStringResponse xmlns:u="urn:schemas-upnp-org:service:PrintEnhanced:1"><X_PrinterStatusString>paSl86WvpKy7xKTqvq+kyqSvpMqkw6TGpKSk3qS5oaM=</X_PrinterStatusString><X_ErrorReason>noerror</X_ErrorReason></u:X_GetPrinterStatusStringResponse></s:Body></s:Envelope>
	
	     --- X_PrinterStatusString:[paSl86WvpKy7xKTqvq+kyqSvpMqkw6TGpKSk3qS5oaM=] ---
	     --- X_ErrorReason:[noerror] ---
	
	    Hit Enter. (return to -Select service type.-)

Result of action has been returned.  
You can view the contents of the HTTP status code and the body, you have to display the value obtained in the action.
"X_PrinterStatusString" results I have indicates that the ink is running low.


	  ____________________
	  Select service type.
	  --------------------
	    1. urn:schemas-upnp-org:service:PrintBasic:1
	    2. urn:schemas-upnp-org:service:PrintEnhanced:1
	
	      Enter No. --> q
	./upnp_da_check.py >
	./upnp_da_check.py > q
	console end.
	$ 
	$ 
	
When the exit from the console, enter the "q".


Tool in the command
------------
- ls  [UDN|ipaddr|friendlyName]  - show device list (friendlyName can be specified by wildcard.)"
- an  UDN                        - analyze device (connect to device and get device info.)"
- info  UDN                      - show device info"
- act  UDN                       - send action to device"
- r                              - join multicast group (toggle on(def)/off)"
- t                              - cache-control (toggle enable(def)/disable)"
- sc  [ipaddr]                   - send SSDP M-SEARCH"
- sd  http-url                   - simple HTTP downloader"
- ss                             - show status"
- c                              - show command hitory"
- h                              - show command referense"
- d                              - debug log (toggle on/off(def))"
- q                              - exit from console"



Platforms
------------
Ubuntu, Fedora

These in operation verification settled.
I think when you work with other distributions.
You need to install some of the python module depending on the operating environment.
