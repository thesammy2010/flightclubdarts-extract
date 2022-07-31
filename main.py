import base64
import json
import os
import pathlib
import subprocess
import sys
import zipfile
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Set
from urllib.parse import SplitResult, urlsplit, urlunsplit

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# from fake_useragent import UserAgent
# docker?


EVENT_NAMES: Set[str] = {
    "Network.requestWillBeSent",
    "Network.requestWillBeSentExtraInfo",
    "Network.responseReceived",
    "Network.responseReceivedExtraInfo",
}


def get_logs(url: str) -> List[Dict[str, Any]]:

    options: Options = Options()
    options.headless = True
    browser: webdriver.Chrome = webdriver.Chrome(
        desired_capabilities={
            **DesiredCapabilities.CHROME,
            "goog:loggingPrefs": {"browser": "ALL", "performance": "ALL"},
        },
        options=options,
        service=Service(
            executable_path="/Users/leoparkes-neptune/chromedriver",
        ),
    )
    browser.get(url)
    browser.implicitly_wait(30)
    logs: List[Dict[str, Any]] = [json.loads(log.get("message"))["message"] for log in browser.get_log("performance")]
    browser.quit()

    return list(filter(lambda log: log.get("method") in EVENT_NAMES, logs))


def log_filter(parsed_url: SplitResult, log: Dict[str, Any]) -> bool:
    match log:
        case {
            "method": "Network.requestWillBeSent",
            "params": {
                "documentURL": document_url,
                "request": {
                    "method": "GET",
                    "mixedContentType": "none",
                    "referrerPolicy": "strict-origin-when-cross-origin",
                    "url": api_url,
                },
            },
        } if document_url == urlunsplit(
            parsed_url
        ) and api_url == "https://flightclubapi.azure-api.net/uk/v2/StoryData{}".format(
            parsed_url.path
        ):
            return True
        case _:
            return False


def get_data_from_api_list(log) -> Dict[str, Any]:
    request: Dict[str, str | Dict[str, str]] = log["params"]["request"]
    for key in ["initialPriority", "isSameSite", "mixedContentType", "referrerPolicy"]:
        request.pop(key)
    req: requests.Response = requests.request(**request)
    if not req.ok:
        print("Request to Flight Club API unsuccessful")
        print(req.json())
        sys.exit(1)

    return req.json()


def download_profiles(payload: Dict[str, Any], directory: str) -> None:
    players: List[Dict[str, Any]] = payload["Players"]
    os.mkdir(f"{directory}/players")
    for player in players:
        with open(file=f"{directory}/players/{player['name'].capitalize()}.jpg", mode="wb") as file:
            file.write(base64.decodebytes(player["photo"].encode()))
            print(f"Player: {player['name']} written to {file.name}")
    return


def download_photos(payload: Dict[str, Any], directory: str) -> None:
    os.mkdir(f"{directory}/groupphotos")
    for photo in filter(
        lambda asset: True if asset.get("asset_uri", "").startswith("_") else False, payload["Newsfeed"]
    ):
        req: requests.Response = requests.request(
            method="GET", url=f"https://flightclubdarts.blob.core.windows.net/groupphotos/{photo['asset_uri']}"
        )
        if not req.ok:
            print(f"failed to download photo {photo['asset_uri']}. skipping")
        with open(file=f"{directory}/groupphotos/{photo['asset_uri']}", mode="wb") as file:
            file.write(req.content)
            print(f"Group Photo: {photo['asset_uri']} written to file {file.name}")
    return


def download_videos(payload: Dict[str, Any], directory: str) -> None:
    os.mkdir(f"{directory}/videos")
    for video in filter(lambda asset: True if asset.get("video_url") else False, payload["Newsfeed"]):
        url: str = video["video_url"] + "(format=m3u8-aapl)"
        filename: str = f"{directory}/videos/{video['asset_uri']}.mp4"
        p: subprocess.CompletedProcess = subprocess.run(
            ["ffmpeg", "-i", url, filename, "-loglevel", "error"]
        )
        if p.returncode:
            print(f"Error running {p.args}")
            sys.exit(1)
        print(f"Video: {video['asset_uri']} written to file {filename}")

    return


def zip_files(source_directory: str, destination_file: str) -> None:
    with zipfile.ZipFile(file=f"{destination_file}.zip", mode="w", compresslevel=zipfile.ZIP_DEFLATED) as zipobj:
        for root, _, files in os.walk(source_directory):
            for file in files:
                filename: pathlib.Path = pathlib.Path(root).joinpath(file)
                arcname: pathlib.Path = filename.relative_to(source_directory)
                zipobj.write(filename=filename, arcname=arcname)
                print(f"File {filename} written to {zipobj.filename}")
    return


def main(url, file) -> None:

    # parse url
    parsed_url: SplitResult = urlsplit(url)

    if parsed_url.netloc != "stories.flightclubdarts.com":
        print("Must use `stories.flightclubdarts.com`")
        sys.exit(1)

    # get logs
    logs: List[Dict[str, Any]] = get_logs(url)
    print("{} logs found".format(len(logs)))

    # v1: get API call
    api_call = next(filter(lambda log: log_filter(parsed_url=parsed_url, log=log), logs), None)

    if api_call is None:
        print("No valid logs have come through, something has gone wrong")
        sys.exit(1)

    payload: Dict[str, Any] = get_data_from_api_list(api_call)
    with TemporaryDirectory() as tempdir:
        print(f"Temporary Directory: {tempdir}")
        download_profiles(payload=payload, directory=tempdir)
        download_photos(payload=payload, directory=tempdir)
        download_videos(payload=payload, directory=tempdir)
        zip_files(source_directory=tempdir, destination_file=file)

    return


if __name__ == "__main__":

    url_input: str = input("Flight Club Stories URL: ").strip()
    if not url_input:
        print("A valid URL must be specified")
        sys.exit(1)

    filename_input: str = input("Destination file: ").strip()
    if not filename_input:
        print("A valid destination filename must be specified")
        sys.exit(1)

    main(url=url_input, file=filename_input)
