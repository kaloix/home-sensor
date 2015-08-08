#!/usr/bin/env python3

import locale
import time
import string
import markdown
import datetime
import logging
import sensor

# initialization
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
logging.basicConfig(
	format = '[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s',
	datefmt = '%yy%mm%dd%Hh%Mm%Ss',
	level = logging.INFO)
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()

# main loop
while True:
	logging.info('collect data')
	# TODO

	data = dict()
	data['temp_wohn_akt'] = sensor.Measurement()
	data['temp_wohn_akt'].value = 1.2
	data['temp_wohn_akt'].time = datetime.datetime.today()
	data['temp_wohn_min'] = sensor.Measurement()
	data['temp_wohn_min'].value = 3.4
	data['temp_wohn_min'].time = datetime.datetime.today()
	data['temp_wohn_max'] = sensor.Measurement()
	data['temp_wohn_max'].value = 5.6
	data['temp_wohn_max'].time = datetime.datetime.today()
	data['temp_klima_akt'] = None
	data['temp_klima_min'] = sensor.Measurement()
	data['temp_klima_min'].value = 9.10
	data['temp_klima_min'].time = datetime.datetime.today()
	data['temp_klima_max'] = sensor.Measurement()
	data['temp_klima_max'].value = 11.12
	data['temp_klima_max'].time = datetime.datetime.today()

	# fill markdown template
	logging.info('write html')
	markdown_filled = string.Template(markdown_template).substitute(
		bild_diagramm = 'plot.png',
		datum_aktualisierung = time.strftime('%c'),
		**data)

	# convert markdown to html
	extensions = [
		'markdown.extensions.tables']
	html_body = markdown.markdown(markdown_filled, extensions)
	identifier = {
		'html_body': html_body}
	html_filled = string.Template(html_template).substitute(identifier)

	# finalization
	with open('data.html', mode='w') as html_file:
		html_file.write(html_filled)

	# wait for next tick
	now = datetime.datetime.today()
	pause = -1 * datetime.timedelta(
		minutes = now.minute % 10 - 10,
		seconds = now.second,
		microseconds = now.microsecond)
	logging.info('sleep for {}'.format(pause))
	try:
		time.sleep(pause.total_seconds())
	except KeyboardInterrupt:
		logging.info('exiting')
		break
