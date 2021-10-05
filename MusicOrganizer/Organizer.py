import json
import os
import re
import sys
import warnings
from pathlib import Path

import mutagen
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).absolute().parent.parent))
import MusicOrganizer.utils as organizerUtils


class Organizer:
	information_columns = ['bitrate', 'length']

	def __init__(self, directory: str):
		"""
		check if directory exists and create necessary paths
		"""
		if not os.path.exists(directory):
			raise FileNotFoundError(directory)

		self.directory = directory
		self.organizer_dir = os.path.join(directory, '_Organizer')
		self.music_info_file = os.path.join(self.organizer_dir, 'music_info.xlsx')
		self.music_info_before_file = os.path.join(self.organizer_dir, 'music_info_before.xlsx')
		self.addrs_file = os.path.join(self.organizer_dir, 'addrs.csv')

		os.makedirs(self.organizer_dir, exist_ok=True)

	def remove_folder(self):
		"""
		remove organizer related files from self.directory
		"""
		try:
			os.remove(self.organizer_dir)
		except:
			pass

	def get_music_addrs(self, from_cache=False) -> pd.Series:
		"""
		loop through directory and get all musics addresses and save them to addrs.csv
		if from_cache -> read data from pre-saved addrs.csv (if file not exists this parameter will be ignored)
		"""
		if not os.path.exists(self.addrs_file) or not from_cache:
			addrs = []
			for dirname, dirnames, filenames in os.walk(self.directory):
				for file in filenames:
					if file.lower().endswith(organizerUtils.audio_extensions):
						addrs.append(os.path.join(dirname, file))
			addrs = pd.Series(addrs, name='addrs')
			addrs.index.name = 'id'

			addrs.to_csv(self.addrs_file)
			return addrs
		return pd.read_csv(self.addrs_file).set_index('id')['addrs']

	@staticmethod
	def _highlighted_rows(musics: pd.DataFrame) -> list:
		"""
		return rows with empty artist or title as highlighted rows
		"""
		highlight_mask = pd.isnull(musics[['artist', 'title']])
		highlight_mask = np.logical_or(highlight_mask.artist, highlight_mask.title)
		return highlight_mask[highlight_mask == True].index.values.tolist()

	def _do_highlight(self, musics: pd.DataFrame):
		highlighted = self._highlighted_rows(musics)
		musics = musics.loc[highlighted].append(musics.drop(highlighted))
		if highlighted:
			def apply_warnings(df):
				x = df.copy()
				x.loc[highlighted] = 'background-color: red'
				return x

			musics = musics.style.apply(apply_warnings, subset=['file', 'artist', 'title'])
			print(
				f'{len(highlighted)} files (highlighted in red) need your attention'
				f' check file at {self.music_info_file}'
			)
		return musics

	def read_music_info(self) -> pd.DataFrame:
		"""
		check existence and read music_info file from self.directory
		"""
		if not os.path.exists(self.music_info_file):
			raise FileNotFoundError(f'run `generate_music_info` to generate `{self.music_info_file}`')

		musics = pd.read_excel(self.music_info_file, dtype={'bpm': 'object'}).set_index('id').replace({np.nan: None})

		# check for bad files
		highlighted = self._highlighted_rows(musics)
		if highlighted:
			print(
				f'{len(highlighted)} files (highlighted in red) need your attention'
				f' check file at {self.music_info_file}'
			)

		return musics

	def generate_music_info(self):
		"""
		main function to generate musics_info.xslx file

		* remove bad music files
		* remove website tags
		* remove telegram channel tags
		* make sure that album-albumartist both exists
		* highlights musics with no artist or title
		* generate excel file from musics with their info

		"""
		musics = []
		must_have_keys = [
			'title',
			'artist',
			'album',
			'albumartist',
			'genre',
			'date',
			'bpm',
			'tracknumber',
			'discnumber'
		]
		for file in self.get_music_addrs(from_cache=False):
			try:
				file_obj = mutagen.File(file, easy=True)
				file_data = {k: v[0] if v else v for k, v in file_obj.items()}
			except:
				# if there was error reading music file info -> ignore them
				continue

			musics.append({
				**{'file': file},
				**{k: file_data.pop(k, None) for k in must_have_keys + ['originaldate']},
				**{
					'bitrate': str(file_obj.info.bitrate // 1000),
					'length': '{:02d}:{:02d}'.format(*[int(x) for x in divmod(file_obj.info.length, 60)]),
					'miscellaneous': file_data,
				}
			})
		musics = pd.DataFrame().from_records(musics)
		musics.index.name = 'id'
		warnings.filterwarnings("ignore")

		musics.to_excel(
			self.music_info_before_file, engine='xlsxwriter', verbose=False, encoding='utf-8', freeze_panes=(1, 1))

		# prioritize `originaldate` over `date` and if `date` contains 'T' get the first part ex:2020/01/01T10:10:00
		musics['date'] = musics['originaldate'].fillna(musics['date']).str.split('T').str[0]
		musics.drop(columns=['originaldate'])

		# filter numeric type columns
		musics['bpm'] = musics['bpm'][musics.bpm.apply(lambda x: str(x).isnumeric())]
		musics['date'] = musics['date'][musics.date.str.replace('-', '').apply(lambda x: str(x).isnumeric())]
		musics['discnumber'] = musics['discnumber'][
			musics['discnumber'].str.replace('/', '').apply(lambda x: str(x).isnumeric())
		]
		musics['tracknumber'] = musics['tracknumber'][
			musics['tracknumber'].str.replace('/', '').apply(lambda x: str(x).isnumeric())
		]

		# filter genre
		musics['genre'][
			organizerUtils.mask_containing_regex(musics['genre'], r'(unknown|^\d+$|\?)')
		] = None
		musics['genre'] = organizerUtils.remove_websites_and_tags(musics['genre'])

		# filter albumartist
		musics['albumartist'][
			pd.isnull(musics.album)
			| organizerUtils.mask_containing_regex(musics.albumartist, r'(unknown|various)')
			] = None
		musics['albumartist'] = organizerUtils.remove_websites_and_tags(musics.albumartist)

		# filter album
		musics['album'][
			pd.isnull(musics.albumartist)
			| organizerUtils.mask_containing_regex(musics.album, r'(unknown|single|music|motion|[\u0600-\u06FF]+)')
			] = None
		musics['album'] = organizerUtils.remove_websites_and_tags(musics['album'])

		# double check album and albumartist
		mask = pd.isnull(musics[['album', 'albumartist']])
		mask = np.logical_or(mask.album, mask.albumartist)
		musics['album'][mask] = None
		musics['albumartist'][mask] = None

		musics['artist'] = musics.artist.str.replace(r'\(RF™\)', '', regex=True, flags=re.IGNORECASE)
		musics['artist'] = organizerUtils.remove_websites_and_tags(musics.artist)
		musics['title'] = organizerUtils.remove_websites_and_tags(musics.title)

		# highlight rows containing data that needs to be fixed by user
		musics = self._do_highlight(musics)

		musics.to_excel(self.music_info_file, engine='xlsxwriter', verbose=False, encoding='utf-8', freeze_panes=(1, 1))
		return musics

	@staticmethod
	def _remove_file_with_permission(file, permission):
		print(f'removing file {file}', end=' ')
		if permission not in ['na', 'ya']:
			permission = input('Accept? [n(a)] [y(a)]')

		if permission.startswith('y'):
			print('[Accepted]')
			try:
				os.remove(file)
			except:
				pass
		else:
			print('[DENIED]')

		return permission

	@staticmethod
	def _gen_new_file_name(file: Path, new_name: str):
		return file.parent / re.subn(r'[<>:"/\\!?*|]*', '', new_name + file.suffix)[0]

	def apply_tags(self, permissions: dict = None, allow_miscellaneous=False):
		"""
		apply tags in musics_info.xlsx

		:param permissions: dictionary of different permissions
			permissions:
				remove_deleted
				remove_not_found
				remove_rename_error
				remove_edit_error
			accepted permissions:
				y -> yes
				ya -> yes for all
				n -> no
				na -> no for all
				None -> ask

		:param allow_miscellaneous: whether to apply miscellaneous tags or not
		"""
		musics = self.read_music_info()

		if permissions is None:
			permissions = {}

		permission_remove_deleted = permissions.pop('remove_deleted', None)
		permission_remove_not_found = permissions.pop('remove_not_found', None)
		permission_remove_rename_error = permissions.pop('remove_rename_error', None)
		permission_remove_edit_error = permissions.pop('remove_edit_error', None)

		# detect and remove deleted musics
		addrs = self.get_music_addrs(from_cache=False)
		for f in addrs[~addrs.isin(musics['file'])]:
			permission_remove_deleted = self._remove_file_with_permission(f, permission_remove_deleted)

		musics = musics.to_dict('records')
		to_pop = []
		try:
			for i, music in enumerate(musics):
				f = Path(music['file'])

				if not os.path.exists(f):
					print(f'\nFileNotFound: {f} remove it from {self.music_info_file}?', end=' - ')
					permission_remove_not_found = self._remove_file_with_permission(f, permission_remove_not_found)
					if permission_remove_not_found.startswith('y'):
						to_pop.append(i)
					# print()
					continue

				if allow_miscellaneous:
					# add miscellaneous tags if exists
					music.update(json.loads(music['miscellaneous']))

				new_file_name = f
				if music['title'] and music['artist']:
					new_file_name = self._gen_new_file_name(f, f"{music['title']}")
					if new_file_name != f and os.path.exists(new_file_name):
						new_file_name = self._gen_new_file_name(f, f"{music['artist']}-{music['title']}")
						if new_file_name != f and os.path.exists(new_file_name):
							print(f'\nrenamed File Already exists so removing current file', end=' - ')
							permission_remove_rename_error = self._remove_file_with_permission(
								f, permission_remove_rename_error)
							if permission_remove_rename_error.startswith('y'):
								to_pop.append(i)
							# print()
							continue

				if new_file_name != f:
					try:
						f.rename(new_file_name)
						f = Path(new_file_name)
						music['file'] = str(f)
					except Exception as e:
						print(f'[RENAME ERROR] `{f}` -> `{new_file_name}` {e}')

				music_file_obj = mutagen.File(f, easy=True)
				new_tags = {
					k: [v] for k, v in music.items() if
					k not in (['file', 'miscellaneous'] + self.information_columns) and v
				}
				if music_file_obj == new_tags:
					continue

				# remove all tags from music
				music_file_obj.clear()

				# add our tags
				music_file_obj.update(new_tags)

				# save music with new tags
				try:
					music_file_obj.save()
				except mutagen.MutagenError as e:
					if e.args[0].__class__ != PermissionError:
						raise
					print(f'\ncant edit file', end=' - ')
					permission_remove_edit_error = self._remove_file_with_permission(f, permission_remove_edit_error)
					if permission_remove_edit_error.startswith('y'):
						to_pop.append(i)
		# print()
		except Exception as e:
			print(f'Unexpected error {e}')
			try:
				# noinspection PyUnboundLocalVariable
				print(f)
			except:
				pass

		for _id in to_pop:
			musics.pop(_id)

		print(f'\nupdating `{self.music_info_file}` ...')
		musics = pd.DataFrame.from_records(musics)
		musics.index.name = 'id'
		musics = self._do_highlight(musics)
		warnings.filterwarnings("ignore")
		musics.to_excel(self.music_info_file, engine='xlsxwriter', verbose=False, encoding='utf-8', freeze_panes=(1, 1))


if __name__ == '__main__':
	if len(sys.argv) >= 2:
		organizer = Organizer(sys.argv[1])
		organizer.generate_music_info()
		organizer.apply_tags()
