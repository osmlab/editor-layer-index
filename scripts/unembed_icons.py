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

def decodeLines(data):
	data_text = None
	try:
		data_text = data.decode()
	except:
		pass
	if isinstance(data_text, str):
		logging.info("data is text")
		return data_text.splitlines()
	else:
		logging.info("data is binary")
		return None

def findFile(parent_path, data, mime): # returns: Path or None upon none found
	# NOTE: all the extra stuff with text data is to compensate for git changing newlines
	
	data_size = len(data)
	extensions = mimetypes.guess_all_extensions(mime, strict=False)
	
	data_istext = False
	data_lines = decodeLines(data)
	if data_lines != None:
		data_istext = True
	
	glob = None
	if len(extensions) == 1:
		glob = "*{}".format(extensions[0])
	elif len(extensions) > 1:
		glob = "*[{}]".format("][".join(extensions))
	else:
		logging.warning("invalid mime-type")
		glob = "*"
	
	logging.info("walking `{}' with glob: `{}'".format(parent_path, glob))
	
	for file_path in parent_path.rglob(glob): # OPTIMIZE: ignore hidden files (especially .git) # TODO: force only match files (not including directories)
		logging.debug("checking against file: `{}'".format(file_path))
		file_size = file_path.stat().st_size
		if file_size == data_size:
			# OPTIMIZE: could be optimized by using buffering
			file_handle = open(file_path, "rb")
			file = file_handle.read()
			file_handle.close()
			if file == data:
				logging.info("found binary match: `{}'".format(file_path))
				return file_path
				break
		if(data_istext):
			# TODO: deduplicate reading file
			file_handle = open(file_path, "rb")
			file = file_handle.read()
			file_handle.close()
			file_lines = decodeLines(file)
			if file_lines == data_lines:
				logging.info("found text match: `{}'".format(file_path))
				return file_path
				break
	return None

def main():
	pass # TODO

if __name__ == "__main__":
	root = Path(__file__).parents[1] # get repository's root
	main()