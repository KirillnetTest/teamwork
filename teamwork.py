import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import time
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, filename="bot.log")

load_dotenv()
TOKEN = os.getenv("VK_TOKEN")
if not TOKEN:
    raise ValueError("VK_TOKEN not found in environment variables")

vk = vk_api.VkApi(token=TOKEN)
longpoll = VkLongPoll(vk)

def create_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Найти человека", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("Добавить в избранное", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Список избранных", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("Следующий", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def write_msg(user_id, message, keyboard=None):
    try:
        vk.method("messages.send", {
            "user_id": user_id,
            "message": message,
            "random_id": int(time.time() * 1000),
            "keyboard": keyboard
        })
    except vk_api.exceptions.ApiError as e:
        logging.error(f"Error sending message to {user_id}: {e}")
        vk.method("messages.send", {
            "user_id": user_id,
            "message": "Произошла ошибка, попробуйте позже.",
            "random_id": int(time.time() * 1000),
            "keyboard": keyboard
        })

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_id = event.user_id
                request = event.text.lower().strip()
                logging.info(f"Message from {user_id}: {request}")

                if not request:
                    write_msg(user_id, "Пожалуйста, введите команду или используйте кнопки!", create_keyboard())
                    continue

                if request == "привет":
                    write_msg(user_id, "Привет! Я бот для знакомств. 🚀\n"
                                      "Нажми «Найти человека», чтобы начать.", create_keyboard())
                
                elif request == "найти человека":
                    write_msg(user_id, "🔍 Ищу подходящих людей... (заглушка)", create_keyboard())
                
                elif request == "добавить в избранное":
                    write_msg(user_id, "✅ Пользователь добавлен в избранное!", create_keyboard())
                
                elif request == "список избранных":
                    write_msg(user_id, "⭐ Список избранных:\n1. Иван Иванов\n2. Мария Петрова", create_keyboard())
                
                elif request == "следующий":
                    write_msg(user_id, "➡️ Показываю следующего пользователя...", create_keyboard())
                
                elif request == "помощь":
                    write_msg(user_id, "Доступные команды:\n"
                                      "1. Найти человека — поиск новых людей\n"
                                      "2. Добавить в избранное — сохранить пользователя\n"
                                      "3. Список избранных — посмотреть избранных\n"
                                      "4. Следующий — следующий пользователь\n"
                                      "Используйте кнопки ниже!", create_keyboard())
                
                else:
                    write_msg(user_id, "Я не понимаю команду. Используйте кнопки или напишите «помощь»!", create_keyboard())
    
    except Exception as e:
        logging.error(f"Longpoll error: {e}")
        time.sleep(5) 