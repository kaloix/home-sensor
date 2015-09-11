import datetime

detail_range = datetime.timedelta(days=1)
summary_range = datetime.timedelta(days=365)
client_interval = datetime.timedelta(minutes=10)
server_interval = datetime.timedelta(minutes=1)
allowed_downtime = 2 * client_interval
warning_pause = datetime.timedelta(days=1)
data_dir = 'data/'
backup_dir = 'backup/'
client_server = 'kaloix@adhara.uberspace.de:home-sensor/'
web_dir = '/home/kaloix/html/sensor/'
admin_address = 'stefan@kaloix.de'
user_address = 'stefan@kaloix.de'
enable_email = False
