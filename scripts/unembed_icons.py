import re
from base64 import b64decode
import mimetypes 

def getData(url):
	data_re = re.search(r"^data:(.*);base64,(.*)$", url)
	if data_re:
		mime = data_re.group(1)
		data = b64decode(data_re.group(2))
		return [mime, data]
	elif url.startswith("data:"):
		print("unsupported data URL variation")
	else:
		print("URL isn't a data URL")
	return None

#def main():

if __name__ == "__main__":
	main()