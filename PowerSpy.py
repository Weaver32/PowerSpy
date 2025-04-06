# -*- coding: utf-8 -*-
"""
Created on Sat Apr  5 22:38:15 2025

@author: Weaver32
"""

import asyncio
from bleak import BleakClient, BleakScanner
import time
import matplotlib.pyplot as plt
import numpy as np
import psutil
import traceback

UUID_COMMAND = "0000fff4-0000-1000-8000-00805f9b34fb"  #The SEM6000's command UUID
UUID_NOTIFY = "0000fff3-0000-1000-8000-00805f9b34fb"  #The SEM6000's notification UUID


AUTH_MSG = bytes.fromhex("0f0c170000000000000000000018ffff")  #Authentication Message, sending PIN (0000 - default)
MEASURE_MSG = bytes.fromhex("0f050400000005ffff")  #Message for instructing the SEM6000 to send a measurement

lastWattage = 0 #Used to transfer the wattage for the plot

def running_mean(x, N):
    if N == 1:
        return x
    cumsum = np.cumsum(np.insert(x, 0, 0)) 
    return (cumsum[N:] - cumsum[:-N]) / float(N)

def notification_handler(sender, data):
    global lastWattage
    #Converting the bytes into numbers
    if len(data) >= 4:
        watts = float(int.from_bytes(data[5:8], byteorder='big')/1000)
        voltage = int.from_bytes(data[8:9], byteorder='big')
        amps = float(int.from_bytes(data[10:11], byteorder='big')/1000)
        frequency = int.from_bytes(data[11:12], byteorder='big')
        totalC = int.from_bytes(data[13:17], byteorder='big')
        print(f"Measurement values: Watts: {watts} Voltage: {voltage} Amps: {amps} Frequency: {frequency} Total Consumption:: {totalC}")
        lastWattage = watts
        
async def main_action():
    #Gather the device address, assuming that the SEM6000's name is still "Voltcraft" (default)
    DEVICE_ADDRESS = ""
    avg = 10
    sampleAmount = 500
    x = (np.array(range(sampleAmount-avg+1)))/2
    y1 = np.zeros(sampleAmount)
    y2 = np.zeros(sampleAmount)
    firstInitiation = True
    while True:
        try:
            while DEVICE_ADDRESS == "":
                print("Looking for Voltcraft SEM6000 device...")
                devices = await BleakScanner.discover(6.0)
                for device in devices:
                    if device.name and "Voltcraft" in device.name:
                        print(f"Found Voltcraft device: {device.name} @ {device.address}")
                        DEVICE_ADDRESS = device.address
                        break
                if DEVICE_ADDRESS == "":
                    print("No Voltcraft SEM6000 device found...\n")  
                    
            
            async with BleakClient(DEVICE_ADDRESS) as client:
                while not client.is_connected:
                    print("Failed to connect to the SEM6000.")
                    time.sleep(2)
                
                print("Connected. Sending handshake init...")
                # Send the initialization message to the auth characteristic
                await client.write_gatt_char(UUID_NOTIFY, AUTH_MSG, response=False)
                print("Subscribing to notifications for measurements...")
                await client.start_notify(UUID_COMMAND, notification_handler)
                
                #
                if firstInitiation is True:
                    plt.ion()
                    fig = plt.figure("Power and CPU load plot. Moving average: "+str(avg)+" samples")
                    ax1 = fig.add_subplot(111)
                    ax2 = ax1.twinx()
                    line1, = ax1.plot(x, running_mean(y1,avg), 'r-') 
                    line2, = ax2.plot(x, running_mean(y2,avg), 'b-')
                    ax1.set_xlabel("Time in seconds")
                    ax1.set_ylabel("Power in Watts", color="r")
                    ax2.set_ylabel("CPU load in %", color="b")
                    firstInitiation = False

                while True:
                    await client.write_gatt_char(UUID_NOTIFY, MEASURE_MSG, response=False)
                    time.sleep(0.5)
                    #Adding new values to the graph and generating avg. version
                    y1 = np.delete(y1,0)
                    y1 = np.append(y1,lastWattage)
                    y2 = np.delete(y2,0)
                    y2 = np.append(y2,psutil.cpu_percent())
                    rmY1 = running_mean(y1,avg)
                    rmY2 = running_mean(y2,avg)
                    #Updating diagram and rescaling axis
                    line1.set_ydata(rmY1)
                    line2.set_ydata(rmY2)
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                    ax1.set(ylim=(0, max(rmY1)))
                    ax2.set(ylim=(0, max(rmY2)))
                        
                   
                    
        
                
        except Exception:
           #traceback.print_exc() 
           print("Connection lost, trying re-connect...") 

if __name__ == "__main__":
    asyncio.run(main_action())
    
