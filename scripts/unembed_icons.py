import re
from base64 import b64decode
import mimetypes
from pathlib import Path
import json
import logging

root = None

def getData(url): # returns: [mime, data] or None upon error
	data_re = re.search(r"^data:(.*);base64,(.*)$", url)
	if data_re:
		mime = data_re.group(1)
		data = b64decode(data_re.group(2))
		return [mime, data]
	elif url.startswith("data:"):
		logging.error("unsupported data-URL variation")
	else:
		logging.error("URL isn't a data-URL")
	return None

def findFile(parent_path, data, mime): # returns: Path or None upon none found
	# NOTE: all the extra stuff with text data is to compensate for git changing newlines
	
	found_path = None
	
	data_size = len(data)
	extensions = mimetypes.guess_all_extensions(mime, strict=False)
	
	data_istext = False
	data_text = None
	data_lines = None
	try:
		data_text = data.decode()
	except:
		pass
	if isinstance(data_text, str):
		logging.info("data is text")
		data_istext = True
		data_lines = data_text.splitlines()
	else:
		logging.info("data is binary")
	
	glob = None
	if len(extensions) == 1:
		glob = "*{}".format(extensions[0])
	elif len(extensions) > 1:
		glob = "*[{}]".format("][".join(extensions))
	else:
		logging.warning("invalid mime-type")
		glob = "*"
	
	logging.info("walking `{}' with glob: `{}'".format(parent_path, glob))
	
	for file_path in parent_path.rglob(glob): # OPTIMIZE: ignore hidden files (especially .git)
		logging.debug("checking against file: `{}'".format(file_path))
		if(data_istext == False):
			file_size = file_path.stat().st_size
			if file_size == data_size:
				# OPTIMIZE: could be optimized by using buffering
				file_handle = open(file_path, "rb")
				file = file_handle.read()
				file_handle.close()
				if file == data:
					logging.info("found match: `{}'".format(file_path))
					found_path = file_path
					break
		# TODO: handle text data
	
	if found_path != None:
		return found_path
	else:
		return None

def main():
	pass # TODO

if __name__ == "__main__":
	root = Path(__file__).parents[1]
	main()