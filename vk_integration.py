import vk_api
from vk_api.exceptions import VkApiError
from typing import Optional, List, Dict
import logging

logging.basicConfig(level = logging.INFO, filename = "api.log")


class VKInteraction:

	def __init__(self, vk_api_instance: vk_api.VkApi):
		"""
		:param vk_api_instance: экземпляр VkApi
		:raises TypeError: если передан не экземпляр VkApi
		"""
		if not isinstance(vk_api_instance, vk_api.VkApi):
			raise TypeError("Ожидается экземпляр vk_api.VkApi")

		self.session = vk_api_instance

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