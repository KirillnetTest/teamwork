import vk_api
from vk_api.exceptions import VkApiError
from typing import Optional, List, Dict
import logging

logging.basicConfig(level = logging.INFO, filename = "api.log", encoding = "utf-8")


class VKInteraction:

	def __init__(self, vk_api_instance: vk_api.VkApi, vk_user_token: str) -> None:
		"""
		:param vk_api_instance: экземпляр VkApi
		:raises TypeError: если передан не экземпляр VkApi
		"""
		if not isinstance(vk_api_instance, vk_api.VkApi):
			raise TypeError("Ожидается экземпляр vk_api.VkApi")

		self.session = vk_api_instance
		self.vk_user_token = vk_user_token

	def _user_session(self):
		vk_session = vk_api.VkApi(token = self.vk_user_token)
		vk = vk_session.get_api()
		return vk

	def get_user_info(self, user_id: int, fields: Optional[List[str]] = None) -> Dict:
		"""
		Получение информации о пользователе
		:param user_id: ID пользователя VK
		:param fields: дополнительные поля (например, ['city', 'photo_max'])
		:return: словарь с информацией о пользователе, содержащий только запрошенные поля
		"""
		# Поля по умолчанию
		default_fields = ['first_name', 'last_name', 'city', 'sex', 'photo_max']
		requested_fields = fields or default_fields

		try:
			# Получаем информацию о пользователе
			user_get_response = self.session.method('users.get', {'user_id':user_id, 'fields':requested_fields})

			if not user_get_response:
				logging.info(f"User {user_id}: no data received")
				return {}

			user_data = user_get_response[0]

			# Фильтруем результат, оставляя только запрошенные поля
			return {field:user_data.get(field) for field in requested_fields}

		except VkApiError as e:
			print(f"Ошибка получения информации о пользователе: {e}")
			return {}

	def user_search(self, age_from: Optional[int] = None, age_to: Optional[int] = None, sex: Optional[int] = None,
					city: Optional[int] = None, count = 1000):
		"""
		Поиск пользователей по заданным параметрам с использованием vk_api

		:param age_from: Минимальный возраст
		:param age_to: максимальный возраст
		:param sex: пол (1 - женский, 2 - мужской)
		:param city: ID города
		:param count: количество возвращаемых пользователей (макс. 1000)
		:return: список пользователей
		"""

		params = {
			'sort':0,  # сортировка по популярности
			'count':count,
			'fields':'id,first_name,last_name,sex,domain,photo_id, photo_max,',
			'has_photo':1,  # только с фото
			'status':1
		}

		if age_from is not None:
			params['age_from'] = age_from
		if age_to is not None:
			params['age_to'] = age_to
		if sex is not None:
			if sex not in (1, 2):  # Проверка допустимых значений
				raise ValueError("Sex must be 1 (female) or 2 (male)")
			params['sex'] = sex
		if city is not None:
			params['city'] = city

		try:
			response = self._user_session().users.search(**params)
			return response.get('items', [])
		except VkApiError as e:
			logging.error(f"Ошибка VK API при поиске пользователей: {e}")
			return []

	def get_user_photos(self, user_id: int) -> List[str]:
		"""
		Получение 3 фотографий из профиля пользователя
		:param user_id:  ID пользователя VK
		:return: Список URL фотографий или пустой список в случае ошибки
		"""

		try:
			response = self._user_session().photos.get(
				owner_id = user_id,
				album_id = 'profile',
				count = 3,
				photo_sizes = 1
			)
			photos = response.get("items", [])
			photo_urls = []

			for photo in photos:
				sizes = photo.get("sizes", [])
				if sizes:
					# Выбираем фото с максимальным размером
					max_size = max(sizes, key = lambda x:x.get("width", 0) * x.get("height", 0))
					photo_urls.append(max_size["url"])

			return photo_urls[:3]  # Возвращаем не более 3 фото
		except VkApiError as e:
			logging.error(f"Ошибка VK API при поиске пользователей: {e}")
			return []