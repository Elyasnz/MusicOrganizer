from MusicOrganizer.Organizer import Organizer

if __name__ == '__main__':
	organizer = Organizer('C:\\Music')
	organizer.generate_music_info()
	# organizer.apply_tags({'remove_edit_error': 'na'})
