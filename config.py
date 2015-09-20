import datetime

detail_range = datetime.timedelta(days=1)
summary_range = datetime.timedelta(days=365)
sampling_interval = datetime.timedelta(seconds=10)
transmit_interval = datetime.timedelta(minutes=10)
allowed_downtime = 2 * transmit_interval
server_interval = datetime.timedelta(minutes=1)
warning_pause = datetime.timedelta(days=1)
data_dir = 'data/'
backup_dir = 'backup/'
client_server = 'kaloix@adhara.uberspace.de:home-sensor/'
web_dir = '/home/kaloix/html/sensor/'
admin_address = 'stefan@kaloix.de'
user_address = 'stefan@kaloix.de'
enable_email = False
