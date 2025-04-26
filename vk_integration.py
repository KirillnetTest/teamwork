import vk_api
from vk_api.exceptions import VkApiError
from typing import Optional, List, Dict
import logging

logging.basicConfig(level = logging.INFO, filename = "api.log", encoding = "utf-8")


class VKInteraction:

	def __init__(self, user_token: str, VK: vk_api.VkApi,
				 api_version: str = "5.199") -> None:
		"""
		Инициализация взаимодействия с VK API
		:param user_token: Токен пользователя (для методов, требующих права пользователя)
		:param VK: Экзепляр VK_API"
		"""
		self.user_token = user_token
		self.group_api = VK
		self.api_version = api_version

		# инициализация сессии для использования методов использующих Токен Пользователя
		self.user_session = vk_api.VkApi(token = user_token,
										 api_version = api_version)
		self.user_api = self.user_session.get_api()

	def get_user_info(self, user_id: int, fields: Optional[List[str]] = None) -> Dict:
		"""
		Получение информации о пользователе
		:param user_id: ID пользователя VK
		:param fields: дополнительные поля (например, ['city', 'photo_max'])
		:return: словарь с информацией о пользователе, содержащий только запрошенные поля
		"""
		# Поля по умолчанию
		default_fields = ['first_name', 'last_name', 'city', 'sex', 'domain', 'bdate']
		requested_fields = fields or default_fields

		try:
			# Получаем информацию о пользователе
			user_get_response = self.group_api.method('users.get', {'user_id':user_id, 'fields':requested_fields})

			if not user_get_response:
				logging.info(f"User {user_id}: no data received")
				return {}

			user_data = user_get_response[0]

			# Фильтруем результат, оставляя только запрошенные поля
			return {field:user_data.get(field) for field in requested_fields}

		except VkApiError as e:
			print(f"Ошибка получения информации о пользователе: {e}")
			return {}

	def user_search(
			self,
			age_from: Optional[int] = None,
			age_to: Optional[int] = None,
			sex: Optional[int] = None,
			city: Optional[int] = None,
			count: int = 1000
	) -> List[Dict]:
		"""
		Поиск пользователей по заданным параметрам

		:param age_from: Минимальный возраст
		:param age_to: Максимальный возраст
		:param sex: Пол (1 - женский, 2 - мужской)
		:param city: ID города
		:param count: количество возвращаемых людей (макс. 1000)
		:return: список людей подходящих под парамметры запроса
		"""

		params = {
			'sort':0,
			'count':min(count, 1000),
			'fields':'sex, domain, bdate',
			'has_photo':1,
			'status':1
		}

		if age_from is not None:
			params['age_from'] = age_from
		if age_to is not None:
			params['age_to'] = age_to
		if sex is not None:
			if sex not in (1, 2):
				raise ValueError("Sex must be 1 (female) or 2 (male)")
			params['sex'] = sex
		if city is not None:
			params['city'] = city

		try:
			response = self.user_api.users.search(**params)
			return response.get('items', [])
		except VkApiError as e:
			logging.error(f"Ошибка поиска пользователей: {e}")
			return []

	def get_user_photos(self, user_id: int, count: int = 3) -> List[str]:
		"""
		Получение 3 фотографий из профиля пользователя в формате Attachment

		:param user_id: ID полизователя VK
		:param count: количество фотографий (по умолчанию 3)
		:return Список Attachment фотографий или пустой список в случае ошибки
		"""
		try:
			response = self.user_api.photos.get(
				owner_id = user_id,
				album_id = 'profile',
				extended = 1
			)
			attachments = []

			photos = response.get('items', [])
			photos_sorted = sorted(photos, key = lambda x:x["likes"]["count"], reverse = True)

			for photo in photos_sorted[:count]:
				attachments.append('photo{}_{}_{}'.format(photo['owner_id'], photo['id'], self.user_token))

			logging.info(f'Attachments: {attachments[:3]}')
			return attachments[:3]

		except VkApiError as e:
			logging.error(f"Ошибка получения фотографий: {e}")
			return []