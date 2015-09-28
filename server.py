#!/usr/bin/env python3

import collections
import csv
import datetime
import json
import logging
import os
import re
import string
import time
import traceback

import matplotlib.dates
import matplotlib.pyplot
import pysolar
import pytz

import notification
import utility


ALLOWED_DOWNTIME = 2 * utility.TRANSMIT_INTERVAL
COLOR_CYCLE = ['b', 'g', 'r', 'c', 'm', 'y', 'k']
DATA_DIR = 'data/'
SERVER_INTERVAL = datetime.timedelta(minutes=3)
WEB_DIR = '/home/kaloix/html/sensor/'

Record = collections.namedtuple('Record', 'value timestamp')


def main():
	utility.init()
	with open('template.html') as html_file:
		html_template = html_file.read()
	with open('sensor.json') as json_file:
		sensor_json = json_file.read()
	devices = json.loads(
		sensor_json, object_pairs_hook=collections.OrderedDict)
	series = collections.defaultdict(list)
	for device in devices:
		for kind, attr in device['output'].items():
			if kind == 'temperature':
				series[attr['group']].append(Temperature(
					attr['name'],
					tuple(attr['usual']),
					tuple(attr['warn'])))
			elif kind == 'switch':
				series[attr['group']].append(Switch(
					attr['name']))
	notify = notification.NotificationCenter()

	while True:
		start = time.time()
		try:
			for group, series_list in series.items():
				loop(group, series_list, html_template)
		except Exception as err:
			tb_lines = traceback.format_tb(err.__traceback__)
			notify.warn_admin('{}: {}\n{}'.format(
				type(err).__name__, err, ''.join(tb_lines)))
			break
		logging.info('sleep, duration was {}s'.format(
			round(time.time() - start)))
		time.sleep(SERVER_INTERVAL.total_seconds())


def loop(group, series_list, html_template):
	logging.info('read csv')
	now = datetime.datetime.now()
	for series in series_list:
		series.update()
		series.check()
	if os.system('cp {}{} {}'.format(DATA_DIR, 'thermosolar.jpg', WEB_DIR)):
		logging.error('cp thermosolar.jpg failed')

	logging.info('write html')
	html_filled = string.Template(html_template).substitute(
		refresh_seconds = int(SERVER_INTERVAL.total_seconds()),
		group = group,
		values = detail_html(series_list),
		update_time = '{:%A %d. %B %Y %X}'.format(now),
		year = '{:%Y}'.format(now))
	with open(WEB_DIR+group+'.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	plot_history(series_list, '{}{}.png'.format(WEB_DIR, group), now)


def detail_html(series_list):
	ret = list()
	ret.append('<ul>')
	for series in series_list:
		ret.append('<li>{}</li>'.format(series))
	ret.append('</ul>')
	return '\n'.join(ret)


def plot_history(series_list, file, now):
	fig, ax = matplotlib.pyplot.subplots(figsize=(12, 4))
	frame_start = now - utility.DETAIL_RANGE
	minimum, maximum = list(), list()
	color_iter = iter(COLOR_CYCLE)
	for series in series_list:
		tail = series.tail
		if not tail:
			continue
		color = next(color_iter)
		if type(series) is Temperature:
			parts = list()
			for record in tail:
				if not parts or record.timestamp-parts[-1][-1].timestamp > \
						ALLOWED_DOWNTIME:
					parts.append(list())
				parts[-1].append(record)
			for index, part in enumerate(parts):
				values, timestamps = zip(*part)
				label = series.name if index == 0 else None
				matplotlib.pyplot.plot(
					timestamps, values, label=label,
					linewidth=3, color=color, zorder=3)
				matplotlib.pyplot.fill_between(
					timestamps, values, series.warn[0],
					where = [value<series.warn[0] for value in values],
					interpolate=True, color='r', zorder=2, alpha=0.7)
				matplotlib.pyplot.fill_between(
					timestamps, values, series.warn[1],
					where = [value>series.warn[1] for value in values],
					interpolate=True, color='r', zorder=2, alpha=0.7)
			minimum.append(min(tail).value)
			minimum.append(series.usual[0])
			maximum.append(max(tail).value)
			maximum.append(series.usual[1])
		elif type(series) is Switch:
			for index, (start, end) in enumerate(series.segments):
				label = series.name if index == 0 else None
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


def _universal_parser(value):
	if value == 'False':
		return False
	elif value == 'True':
		return True
	else:
		return float(value)


class Series(object):

	def __init__(self, name):
		self.name = name
		self.records = collections.deque()
		self.year = int()
		for file in sorted(os.listdir(DATA_DIR)):
			match = re.search(r'(?P<name>\S+)_(?P<year>\d+).csv', file)
			if match and match.group('name') == self.name:
				year = int(match.group('year'))
				self._read(year)
				self.year = year

	def _append(self, value, timestamp):
		if self.records and timestamp <= self.records[-1].timestamp:
			return
		self.records.append(Record(value, timestamp))
		# delete center of three equal values while keeping some
		if len(self.records) >= 3 and self.records[-3].value == \
				self.records[-2].value == self.records[-1].value and \
				self.records[-2].timestamp-self.records[-3].timestamp < \
				utility.TRANSMIT_INTERVAL:
			del self.records[-2]

	def _read(self, year):
		filename = '{}/{}_{}.csv'.format(DATA_DIR, self.name, year)
		try:
			with open(filename, newline='') as csv_file:
				for row in csv.reader(csv_file):
					self._append(_universal_parser(row[1]),
					             datetime.datetime.fromtimestamp(int(row[0])))
		except OSError:
			pass

	@property
	def current(self):
		now = datetime.datetime.now()
		if self.records and self.records[-1].timestamp >= now-ALLOWED_DOWNTIME:
			return self.records[-1].value
		else:
			return None

	@property
	def tail(self):
		now = datetime.datetime.now()
		start = now - utility.DETAIL_RANGE
		ret = collections.deque()
		for record in reversed(self.records):
			if record.timestamp >= start:
				ret.append(record)
			else:
				break
		return reversed(ret)

	def update(self):
		now = datetime.datetime.now()
		if self.year < now.year:
			self._read(self.year)
			self.year = now.year
		self._read(now.year)


class Temperature(Series):

	def __init__(self, name, usual, warn):
		super().__init__(name)
		self.usual = usual
		self.warn = warn

	def __str__(self):
		current = self.current
		rev_tail = reversed(self.tail)
		minimum = min(rev_tail) if rev_tail else None
		maximum = max(rev_tail) if rev_tail else None
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current is None:
			ret.append('Fehler')
		else:
			ret.append('{:.1f} °C'.format(current))
			if current < self.warn[0] or current > self.warn[1]:
				ret.append(' ⚠')
		ret.append('<ul>\n')
		if minimum:
			ret.append(
				'<li>Minimum bei {:.1f} °C am {:%A um %H:%M} Uhr.'.format(
					*minimum))
			if minimum.value < self.warn[0]:
				ret.append(' ⚠')
			ret.append('</li>\n')
		if maximum:
			ret.append(
				'<li>Maximum bei {:.1f} °C am {:%A um %H:%M} Uhr.'.format(
					*maximum))
			if maximum.value > self.warn[1]:
				ret.append(' ⚠')
			ret.append('</li>\n')
		ret.append(
			'<li>Warnbereich unter {:.0f} °C und über {:.0f} °C.</li>\n'
				.format(*self.warn))
		ret.append('</ul>')
		return ''.join(ret)

	def check(self):
		pass # TODO
#		if not self.history.current:
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


class Switch(Series):

	def __init__(self, name):
		super().__init__(name)

	def __str__(self):
		current = self.current
		last_false = last_true = None
		for value, timestamp in self.records:
			if value:
				last_true = timestamp
			else:
				last_false = timestamp
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current is None:
			ret.append('Fehler')
		elif current:
			ret.append('Ein')
		else:
			ret.append('Aus')
		ret.append('<ul>\n')
		if last_true and (current is None or not current):
			ret.append(
				'<li>Zuletzt Ein am {:%A um %H:%M} Uhr.</li>\n'.format(
					last_true))
		if last_false and (current is None or current):
			ret.append(
				'<li>Zuletzt Aus am {:%A um %H:%M} Uhr.</li>\n'.format(
					last_false))
		if self.records:
			ret.append(
				'<li>Insgesamt {} Einschaltdauer.</li>\n'.format(
					utility.format_timedelta(self.uptime)))
		ret.append('</ul>')
		return ''.join(ret)

	@property
	def segments(self):
		expect = True
		for value, timestamp in self.records:
			if value != expect:
				continue
			if expect:
				start = timestamp
				expect = False
			else:
				yield start, timestamp
				expect = True
		if not expect:
			now = datetime.datetime.now()
			yield start, min(timestamp+ALLOWED_DOWNTIME, now)

	@property
	def uptime(self):
		total = datetime.timedelta()
		for start, stop in self.segments:
			total += stop - start
		return total

	def check(self):
		pass


if __name__ == "__main__":
	main()
