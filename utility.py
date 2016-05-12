import gc
import logging
import resource
import time


def logging_config():
	logging.basicConfig(
		format = '[%(asctime)s:%(levelname)s:%(module)s] %(message)s',
		datefmt = '%d-%H-%M-%S',
		level = logging.DEBUG)


def memory_check():
	gc.collect()
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3
	if memory > 200:
		raise MemoryLeakError('{} MB'.format(memory))


def allow_every_x_seconds(interval):
	def decorating_function(user_function):
		target = int()
		def new_function(*args, **kwargs):
			nonlocal target
			now = time.perf_counter()
			if now >= target:
				target = now + interval
				return user_function(*args, **kwargs)
			else:
				raise CallDenied
		return new_function
	return decorating_function


class MemoryLeakError(Exception):
	pass

class CallDenied(Exception):
	pass
