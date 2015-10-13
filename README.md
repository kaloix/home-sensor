# Kaloix Sensor System
> **Notice:** This project was made with only personal use by me in mind. Code
> is not commentated, maybe bad structured and the user interface is in German
> language.

## Installation
### Client
1. The base platform is  **Debian Jessie** with **Python 3.4.2**. Install
   German locale by uncommenting `de_DE.UTF-8 UTF-8` in `/etc/locale.gen` and
   run `sudo locale-gen`.

2. 1-Wire temperature sensor:

		modprobe w1-gpio
		modprobe w1-therm

3. Optical character recognition of seven segment display with [ssocr](https://www.unix-ag.uni-kl.de/~auerswal/ssocr/):

		sudo apt-get install fswebcam libimlib2 libimlib2-dev python3-numpy
			python3-scipy python3-pil
		wget "https://www.unix-ag.uni-kl.de/~auerswal/ssocr/ssocr-2.16.3.tar.
			bz2"
		bzip2 --decompress ssocr-2.16.3.tar.bz2
		tar --extract --file ssocr-2.16.3.tar
		rm ssocr-2.16.3.tar
		make --directory ssocr-2.16.3/ ssocr
		ln --symbolic ssocr-2.16.3/ssocr

4. Usage:

		./client.py <station>

	The *station* parameter corresponds with the same field in the sensor list
	of `sensor.json`.

### Server
1. The base platform is **CentOS 6.7** with **Python 3.4.3**.

2. Python module installation on hoster Uberspace:

		pip3 install matplotlib pysolar pytz --user

3. Usage:

		./server.py

## Acknowledgements
* File `static/favicon.png` from
  [VeryIcon.com](http://www.veryicon.com/icons/system/icons8-metro-style/measurement-units-temperature.html)
  with license *Free for non-commercial use*

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License v3
