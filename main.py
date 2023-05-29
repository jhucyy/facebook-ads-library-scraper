import json
import os
from functools import partial
from pprint import pprint
from urllib.parse import urlencode, urlunparse

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

proxy = True
ZERO_WIDTH = "​"

options = {
	"verify_ssl": False,
	'ignore_http_methods': ["GET", "DELETE", "OPTIONS", "HEAD"],
	'connection_keep_alive': True,
	'disable_encoding': True,
	'mitm_http2': False,
	"request_storage": "memory",
	"request_storage_max_size": 10,
	"proxy": ({
		"http": "http://localhost:8080",
		"https": "https://localhost:8080",
	} if proxy else {}),
}


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
		.find_element_wait("body", By.CSS_SELECTOR, 60) \
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
			print(f"{result['adArchiveID']=}, {result['requestDate']=} ", result)

			# Save dict to csv
			# df = df.append(result, ignore_index=True)
			df = pd.concat([df, result], ignore_index=True)
			df.to_csv(csv_out_path, mode="a", header=not os.path.exists(csv_out_path))
			print(f"Result written to csv file, {len(df)}")


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

	driver.execute_script("document.body.style.zoom='10%'")
	print("Zoomed out")

	driver.response_interceptor = interceptor
	print("Added interceptor")

	while 1:
		scroll_down(driver)
		time.sleep(1)




if __name__ == "__main__":

	csv_out_path = "./facebook_ads2.csv"

	chrome_options = webdriver.ChromeOptions()
	chrome_options.add_argument("--blink-settings=imagesEnabled=false")
	chrome_options.add_argument("--no-sandbox")
	chrome_options.add_argument("--headless")

	driver = webdriver.Chrome(
		service=ChromeService(ChromeDriverManager().install()),
		options=chrome_options,
		seleniumwire_options=options
	)
	print("Instantiated browser")

	driver.find_element_wait = partial(find_element_wait, driver)
	print("Added method to driver")

	try:
		get_ad_library_items()
	finally:
		input("Press any key to close driver")
		driver.quit()
