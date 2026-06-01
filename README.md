Deprecated
===========

We are currently using and maintaining a java clone of this program which you can find here [AOML LADCP Terminal](https://github.com/pedrolpena/aoml_ladcp_terminal).
This repository is being kep here for historical purposes.


Disclaimer
==========
This repository is a scientific product and is not official communication of the National Oceanic and
Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is
provided on an ‘as is’ basis and the user assumes responsibility for its use. Any claims against the Department of
Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed
by all applicable Federal law. Any reference to specific commercial products, processes, or services by service
mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or
favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a
DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by
DOC or the United States Government.

# UHDAS LADCP Terminal 

This program was originally part of a suite of programs that form the [UHDAS + CODAS](https://currents.soest.hawaii.edu/uhdas_home/) processing and aquisition tools for ADCP's. We've extracted it and modified it for use on our oceanographic cruises that have lowered ADCP's installed.


# Installation
This installation guide was tested with Debian Bookworm and Ubuntu 22.04 using python 3. This guide may not work with other Linux distributions or may need some adjustments.

## Install requirements 
In order to have access to serial ports under linux, the user account must be part of the dialout group.
To add the user to the dialout group, issue the following command. 

```bash
sudo usermod -a -G dialout $USER
```

Additionally, install python 3 with some packages and lrzsz.
## Debian Bookworm
```bash
sudo apt-get install python3-six python3-future python3-tk python3-pmw python3-numpy
```

## Ubuntu 22.04
```bash
sudo apt-get install python3-six python3-future python3-tk python3-pip python3-numpy
sudo pip3 install pmw
```

## Ubuntu 22.04 & Debian Bookworm
```bash
sudo apt-get install lrzsz
cd uhdas_ladcp_terminal/
sudo -E ./install
python3 ./runsetup.py install --sudo
```

# Screenshots

![Screenshot_2024-02-02_12-14-13](https://github.com/ExplodingTuna/uhdas_ladcp_terminal/assets/146979376/89f1556b-a4f9-42a2-90c3-bf0fd6c7fd68)



### Modifications to UHDAS installation to remove codas and pycurrents dependencies 
These are the changes made to allow the program to run independently.

- Modified runsetup.py to remove all codas references
- Modified setup.py and remove all pycurrents references
- Copied logutils.py to uhdas/system folder
- Modified rditerm.py
- Changed pycurrents.system import logutils to uhdas.system import logutils
- Modified method "_validated_commands" so that the send script can ignore lines starting with "$" or ";" to use unmodifed BBTALK scripts. This will allow BBTALK scripts to be read withput causing any errors.
- Added Prefix and Cruise Name lables.
- Modified "make_filename" method to create a ladcp processing compatible filename
- Modified "terminal" class to include suffix and cruiseName in the constructor





