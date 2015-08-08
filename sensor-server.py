#!/usr/bin/env python3

import locale
import time
import string
import markdown
import datetime
import logging

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

	# fill markdown template
	logging.info('write html')
	identifier = {
		'temp_wohn_akt': 23.6,
		'temp_wohn_min': 10.0,
		'temp_wohn_max': 30.1,
		'temp_klima_akt': 11.1,
		'temp_klima_min': 10.9,
		'temp_klima_max': 29.5,
		'bild_diagramm': 'plot.png',
		'datum_aktualisierung': time.strftime('%c')}
	markdown_filled = string.Template(markdown_template).substitute(identifier)

	# convert markdown to html
	extensions = [
		'markdown.extensions.tables']
	html_body = markdown.markdown(markdown_filled, extensions)
	identifier = {
		'html_body': html_body}
	html_filled = string.Template(html_template).substitute(identifier)

	# Finalization
	with open('data.html', mode='w') as html_file:
		html_file.write(html_filled)

	# Wait for next tick
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
