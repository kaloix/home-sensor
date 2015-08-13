import csv
import logging

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
		level = logging.INFO)
