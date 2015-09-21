import matplotlib.pyplot
import pytz
import datetime
import pysolar
import config
import markdown

COLOR_CYCLE = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')

def detail_table(histories):
	float_table = list()
	float_table.append('Messpunkt | Aktuell | Tagestief | Tageshoch | Normalbereich')
	float_table.append('--- | --- | --- | --- | ---')
	bool_table = list()
	bool_table.append('Messpunkt | Aktuell | Zuletzt Aus | Zuletzt Ein')
	bool_table.append('--- | --- | --- | ---')
	for history in histories:
		if hasattr(history, 'float') and history.float:
			float_table.append(str(history))
		elif hasattr(history, 'boolean') and history.boolean:
			bool_table.append(str(history))
	string = list()
	if len(float_table) > 2:
		string.extend(float_table)
		string.append('')
	if len(bool_table) > 2:
		string.extend(bool_table)
	return markdown_to_html.convert('\n'.join(string))

def plot_history(history, file, now):
	matplotlib.pyplot.figure(figsize=(12, 4))
	# detail record
	frame_start = now - config.detail_range
#	matplotlib.pyplot.subplot(2, 1, 1)
	minimum, maximum = list(), list()
	color_iter = iter(COLOR_CYCLE)
	for h in history:
		color = next(color_iter)
		if hasattr(h, 'float') and h.float:
			parts = list()
			for measurement in h.float:
				if not parts or measurement.timestamp - parts[-1][-1].timestamp > config.allowed_downtime:
					parts.append(list())
				parts[-1].append(measurement)
			for index, part in enumerate(parts):
				values, timestamps = zip(*part)
				label = h.name if index == 0 else None
				matplotlib.pyplot.plot(timestamps, values, linewidth=3, color=color, label=label)
			minimum.append(min(h.float.value)-1)
			minimum.append(h.floor)
			maximum.append(max(h.float.value)+1)
			maximum.append(h.ceiling)
		elif hasattr(h, 'boolean') and h.boolean:
			for index, (start, end) in enumerate(prepare_bool_plot(h.boolean)):
				label = h.name if index == 0 else None
				matplotlib.pyplot.axvspan(start, end, color=color ,alpha=0.33, label=label)
	nights = int(config.detail_range / datetime.timedelta(days=1)) + 2
	for index, (sunset, sunrise) in enumerate(nighttime(nights, now)):
		label = 'Nacht' if index == 0 else None
		matplotlib.pyplot.axvspan(sunset, sunrise, color='black', alpha=0.17, label=label)
	matplotlib.pyplot.xlim(frame_start, now)
	matplotlib.pyplot.ylim(min(minimum), max(maximum))
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.gca().yaxis.tick_right()
	matplotlib.pyplot.gca().yaxis.set_label_position('right')
	matplotlib.pyplot.legend(loc='lower left', bbox_to_anchor=(0, 1), borderaxespad=0, ncol=3, frameon=False)
	# summary records
#	matplotlib.pyplot.subplot(2, 1, 2)
#	for h in history:
#		matplotlib.pyplot.plot(h.summary_avg.timestamp, h.summary_avg.value, lw=3)
#		matplotlib.pyplot.fill_between(h.summary_min.timestamp, h.summary_min.value, h.summary_max.value, alpha=0.5)
#	matplotlib.pyplot.xlabel('Datum')
#	matplotlib.pyplot.ylabel('Temperatur °C')
#	matplotlib.pyplot.grid(True)
#	matplotlib.pyplot.gca().yaxis.tick_right()
#	matplotlib.pyplot.gca().yaxis.set_label_position('right')
	# save file
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
		sun_change.extend(pysolar.util.get_sunrise_sunset(49.2, 11.08, date_time))
	sun_change = sun_change[1:-1]
	night = list()
	for r in range(0, count):
		night.append((sun_change[2*r], sun_change[2*r+1]))
	# make naive
	for sunset, sunrise in night:
		yield sunset.replace(tzinfo=None), sunrise.replace(tzinfo=None)

def prepare_bool_plot(boolean):
	expect = True
	for value, timestamp in boolean:
		if value != expect:
			continue
		if expect:
			start = timestamp
			expect = False
		else:
			yield start, timestamp
			expect = True
	if not expect:
		yield start, timestamp + config.allowed_downtime
