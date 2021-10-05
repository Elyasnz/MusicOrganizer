import os

try:
	import mutagen
	import pandas as pd
	import numpy as np
	import xlsxwriter
	import jinja2
except ImportError as e:
	print(f'ImportError {e}')
	os.system('pip install mutagen==1.45.1')
	os.system('pip install pandas==1.2.4 pytz==2021.1')
	os.system('pip install numpy==1.21.2')
	os.system('pip install xlsxwriter==3.0.1')
	os.system('pip install Jinja2==3.0.1')
	os.system('pip install xlrd==1.2.0')

