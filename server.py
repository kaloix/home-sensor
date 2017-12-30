#!/usr/bin/env python3

import collections
import configparser
import contextlib
import csv
import datetime
import itertools
import json
import locale
import logging
import queue
import shutil
import time

import dateutil.rrule
import matplotlib.dates
import matplotlib.pyplot
import pysolar
import pytz

import api
import notify
import utility

ALLOWED_DOWNTIME = datetime.timedelta(minutes=30)
COLOR_CYCLE = ['b', 'g', 'r', 'c', 'm', 'y', 'k']
DATA_DIR = 'data/'
INTERVAL = 60
PAUSE_WARN_FAILURE = 30 * 24 * 60 * 60
PAUSE_WARN_VALUE = 24 * 60 * 60
PLOT_INTERVAL = 10 * 60
RECORD_DAYS = 7
SUMMARY_DAYS = 183
TIMEZONE = pytz.timezone('Europe/Berlin')
WEB_DIR = '/home/kaloix/html/sensor/'

config = configparser.ConfigParser()
groups = collections.defaultdict(collections.OrderedDict)
inbox = queue.Queue()
now = datetime.datetime.now(tz=datetime.timezone.utc)
Record = collections.namedtuple('Record', 'timestamp value')
Summary = collections.namedtuple('Summary', 'date minimum maximum')
Uptime = collections.namedtuple('Uptime', 'date value')


def main():
    global now
    utility.logging_config()
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    config.read('config.ini')
    with open('sensor.json') as json_file:
        sensor_json = json_file.read()
    devices = json.loads(sensor_json,
                         object_pairs_hook=collections.OrderedDict)
    for device in devices:
        for kind, attr in device['output'].items():
            if kind == 'temperature':
                groups[attr['group']][attr['name']] = Temperature(
                    attr['low'],
                    attr['high'],
                    attr['name'],
                    device['input']['interval'],
                    attr['fail-notify'])
            elif kind == 'switch':
                groups[attr['group']][attr['name']] = Switch(
                    attr['name'],
                    device['input']['interval'],
                    attr['fail-notify'])
    with website(), api.ApiServer(accept_record), \
            notify.MailSender(
                config['email']['source_address'],
                config['email']['admin_address'],
                config['email']['user_address'],
                config['email'].getboolean('enable_email')) as mail:
        while True:
            # get new record
            start = time.perf_counter()
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            record_counter = int()
            with contextlib.suppress(queue.Empty):
                while True:
                    group, name, record = inbox.get(block=False)
                    groups[group][name].save(record)
                    record_counter += 1
            # update content
            for group, series_dict in groups.items():
                for series in series_dict.values():
                    if series.error:
                        mail.queue(series.error, PAUSE_WARN_FAILURE)
                    if series.warning:
                        mail.queue(series.warning, PAUSE_WARN_VALUE)
                detail_html(group, series_dict.values())
            with contextlib.suppress(utility.CallDenied):
                make_plots()
            mail.send_all()
            # log processing
            utility.memory_check()
            logging.info('updated website in {:.3f}s, {} new records'.format(
                time.perf_counter() - start, record_counter))
            time.sleep(INTERVAL)


@contextlib.contextmanager
def website():
    shutil.copy('static/favicon.png', WEB_DIR)
    shutil.copy('static/htaccess', WEB_DIR + '.htaccess')
    shutil.copy('static/index.html', WEB_DIR)
    try:
        yield
    finally:
        logging.info('disable website')
        shutil.copy('static/htaccess_maintenance', WEB_DIR + '.htaccess')


def accept_record(group, name, timestamp, value):
    timestamp = datetime.datetime.fromtimestamp(int(timestamp),
                                                tz=datetime.timezone.utc)
    logging.info('{}: {} / {}'.format(name, timestamp, value))
    filename = '{}/{}_{}.csv'.format(DATA_DIR, name,
                                     timestamp.astimezone(TIMEZONE).year)
    with open(filename, mode='a', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow((int(timestamp.timestamp()), value))
    inbox.put((group, name, Record(timestamp, value)))


def detail_html(group, series_list):
    text = list()
    text.append('<ul>')
    for series in series_list:
        text.append('<li>{}</li>'.format(series))
    text.append('</ul>')
    values = '\n'.join(text)
    filename = '{}{}.html'.format(WEB_DIR, group)
    with open(filename, mode='w') as html_file:
        html_file.write(values)


@utility.allow_every_x_seconds(PLOT_INTERVAL)
def make_plots():
    for group, series_dict in groups.items():
        # FIXME svg backend has memory leak in matplotlib 1.4.3
        plot_history(series_dict.values(), '{}{}.png'.format(WEB_DIR, group))


def _nighttime(count, date_time):
    date_time -= datetime.timedelta(days=count)
    sun_change = list()
    for c in range(0, count + 1):
        date_time += datetime.timedelta(days=1)
        sun_change.extend(pysolar.util.get_sunrise_sunset(
            49.2, 11.08, date_time))
    sun_change = sun_change[1:-1]
    for r in range(0, count):
        yield sun_change[2 * r], sun_change[2 * r + 1]


def _plot_records(series_list, days):
    color_iter = iter(COLOR_CYCLE)
    for series in series_list:
        color = next(color_iter)
        if type(series) is Temperature:
            parts = list()
            for record in series.day if days == 1 else series.records:
                if (not parts or record.timestamp - parts[-1][-1].timestamp >
                        ALLOWED_DOWNTIME):
                    parts.append(list())
                parts[-1].append(record)
            for part in parts:
                timestamps, values = zip(*part)
                matplotlib.pyplot.plot(timestamps, values, label=series.name,
                                       linewidth=2, color=color, zorder=3)
        elif type(series) is Switch:
            for start, end in series.segments(series.records):
                matplotlib.pyplot.axvspan(start, end, label=series.name,
                                          color=color, alpha=0.5, zorder=1)
    for sunset, sunrise in _nighttime(days + 1, now):
        matplotlib.pyplot.axvspan(sunset, sunrise, label='Nacht', hatch='//',
                                  facecolor='0.9', edgecolor='0.8', zorder=0)
    matplotlib.pyplot.xlim(now - datetime.timedelta(days), now)
    matplotlib.pyplot.ylabel('Temperatur °C')
    ax = matplotlib.pyplot.gca()  # FIXME not available in mplrc 1.4.3
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position('right')


def _plot_summary(series_list):
    ax1 = matplotlib.pyplot.gca()  # FIXME not available in mplrc 1.4.3
    ax2 = ax1.twinx()
    color_iter = iter(COLOR_CYCLE)
    switch = False
    for series in series_list:
        color = next(color_iter)
        if type(series) is Temperature:
            parts = list()
            for summary in series.summary:
                if (not parts or summary.date - parts[-1][-1].date >
                        datetime.timedelta(days=7)):
                    parts.append(list())
                parts[-1].append(summary)
            for part in parts:
                dates, mins, maxs = zip(*part)
                ax1.fill_between(dates, mins, maxs, label=series.name,
                                 color=color, alpha=0.5, interpolate=True,
                                 zorder=0)
        elif type(series) is Switch:
            switch = True
            dates, values = zip(*series.summary)
            ax2.plot(dates, values, color=color,
                     marker='o', linestyle='', zorder=1)
    today = now.astimezone(TIMEZONE).date()
    matplotlib.pyplot.xlim(today - datetime.timedelta(days=SUMMARY_DAYS),
                           today)
    ax1.set_ylabel('Temperatur °C')
    ax1.yaxis.tick_right()
    ax1.yaxis.set_label_position('right')
    if switch:
        ax2.set_ylabel('Laufzeit h')
        ax2.yaxis.tick_left()
        ax2.yaxis.set_label_position('left')
        ax2.grid(False)
    else:
        ax2.set_visible(False)


def plot_history(series_list, file):
    fig = matplotlib.pyplot.figure(figsize=(12, 7))
    # last week
    ax = matplotlib.pyplot.subplot(312)
    _plot_records(series_list, RECORD_DAYS)
    frame_start = now - datetime.timedelta(days=RECORD_DAYS)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%a.'))
    ax.xaxis.set_ticks(_day_locator(frame_start, now, TIMEZONE))
    ax.xaxis.set_ticks(_hour_locator(frame_start, now, 6, TIMEZONE),
                       minor=True)
    handles, labels = ax.get_legend_handles_labels()
    # last day
    ax = matplotlib.pyplot.subplot(311)
    _plot_records(series_list, 1)
    matplotlib.pyplot.legend(
        handles=list(collections.OrderedDict(zip(labels, handles)).values()),
        loc='lower left', bbox_to_anchor=(0, 1), ncol=5, frameon=False)
    frame_start = now - datetime.timedelta(days=1)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H'))
    ax.xaxis.set_ticks(_hour_locator(frame_start, now, 2, TIMEZONE))
    ax.xaxis.set_minor_locator(matplotlib.dates.HourLocator())
    # summary
    ax = matplotlib.pyplot.subplot(313)
    _plot_summary(series_list)
    frame_start = now - datetime.timedelta(days=SUMMARY_DAYS)
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
    hours = td.days * 24 + td.seconds // 3600
    if hours:
        ret.append(str(hours))
        ret.append('Stunde' if hours == 1 else 'Stunden')
    minutes = (td.seconds // 60) % 60
    ret.append(str(minutes))
    ret.append('Minute' if minutes == 1 else 'Minuten')
    return ' '.join(ret)


def _format_timestamp(ts):
    ts = ts.astimezone(TIMEZONE)
    local_now = now.astimezone(TIMEZONE)
    if ts.date() == local_now.date():
        return 'um {:%H:%M} Uhr'.format(ts)
    if local_now.date() - ts.date() == datetime.timedelta(days=1):
        return 'gestern um {:%H:%M} Uhr'.format(ts)
    if local_now.date() - ts.date() < datetime.timedelta(days=7):
        return 'am {:%A um %H:%M} Uhr'.format(ts)
    if ts.year == local_now.year:
        return 'am {:%d. %B um %H:%M} Uhr'.format(ts)
    return 'am {:%d. %B %Y um %H:%M} Uhr'.format(ts)


def _format_temperature(record, low, high):
    if not record:
        return 'Keine Daten empfangen'
    text = '{:.1f} °C {}'.format(record.value,
                                 _format_timestamp(record.timestamp))
    if low <= record.value <= high:
        return text
    return '<mark>{}</mark>'.format(text)


def _format_switch(record):
    if not record:
        return 'Keine Daten empfangen'
    return '{} {}'.format('Ein' if record.value else 'Aus',
                          _format_timestamp(record.timestamp))


class Series(object):
    text = None

    def __init__(self, name, interval, fail_notify):
        self.name = name
        self.interval = datetime.timedelta(seconds=interval)
        self.notify = fail_notify
        self.fail_status = False
        self.fail_counter = int()
        self.records = collections.deque()
        self.summary = collections.deque()
        self._read(now.year - 1)
        self._read(now.year)
        self._clear()

    def __str__(self):
        ret = list()
        first, *lines = self.text
        lines.append('Aktualisierung alle {}'.format(
            _format_timedelta(self.interval)))
        ret.append('<strong>{}</strong>'.format(first))
        ret.append('<ul>')
        for line in lines:
            ret.append('<li>{}</li>'.format(line))
        ret.append('</ul>')
        return '\n'.join(ret)

    def _append(self, record):
        if self.records and record.timestamp <= self.records[-1].timestamp:
            raise OlderThanPreviousError('{}: previous {}, new {}'.format(
                self.name, self.records[-1].timestamp.timestamp(),
                record.timestamp.timestamp()))
        self.records.append(record)
        if (len(self.records) >= 3 and self.records[-3].value ==
                self.records[-2].value == self.records[-1].value and
                self.records[-1].timestamp - self.records[-3].timestamp <
                ALLOWED_DOWNTIME):
            del self.records[-2]

    def _clear(self):
        while (self.records and self.records[0].timestamp < now -
                datetime.timedelta(RECORD_DAYS)):
            self.records.popleft()
        while (self.summary and self.summary[0].date < (now -
                datetime.timedelta(SUMMARY_DAYS)).astimezone(TIMEZONE).date()):
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
                    try:
                        self._append(record)
                    except OlderThanPreviousError:
                        # FIXME: remove this except, instead don't save invalid data
                        continue
                    self._summarize(record)
        except OSError:
            pass

    @property
    def current(self):
        if (self.records and now - self.records[-1].timestamp <=
                ALLOWED_DOWNTIME):
            return self.records[-1]
        else:
            return None

    @property
    def error(self):
        if not self.notify:
            return None
        if self.current:
            self.fail_status = False
            return None
        if not self.fail_status:
            self.fail_status = True
            self.fail_counter += 1
        return 'Messpunkt "{}" liefert keine Daten. (#{})'.format(
            self.name, self.fail_counter)

    @property
    def day(self):
        min_time = now - datetime.timedelta(days=1)
        start = len(self.records)
        while start > 0 and self.records[start - 1].timestamp >= min_time:
            start -= 1
        return itertools.islice(self.records, start, None)

    def save(self, record):
        try:
            self._append(record)
        except OlderThanPreviousError as err:
            logging.warning('ignore {}'.format(err))
            return
        self._summarize(record)
        self._clear()


class Temperature(Series):
    def __init__(self, low, high, *args):
        self.low = low
        self.high = high
        self.date = datetime.date.min
        self.today = None
        super().__init__(*args)

    @classmethod
    def minmax(cls, records):
        minimum = maximum = None
        for record in records:
            if not minimum or record.value <= minimum.value:
                minimum = record
            if not maximum or record.value >= maximum.value:
                maximum = record
        return minimum, maximum

    def _summarize(self, record):
        date = record.timestamp.astimezone(TIMEZONE).date()
        if date > self.date:
            if self.today:
                self.summary.append(Summary(self.date,
                                            min(self.today), max(self.today)))
            self.date = date
            self.today = list()
        self.today.append(record.value)

    @property
    def text(self):
        minimum, maximum = self.minmax(self.records)
        minimum_d, maximum_d = self.minmax(self.day)
        yield '{}: {}'.format(
            self.name, _format_temperature(self.current, self.low, self.high))
        if minimum_d:
            yield 'Letzte 24 Stunden: ▼ {} / ▲ {}'.format(
                _format_temperature(minimum_d, self.low, self.high),
                _format_temperature(maximum_d, self.low, self.high))
        if minimum:
            yield 'Letzte 7 Tage: ▼ {} / ▲ {}'.format(
                _format_temperature(minimum, self.low, self.high),
                _format_temperature(maximum, self.low, self.high))
        yield 'Warnbereich unter {:.0f} °C und über {:.0f} °C'.format(
            self.low, self.high)

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
        self.date = None
        super().__init__(*args)

    @classmethod
    def uptime(cls, segments):
        total = datetime.timedelta()
        for start, stop in segments:
            total += stop - start
        return total

    @classmethod
    def segments(cls, records):
        expect = True
        for timestamp, value in records:
            # assume false during downtime
            if not expect and timestamp - running > ALLOWED_DOWNTIME:
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

    def _summarize(self, record):  # TODO record.value not used
        date = record.timestamp.astimezone(TIMEZONE).date()
        if not self.date:
            self.date = date
            return
        if date <= self.date:
            return
        lower = datetime.datetime.combine(self.date, datetime.time.min)
        lower = TIMEZONE.localize(lower)
        upper = datetime.datetime.combine(
            self.date + datetime.timedelta(days=1),
            datetime.time.min)
        upper = TIMEZONE.localize(upper)
        total = datetime.timedelta()
        for start, end in self.segments(self.records):
            if end <= lower or start >= upper:
                continue
            if start < lower:
                start = lower
            if end > upper:
                end = upper
            total += end - start
        hours = total / datetime.timedelta(hours=1)
        self.summary.append(Uptime(self.date, hours))
        self.date = date

    @property
    def text(self):
        last_false = last_true = None
        for record in reversed(self.records):
            if record.value:
                if not last_true:
                    last_true = record
            elif not last_false:
                last_false = record
            if last_false and last_true:
                break
        current = self.current
        yield '{}: {}'.format(self.name, _format_switch(current))
        if last_true and (not current or not current.value):
            yield 'Zuletzt {}'.format(_format_switch(last_true))
        if last_false and (not current or current.value):
            yield 'Zuletzt {}'.format(_format_switch(last_false))
        yield 'Letzte 24 Stunden: Einschaltdauer {}'.format(
            _format_timedelta(self.uptime(self.segments(self.day))))
        yield 'Letzte 7 Tage: Einschaltdauer {}'.format(
            _format_timedelta(self.uptime(self.segments(self.records))))

    @property
    def warning(self):
        return None


class OlderThanPreviousError(Exception):
    pass


if __name__ == "__main__":
    main()
