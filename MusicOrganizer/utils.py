import re

import pandas as pd

audio_extensions = (
	"3gp", "aa", "aac", "aax", "act", "aiff", "alac", "amr", "ape", "au", "awb", "dct", "dss", "dvf", "8svx", "flac",
	"gsm", "iklax", "ivs", "m4a", "m4b", "m4p", "mmf", "mp3", "mpc", "msv", "nmf", "ogg", "oga", "cda", "mogg", "opus",
	"ra", "rm", "raw", "rf64", "sln", "tta", "voc", "vox", "wav", "wma", "wv", "webm",
)


def remove_websites_and_tags(data: pd.Series) -> pd.Series:
	"""
	remove any kind of website link from data.str

	Example:
		"Pop [test.com] Rock" -> "Pop Rock"
	"""
	return data.str.replace(
		r"""(((telegram[\s]?)?(channel)?)|((کانال[\s]?)?(تلگرام)))?[\-@:%_\+.~#?&//=\s\(\)\[\]\*^$!{}<>\"\']*([\w@\-%\+.~#?&//=]{1,256}\.(cc|me|ir|in|net|info|org|biz|com|us|pro|ws)[\w@\-:%\+.~#?&//=]*|@[\w@\-:%\+.~#?&//=]{1,256})[-@:%_\+.~#?&//=\s\(\)\[\]\*^$!{}<>\"\']*""",
		' ',
		regex=True,
		flags=re.IGNORECASE
	).str.strip().replace({'': None})


def mask_containing_regex(data: pd.Series, regex: str) -> pd.Series:
	"""
	if data.str contains regex mark it as True in returning mask
	"""
	return data.str.contains(regex, regex=True, flags=re.IGNORECASE).replace({None: False})
