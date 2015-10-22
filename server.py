#!/usr/bin/env python3

import collections
import csv
import datetime
import functools
import itertools
import json
import locale
import logging
import shutil
import string
import time
import traceback

import matplotlib.dates
import matplotlib.pyplot
import pysolar
import pytz

import monitor
import notification
import utility


ALLOWED_DOWNTIME = datetime.timedelta(minutes=30)
COLOR_CYCLE = ['b', 'g', 'r', 'c', 'm', 'y', 'k']
DATA_DIR = 'data/'
RECORD_DAYS = 7
SERVER_INTERVAL = datetime.timedelta(minutes=3)
SUMMARY_DAYS = 365
WEB_DIR = '/home/kaloix/html/sensor/'

notify = notification.NotificationCenter()
Record = collections.namedtuple('Record', 'timestamp value')
Summary = collections.namedtuple('Summary', 'date minimum maximum')


def main():
	utility.logging_config()
	locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
	shutil.copy('static/favicon.png', WEB_DIR)
	shutil.copy('static/htaccess', WEB_DIR+'.htaccess')
	with open('template.html') as html_file:
		html_template = html_file.read()
	with open('sensor.json') as json_file:
		sensor_json = json_file.read()
	devices = json.loads(sensor_json,
	                     object_pairs_hook=collections.OrderedDict)
	series = collections.defaultdict(list)
	for device in devices:
		for kind, attr in device['output'].items():
			if kind == 'temperature':
				series[attr['group']].append(Temperature(
					attr['name'],
					attr['low'],
					attr['high']))
			elif kind == 'switch':
				series[attr['group']].append(Switch(
					attr['name']))
	with monitor.MonitorServer(functools.partial(save_record, series)):
		while True:
			start = datetime.datetime.now()
			for group, series_list in series.items():
				loop(group, series_list, html_template, start)
			utility.memory_check()
			duration = (datetime.datetime.now() - start).total_seconds()
			logging.info('updated website in {:.1f}s'.format(duration))
			time.sleep(SERVER_INTERVAL.total_seconds())


def on_shutdown():
	logging.info('shutdown')
	shutil.copy('static/htaccess_maintenance', WEB_DIR+'.htaccess')


def save_record(series, name, timestamp, value):
	record = Record(datetime.datetime.fromtimestamp(int(timestamp)), value)
	for series_list in series.values():
		for series in series_list:
			if series.name == name:
				series.save(record)
				return


def loop(group, series_list, html_template, now):
	for series in series_list:
		error = series.error # FIXME no data warning only once per failure
		if error:
			notify.user_warning(error)
	shutil.copy(DATA_DIR+'thermosolar.jpg', WEB_DIR)
	html_filled = string.Template(html_template).substitute(
		refresh_seconds = int(SERVER_INTERVAL.total_seconds()),
		group = group,
		values = detail_html(series_list),
		update_time = '{:%A, %d. %B %Y, %X}'.format(now),
		year = '{:%Y}'.format(now))
	with open(WEB_DIR+group.lower()+'.html', mode='w') as html_file:
		html_file.write(html_filled)
	# FIXME svg backend has memory leak in matplotlib 1.4.3
	plot_history(series_list, '{}{}.png'.format(WEB_DIR, group), now)


def detail_html(series_list):
	ret = list()
	ret.append('<ul>')
	for series in series_list:
		ret.append('<li>{}</li>'.format(series))
	ret.append('</ul>')
	return '\n'.join(ret)


def _nighttime(count, date_time):
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


def _plot_records(series_list, days, now):
	color_iter = iter(COLOR_CYCLE)
	for series in series_list:
		color = next(color_iter)
		if type(series) is Temperature:
			parts = list()
			for record in series.day if days==1 else series.records:
				if not parts or record.timestamp-parts[-1][-1].timestamp > \
						ALLOWED_DOWNTIME:
					parts.append(list())
				parts[-1].append(record)
			for part in parts:
				timestamps, values = zip(*part)
				matplotlib.pyplot.plot(
					timestamps, values, label=series.name,
					linewidth=3, color=color, zorder=3)
				matplotlib.pyplot.fill_between(
					timestamps, values, series.low,
					where = [value<series.low for value in values], # FIXME runtime warning
					interpolate=True, color='r', zorder=2, alpha=0.7)
				matplotlib.pyplot.fill_between(
					timestamps, values, series.high,
					where = [value>series.high for value in values], # FIXME runtime warning
					interpolate=True, color='r', zorder=2, alpha=0.7)
		elif type(series) is Switch:
			for start, end in series.segments:
				matplotlib.pyplot.axvspan(start, end, label=series.name,
				                          color=color, alpha=0.5, zorder=1)
	for sunset, sunrise in _nighttime(days+1, now):
		matplotlib.pyplot.axvspan(
			sunset, sunrise, label='Nacht',
			hatch='//', facecolor='0.9', edgecolor='0.8', zorder=0)
	matplotlib.pyplot.xlim(now-datetime.timedelta(days), now)
	matplotlib.pyplot.ylabel('Temperatur °C')
	ax = matplotlib.pyplot.gca() # FIXME not available in mplrc 1.4.3
	ax.yaxis.tick_right()
	ax.yaxis.set_label_position('right')


def _plot_summary(series_list, now):
	color_iter = iter(COLOR_CYCLE)
	for series in series_list:
		color = next(color_iter)
		if type(series) is Temperature:
			parts = list()
			for summary in series.summary:
				if not parts or summary.date-parts[-1][-1].date > \
						datetime.timedelta(days=7):
					parts.append(list())
				parts[-1].append(summary)
			for part in parts:
				dates, mins, maxs = zip(*part)
				matplotlib.pyplot.fill_between(
					dates, mins, maxs, label=series.name,
					color=color, alpha=0.5, interpolate=True)
		elif type(series) is Switch:
			pass
	matplotlib.pyplot.xlim(now-datetime.timedelta(days=365), now)
	matplotlib.pyplot.ylabel('Temperatur °C')
	ax = matplotlib.pyplot.gca() # FIXME not available in mplrc 1.4.3
	ax.yaxis.tick_right()
	ax.yaxis.set_label_position('right')


def plot_history(series_list, file, now):
	fig = matplotlib.pyplot.figure(figsize=(13, 7))
	# last week
	ax = matplotlib.pyplot.subplot(312)
	_plot_records(series_list, RECORD_DAYS, now)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%a.'))
	ax.xaxis.set_major_locator(matplotlib.dates.DayLocator())
	ax.xaxis.set_minor_locator(matplotlib.dates.HourLocator(range(0, 24, 6)))
	handles, labels = ax.get_legend_handles_labels()
	# last day
	ax = matplotlib.pyplot.subplot(311)
	_plot_records(series_list, 1, now)
	matplotlib.pyplot.legend(
		handles=list(collections.OrderedDict(zip(labels, handles)).values()),
		loc='lower left', bbox_to_anchor=(0, 1), ncol=5, frameon=False)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H Uhr'))
	ax.xaxis.set_major_locator(matplotlib.dates.HourLocator(range(0, 24, 3)))
	ax.xaxis.set_minor_locator(matplotlib.dates.HourLocator())
	# summary
	ax = matplotlib.pyplot.subplot(313)
	_plot_summary(series_list, now)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%b.'))
	ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator())
	ax.xaxis.set_minor_locator(matplotlib.dates.WeekdayLocator(
		matplotlib.dates.MO))
	# save file
	matplotlib.pyplot.savefig(file, bbox_inches='tight')
	matplotlib.pyplot.close()


def _universal_parser(value):
	if value == 'False':
		return False
	elif value == 'True':
		return True
	else:
		return float(value)


def _format_timedelta(td):
	ret = list()
	hours = td.days*24 + td.seconds//3600
	if hours:
		ret.append(str(hours))
		ret.append('Stunde' if hours==1 else 'Stunden')
	minutes = (td.seconds//60) % 60
	ret.append(str(minutes))
	ret.append('Minute' if minutes==1 else 'Minuten')
	return ' '.join(ret)


def _format_timestamp(ts, now):
	if ts.date() == now.date():
		return 'um {:%H:%M} Uhr'.format(ts)
	elif now.date()-ts.date() == datetime.timedelta(days=1):
		return 'gestern um {:%H:%M} Uhr'.format(ts)
	elif now.date()-ts.date() < datetime.timedelta(days=7):
		return 'am {:%A um %H:%M} Uhr'.format(ts)
	elif ts.year == now.year:
		return 'am {:%d. %B um %H:%M} Uhr'.format(ts)
	else:
		return 'am {:%d. %B %Y um %H:%M} Uhr'.format(ts)


class Series(object):

	def __init__(self, name):
		self.name = name
		self.now = datetime.datetime.now()
		self.records = collections.deque()
		self.summary = collections.deque()
		self._read(self.now.year-1)
		self._read(self.now.year)
		self._clear()

	def _append(self, record):
		if self.records and record.timestamp <= self.records[-1].timestamp:
			return
		self.records.append(record)
		if len(self.records) >= 3 and self.records[-3].value == \
				self.records[-2].value == self.records[-1].value and \
				self.records[-1].timestamp-self.records[-3].timestamp < \
				ALLOWED_DOWNTIME:
			del self.records[-2]

	def _clear(self):
		while self.records and self.records[0].timestamp < \
				self.now-datetime.timedelta(RECORD_DAYS):
			self.records.popleft()
		while self.summary and self.summary[0].date < \
				(self.now - datetime.timedelta(SUMMARY_DAYS)).date():
			self.summary.popleft()

	def _read(self, year):
		filename = '{}/{}_{}.csv'.format(DATA_DIR, self.name, year)
		try:
			with open(filename, newline='') as csv_file:
				for row in csv.reader(csv_file):
					record = Record(
						datetime.datetime.fromtimestamp(int(row[0])),
						_universal_parser(row[1]))
					self._append(record)
					self._summarize(record)
		except OSError:
			pass

	def _write(self, record):
		filename = '{}/{}_{}.csv'.format(DATA_DIR, self.name, self.now.year)
		with open(filename, mode='a', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerow((int(record.timestamp.timestamp()), record.value))

	@property
	def current(self):
		if self.records and \
				self.now-self.records[-1].timestamp <= ALLOWED_DOWNTIME:
			return self.records[-1]
		else:
			return None

	@property
	def day(self):
		min_time = self.now - datetime.timedelta(days=1)
		start = len(self.records)
		while start > 0 and self.records[start-1].timestamp >= min_time:
			start -= 1
		return itertools.islice(self.records, start, None)

	def save(self, record):
		logging.info('{}: {} / {}'.format(self.name, *record))
		self.now = datetime.datetime.now()
		self._append(record)
		self._summarize(record)
		self._clear()
		self._write(record)


class Temperature(Series):

	def __init__(self, name, low, high):
		self.low = low
		self.high = high
		self.date = datetime.date.min
		self.today = None
		super().__init__(name)

	def __str__(self):
		current = self.current
		minimum, maximum = self.minmax
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current is None:
			ret.append('Fehler')
		else:
			ret.append('{:.1f} °C {}'.format(
				current.value, _format_timestamp(current.timestamp, self.now)))
			if current.value < self.low or current.value > self.high:
				ret.append(' ⚠')
		ret.append('<ul>\n')
		if minimum:
			ret.append('<li>Wochen-Tief bei {:.1f} °C {}'.format(
				minimum.value, _format_timestamp(minimum.timestamp, self.now)))
			if minimum.value < self.low:
				ret.append(' ⚠')
			ret.append('</li>\n')
		if maximum:
			ret.append('<li>Wochen-Hoch bei {:.1f} °C {}'.format(
				maximum.value, _format_timestamp(maximum.timestamp, self.now)))
			if maximum.value > self.high:
				ret.append(' ⚠')
			ret.append('</li>\n')
		ret.append(
			'<li>Warnbereich unter {:.0f} °C und über {:.0f} °C</li>\n'
				.format(self.low, self.high))
		ret.append('</ul>')
		return ''.join(ret)

	def _summarize(self, record):
		if record.timestamp.date() > self.date:
			if self.today:
				self.summary.append(Summary(self.date,
					                        min(self.today), max(self.today)))
			self.date = record.timestamp.date()
			self.today = list()
		self.today.append(record.value)

	@property
	def minmax(self):
		minimum = maximum = None
		for record in self.records:
			if not minimum or record.value <= minimum.value:
				minimum = record
			if not maximum or record.value >= maximum.value:
				maximum = record
		return minimum, maximum

	@property
	def error(self):
		current = self.current
		if current is None:
			return 'Messpunkt "{}" liefert keine Daten.'.format(self.name)
		elif current.value < self.low:
			return 'Messpunkt "{}" unter {:.0f} °C.'.format(
				self.name, self.low)
		elif current.value > self.high:
			return 'Messpunkt "{}" über {:.0f} °C.'.format(
				self.name, self.high)
		else:
			return None


class Switch(Series):

	def __init__(self, name):
		super().__init__(name)

	def __str__(self):
		current = self.current
		last_false = last_true = None
		for timestamp, value in reversed(self.records):
			if value:
				if not last_true:
					last_true = timestamp
			else:
				if not last_false:
					last_false = timestamp
			if last_false and last_true:
				break
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current is None:
			ret.append('Fehler')
		else:
			ret.append('{} {}'.format(
				'Ein' if current.value else 'Aus',
				_format_timestamp(current.timestamp, self.now)))
		ret.append('<ul>\n')
		if last_true and (current is None or not current):
			ret.append('<li>Zuletzt Ein {}</li>\n'.format(
				_format_timestamp(last_true, self.now)))
		if last_false and (current is None or current):
			ret.append('<li>Zuletzt Aus {}</li>\n'.format(
				_format_timestamp(last_false, self.now)))
		if self.records:
			ret.append(
				'<li>{} Einschaltdauer in der letzten Woche</li>\n'
					.format(_format_timedelta(self.uptime)))
		ret.append('</ul>')
		return ''.join(ret)

	def _summarize(self, record):
		pass

	@property
	def segments(self):
		expect = True
		for timestamp, value in self.records:
			# assume false during downtime
			if not expect and timestamp-running > ALLOWED_DOWNTIME:
				expect = True
				yield start, running
			if value:
				running = timestamp
			# identify segments
			if expect != value:
				continue
			if expect:
				expect = False
				start = timestamp
			else:
				expect = True
				yield start, timestamp
		if not expect:
			yield start, running

	@property
	def uptime(self):
		total = datetime.timedelta()
		for start, stop in self.segments:
			total += stop - start
		return total

	@property
	def error(self):
		if self.current is None:
			return 'Messpunkt "{}" liefert keine Daten.'.format(self.name)
		else:
			return None


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		on_shutdown()
	except Exception as err:
		on_shutdown()
		tb_lines = traceback.format_tb(err.__traceback__)
		notification.crash_report('{}: {}\n{}'.format(
			type(err).__name__, err, ''.join(tb_lines)))
