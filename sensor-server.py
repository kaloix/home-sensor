#!/usr/bin/env python3

import locale
import time
import string
import markdown

# initialization
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()

# fill markdown template
identifier = {
	'temp_wohn_akt': 23.6,
	'temp_wohn_min': 10.0,
	'temp_wohn_max': 30.1,
	'temp_klima_akt': 11.1,
	'temp_klima_min': 10.9,
	'temp_klima_max': 29.5,
	'bild_diagramm': 'placeholder.png',
	'datum_aktualisierung': time.strftime('%c')
}
markdown_filled = string.Template(markdown_template).substitute(identifier)

# convert markdown to html
extensions = [
	'markdown.extensions.tables'
]
html_body = markdown.markdown(markdown_filled, extensions)
identifier = {
	'html_body': html_body
}
html_filled = string.Template(html_template).substitute(identifier)

# Finalization
with open('data.html', mode='w') as html_file:
	html_file.write(html_filled)

