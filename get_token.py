import time

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome, ChromeOptions, Keys
from selenium.webdriver.chrome.service import Service

user_token = None

# Параметры приложения VK
CLIENT_ID = "52935184"
REDIRECT_URI = "https://oauth.vk.com/blank.html"  # Сервер авторизации
SCOPE = "photos.get,users.search,wall,likes.add"


def get_token_with_selenium():
	global user_token

	chrome_path = ChromeDriverManager().install()
	service = Service(executable_path = chrome_path)
	options = ChromeOptions()
	browser = Chrome(service = service, options = options)

	try:
		# Формируем URL для OAuth-авторизации в VK
		auth_url = (
			f"https://oauth.vk.com/authorize?"
			f"client_id={CLIENT_ID}&"
			f"display=page&"
			f"redirect_uri={REDIRECT_URI}&"
			f"scope={SCOPE}&"
			f"response_type=token&"
			f"v=5.199"
		)

		browser.get(auth_url)


		# Ждем, пока URL не изменится на redirect_uri
		while not browser.current_url.startswith(REDIRECT_URI):
			time.sleep(1)

		if "#access_token=" in browser.current_url:
			token_part = browser.current_url.split("#access_token=")[1]
			user_token = token_part.split("&")[0]
			return user_token
		else:
			return None

	finally:
		browser.quit()