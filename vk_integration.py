from time import sleep

import vk_api
from vk_api.exceptions import VkApiError
from typing import Optional, List, Dict
import logging

logging.basicConfig(
	level = logging.INFO,
	filename = "api.log",
	encoding = "utf-8",
	format = "%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VKInteraction:

	def __init__(self, user_token: str, vk: vk_api.VkApi,
				 api_version: str = "5.199") -> None:
		"""
		Инициализация взаимодействия с VK API
		:param user_token: Токен пользователя (для методов, требующих права пользователя)
		:param vk: Экзепляр VK_API
		"""
		self.user_token = user_token
		group_session = vk
		self.api_version = api_version

		# инициализация сессии для использования методов использующих Токен Пользователя
		try:
			self.user_session = vk_api.VkApi(token = user_token,
											 api_version = api_version)
			self.user_api = self.user_session.get_api()
			self.group_api = group_session.get_api()
			logger.info(f'Инициализация сессии прошла успешно')
		except Exception as e:
			logger.critical(f"Не удалось инициализировать сессию: {e}")

	def get_user_info(self, user_id: int, fields: Optional[List[str]] = None) -> Dict:
		"""
		Получение информации о пользователе
		:param user_id: ID пользователя VK
		:param fields: дополнительные поля (по умолчанию, ['first_name', 'last_name', 'city', 'sex', 'domain',
		'bdate'])
		:return: словарь с информацией о пользователе, содержащий только запрошенные поля
		"""
		# Поля по умолчанию
		default_fields = ['first_name', 'last_name', 'city', 'sex', 'domain', 'bdate']
		requested_fields = fields or default_fields

		try:
			# Получаем информацию о пользователе
			logger.info(f'Получаем информацию для user_id: {user_id}')

			user_get_response = self.group_api.users.get(
				user_id = user_id,
				fields = requested_fields
			)

			if not user_get_response:
				logging.info(f'Получены неверные данные: {user_id}')

			user_data = user_get_response[0]
			logger.info(f'Данные получены для пользователя с user_id: {user_id}')

			# Фильтруем результат, оставляя только запрошенные поля
			return {field:user_data.get(field) for field in requested_fields}

		except VkApiError as e:
			logger.error(f"Ошибка получения информации для user_id {user_id}: {e}")
			return {}

	def user_search(
			self,
			age_from: Optional[int] = None,
			age_to: Optional[int] = None,
			sex: Optional[int] = None,
			city: Optional[int] = None,
			count: Optional[int] = None
	) -> List[Dict]:
		"""
		Поиск пользователей по заданным параметрам

		:param age_from: Минимальный возраст
		:param age_to: Максимальный возраст
		:param sex: Пол (1 - женский, 2 - мужской)
		:param city: ID города
		:param count: количество возвращаемых людей
		:return: список людей подходящих под парамметры запроса (возвращат Словарь содержащих поля
		"""
		result = []
		logger.info(f'Начало поиска пользователей с параметрами: возраст от {age_from} до {age_to}, '
					f'пол {sex}, город {city}, количество {count}')

		# Проверяем что количество возвращаемых людей больше 0
		if count <= 0:
			logger.warning('Параметр количества <= 0, возвращаем пустой список')
			return result

		params = {
			'sort':0,
			'count':count,
			'fields':'first_name,last_name,city,sex,bdate',
			'has_photo':1,
			'status':1
		}

		try:
			if age_from is not None:
				params['age_from'] = age_from
			if age_to is not None:
				params['age_to'] = age_to
			if age_from is not None and age_to is not None and age_from > age_to:
				error_msg = 'Минимальный возраст должен быть меньше максимального'
				logger.error(error_msg)
				raise ValueError(error_msg)
			if sex is not None:
				if sex not in (1, 2):
					error_msg = 'Пол должен быть 1 (женский) или 2 (мужской)'
					logger.error(error_msg)
					raise ValueError(error_msg)
				params['sex'] = sex
			if city is not None:
				params['city'] = city

			remaining = count
			sleep_count = 0
			# Обходим циклом все пользователей переданных в переменной count группами по 1000 человек
			while remaining > 0:
				# Обходим ограничение на 3 запроса в секунду. Используем sleep на 1 секунду каждые 3 цикла
				if sleep_count % 3 == 0 and sleep_count > 0:
					sleep(1)
				sleep_count += 1

				params['count'] = min(remaining, 1000)
				params['offset'] = len(result)

				try:
					logger.info(
						f'Запрашиваем список людей соответсвующих парамметрам: age_from = {age_from}, age_to = {age_to}, sex = {sex}, city = {city}, count = {remaining}')
					response = self.user_api.users.search(**params)
					result.extend(response['items'])
					remaining -= params['count']
					logger.info(f"Получено {len(response['items'])} пользователей в текущей выборке")

					if len(response['items']) < params['count']:
						logger.info(f"Получено меньше запрошенного ({len(response['items'])} < {params['count']}), "
									"завершение цикла")
						break

				except VkApiError as e:
					logging.error(f"Ошибка поиска пользователей: {e}")
					break
		except Exception as e:
			logger.error(f"Ошибка при настройке параметров поиска: {e}")

		# Удаление дубликатов пользователей по ID
		seen_ids = set()
		unique_result = []
		for user in result:
			if user['id'] not in seen_ids:
				seen_ids.add(user['id'])
				unique_result.append(user)

		logger.info(f"Поиск пользователей завершен. Найдено {len(unique_result)} уникальных пользователей")
		return unique_result

	def get_user_photos(self, user_id: int) -> List[str]:
		"""
		Получение фотографий из профиля пользователя и фотографий, где пользователь отмечен.
		Возвращает указанное количество самых популярных фотографий (по лайкам) в формате Attachment.

		:param user_id: ID пользователя VK
		:return Список Attachment фотографий или пустой список в случае ошибки
		"""
		logger.info(f"Получение фотографий пользователя с ID: {user_id}")
		try:
			# Получаем список фотографий из профиля пользователя
			response_profile = self.user_api.photos.get(
				owner_id = user_id,
				album_id = 'profile',
				extended = 1
			)

			# Получаем список фотографий, где отмечен пользователь
			response_tag = self.user_api.photos.get(
				owner_id = user_id,
				album_id = 'wall',
				feed_type = 'photo_tag',
				extended = 1
			)

			photos_profile = response_profile.get('items', [])
			photos_tag = response_tag.get('items', [])
			logger.debug(f"Получено {len(photos_profile)} фото профиля и {len(photos_tag)} фото с отметками")

			# Объединяем оба списка в один и сортируем по количеству Лайков
			photos = photos_profile + photos_tag
			photos_sorted = sorted(photos, key = lambda x:x["likes"]["count"], reverse = True)

			# Фортируем список Attachments по выбранным фотографиям
			result = [
				# f"photo{photo['owner_id']}_{photo['id']}_{self.user_token}"
				f"photo{photo['owner_id']}_{photo['id']}"
				for photo in photos_sorted
			]
			logger.info(f"Успешно подготовлено {len(result)} фото-прикреплений")
			logger.info(f"Итоговая строка Attachments: {result}")

			return result

		except VkApiError as e:
			logging.error(f"Ошибка получения фотографий: {e}")
			return []

	def get_like_to_photo(self, owner_id: int, photo_id: int) -> bool:
		"""
		Поставить лайк на фото
		:param owner_id: ID владельца фото (может быть отрицательным для групп)
		:param photo_id: ID фотографии
		:return: True - если удачно и False в противном случае
		"""
		logger.info(f"Попытка поставить лайк на фото {photo_id} пользователя {owner_id}")
		try:
			response = self.user_api.likes.add(
				type = 'photo',
				owner_id = owner_id,
				item_id = photo_id,
				access_token = self.user_token
			)

			# Проверяем, что лайк действительно был поставлен
			if response.get('likes', 0) > 0:
				logging.info(f"Лайк успешно поставлен на фото {photo_id} пользователя {owner_id}")
				return True

			logging.warning(f"Лайк не был зарегистрирован для фото {photo_id} пользователя {owner_id}")
			return False

		except VkApiError as e:
			logging.error(f"Ошибка при попытке поставить лайк на фото {photo_id} пользователя {owner_id}: {e}")
			return False

	def get_cities(self, city_name: str) -> List[dict]:
		"""
		Получаем список ID городов подходящих по запросу city_name
		:param city_name: Строка поиска
		:return: Список словарей с информацией о городах
		"""
		logger.info(f"Поиск городов по названию: {city_name}")
		try:
			if not city_name or not isinstance(city_name, str):
				logging.warning(f"Получен некорректный город для поиска: {city_name}")
				return []

			response = self.user_api.database.getCities(q = city_name, need_all = 1)
			cities = response.get('items', [])
			logger.info(f"Найдено {len(cities)} городов по запросу '{city_name}'")
			return cities

		except VkApiError as e:
			logging.error(f"Не удалось получить список городов>: {city_name}, ошибка: {e}")
			return []