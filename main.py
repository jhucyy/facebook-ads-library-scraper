import builtins
import json
import logging
import os
import sys
import warnings
from datetime import datetime
from functools import partial
from pprint import pprint
from urllib.parse import urlencode, urlunparse

import json_flattening
import pandas as pd
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from seleniumwire.utils import decode

import time
import base64


# import seleniumwire.undetected_chromedriver as webdriver
from seleniumwire import webdriver

SCROLL_TIMES = sys.maxsize
ZOOM_LEVEL = 100
PROXY = True
ZERO_WIDTH = "​"
HEADLESS = False
KEEP_OPEN = True
DISABLE_IMAGES = False
csv_out_path = "./facebook_ads_" + time.strftime("%Y%m%d-%H%M%S") +  ".csv"


# Using this because the logger lib acts extremely anoyingly
def print(*arg, **kwarg):
	timestamp = datetime.now().strftime("%H:%M:%S")
	builtins.print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", *arg, **kwarg)


options = {
	"verify_ssl": False,
	'ignore_http_methods': ["GET", "DELETE", "OPTIONS", "HEAD"],
	'connection_keep_alive': True,
	'disable_encoding': True,
	'mitm_http2': False,
	"request_storage": "memory",
	"request_storage_max_size": 10,
	"exclude_hosts": [
		"static.xx.fbcdn.net"
	],
	"proxy": ({
		"http": "http://localhost:8080",
		"https": "https://localhost:8080",
	} if PROXY else {}),
}


# warnings.filterwarnings("ignore", message=".*A value is trying to be set on a copy of a slice from a DataFrame.*")
pd.options.mode.chained_assignment = None
def build_ads_library_url(
		q=ZERO_WIDTH,
		active_status="all",
		ad_type="all",
		country="ALL",
		sort_data_direction="desc",
		sort_data_mode="relevancy_monthly_grouped",
		search_type="keyword_unordered",
		media_type="all"):
	# Define the query parameters as a dictionary
	query_params = {
		"active_status": active_status,
		"ad_type": ad_type,
		"country": country,
		"sort_data[direction]": sort_data_direction,
		"sort_data[mode]": sort_data_mode,
		"search_type": search_type,
		"media_type": media_type,
		"q": q,

	}

	# Encode the query parameters
	encoded_params = urlencode(query_params)

	# Build the complete URL
	url = urlunparse(("https", "www.facebook.com", "/ads/library/", "", encoded_params, ""))
	return url


def find_element_wait(driver, locator, by=By.ID, waiting_time=3,
					  *findElementArgs, **findElementKwargs):
	webdriver_wait = WebDriverWait(driver, waiting_time)
	locator_tuple = (by, locator)
	located = EC.visibility_of_element_located(locator_tuple,
								*findElementArgs, **findElementKwargs)
	element = webdriver_wait.until(located)
	return element


def accept_cookies():
	cookie_button = driver.find_element_wait(
		'[data-testid="cookie-policy-manage-dialog-accept-button"]',
		By.CSS_SELECTOR, 60 * 3)
	cookie_button.click()


def scroll_down(driver):
	driver \
		.find_element_wait("body", By.CSS_SELECTOR, 60*10) \
		.send_keys(Keys.CONTROL + Keys.END)


def interceptor(request, response):
	global df, csv_out_path

	# replace parameter with 30
	params = request.params
	params["count"] = 30
	request.params = params

	# Prep body
	body = decode(response.body, response.headers.get("Content-Encoding", "identity"))
	body = body.decode("utf-8")
	body = body.replace("for (;;);", "")

	# Json to dict
	j = json.loads(body)
	payload = j["payload"]
	results = payload["results"]

	# Loop through results
	for item in results:
		for sub_item in item:

			# Create new dict
			result = {
				"requestDate":request.date,
				"responseDate":response.date,
				"requestUrl":request.url,
				"requestMethod":request.method,
				**sub_item
			}

			flattened_result = json_flattening.json_flatten(result)



			print(f"{result['adArchiveID']=}, {result['requestDate']=} | ", flattened_result.to_json())

			# Save dict to csv
			# result_df = pd.DataFrame([flattened_result])

			result_df = flattened_result

			# df = df.append(result, ignore_index=True)
			df = pd.concat([df, result_df], ignore_index=True)
			df.to_csv(csv_out_path, mode="a", header=not os.path.exists(csv_out_path))
			print(f"Result written to csv file, {len(df)=}")


def get_ad_library_items():

	global df, driver
	df = pd.DataFrame()


	driver.scopes = [
		"https://www.facebook.com/ads/library/async/search_ads/.*"
	]
	print("Added driver scope")

	ads_library_url = build_ads_library_url(country="NL")
	print("Built url")

	driver.get(ads_library_url)
	print("Requested url")
	time.sleep(3)

	accept_cookies()
	print("Accepted cookies")

	driver.execute_script(f"document.body.style.zoom='{ZOOM_LEVEL}%'")
	print("Zoomed out")

	driver.response_interceptor = interceptor
	print("Added interceptor")

	# while 1:
	for _ in range(SCROLL_TIMES):
		scroll_down(driver)
		time.sleep(1)




if __name__ == "__main__":
	chrome_options = webdriver.ChromeOptions()
	chrome_options.add_argument("--no-sandbox")
	if KEEP_OPEN: chrome_options.add_experimental_option("detach", True)
	if DISABLE_IMAGES:chrome_options.add_argument("--blink-settings=imagesEnabled=false")
	if HEADLESS:chrome_options.add_argument("--headless")
	# Easiest way to override setting the headless chrome header
	chrome_options.add_argument(
		'--user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"')

	driver = webdriver.Chrome(
		service=ChromeService(ChromeDriverManager().install()),
		options=chrome_options,
		seleniumwire_options=options
	)
	print("Instantiated browser")

	driver.find_element_wait = partial(find_element_wait, driver)
	print("Added method to driver")

	start = time.time()
	try:
		print("Started scraping")
		get_ad_library_items()
	finally:
		end = time.time()
		hours, rem = divmod(end - start, 3600)
		minutes, seconds = divmod(rem, 60)

		print("Reached final statement, took: {:0>2}h:{:0>2}m:{:05.2f}s".format(int(hours), int(minutes), seconds))
		driver.get_screenshot_as_file("./final_screenshot_" + time.strftime("%Y%m%d-%H%M%S") + ".png" )

		input("Press any key to close browser...")

		driver.quit()
