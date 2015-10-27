#!/usr/bin/env python3

import collections
import contextlib
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

import dateutil.rrule
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
INTERVAL = 180
RECORD_DAYS = 7
SUMMARY_DAYS = 365
TIMEZONE = pytz.timezone('Europe/Berlin')
WEB_DIR = '/home/kaloix/html/sensor/'

Record = collections.namedtuple('Record', 'timestamp value')
Summary = collections.namedtuple('Summary', 'date minimum maximum')


def main():
	utility.logging_config()
	locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
	with open('template.html') as html_file:
		html_template = string.Template(html_file.read())
	with open('sensor.json') as json_file:
		sensor_json = json_file.read()
	devices = json.loads(sensor_json,
	                     object_pairs_hook=collections.OrderedDict)
	groups = collections.defaultdict(list)
	for device in devices:
		for kind, attr in device['output'].items():
			if kind == 'temperature':
				groups[attr['group']].append(Temperature(
					attr['low'],
					attr['high'],
					attr['name'],
					device['input']['interval'],
					attr['fail-notify']))
			elif kind == 'switch':
				groups[attr['group']].append(Switch(
					attr['name'],
					device['input']['interval'],
					attr['fail-notify']))
	with monitor.MonitorServer(verify_record) as ms, website(), \
			notification.NotificationCenter() as notify:
		while True:
			start = time.perf_counter()
			for name, record in ms.fetch():
				save_record(groups, name, record) # FIXME simplify
			now = datetime.datetime.now(tz=datetime.timezone.utc)
			Series.now = now
			for group, series_list in groups.items():
				for series in series_list:
					if series.error:
						notify.user_warning(series.error) # TODO only one per failure
					if series.warning:
						notify.user_warning(series.warning)
				html_filled = html_template.substitute(
					refresh_seconds = INTERVAL,
					group = group,
					values = detail_html(series_list),
					update_time = '{:%A %d. %B %Y %X %Z}'.format(
						now.astimezone(TIMEZONE)),
					year = '{:%Y}'.format(now))
				filename = '{}{}.html'.format(WEB_DIR, group.lower())
				with open(filename, mode='w') as html_file:
					html_file.write(html_filled)
				# FIXME svg backend has memory leak in matplotlib 1.4.3
				plot_history(series_list,
				             '{}{}.png'.format(WEB_DIR, group), now)
			utility.memory_check()
			duration = time.perf_counter() - start
			logging.info('updated website in {:.1f}s'.format(duration))
			time.sleep(INTERVAL)


@contextlib.contextmanager
def website():
	shutil.copy('static/favicon.png', WEB_DIR)
	shutil.copy('static/htaccess', WEB_DIR+'.htaccess')
	try:
		yield
	finally:
		logging.info('disable website')
		shutil.copy('static/htaccess_maintenance', WEB_DIR+'.htaccess')


def verify_record(name, timestamp, value):
	timestamp = datetime.datetime.fromtimestamp(int(timestamp),
	                                            tz=datetime.timezone.utc)
	logging.info('{}: {} / {}'.format(name, timestamp, value))
	return name, Record(timestamp, value)


def save_record(groups, name, record):
	for series_list in groups.values():
		for series in series_list:
			if series.name == name:
				series.save(record)
				return


def detail_html(series_list):
	ret = list()
	ret.append('<ul>')
	for series in series_list:
		ret.append('<li>{}</li>'.format(series))
	ret.append('</ul>')
	return '\n'.join(ret)


def _nighttime(count, date_time):
	date_time -= datetime.timedelta(days=count)
	sun_change = list()
	for c in range(0, count+1):
		date_time += datetime.timedelta(days=1)
		sun_change.extend(pysolar.util.get_sunrise_sunset(
			49.2, 11.08, date_time))
	sun_change = sun_change[1:-1]
	for r in range(0, count):
		yield sun_change[2*r], sun_change[2*r+1]


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
	frame_start = now - datetime.timedelta(days=RECORD_DAYS)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%a.'))
	ax.xaxis.set_ticks(_day_locator(frame_start, now, TIMEZONE))
	ax.xaxis.set_ticks(_hour_locator(frame_start, now, 6, TIMEZONE),
	                   minor=True)
	handles, labels = ax.get_legend_handles_labels()
	# last day
	ax = matplotlib.pyplot.subplot(311)
	_plot_records(series_list, 1, now)
	matplotlib.pyplot.legend(
		handles=list(collections.OrderedDict(zip(labels, handles)).values()),
		loc='lower left', bbox_to_anchor=(0, 1), ncol=5, frameon=False)
	frame_start = now - datetime.timedelta(days=1)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H'))
	ax.xaxis.set_ticks(_hour_locator(frame_start, now, 2, TIMEZONE))
	ax.xaxis.set_minor_locator(matplotlib.dates.HourLocator())
	# summary
	ax = matplotlib.pyplot.subplot(313)
	_plot_summary(series_list, now)
	frame_start = now - datetime.timedelta(days=365)
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%b.'))
	ax.xaxis.set_ticks(_month_locator(frame_start, now, TIMEZONE))
	ax.xaxis.set_ticks(_week_locator(frame_start, now, TIMEZONE), minor=True)
	# save file
	matplotlib.pyplot.savefig(file, bbox_inches='tight')
	matplotlib.pyplot.close()


# matplotlib.dates.RRuleLocator is bugged at dst transitions
# http://matplotlib.org/api/dates_api.html#matplotlib.dates.RRuleLocator
# https://github.com/matplotlib/matplotlib/issues/2737/
# https://github.com/dateutil/dateutil/issues/102

def _month_locator(start, end, tz):
	lower = start.astimezone(tz).date().replace(day=1)
	upper = end.astimezone(tz).date()
	rule = dateutil.rrule.rrule(dateutil.rrule.MONTHLY,
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]

def _week_locator(start, end, tz):
	lower = start.astimezone(tz).date()
	upper = end.astimezone(tz).date()
	rule = dateutil.rrule.rrule(dateutil.rrule.WEEKLY,
	                            byweekday=dateutil.rrule.MO,
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]

def _day_locator(start, end, tz):
	lower = start.astimezone(tz).date()
	upper = end.astimezone(tz).date()
	rule = dateutil.rrule.rrule(dateutil.rrule.DAILY,
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]

def _hour_locator(start, end, step, tz):
	lower = start.astimezone(tz).date()
	upper = end.astimezone(tz).replace(tzinfo=None)
	rule = dateutil.rrule.rrule(dateutil.rrule.HOURLY,
	                            byhour=range(0, 24, step),
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]


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
	ts = ts.astimezone(TIMEZONE)
	now = now.astimezone(TIMEZONE)
	if ts.date() == now.date():
		return 'um {:%H:%M} Uhr'.format(ts)
	if now.date()-ts.date() == datetime.timedelta(days=1):
		return 'gestern um {:%H:%M} Uhr'.format(ts)
	if now.date()-ts.date() < datetime.timedelta(days=7):
		return 'am {:%A um %H:%M} Uhr'.format(ts)
	if ts.year == now.year:
		return 'am {:%d. %B um %H:%M} Uhr'.format(ts)
	return 'am {:%d. %B %Y um %H:%M} Uhr'.format(ts)


class Series(object):

	now = datetime.datetime.now(tz=datetime.timezone.utc)

	def __init__(self, name, interval, fail_notify):
		self.name = name
		self.interval = datetime.timedelta(seconds=interval)
		self.notify = fail_notify
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
					timestamp = datetime.datetime.fromtimestamp(
						int(row[0]), tz=datetime.timezone.utc)
					value = _universal_parser(row[1])
					record = Record(timestamp, value)
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
	def error(self):
		if self.notify and not self.current:
			return 'Messpunkt "{}" liefert keine Daten.'.format(self.name)
		return None

	@property
	def day(self):
		min_time = self.now - datetime.timedelta(days=1)
		start = len(self.records)
		while start > 0 and self.records[start-1].timestamp >= min_time:
			start -= 1
		return itertools.islice(self.records, start, None)

	def save(self, record):
		self._append(record)
		self._summarize(record)
		self._clear()
		self._write(record)


class Temperature(Series):

	def __init__(self, low, high, *args):
		self.low = low
		self.high = high
		self.date = datetime.date.min
		self.today = None
		super().__init__(*args)

	def __str__(self):
		current = self.current
		minimum, maximum = self.minmax
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current:
			ret.append('{:.1f} °C {}'.format(
				current.value, _format_timestamp(current.timestamp, self.now)))
			if current.value < self.low or current.value > self.high:
				ret.append(' ⚠')
		else:
			ret.append('Fehler')
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
		ret.append('<li>Aktualisierung alle {}</li>\n'.format(
			_format_timedelta(self.interval)))
		ret.append('<li>Warnbereich unter {:.0f} °C und über {:.0f} °C</li>\n'
			.format(self.low, self.high))
#		if not self.notify:
#			ret.append('<li>Keine Benachrichtigung bei Ausfall</li>\n')
		ret.append('</ul>')
		return ''.join(ret)

	def _summarize(self, record):
		timestamp = record.timestamp.astimezone(TIMEZONE)
		if timestamp.date() > self.date:
			if self.today:
				self.summary.append(Summary(self.date,
					                        min(self.today), max(self.today)))
			self.date = timestamp.date()
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
	def warning(self):
		current = self.current
		if not current:
			return None
		if current.value < self.low:
			return 'Messpunkt "{}" unter {} °C.'.format(self.name, self.low)
		if current.value > self.high:
			return 'Messpunkt "{}" über {} °C.'.format(self.name, self.high)
		return None


class Switch(Series):

	def __init__(self, *args):
		super().__init__(*args)

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
		if current:
			ret.append('{} {}'.format(
				'Ein' if current.value else 'Aus',
				_format_timestamp(current.timestamp, self.now)))
		else:
			ret.append('Fehler')
		ret.append('<ul>\n')
		if last_true and (not current or not current.value):
			ret.append('<li>Zuletzt Ein {}</li>\n'.format(
				_format_timestamp(last_true, self.now)))
		if last_false and (not current or current.value):
			ret.append('<li>Zuletzt Aus {}</li>\n'.format(
				_format_timestamp(last_false, self.now)))
		if self.records:
			ret.append('<li>{} Einschaltdauer in der letzten Woche</li>\n'
				.format(_format_timedelta(self.uptime)))
		ret.append('<li>Aktualisierung alle {}</li>\n'.format(
			_format_timedelta(self.interval)))
#		if not self.notify:
#			ret.append('<li>Keine Benachrichtigung bei Ausfall</li>\n')
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
	def warning(self):
		return None


if __name__ == "__main__":
	main()
