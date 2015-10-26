import dateutil.rrule
import gc
import logging
import resource
import time


def logging_config():
	logging.basicConfig(
		format = '[%(asctime)s:%(levelname)s:%(module)s] %(message)s',
		datefmt = '%m-%d-%H-%M-%S',
		level = logging.DEBUG)


def memory_check():
	gc.collect()
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3
	if memory > 100:
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


# matplotlib.dates.RRuleLocator is bugged at dst transitions
# http://matplotlib.org/api/dates_api.html#matplotlib.dates.RRuleLocator
# https://github.com/matplotlib/matplotlib/issues/2737/
# https://github.com/dateutil/dateutil/issues/102

def month_locator(start, end, tz):
	lower = start.astimezone(tz).date().replace(day=1)
	upper = end.astimezone(tz).date()
	rule = dateutil.rrule.rrule(dateutil.rrule.MONTHLY,
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]

def week_locator(start, end, tz):
	lower = start.astimezone(tz).date()
	upper = end.astimezone(tz).date()
	rule = dateutil.rrule.rrule(dateutil.rrule.WEEKLY,
	                            byweekday=dateutil.rrule.MO,
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]

def day_locator(start, end, tz):
	lower = start.astimezone(tz).date()
	upper = end.astimezone(tz).date()
	rule = dateutil.rrule.rrule(dateutil.rrule.DAILY,
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]

def hour_locator(start, end, step, tz):
	lower = start.astimezone(tz).date()
	upper = end.astimezone(tz).replace(tzinfo=None)
	rule = dateutil.rrule.rrule(dateutil.rrule.HOURLY,
	                            byhour=range(0, 24, step),
	                            dtstart=lower, until=upper)
	return [tz.localize(dt) for dt in rule if start <= tz.localize(dt) <= end]
