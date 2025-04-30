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

logging.basicConfig(level = logging.INFO, filename = "bot.log", encoding = "utf-8",
					format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("VK_TOKEN")
USER_TOKEN = os.getenv("USER_TOKEN")

# if not USER_TOKEN:
# 	USER_TOKEN = get_token_with_selenium()

if not TOKEN:
	raise ValueError("VK_TOKEN not found in environment variables")

vk = vk_api.VkApi(token = TOKEN, api_version = "5.199")
longpoll = VkLongPoll(vk)
user = None
db = DataBase()
user_state = {}


def create_main_keyboard():
	keyboard = VkKeyboard(one_time = False)
	keyboard.add_button("Найти человека", color = VkKeyboardColor.POSITIVE, payload = {"command":"set_search_params"})
	keyboard.add_button("Список избранных", color = VkKeyboardColor.SECONDARY, payload = {"command":"list_favorites"})
	return keyboard.get_keyboard()


def create_search_keyboard():
	keyboard = VkKeyboard(one_time = False)
	keyboard.add_button("Добавить в избранное", color = VkKeyboardColor.PRIMARY, payload = {"command":"add_favorite"})
	keyboard.add_button("Добавить в черный список", color = VkKeyboardColor.NEGATIVE,
						payload = {"command":"add_blacklist"})
	keyboard.add_line()
	keyboard.add_button("Следующий", color = VkKeyboardColor.SECONDARY, payload = {"command":"next_person"})
	keyboard.add_button("Назад", color = VkKeyboardColor.SECONDARY, payload = {"command":"back"})
	return keyboard.get_keyboard()


def create_photo_like_keyboard(photo):
	if not photo:
		return None

	keyboard = VkKeyboard(inline = True)

	try:
		parts = photo.split('_')
		if len(parts) < 2 or not parts[0].startswith('photo'):
			logging.error(f"Invalid photo attachment format: {photo}")
			return None

		owner_id = int(parts[0][5:])
		photo_id = int(parts[1])

		keyboard.add_button(
			"❤️ Лайк фото",
			color = VkKeyboardColor.POSITIVE,
			payload = {
				"command":"like_photo",
				"owner_id":owner_id,
				"photo_id":photo_id
			}
		)

		return keyboard.get_keyboard()

	except (ValueError, IndexError) as e:
		logging.error(f"Error parsing photo attachment {photo}: {e}")
		return None


def create_cancel_keyboard():
	keyboard = VkKeyboard(one_time = True)
	keyboard.add_button("Отмена", color = VkKeyboardColor.NEGATIVE, payload = {"command":"cancel"})
	return keyboard.get_keyboard()


def create_city_selection_keyboard(cities):
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
	for attempt in range(retries):
		try:
			vk.method("messages.send", {
				"user_id":user_id,
				"message":message,
				"random_id":random.randint(1, 2 ** 31),
				"keyboard":keyboard,
				"attachment":attachment
			})
			logging.info(f"Message sent to {user_id}: {message}")
			return
		except vk_api.exceptions.ApiError as e:
			if "too many requests" in str(e).lower():
				time.sleep(0.5 * (2 ** attempt))
				continue
			logging.error(f"Error sending message to {user_id}: {e}")
			vk.method("messages.send", {
				"user_id":user_id,
				"message":f"Ошибка: {str(e)}. Попробуйте позже.",
				"random_id":random.randint(1, 2 ** 31),
				"keyboard":keyboard,
				"attachment":attachment
			})
			return
	logging.error(f"Failed to send message to {user_id} after {retries} attempts")


def calculate_age(bdate: str) -> int:
	"""Calculate age from birthdate string (DD.MM.YYYY or DD.MM)."""
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


def handle_set_search_params(user_id):
	user_state[user_id] = {
		"last_command":"set_search_params",
		"step":"age_from",
		"search_params":{}
	}
	write_msg(user_id, "Введите минимальный возраст (например, 18):", create_cancel_keyboard())


def handle_search_params_input(user_id, text):
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
	try:
		blacklist = db.get_blacklist(user_id)
		users = user.user_search(
			age_from = params["age_from"],
			age_to = params["age_to"],
			sex = params["sex"],
			city = params["city_id"],
			count = 10
		)
		users = [u for u in users if u["id"] not in blacklist]
		user_state[user_id] = {
			"search_results":[u["id"] for u in users],
			"current_index":0,
			"last_command":"find_person",
			"last_search_params":params
		}
		logging.info(f"Метод handle_find_person_with_params получил данные: age_from = {params['age_from']}, age_to = {params['age_to']}, sex = {params['sex']}, city = {params['city_id']}")
		if users:
			current_user = users[0]
			profile_link = f"https://vk.com/id{current_user['id']}"
			user_info = f"{current_user['first_name']} {current_user['last_name']}\nПрофиль: {profile_link}"

			photos = user.get_user_photos(current_user["id"])
			logging.info(f"Получены photos = {photos}")
			keyboard = create_search_keyboard()

			if photos:
				# Отправляем каждое фото с кнопкой отдельным сообщением
				for i, photo in enumerate(photos[:3]):
					logging.info(f"<UNK> photo = {photo}")
					photo_keyboard = create_photo_like_keyboard(str(photo))  # Создаем клавиатуру для одного фото
					write_msg(user_id, attachment = photo)
					if photo_keyboard:
						write_msg(user_id, f"Лайкнуть фото {i + 1}:", keyboard = photo_keyboard)

				# Отправляем основную информацию и клавиатуру поиска
				write_msg(user_id, user_info, keyboard = keyboard)

		else:
			write_msg(user_id, "😔 Никто не найден. Попробуйте снова!", create_main_keyboard())
	except (ValueError, vk_api.exceptions.ApiError) as e:
		logging.error(f"Search error for user {user_id}: {e}")
		write_msg(user_id, f"Ошибка поиска: {str(e)}. Попробуйте снова.", create_main_keyboard())


def handle_find_person(user_id):
	handle_set_search_params(user_id)


def handle_next_person(user_id):
	logging.info(f"Обработка запроса 'следующий человек' для пользователя {user_id}")
	state = user_state.get(user_id, {})

	state["current_index"] = (state["current_index"] + 1) % len(state["search_results"])
	next_user_id = state["search_results"][state["current_index"]]

	user_info = user.get_user_info(next_user_id)
	photos = user.get_user_photos(next_user_id)

	message = f"{user_info['first_name']} {user_info['last_name']}\nПрофиль: https://vk.com/id{next_user_id}"
	keyboard = create_search_keyboard()

	if photos:
		# Отправляем каждое фото с кнопкой отдельным сообщением
		for i, photo in enumerate(photos[:3]):
			photo_keyboard = create_photo_like_keyboard([photo])  # Создаем клавиатуру для одного фото
			write_msg(user_id, attachment = photo)
			if photo_keyboard:
				write_msg(user_id, f"Лайкнуть фото {i + 1}:", keyboard = photo_keyboard)

		# Отправляем основную информацию и клавиатуру поиска
		write_msg(user_id, message, keyboard = keyboard)



def handle_add_favorite(user_id):
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

	# Добавление текущего пользователя в БД (если его нет)
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

	# Добавление избранного пользователя в БД (если его нет)
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
		logging.info(f"User {user_id} liked photo {photo_id} of user {owner_id}")
		write_msg(user_id, "❤️ Лайк поставлен на фото!", create_search_keyboard())
	else:
		logging.error(f"User {user_id} failed to like photo {photo_id} of user {owner_id}")
		write_msg(user_id, "❌ Не удалось поставить лайк на фото.", create_search_keyboard())


def handle_list_favorites(user_id):
	favorites = db.get_info_favorite(user_id)
	if not favorites:
		write_msg(user_id, "😔 У вас нет избранных.", create_main_keyboard())
		return
	message = "⭐ Ваши избранные:\n" + "\n".join(f"{i + 1}. {name} ({url})" for i, (url, name) in enumerate(favorites))
	write_msg(user_id, message, create_main_keyboard())


while True:
	try:
		for event in longpoll.listen():
			if event.type == VkEventType.MESSAGE_NEW:
				logging.info(f"Новое входящее сообщение || ID пользователя: {event.user_id} || Текст: '{event.text}'")

			if event.type == VkEventType.MESSAGE_NEW and event.to_me:
				user_id = event.user_id
				text = event.text.lower().strip() if hasattr(event, 'text') else ""

				# logging.info(f"Получено сообщение от пользователя {user_id}: {text}")
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
						logging.error(f"Payload JSON decode error: {e}, payload: {payload}")
						write_msg(user_id, "Ошибка обработки команды. Попробуйте снова.", create_main_keyboard())
						continue

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
						user = VKInteraction(USER_TOKEN, vk)
						write_msg(user_id, "Активация прошла успешно!🚀\nНажми «Найти человека», чтобы начать.", create_main_keyboard())
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
		logging.error(f"Longpoll error: {e}")
		time.sleep(5)