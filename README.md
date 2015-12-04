# Kaloix Sensor System
> **Notice:** This project was made with only personal use by me in mind. Code
> is not commentated and the user interface is in German language.

## Installation
### Client
1. The base platform is  **Debian Jessie** with **Python 3.4.2**.

2. 1-Wire temperature sensor:

		sudo echo dtoverlay=w1-gpio >> /boot/config.txt
		sudo reboot
		sudo modprobe w1-gpio
		sudo modprobe w1-therm

3. Optical character recognition of seven segment display:

		sudo apt-get install fswebcam libimlib2 libimlib2-dev python3-numpy python3-scipy python3-pil
		wget "https://www.unix-ag.uni-kl.de/~auerswal/ssocr/ssocr-2.16.3.tar.bz2"
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

2. Create self signed certificate for HTTP API:

		openssl genrsa -out server.key 4096
		openssl req -new -key server.key -out server.csr
		openssl x509 -req -days 1460 -in server.csr -signkey server.key -out server.crt
		rm server.csr

	Copy `server.crt` to clients.

3. Generate an API token for each client:

		pwgen 32 2 > api_token

	Copy one unique token to every client.

4. Python module installation on hoster Uberspace:

		pip3 install matplotlib pysolar pytz --user

5. Usage:

		./server.py

## Acknowledgements
* [Seven Segment Optical Character Recognition](https://www.unix-ag.uni-kl.de/~auerswal/ssocr/)
  by *Erik Auerswald* under license *GPLv3*
* [fswebcam](http://www.sanslogic.co.uk/fswebcam/) by *Philip Heron* under
  license *GPLv2*
* [Pysolar](http://pysolar.org/) Python 3 module by *pingswept* for
  sunrise/sunset calculation under license *GPLv3*
* [Measurement Units Temperature](http://www.veryicon.com/icons/system/icons8-metro-style/measurement-units-temperature.html)
  icon by *VisualPharm* under license *Free for non-commercial use*
* [Simple HTTPS Server In Python Using Self Signed Certs](http://pankajmalhotra.com/Simple-HTTPS-Server-In-Python-Using-Self-Signed-Certs/)
  by *Pankaj Malhotra*
* [HTTP API Design](https://geemus.gitbooks.io/http-api-design/content/) by
  *interagent*

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License version 3
