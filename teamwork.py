import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import time
import logging
import os
import json
from dotenv import load_dotenv
from vk_integration import VKInteraction
from database import DataBase
from get_token import get_token_with_selenium
from datetime import datetime

# Настройка логирования для отладки и мониторинга
logging.basicConfig(level = logging.INFO, filename = "bot.log", encoding = "utf-8",
					format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение токенов VK из переменных окружения
TOKEN = os.getenv("VK_TOKEN")
USER_TOKEN = os.getenv("USER_TOKEN")

if not TOKEN:
	raise ValueError("VK_TOKEN не найден в переменных окружения")

# Инициализация VK API и longpoll
vk = vk_api.VkApi(token = TOKEN, api_version = "5.199")
longpoll = VkLongPoll(vk)
user = None
db = DataBase()
user_state = {}


def create_main_keyboard():
	"""Создаёт основную клавиатуру с кнопками для поиска людей и просмотра избранных.

	Returns:
		str: JSON-представление клавиатуры VK.
	"""
	keyboard = VkKeyboard(one_time = False)
	keyboard.add_button("Найти человека", color = VkKeyboardColor.POSITIVE, payload = {"command":"set_search_params"})
	keyboard.add_button("Список избранных", color = VkKeyboardColor.SECONDARY, payload = {"command":"list_favorites"})
	return keyboard.get_keyboard()


def create_search_keyboard():
	"""Создаёт клавиатуру для взаимодействия с результатами поиска, включая избранное, чёрный список и навигацию.

	Returns:
		str: JSON-представление клавиатуры VK.
	"""
	keyboard = VkKeyboard(one_time = False)
	keyboard.add_button("Добавить в избранное", color = VkKeyboardColor.PRIMARY, payload = {"command":"add_favorite"})
	keyboard.add_button("Добавить в черный список", color = VkKeyboardColor.NEGATIVE,
						payload = {"command":"add_blacklist"})
	keyboard.add_line()
	keyboard.add_button("Следующий", color = VkKeyboardColor.SECONDARY, payload = {"command":"next_person"})
	keyboard.add_button("Назад", color = VkKeyboardColor.SECONDARY, payload = {"command":"back"})
	return keyboard.get_keyboard()


def create_photo_like_keyboard(photo):
	"""Создаёт встроенную клавиатуру для лайка конкретного фото.

	Args:
		photo (str): Строка вложения фото в формате 'photo{owner_id}_{photo_id}'.

	Returns:
		str | None: JSON-представление клавиатуры VK или None, если формат фото неверный.
	"""
	if not photo:
		return None

	keyboard = VkKeyboard(inline = True)

	try:
		parts = photo.split('_')
		if len(parts) < 2 or not parts[0].startswith('photo'):
			logging.error(f"Неверный формат вложения фото: {photo}")
			return None

		owner_id = int(parts[0][5:])
		photo_id = int(parts[1])

		keyboard.add_button(
			"❤️ Лайк фото",
			color = VkKeyboardColor.POSITIVE,
			payload = {"command":"like_photo", "owner_id":owner_id, "photo_id":photo_id}
		)
		return keyboard.get_keyboard()

	except (ValueError, IndexError) as e:
		logging.error(f"Ошибка разбора вложения фото {photo}: {e}")
		return None


def create_cancel_keyboard():
	"""Создаёт клавиатуру с кнопкой отмены.

	Returns:
		str: JSON-представление клавиатуры VK.
	"""
	keyboard = VkKeyboard(one_time = True)
	keyboard.add_button("Отмена", color = VkKeyboardColor.NEGATIVE, payload = {"command":"cancel"})
	return keyboard.get_keyboard()


def create_city_selection_keyboard(cities):
	"""Создаёт клавиатуру для выбора города из списка результатов поиска.

	Args:
		cities (list): Список словарей городов, содержащих 'id' и 'title'.

	Returns:
		str: JSON-представление клавиатуры VK.
	"""
	keyboard = VkKeyboard(one_time = True)
	for i, city in enumerate(cities[:5]):
		keyboard.add_button(city["title"], color = VkKeyboardColor.PRIMARY,
							payload = {"command":"select_city", "city_id":city["id"]})
		if i < len(cities) - 1 and i < 4:
			keyboard.add_line()
	keyboard.add_line()
	keyboard.add_button("Отмена", color = VkKeyboardColor.NEGATIVE, payload = {"command":"cancel"})
	return keyboard.get_keyboard()


def write_msg(user_id, message = None, keyboard = None, attachment = None, retries = 3):
	"""Отправляет сообщение пользователю с логикой повторных попыток для обработки ограничений скорости.

	Args:
		user_id (int): ID пользователя VK для отправки сообщения.
		message (str, optional): Текст сообщения.
		keyboard (str, optional): JSON-представление клавиатуры VK.
		attachment (str, optional): Строка вложения (например, фото).
		retries (int): Количество попыток повторной отправки при сбое.
	"""
	for attempt in range(retries):
		try:
			vk.method("messages.send", {
				"user_id":user_id,
				"message":message,
				"random_id":random.randint(1, 2 ** 31),
				"keyboard":keyboard,
				"attachment":attachment
			})
			logging.info(f"Сообщение отправлено пользователю {user_id}: {message}")
			return
		except vk_api.exceptions.ApiError as e:
			if "too many requests" in str(e).lower():
				time.sleep(0.5 * (2 ** attempt))  # Экспоненциальная задержка
				continue
			logging.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
			vk.method("messages.send", {
				"user_id":user_id,
				"message":f"Ошибка: {str(e)}. Попробуйте позже.",
				"random_id":random.randint(1, 2 ** 31),
				"keyboard":keyboard,
				"attachment":attachment
			})
			return
	logging.error(f"Не удалось отправить сообщение пользователю {user_id} после {retries} попыток")


def calculate_age(bdate: str) -> int:
	"""Вычисляет возраст на основе строки даты рождения (ДД.ММ.ГГГГ или ДД.ММ).

	Args:
		bdate (str): Строка даты рождения.

	Returns:
		int: Вычисленный возраст или 0, если данные неверные или отсутствуют.
	"""
	if not bdate:
		return 0
	parts = bdate.split(".")
	if len(parts) < 3:
		return 0
	try:
		birth_year = int(parts[-1])
		current_year = datetime.now().year
		age = current_year - birth_year
		return age if 0 < age <= 100 else 0
	except ValueError:
		return 0


def handle_set_search_params(user_id: int) -> None:
	"""Инициирует процесс сбора параметров поиска для пользователя.

	Args:
		user_id (int): ID пользователя VK.
	"""
	user_state[user_id] = {
		"last_command":"set_search_params",
		"step":"age_from",
		"search_params":{}
	}
	write_msg(user_id, "Введите минимальный возраст (например, 18):", create_cancel_keyboard())


def handle_search_params_input(user_id, text):
	"""Обрабатывает ввод параметров поиска пользователем (возраст, пол, город).

	Args:
		user_id (int): ID пользователя VK.
		text (str): Введённый пользователем текст.

	Returns:
		bool: True, если ввод обработан, False в противном случае.
	"""
	state = user_state.get(user_id, {})
	if state.get("last_command") != "set_search_params":
		return False

	step = state.get("step")
	try:
		if step == "age_from":
			age_from = int(text)
			if 18 <= age_from <= 100:
				state["search_params"]["age_from"] = age_from
				state["step"] = "age_to"
				write_msg(user_id, "Введите максимальный возраст (например, 30):", create_cancel_keyboard())
			else:
				write_msg(user_id, "Возраст должен быть от 18 до 100 лет.", create_cancel_keyboard())
		elif step == "age_to":
			age_to = int(text)
			if state["search_params"]["age_from"] <= age_to <= 100:
				state["search_params"]["age_to"] = age_to
				state["step"] = "sex"
				write_msg(user_id, "Выберите пол (1 - женский, 2 - мужской):", create_cancel_keyboard())
			else:
				write_msg(user_id, f"Максимальный возраст должен быть от {state['search_params']['age_from']} до 100.",
						  create_cancel_keyboard())
		elif step == "sex":
			sex = int(text)
			if sex in [1, 2]:
				state["search_params"]["sex"] = sex
				state["step"] = "city"
				write_msg(user_id, "Введите название города (например, Москва):", create_cancel_keyboard())
			else:
				write_msg(user_id, "Введите 1 для женского пола или 2 для мужского.", create_cancel_keyboard())
		elif step == "city":
			state["search_params"]["city"] = text
			cities = user.get_cities(text)
			if not cities:
				write_msg(user_id, "Город не найден. Попробуйте снова:", create_cancel_keyboard())
			elif len(cities) == 1:
				state["search_params"]["city_id"] = cities[0]["id"]
				handle_find_person_with_params(user_id, state["search_params"])
			else:
				state["step"] = "select_city"
				state["cities"] = cities
				write_msg(user_id, "Найдено несколько городов. Выберите один:", create_city_selection_keyboard(cities))
		elif step == "select_city":
			write_msg(user_id, "Пожалуйста, выберите город из списка кнопок.",
					  create_city_selection_keyboard(state["cities"]))
	except ValueError:
		write_msg(user_id, "Пожалуйста, введите числовое значение для возраста или пола.", create_cancel_keyboard())
	return True


def handle_find_person_with_params(user_id, params):
	"""Выполняет поиск пользователей на основе предоставленных параметров и отображает результаты.

	Args:
		user_id (int): ID пользователя VK.
		params (dict): Параметры поиска (age_from, age_to, sex, city_id).
	"""
	try:
		blacklist = db.get_blacklist(user_id)
		users = user.user_search(
			age_from = params["age_from"],
			age_to = params["age_to"],
			sex = params["sex"],
			city = params["city_id"],
			count = int(os.getenv('USER_COUNT_LIMIT', 50))
		)

		# Фильтрация пользователей, исключая тех, кто в чёрном списке
		users = [u for u in users if u["id"] not in blacklist]

		# Вставка найденных пользователей в таблицу SearchUser
		for search_user in users:
			vk_id = search_user["id"]
			if not db.is_exist_searchuser(vk_id):
				city = search_user.get("city", {}).get("title", "Unknown")
				age = calculate_age(search_user.get("bdate", ""))
				db.searchuser_insert(
					vk_id = vk_id,
					first_name = search_user.get("first_name", "Unknown"),
					last_name = search_user.get("last_name", "Unknown"),
					city = city,
					age = age,
					sex = search_user.get("sex", 0)
				)
			else:
				continue

		# Сохранение результатов поиска в состоянии пользователя
		user_state[user_id] = {
			"search_results":[u["id"] for u in users],
			"current_index":0,
			"last_command":"find_person",
			"last_search_params":params
		}
		logging.info(
			f"Метод handle_find_person_with_params получил данные: age_from = {params['age_from']}, age_to = "
            f"{params['age_to']}, sex = {params['sex']}, city = {params['city_id']}")

		if users:
			current_user = users[0]
			profile_link = f"https://vk.com/id{current_user['id']}"
			user_info = f"{current_user['first_name']} {current_user['last_name']}\nПрофиль: {profile_link}"

			photos = user.get_user_photos(current_user["id"])
			logging.info(f"Получены photos = {photos}")
			keyboard = create_search_keyboard()

			if photos:
				# Отправка каждого фото с собственной кнопкой лайка
				for i, photo in enumerate(photos[:3]):
					logging.info(f"photo = {photo}")
					photo_keyboard = create_photo_like_keyboard(str(photo))
					write_msg(user_id, attachment = photo)
					if photo_keyboard:
						write_msg(user_id, f"Лайкнуть фото {i + 1}:", keyboard = photo_keyboard)

				# Отправка информации о пользователе и клавиатуры поиска
				write_msg(user_id, user_info, keyboard = keyboard)
			else:
				# Отправка информации о пользователе без фото
				write_msg(user_id, user_info, keyboard = keyboard)
		else:
			write_msg(user_id, "😔 Никто не найден. Попробуйте снова!", create_main_keyboard())
	except (ValueError, vk_api.exceptions.ApiError) as e:
		logging.error(f"Ошибка поиска для пользователя {user_id}: {e}")
		write_msg(user_id, f"Ошибка поиска: {str(e)}. Попробуйте снова.", create_main_keyboard())


def handle_find_person(user_id):
	"""Инициирует процесс поиска человека, начиная с ввода параметров.

	Args:
		user_id (int): ID пользователя VK.
	"""
	handle_set_search_params(user_id)


def handle_next_person(user_id):
	"""Отображает следующего пользователя в результатах поиска.

	Args:
		user_id (int): ID пользователя VK.
	"""
	logging.info(f"Обработка запроса 'следующий человек' для пользователя {user_id}")
	state = user_state.get(user_id, {})

	state["current_index"] = (state["current_index"] + 1) % len(state["search_results"])
	next_user_id = state["search_results"][state["current_index"]]

	user_info = user.get_user_info(next_user_id)
	photos = user.get_user_photos(next_user_id)

	message = f"{user_info['first_name']} {user_info['last_name']}\nПрофиль: https://vk.com/id{next_user_id}"
	keyboard = create_search_keyboard()

	if photos:
		# Отправка каждого фото с собственной кнопкой лайка
		for i, photo in enumerate(photos[:3]):
			photo_keyboard = create_photo_like_keyboard(str(photo))
			write_msg(user_id, attachment = photo)
			if photo_keyboard:
				write_msg(user_id, f"Лайкнуть фото {i + 1}:", keyboard = photo_keyboard)

		# Отправка информации о пользователе и клавиатуры поиска
		write_msg(user_id, message, keyboard = keyboard)


def handle_add_favorite(user_id):
	"""Добавляет текущего просматриваемого пользователя в список избранных.

	Args:
		user_id (int): ID пользователя VK.
	"""
	state = user_state.get(user_id, {})
	if not state or state["last_command"] != "find_person" or not state["search_results"]:
		logger.warning(f"Попытка добавить в избранное без поиска (user_id={user_id})")
		write_msg(user_id, "Сначала найдите человека!", create_main_keyboard())
		return

	favorite_vk_id = state["search_results"][state["current_index"]]
	logger.info(f"Добавление пользователя {favorite_vk_id} в избранное (user_id={user_id})")

	if db.is_exist_favorite(favorite_vk_id, user_id):
		logger.warning(f"Пользователь {favorite_vk_id} уже в избранном (user_id={user_id})")
		write_msg(user_id, "Этот пользователь уже в избранном!", create_search_keyboard())
		return

	# Проверка наличия текущего пользователя в базе данных
	if not db.is_exist_user(user_id):
		logger.info(f"Пользователь {user_id} не найден в БД, запрашиваем данные...")
		user_info = user.get_user_info(user_id)
		if not user_info:
			logger.error(f"Не удалось получить данные пользователя {user_id}")
			write_msg(user_id, "Не удалось получить ваши данные", create_main_keyboard())
			return

		city = user_info.get("city", {}).get("title", "Unknown")
		age = calculate_age(user_info.get("bdate", ""))
		db.user_insert(
			user_id,
			user_info["first_name"],
			user_info["last_name"],
			city, age,
			user_info["sex"]
		)
		logger.info(f"Пользователь {user_id} добавлен в БД")

	# Проверка наличия избранного пользователя в базе данных
	if not db.is_exist_searchuser(favorite_vk_id):
		logger.info(f"Избранный пользователь {favorite_vk_id} не найден в БД, запрашиваем данные...")
		user_info = user.get_user_info(favorite_vk_id)
		if not user_info:
			logger.error(f"Не удалось получить данные пользователя {favorite_vk_id}")
			write_msg(user_id, "Не удалось получить данные пользователя", create_search_keyboard())
			return

		city = user_info.get("city", {}).get("title", "Unknown")
		age = calculate_age(user_info.get("bdate", ""))
		db.searchuser_insert(
			favorite_vk_id,
			user_info["first_name"],
			user_info["last_name"],
			city, age,
			user_info["sex"]
		)
		logger.info(f"Избранный пользователь {favorite_vk_id} добавлен в БД")

	# Добавление в избранное
	db.favorites_insert(favorite_vk_id, user_id)
	logger.info(f"Пользователь {favorite_vk_id} успешно добавлен в избранное (user_id={user_id})")
	write_msg(user_id, "✅ Добавлено в избранное!", create_search_keyboard())


def handle_add_blacklist(user_id):
	"""Добавляет текущего просматриваемого пользователя в чёрный список.

	Args:
		user_id (int): ID пользователя VK.
	"""
	state = user_state.get(user_id, {})
	if not state or state["last_command"] != "find_person" or not state["search_results"]:
		write_msg(user_id, "Сначала найдите человека!", create_main_keyboard())
		return
	blacklist_vk_id = state["search_results"][state["current_index"]]
	if db.is_exist_blackuser(user_id, blacklist_vk_id):
		write_msg(user_id, "Этот пользователь уже в черном списке!", create_search_keyboard())
		return
	if not db.is_exist_user(user_id):
		user_info = user.get_user_info(user_id)
		city = user_info.get("city", {}).get("title", "Unknown")
		age = calculate_age(user_info.get("bdate", ""))
		db.user_insert(user_id, user_info["first_name"], user_info["last_name"], city, age, user_info["sex"])
	db.blacklist_insert(blacklist_vk_id, user_id)
	write_msg(user_id, "🚫 Добавлено в черный список!", create_search_keyboard())


def handle_like_photo(user_id, owner_id, photo_id):
	"""Ставит лайк на фото текущего просматриваемого пользователя.

	Args:
		user_id (int): ID пользователя VK, ставящего лайк.
		owner_id (int): ID пользователя VK, владельца фото.
		photo_id (int): ID фото для лайка.
	"""
	state = user_state.get(user_id, {})
	if not state or state["last_command"] != "find_person" or not state["search_results"]:
		write_msg(user_id, "Сначала найдите человека!", create_main_keyboard())
		return
	current_user_id = state["search_results"][state["current_index"]]
	if owner_id != current_user_id:
		write_msg(user_id, "Ошибка: Нельзя лайкнуть фото другого пользователя!", create_search_keyboard())
		return
	success = user.get_like_to_photo(owner_id, photo_id)
	if success:
		logging.info(f"Пользователь {user_id} поставил лайк на фото {photo_id} пользователя {owner_id}")
		write_msg(user_id, "❤️ Лайк поставлен на фото!", create_search_keyboard())
	else:
		logging.error(f"Пользователь {user_id} не смог поставить лайк на фото {photo_id} пользователя {owner_id}")
		write_msg(user_id, "❌ Не удалось поставить лайк на фото.", create_search_keyboard())


def handle_list_favorites(user_id):
	"""Отображает список избранных пользователей для указанного пользователя.

	Args:
		user_id (int): ID пользователя VK.
	"""
	favorites = db.get_info_favorite(user_id)
	if not favorites:
		write_msg(user_id, "😔 У вас нет избранных.", create_main_keyboard())
		return
	message = "⭐ Ваши избранные:\n" + "\n".join(f"{i + 1}. {name} ({url})" for i, (url, name) in enumerate(favorites))
	write_msg(user_id, message, create_main_keyboard())


# Основной цикл обработки событий
while True:
	try:
		for event in longpoll.listen():
			if event.type == VkEventType.MESSAGE_NEW:
				logging.info(f"Новое входящее сообщение || ID пользователя: {event.user_id} || Текст: '{event.text}'")

			if event.type == VkEventType.MESSAGE_NEW and event.to_me:
				user_id = event.user_id
				text = event.text.lower().strip() if hasattr(event, 'text') else ""

				# Обработка payload кнопок
				payload = event.extra_values.get("payload")
				if payload:
					try:
						payload = json.loads(payload) if isinstance(payload, str) else payload

						command = payload.get("command")
						if command == "set_search_params":
							handle_set_search_params(user_id)
						elif command == "find_person":
							handle_find_person(user_id)
						elif command == "add_favorite":
							handle_add_favorite(user_id)
						elif command == "list_favorites":
							handle_list_favorites(user_id)
						elif command == "next_person":
							handle_next_person(user_id)
						elif command == "back":
							write_msg(user_id, "Возвращаемся в главное меню.", create_main_keyboard())
						elif command == "cancel":
							user_state.pop(user_id, None)
							write_msg(user_id, "Поиск отменён.", create_main_keyboard())
						elif command == "select_city":
							city_id = payload.get("city_id")
							if city_id and user_id in user_state and user_state[user_id].get("step") == "select_city":
								user_state[user_id]["search_params"]["city_id"] = city_id
								handle_find_person_with_params(user_id, user_state[user_id]["search_params"])
							else:
								write_msg(user_id, "Ошибка выбора города. Попробуйте снова.", create_main_keyboard())
						elif command == "add_blacklist":
							handle_add_blacklist(user_id)
						elif command == "like_photo":
							owner_id = payload.get("owner_id")
							photo_id = payload.get("photo_id")
							if owner_id and photo_id:
								handle_like_photo(user_id, owner_id, photo_id)
							else:
								write_msg(user_id, "Ошибка: Не удалось определить фото для лайка.",
										  create_search_keyboard())
						continue
					except json.JSONDecodeError as e:
						logging.error(f"Ошибка декодирования JSON payload: {e}, payload: {payload}")
						write_msg(user_id, "Ошибка обработки команды. Попробуйте снова.", create_main_keyboard())
						continue

				# Обработка текстовых команд
				request = event.text.lower().strip() if hasattr(event, 'text') else ""
				logging.info(f"Получено сообщение от пользователя {user_id}: {text}")
				if not request:
					write_msg(user_id, "Пожалуйста, введите команду или используйте кнопки!", create_main_keyboard())
					continue

				if handle_search_params_input(user_id, request):
					continue

				if request == "привет":
					write_msg(user_id, "Привет! Я бот для знакомств. 🚀")
					time.sleep(0.5)
					if not USER_TOKEN:
						write_msg(user_id, "Пожалуйста авторизуйтесь во ВКонтакте для продолжения работы бота")
						USER_TOKEN = get_token_with_selenium()
						if not USER_TOKEN:
							continue
						write_msg(user_id, "Активация прошла успешно!")
					user = VKInteraction(USER_TOKEN, vk)
					write_msg(user_id, "Нажми «Найти человека», чтобы начать.", create_main_keyboard())
				elif request == "найти человека":
					handle_set_search_params(user_id)
				elif request == "добавить в избранное":
					handle_add_favorite(user_id)
				elif request == "список избранных":
					handle_list_favorites(user_id)
				elif request == "следующий":
					handle_next_person(user_id)
				elif request == "помощь":
					write_msg(user_id,
							  "Доступные команды:\n1. Найти человека — поиск новых людей\n2. Добавить в избранное — "
							  "сохранить пользователя\n3. Добавить в черный список — исключить пользователя\n"
							  "4. Лайк фото — лайкнуть фото пользователя\n5. Список избранных — посмотреть избранных\n"
							  "6. Следующий — следующий пользователь\nИспользуйте кнопки ниже!",
							  create_main_keyboard())
				else:
					write_msg(user_id, "Команда не распознана. Попробуйте «помощь» или используйте кнопки.",
							  create_main_keyboard())

	except Exception as e:
		logging.error(f"Ошибка longpoll: {e}")
		time.sleep(5)  # Задержка перед повторной попыткой, чтобы избежать спама