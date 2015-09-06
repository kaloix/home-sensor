# Kaloix Sensor System
> This project was made with only personal use by me in mind. Code is not commentated, maybe bad structured and the user interface is in German language.

## Requirements
* Python 3.2.3
* [markdown](https://pythonhosted.org/Markdown/)
* [matplotlib](http://matplotlib.org/index.html)

## Client
### Features
* Import relevant sensors from `sensor.json`
* Collect and parse sensor data using a file system interface
* Export data as CSV files to folder `csv/`
* Copy these files to the server, when new data is available

### Usage
The directory `data/` on the server must be created manually first.

    modprobe w1-gpio
    modprobe w1-therm
    ./client.py <station>

The *station* parameter corresponds with the same field in the sensor list of `sensor.json`.

## Server
### Features
* Import sensor list from `sensor.json`
* Monitor directory `csv/` for new sensor data
* Send admin email on missing sensor updates and crash
* Send user email on out of range sensor values
* Generate `index.html` document with sensor values from `template.md` and `template.html`
* Generate `plot.png` with sensor history
* Copy these files in webserver directory

### Usage
    pip install virtualenv
    virtualenv --python=python3 ve/
    source ve/bin/activate
    pip install markdown matplotlib
    ./server.py
    deactivate

## Acknowledgements
* File `favicon.png` from [VeryIcon.com](http://www.veryicon.com/icons/system/icons8-metro-style/measurement-units-temperature.html) with license *Free for non-commercial use*

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License v3
