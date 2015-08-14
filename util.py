import csv
import logging
import resource

def read_csv(file):
	data = list()
	with open(file, newline='') as csv_file:
		reader = csv.reader(csv_file)
		for row in reader:
			data.append(row)
	return data

def write_csv(file, data):
	with open(file, mode='w', newline='') as csv_file:
		writer = csv.writer(csv_file)
		writer.writerows(data)

def init_logging():
	logging.basicConfig(
		format = '[%(asctime)s:%(levelname)s:%(module)s] %(message)s',
		datefmt = '%y-%m-%d-%H-%M-%S',
		level = logging.DEBUG)

def memory_check():
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000000
	logging.debug('using {:.0f} megabytes of memory'.format(memory))
	if memory > 100:
		raise SystemExit('memory leak')
