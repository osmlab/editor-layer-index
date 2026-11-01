"""Audit imagery URLs for redirects and HTTPS support."""

import re

import requests

switch = re.compile("{switch:([^,]*),[^}]*}")


def check_url(url: str, verbose: bool = False) -> None:
    if url.startswith(("IRS", "data", "SPOT", "bing")):
        return
    url = switch.sub("\\1", url)
    if not url.startswith("http"):
        print("Whoa, url is weird: " + url)
        return
    try:
        response = requests.get(url, timeout=5)
    except requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError:
        if verbose:
            print("Could not connect to " + url)
            print("--")
        return
    if response.history and response.url != "http://imagico.de/map/empty_tile.png":
        print("Request was redirected")
        for resp in response.history:
            print(resp.status_code, resp.url)
        print("Final destination:")
        print(response.status_code, response.url)
        print("--")
    if url.startswith("http://"):
        urls = url.replace("http://", "https://", 1)
        try:
            response2 = requests.get(urls, timeout=5)
            if response.text == response2.text:
                print(f"It looks like {url} can be converted to https")
                print("--")
        except requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError:
            pass
