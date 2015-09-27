#!/usr/bin/env python3

import collections
import datetime
import json
import logging
import os
import string
import time
import traceback

import matplotlib.dates
import matplotlib.pyplot
import pysolar
import pytz

import notification
import utility


BACKUP_DIR = 'backup/'
COLOR_CYCLE = ['b', 'g', 'r', 'c', 'm', 'y', 'k']
DATA_DIR = 'data/'
SERVER_INTERVAL = datetime.timedelta(minutes=3)
WEB_DIR = '/home/kaloix/html/sensor/'


def main():
	utility.init()
	with open('template.html') as html_file:
		html_template = html_file.read()
	with open('sensor.json') as json_file:
		sensor_json = json_file.read()
	devices = json.loads(
		sensor_json, object_pairs_hook=collections.OrderedDict)
	sensors = collections.defaultdict(list)
	for device in devices:
		for kind, attr in device['output'].items():
			if kind == 'temperature':
				sensors[attr['group']].append(Temperature(
					attr['name'],
					tuple(attr['usual']),
					tuple(attr['warn'])))
			elif kind == 'switch':
				sensors[attr['group']].append(Switch(
					attr['name']))
	notify = notification.NotificationCenter()

	while True:
		start = time.time()
		try:
			for group, sensor_list in sensors.items():
				loop(group, sensor_list, html_template)
			utility.memory_check()
		except Exception as err:
			tb_lines = traceback.format_tb(err.__traceback__)
			notify.warn_admin('{}: {}\n{}'.format(
				type(err).__name__, err, ''.join(tb_lines)))
			break
		logging.info('sleep, duration was {}s'.format(
			round(time.time() - start)))
		time.sleep(SERVER_INTERVAL.total_seconds())


def loop(group, sensor_list, html_template):
	logging.info('read csv')
	now = datetime.datetime.now()
	for s in sensor_list:
		s.update()
		s.check()
	if os.system('cp {}{} {}'.format(DATA_DIR, 'thermosolar.jpg', WEB_DIR)):
		logging.error('cp thermosolar.jpg failed')

	logging.info('write html')
	html_filled = string.Template(html_template).substitute(
		refresh_seconds = int(SERVER_INTERVAL.total_seconds()),
		group = group,
		values = detail_html([s.history for s in sensor_list]),
		update_time = '{:%A %d. %B %Y %X}'.format(now),
		year = '{:%Y}'.format(now))
	with open(WEB_DIR+group+'.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	plot_history([s.history for s in sensor_list], WEB_DIR+group+'.png', now)


def detail_html(histories):
	string = list()
	string.append('<ul>')
	for history in histories:
		string.append('<li>{}</li>'.format(history))
	string.append('</ul>')
	return '\n'.join(string)


def plot_history(history, file, now):
	fig, ax = matplotlib.pyplot.subplots(figsize=(12, 4))
	frame_start = now - utility.DETAIL_RANGE
	minimum, maximum = list(), list()
	color_iter = iter(COLOR_CYCLE)
	for h in history:
		color = next(color_iter)
		if hasattr(h, 'float') and h.float:
			parts = list()
			for measurement in h.float:
				if not parts or measurement.timestamp - \
						parts[-1][-1].timestamp > utility.ALLOWED_DOWNTIME:
					parts.append(list())
				parts[-1].append(measurement)
			for index, part in enumerate(parts):
				values, timestamps = zip(*part)
				label = h.name if index == 0 else None
				matplotlib.pyplot.plot(
					timestamps, values, label=label,
					linewidth=3, color=color, zorder=3)
				matplotlib.pyplot.fill_between(
					timestamps, values, h.warn[0],
					where = [value<h.warn[0] for value in values],
					interpolate=True, color='r', zorder=2, alpha=0.7)
				matplotlib.pyplot.fill_between(
					timestamps, values, h.warn[1],
					where = [value>h.warn[1] for value in values],
					interpolate=True, color='r', zorder=2, alpha=0.7)
			minimum.append(min(h.float.value))
			minimum.append(h.usual[0])
			maximum.append(max(h.float.value))
			maximum.append(h.usual[1])
		elif hasattr(h, 'boolean') and h.boolean:
			for index, (start, end) in enumerate(h.segments):
				label = h.name if index == 0 else None
				matplotlib.pyplot.axvspan(
					start, end, label=label, color=color, alpha=0.5, zorder=1)
	nights = int(utility.DETAIL_RANGE / datetime.timedelta(days=1)) + 2
	for index, (sunset, sunrise) in enumerate(nighttime(nights, now)):
		label = 'Nacht' if index == 0 else None
		matplotlib.pyplot.axvspan(
			sunset, sunrise, label=label,
			hatch='//', color='black', alpha=0.1, zorder=0)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H'))
	ax.xaxis.set_major_locator(matplotlib.dates.HourLocator())
	ax.yaxis.get_major_formatter().set_useOffset(False)
	ax.yaxis.set_label_position('right')
	ax.yaxis.tick_right()
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.xlim(frame_start, now)
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.ylim(min(minimum), max(maximum))
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.legend(
		loc='lower left', bbox_to_anchor=(0, 1), borderaxespad=0, ncol=5,
		frameon=False)
	matplotlib.pyplot.savefig(filename=file, bbox_inches='tight')
	matplotlib.pyplot.close()


def nighttime(count, date_time):
	# make aware
	date_time = pytz.timezone('Europe/Berlin').localize(date_time)
	# calculate nights
	date_time -= datetime.timedelta(days=count)
	sun_change = list()
	for c in range(0, count+1):
		date_time += datetime.timedelta(days=1)
		sun_change.extend(pysolar.util.get_sunrise_sunset(
			49.2, 11.08, date_time))
	sun_change = sun_change[1:-1]
	night = list()
	for r in range(0, count):
		night.append((sun_change[2*r], sun_change[2*r+1]))
	# make naive
	for sunset, sunrise in night:
		yield sunset.replace(tzinfo=None), sunrise.replace(tzinfo=None)


class Temperature(object):

	def __init__(self, name, usual, warn):
		self.name = name
		self.history = utility.FloatHistory(name, usual, warn)
		self.history.restore(BACKUP_DIR)

	def update(self):
		self.history.restore(DATA_DIR)
		self.history.backup(BACKUP_DIR)

	def check(self):
		pass # TODO
		if not self.history.current:
#			text = 'Messpunkt "{}" liefert keine Daten.'.format(self.name)
#			notify.warn_user(text, self.name+'s')
#		if self.history.warn_low:
#			text = 'Messpunkt "{}" unterhalb des zulässigen Bereichs:\n{}' \
#				.format(self.name, self.history.minimum)
#			notify.warn_user(text, self.name+'l')
#		if self.history.warn_high:
#			text = 'Messpunkt "{}" überhalb des zulässigen Bereichs:\n{}' \
#				.format(self.name, self.history.maximum)
#			notify.warn_user(text, self.name+'h')


class Switch(object):

	def __init__(self, name):
		self.history = utility.BoolHistory(name)
		self.history.restore(BACKUP_DIR)
		self.name = name

	def update(self):
		self.history.restore(DATA_DIR)
		self.history.backup(BACKUP_DIR)

	def check(self):
		pass


if __name__ == "__main__":
	main()
