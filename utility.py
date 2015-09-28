import datetime
import locale
import logging
import resource


DETAIL_RANGE = datetime.timedelta(days=1)
TRANSMIT_INTERVAL = datetime.timedelta(minutes=10)


def init():
	locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
	logging.basicConfig(
		format = '[%(asctime)s:%(levelname)s:%(module)s] %(message)s',
		datefmt = '%y-%m-%d-%H-%M-%S',
		level = logging.DEBUG)


def memory_check():
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3
	logging.debug('using {:.0f} megabytes of memory'.format(memory))
	if memory > 100:
		raise Exception('memory leak')
