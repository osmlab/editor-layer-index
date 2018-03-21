#!/usr/bin/env python

import json
import requests
import argparse
import re

switch = re.compile('{switch:([^,]*),[^}]*}')
verbose = False

def check_url(url):
    if url.startswith(("IRS", "data", "SPOT", "bing")):
        # not for me
        return True

    url = switch.sub(r'\1', url)
    try:
        response = requests.get(url, timeout=5)
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        if verbose:
            print("Could not connect to " + url)
            print("--")
        return True
    if response.history and response.url != "http://imagico.de/map/empty_tile.png":
        print("Request was redirected")
        for resp in response.history:
            print(resp.status_code, resp.url)
        print("Final destination:")
        print(response.status_code, response.url)
        print("--")
    if url.startswith("http://"):
        urls = url.replace("http://","https://",1)
        try:
            response2 = requests.get(urls, timeout=5)
            if response.text == response2.text:
                print("It looks like {} can be converted to https".format( url.encode('ascii')))
                print("--")
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            pass

# check_url("http://github.com")

parser = argparse.ArgumentParser(description='Check all urls in geojson for redirects and possible https conversions')
parser.add_argument('files', metavar='F', nargs='+', help='file(s) to process')
parser.add_argument('-v', dest='verbose', action='store_true', help="List servers that can't be reached")


args = parser.parse_args()

features = []
for file in args.files:
    with open(file, 'r') as f:
        data = json.load(f)
        for feature in data["features"]:
            try:
                check_url(feature["properties"]["url"])
                check_url(feature["properties"]["icon"])
                check_url(feature["properties"]["license_url"])
                check_url(feature["properties"]["attribution"]["url"])
            except KeyError:
                continue
