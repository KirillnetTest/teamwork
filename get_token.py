import time
import pyautogui
import logging
import os

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service

logging.basicConfig(level = logging.INFO, filename = "bot.log", encoding = "utf-8",
					format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Параметры приложения VK
CLIENT_ID = os.getenv("CLIENT_ID")
REDIRECT_URI = "https://oauth.vk.com/blank.html"  # Сервер авторизации
SCOPE = "photos,users,database,wall,likes"

def get_token_with_selenium():
	"""
	Авторизация пользователя во Вконтаке и получение Токена пользователя
	:return: Токен пользователя Вконтакте
	"""

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
		logger.info(f'Строка URL запроса: {auth_url} ')

		# Устанавливаем окно в центр экрана
		screen_width, screen_height = pyautogui.size()
		window_width = 900
		window_height = 650
		position_x = (screen_width - window_width) // 2
		position_y = (screen_height - window_height) // 2

		browser.set_window_rect(x = position_x, y = position_y, width = window_width, height = window_height)

		browser.get(auth_url)

		# Ждем, пока URL не изменится на redirect_uri
		while not browser.current_url.startswith(REDIRECT_URI):
			time.sleep(1)

		if "#access_token=" in browser.current_url:
			logger.info(f'Строка URL содержащая Токен: {browser.current_url}')
			token_part = browser.current_url.split("#access_token=")[1]
			user_token = token_part.split("&")[0]
			logger.info(f'Получен Токен: {user_token}')
			return user_token
		else:
			return None

	finally:
		browser.quit()