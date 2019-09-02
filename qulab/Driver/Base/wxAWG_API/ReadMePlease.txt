It is recommended to use PyVISA in order to control your instrument with python.
(see: https://pyvisa.readthedocs.io/en/stable/)

However, PyVISA requires NI-VISA, which might be hard 
or even impossible to install on some Linux distributions.

==============================================================================
This example shows how to control your instrument with python *Without PyVISA*
==============================================================================

Currently it shows how to use either LAN Communication or USB Communication.

 - In order to use USB based communication, one should install Python-USBTMC 
   (see installation instructions below).

 - If only LAN based communication is required, then Python-USBTMC is not needed.

========================================
Python USBTMC Installation Instructions
========================================

Requirements:
-------------
 1. libusb
   - linux: https://sourceforge.net/projects/libusb/
   - Windows: https://sourceforge.net/projects/libusb-win32/
     (also see: http://www.libusb.org/wiki/libusb-win32)
	 
 2. pyusb
    - https://sourceforge.net/projects/pyusb/
	  (there is no need to download anything, it can be installed with pip)

 3. python usbtmc:
    - https://github.com/python-ivi/python-usbtmc



Installation
------------

1. Install libusb 
   - Windows: see: libusb-windows7.pdf (inside libusb-win32-bin-1.2.6.0)
   - Linux: extract libusb-1.0.9.tar.bz2 and follow the instructions in the INSTALL text file
     (basic instalation: ./configure; make; sudo make install).
	 Alternatively install it from software-manager (sudo apt-get install libusb-1.0-9-dev).

2. Install pyusb: 
   - from command-line: pip install pyusb (might need sudo / administrator privilages)

3. Install python-usbtmc: 
   - open command-line terminal in the python-usbtmc folder and run: python setup.py install
     (see usage examples in https://github.com/python-ivi/python-usbtmc)

Important:
==========
In Windows you must configure libusb to capture the usb-connected instrument.
Note that when libusb captures the instrument, NI-VISA won't recognize it.

In order to configure libusb to capture the instrument:
 1. connect the instrument to the pc through USB, and activate the instrument's USB-Interface.
 2. run inf-wizard.exe (found in the folder libusb-win32-bin-1.2.6.0\bin) and follow the instructions.
 
In order to cancel that configuration (and let NI-VISA recognize the instrument):
 1. connect the instrument to the pc through USB, and activate the instrument's USB-Interface.
 2. open Windows device-manager, and under libusb-win32 devices Uninstall the device.
