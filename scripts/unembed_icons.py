# NOTE: please do not import any modules outside of the standard library
import re
from base64 import b64decode
import mimetypes
from pathlib import Path
import json
import logging
import tkinter.filedialog as fd # TODO: handle if not present

host = "https://osmlab.github.io/editor-layer-index/" # TODO: ideally load this from a common config/etc file

root_path = None

def getData(url): # returns: [mime, data] or False upon error
	data_re = re.search(r"^data:(.*);base64,(.*)$", url)
	if data_re:
		mime = data_re.group(1)
		data = b64decode(data_re.group(2))
		return [mime, data]
	elif url.startswith("data:"):
		logging.error("unsupported data-URL variation")
	else:
		logging.error("URL isn't a data-URL")
	return False

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
		return False

def findFile(parent_path, mime, data): # returns: Path or False upon none found
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
		glob = "*[{}]".format("][".join(extensions)) # IMPROVEMENT: separate out the dot, instead of having it in every [].
	else:
		logging.warning("invalid mime-type")
		glob = "*"
	
	logging.info("walking `{}' with glob: `{}'".format(parent_path, glob))
	check_count = 0
	for file_path in parent_path.rglob(glob):
		if not file_path.is_file():
			logging.debug("`{}' is a directory, skipping..".format(file_path))
			continue
		if re.search(r"/\.", file_path.relative_to(parent_path).as_posix()):
			logging.debug("`{}' is hidden, skipping..".format(file_path))
			continue
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
	return False

def saveAs(directory, mime):
	exts = mimetypes.guess_all_extensions(mime, strict=True)
	logging.debug("opening Save As dialog in `{}', with the mime type `{}' which means the extensions: {}".format(directory, mime, exts)) 
	exts_mod = []
	for ext in exts:
		exts_mod.append((ext[1:].upper(), ext))
	logging.info("(waiting for user to finish Save As dialog)") # TODO: rewrite the english
	if len(exts_mod) > 0:
		output_path = fd.asksaveasfilename(filetypes=exts_mod, defaultextension=exts_mod[0], initialdir=directory)
	else:
		output_path = fd.asksaveasfilename(initialdir=directory)
	# TODO: backup input for terminal interfaces (dumb input(); check if parent is at least valid; relative to repo root_path; list recommended extensions; make sure the import failure is dealt with)
	
	if len(output_path) <= 0:
		return False
	return Path(output_path)

def confirm(string):
	# TODO: honor command line arguments
	answer = ""
	while answer not in ["y", "n"]: # TODO: inform user when invalid input
		answer = input("{} [Y/n]: ".format(string)).lower()
	return answer == "y"

def save(path, binary, data):
	if path == False:
		logging.warning("not saving, as False passed as path")
		return False
	if path.is_dir():
		logging.warning("not saving, as directory passed as path")
		return False
	if path.exists():
		if not confirm("would you like to overwrite `{}'?".format(path)):
			logging.warning("not saving, as file exists, and got confirmation that it is not okay to overwrite") # TODO: rewrite the english
			return False
		logging.warning("saving, file exists, but got confirmation that it is okay to overwrite") # TODO: rewrite the english
	
	# TODO: confirm with user first, and show if it will be replacing something, their relative sizes, plus of course honor command line arguments
	mode = None # TODO: maybe just require input to be binary, actually? or rewrite this functionality general, maybe not as a function at all?
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
	logging.info("operating on `{}'".format(geojson_path))
	
	# TODO: clean this up
	geojson_handle = open(geojson_path, "r", encoding='utf8')
	geojson = json.loads(geojson_handle.read())
	geojson_handle.close()
	
	url = geojson["properties"]["icon"]
	
	url_all = getData(url)
	
	if url_all == False:
		return False
	
	url_mime, url_data = url_all
	
	icon_path = findFile(root_path, url_mime, url_data)
	if icon_path == False:
		logging.info("will now be saving it, since couldn't find existing") # TODO: rewrite the english
		icon_path = saveAs(geojson_path.parent, url_mime)
		if save(icon_path, True, url_data) == False:
			logging.warning("canceled saving of icon, and subsequent modification of the GeoJSON, because no output path was selected, or writing was canceled")
			return False
	new_url = host + icon_path.relative_to(root_path).as_posix() # TODO: make sure it is underneath
	logging.info("new URL: `{}'".format(new_url))
	
	# NOTE: It is done this way (binary search and replace) to preserve the formatting of the file. Yes I know this could cause issues normally, because escaped characters and such, but data URLs shouldn't have that.
	# TODO: gracefully continue if there's an error. alternatively, perform a traditional json dumps (with an argument to disable it).
	geojson_binary_handle = open(geojson_path, "rb")
	geojson_binary = geojson_binary_handle.read()
	geojson_binary_new = geojson_binary.replace(bytes(url, encoding="utf8"), bytes(new_url, encoding="utf8")) # IMPROVEMENT: utf8 should be safe, though really you would want it following the input GeoJSON's detected encoding (I now force utf8, so this is invalid).
	geojson_binary_handle.close()
	save(geojson_path, True, geojson_binary_new) # TODO: maybe return result of this

def main():
	logging.getLogger().setLevel(logging.DEBUG) # TODO: add color
	
	geojson_path = fd.askopenfilename(filetypes=[("GeoJSON", ".geojson")], initialdir=root_path / "sources")
	
	if len(geojson_path) <= 0:
		logging.info("exited because nothing selected for input")
		return False
	
	single(Path(geojson_path))
	
	# TODO: handle more than one GeoJSON (should take in a folder too (rglob that), and multiple files, or a mix of both)
	# OPTIMIZE: use a cache of hashes if doing multiple files
	# TODO: posix interface with these options: --confirm-all --no-confirm-overwrite --only-existing --no-write (for testing) + log-level stuff; specify input file(s) (and possible output if inputting only one geojson) + force cli file selectors + force save (i.e. skip checking for existing icon files) + override root_path
	# TODO: maybe duplicate the old version's interface as much as possible?
	# TODO: write a help text on how to use it and how it operates

if __name__ == "__main__":
	root_path = Path(__file__).parents[1] # get repository's root_path
	main()

# NOTE: one of the goals is for it to also be usable as a module
# TODO: be clear about what file(s) you're now supposed to be selecting
# TODO: use exceptions instead of bools
