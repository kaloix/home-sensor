import matplotlib.pyplot
import pytz
import datetime
import pysolar
import config
import markdown
import util # FIXME

markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')

def detail_table(history):
	string = list()
	string.append('Messpunkt | Aktuell | Tagestief | Tageshoch | Normal')
	string.append('--- | --- | --- | --- | ---')
	string.extend([str(h) for h in history])
	return markdown_to_html.convert('\n'.join(string))

def plot_history(history, file, now):
	history = [h for h in history if type(h) is util.FloatHistory] # FIXME
	matplotlib.pyplot.figure(figsize=(11, 6))
	# detail record
	matplotlib.pyplot.subplot(2, 1, 1)
	night1, night2 = nighttime(2, now)
	matplotlib.pyplot.axvspan(*night1, color='black', alpha=0.3)
	matplotlib.pyplot.axvspan(*night2, color='black', alpha=0.3)
	for h in history:
		matplotlib.pyplot.plot(h.detail.timestamp, h.detail.value, lw=3, label=h.name)
	matplotlib.pyplot.xlim(now-config.detail_range, now)
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.gca().yaxis.tick_right()
	matplotlib.pyplot.gca().yaxis.set_label_position('right')
	matplotlib.pyplot.legend(loc='lower left', bbox_to_anchor=(0, 1), borderaxespad=0, ncol=3, frameon=False)
	# summary records
	matplotlib.pyplot.subplot(2, 1, 2)
	for h in history:
		matplotlib.pyplot.plot(h.summary_avg.timestamp, h.summary_avg.value, lw=3)
		matplotlib.pyplot.fill_between(h.summary_min.timestamp, h.summary_min.value, h.summary_max.value, alpha=0.5)
	matplotlib.pyplot.xlabel('Datum')
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.gca().yaxis.tick_right()
	matplotlib.pyplot.gca().yaxis.set_label_position('right')
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
