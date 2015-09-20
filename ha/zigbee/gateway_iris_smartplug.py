import xbee, struct, time, threading
import binascii # just for debugging

from socket import *

# Your device's extended address
EXT_ADDR = "[00:0d:6f:00:02:37:b0:4d]!"

# ZigBee Device Objects endpoint
ZDO_ENDPOINT = 0x00

# ZigBee Device Profile Application Profile Identifier
ZDP_PROFILE_ID = 0x0000

# Match Descriptor Request cluster prompts us to
# send special init messages to the Smart Plug
MATCH_DESCRIPTOR_REQUEST_CLUSTER = 0x0006

# Match Descriptor Response cluster
MATCH_DESCRIPTOR_RESP_CLUSTER = 0x8006

# Smart Iris endpoint
IRIS_ENDPOINT = 0x02

# profile id for the Iris Smart Plug messages (OEM AlertMe)
AM_PROFILE_ID = 0xC216

# Cluster for on/off notifications
CURRENT_STATUS_CLUSTER = 0x00EE

# Smart Plug power report cluster
POWER_REPORT_CLUSTER = 0x00EF

# listen for ZCL messages so we can send special init messages
# needed by the Iris Smart 
sd_announce = socket(AF_XBEE, SOCK_DGRAM, XBS_PROT_TRANSPORT)
sd_announce.bind(("", ZDO_ENDPOINT, 0, 0))
sd_announce.settimeout(1)

# listen and send higher level messages for control and reporting
sd_data = socket(AF_XBEE, SOCK_DGRAM, XBS_PROT_TRANSPORT)
sd_data.bind(("", IRIS_ENDPOINT, 0, 0))
sd_data.settimeout(1)

# pass through frames necessary to join Iris Smart Plug
xbee.ddo_set_param(None, "AO", 3)

# Set this true to print out extra message details
debug = False

def handle_message(sd):
    payload = None
    
    try:
        payload, (address_string, endpoint, profile_id, cluster_id, options_bitmask, transmission_id) = sd.recvfrom(255)
    except timeout:
        return False
    
    if debug: print "Received data from endpoint %02X profile %04X cluster %04X tid %02X: %s" % (endpoint, profile_id, cluster_id, transmission_id, binascii.hexlify(payload))
    
    # is it a ZDO level message?
    if endpoint == ZDO_ENDPOINT:
        if cluster_id == MATCH_DESCRIPTOR_REQUEST_CLUSTER:
            print "*** Sending special init messages"
            address = (EXT_ADDR, ZDO_ENDPOINT, ZDP_PROFILE_ID, MATCH_DESCRIPTOR_RESP_CLUSTER)
            sd_announce.sendto("\x00\x00\x00\x00\x01\x02", 0, address)      #
            address = (EXT_ADDR, IRIS_ENDPOINT, AM_PROFILE_ID, 0x00F6) 
            sd_announce.sendto("\x11\x01\x01", 0, address)
            address = (EXT_ADDR, IRIS_ENDPOINT, AM_PROFILE_ID, 0x00F0)
            sd_announce.sendto("\x19\x01\xfa\x00\x01", 0, address)
    elif endpoint == IRIS_ENDPOINT:
        if cluster_id == POWER_REPORT_CLUSTER:
            print "*** Power Report Message, ",
            command = ord(payload[2])
            
            if command == 0x81: # Current Power Report
                power = struct.unpack("<H", payload[3:5])[0] # two bytes little endian
                print "Instantaneous Power is %d watts" % power
            elif command == 0x82: # Summary Power Report
                (watt_seconds, uptime, was_reset) = struct.unpack("<IIB", payload[3:12]) 
                print "Summary: %d watt seconds, Uptime: %d seconds, Reset Ind: %d" % (watt_seconds, uptime, was_reset)
        elif cluster_id == CURRENT_STATUS_CLUSTER:
            print "*** Current Status Message, ", 
            if ord(payload[2]) == 0x80:
                if ord(payload[3]) & 0x01:
                    print "Switched On"
                else:
                    print "Switched Off"
    
    return True


def poll_for_messages():
    while True:
        received_message = handle_message(sd_announce)
        received_message |= handle_message(sd_data)
        if not received_message:
            # print "No message received, waiting a bit"
            time.sleep(0.1)

def set_outlet(on):
    address = (EXT_ADDR, IRIS_ENDPOINT, AM_PROFILE_ID, CURRENT_STATUS_CLUSTER)
    # below might be needed...wasn't for me
    sd_data.sendto("\x11\x00\x01\x03", 0, address)
    
    payload = "\x11\x00\x02\x00\x01"
    if on:
        payload = "\x11\00\02\x01\x01"
    
    sd_data.sendto(payload, 0, address) # turn on

thread = threading.Thread(target=poll_for_messages)
thread.start()

# and then just call set_outlet(True) or set_outlet(False)
# whenever you want to adjust it on or off.
# And if you're not running it interactively you can get
# rid of the thread above and just call poll_for_messages()
# directly or add a while True: time.sleep(1) below
