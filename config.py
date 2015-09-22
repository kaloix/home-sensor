import datetime

detail_range = datetime.timedelta(days=1)
summary_range = datetime.timedelta(days=365)
transmit_interval = datetime.timedelta(minutes=10)
allowed_downtime = 2 * transmit_interval
warning_pause = datetime.timedelta(days=1)
client_server = 'kaloix@adhara.uberspace.de:home-sensor/'
admin_address = 'stefan@kaloix.de'
user_address = 'stefan@kaloix.de'
enable_email = False
