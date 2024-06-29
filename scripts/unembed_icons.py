import re
from base64 import b64decode
import mimetypes
from pathlib import Path
import json
import logging
import tkinter.filedialog as fd

host = "https://osmlab.github.io/editor-layer-index/"

root_path = None

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
		logging.debug("data is text")
		return data_text.splitlines()
	else:
		logging.debug("data is binary")
		return None

def findFile(parent_path, mime, data): # returns: Path or None upon none found
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
		glob = "*[{}]".format("][".join(extensions)) # IMPROVEMENT: separate out the dot, instead of having all.
	else:
		logging.warning("invalid mime-type")
		return None # TODO: remove when `TODO: force only match files (not including directories)' is done
		glob = "*"
	
	logging.info("walking `{}' with glob: `{}'".format(parent_path, glob))
	check_count = 0
	for file_path in parent_path.rglob(glob): # TODO: ignore hidden files (especially .git) and only match files (i.e. not including directories)
		check_count += 1
		logging.debug("checking against file: `{}'".format(file_path))
		file = None
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
			if file == None:
				file_handle = open(file_path, "rb")
				file = file_handle.read()
				file_handle.close()
			file_lines = decodeLines(file)
			if file_lines == data_lines:
				logging.info("found text match: `{}'".format(file_path))
				return file_path
				break
	logging.warning("no match found in {} checked files".format(check_count))
	return None

def saveAs(directory, mime):
	exts = mimetypes.guess_all_extensions(mime, strict=True)
	exts_mod = []
	for ext in exts:
		exts_mod.append((ext[1:].upper(), ext))
	logging.info("waiting for Save As dialog")
	output_path = Path(fd.asksaveasfilename(filetypes=exts_mod, defaultextension=exts_mod[0], initialdir=directory))
	# TODO: backup input for terminal interfaces (dumb input(); check if parent is at least valid; relative to repo root_path; list recommended extensions; make sure the import failure is dealt with)
	
	return output_path

def save(path, binary, data):
	# TODO: confirm with user first, and show if it will be replacing something, and of course honor command line arguments
	mode = None # TODO: maybe just require input to be binary, actually?
	if binary == True:
		mode = "wb"
		mode_str = "bytes"
	elif binary == False:
		mode = "w"
		mode_str = "chars"
	file_handle = open(path, mode)
	logging.info("saving {} {} into the file `{}'".format(len(data), mode_str, path))
	file = file_handle.write(data)
	file_handle.close()

def single(geojson_path):
	geojson_handle = open(geojson_path)
	geojson = json.load(geojson_handle)
	geojson_handle.close()
	
	url = geojson["properties"]["icon"]
	
	url_mime, url_data = getData(url) # TODO: gracefully quit if it returns None
	
	icon_path = findFile(root_path, url_mime, url_data)
	if icon_path == None:
		icon_path = saveAs(geojson_path.parent, url_mime) # TODO: handle cancel
		save(icon_path, True, url_data)
	new_url = host + icon_path.relative_to(root_path).as_posix() # TODO: make sure it is underneath
	logging.info("new URL: `{}'".format(new_url))
	# TODO: handle replacing url in the GeoJSON: do a search and replace of the icon url as to preserve formatting of file (check it can find it at the beginning, to present a warning to the user (that it wont be able to replace)). (yes I know this method could cause issues normally, because escaped chars, but data URLs shouldn't have that)

def main():
	logging.getLogger().setLevel(logging.DEBUG)
	
	geojson_path = fd.askopenfilename(filetypes=[("GeoJSON", ".geojson")], initialdir=root_path / "sources")
	single(Path(geojson_path))
	
	# TODO: handle more than one GeoJSON (should take in a folder too (rglob that), and multiple files, or a mix of both)
	# OPTIMIZE: use a cache of hashes if doing multiple files
	# TODO: posix interface with these options: --confirm-all --no-confirm-overwrite --only-existing + log level stuff
	# TODO: maybe duplicate the old version's interface as much as possible?

if __name__ == "__main__":
	root_path = Path(__file__).parents[1] # get repository's root_path
	main()