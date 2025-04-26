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

logging.basicConfig(level=logging.INFO, filename="bot.log", encoding="utf-8")
load_dotenv()
TOKEN = os.getenv("VK_TOKEN")
USER_TOKEN = os.getenv("USER_TOKEN")

if not TOKEN or not USER_TOKEN:
    raise ValueError("VK_TOKEN or USER_TOKEN not found in environment variables")

vk = vk_api.VkApi(token=TOKEN)
longpoll = VkLongPoll(vk)
user = VKInteraction(USER_TOKEN, vk)
db = DataBase()
user_state = {}

def create_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Найти человека", color=VkKeyboardColor.POSITIVE, payload={"command": "find_person"})
    keyboard.add_button("Список избранных", color=VkKeyboardColor.SECONDARY, payload={"command": "list_favorites"})
    return keyboard.get_keyboard()

def create_search_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Добавить в избранное", color=VkKeyboardColor.PRIMARY, payload={"command": "add_favorite"})
    keyboard.add_button("Следующий", color=VkKeyboardColor.NEGATIVE, payload={"command": "next_person"})
    keyboard.add_line()
    keyboard.add_button("Назад", color=VkKeyboardColor.SECONDARY, payload={"command": "back"})
    return keyboard.get_keyboard()

def write_msg(user_id, message, keyboard=None, attachment=None, retries=3):
    for attempt in range(retries):
        try:
            vk.method("messages.send", {
                "user_id": user_id,
                "message": message,
                "random_id": random.randint(1, 2**31),
                "keyboard": keyboard,
                "attachment": attachment
            })
            return
        except vk_api.exceptions.ApiError as e:
            if "too many requests" in str(e).lower():
                time.sleep(1 << attempt)
                continue
            logging.error(f"Error sending message to {user_id}: {e}")
            vk.method("messages.send", {
                "user_id": user_id,
                "message": f"Ошибка: {str(e)}. Попробуйте позже.",
                "random_id": random.randint(1, 2**31),
                "keyboard": keyboard,
                "attachment": attachment
            })
            return
    logging.error(f"Failed to send message to {user_id} after {retries} attempts")

def handle_find_person(user_id):
    users = user.user_search(age_from=18, age_to=30, sex=2, city=1, count=10)
    user_state[user_id] = {
        "search_results": [u["id"] for u in users],
        "current_index": 0,
        "last_command": "find_person"
    }
    if users:
        current_user = users[0]
        user_info = f"{current_user['first_name']} {current_user['last_name']}"
        photos = user.get_user_photos(current_user["id"])
        write_msg(user_id, f"🔍 Найден: {user_info}", create_search_keyboard(), attachment=",".join(photos))
    else:
        write_msg(user_id, "😔 Никто не найден. Попробуйте снова!", create_main_keyboard())

def handle_next_person(user_id):
    state = user_state.get(user_id, {})
    if not state or state["last_command"] != "find_person" or not state["search_results"]:
        write_msg(user_id, "Сначала выполните поиск!", create_main_keyboard())
        return
    state["current_index"] = (state["current_index"] + 1) % len(state["search_results"])
    next_user_id = state["search_results"][state["current_index"]]
    user_info = user.get_user_info(next_user_id)
    photos = user.get_user_photos(next_user_id)
    message = f"{user_info['first_name']} {user_info['last_name']}"
    write_msg(user_id, message, create_search_keyboard(), attachment=",".join(photos))

def handle_add_favorite(user_id):
    state = user_state.get(user_id, {})
    if not state or state["last_command"] != "find_person" or not state["search_results"]:
        write_msg(user_id, "Сначала найдите человека!", create_main_keyboard())
        return
    favorite_vk_id = state["search_results"][state["current_index"]]
    if not db.is_exist_user(user_id):
        user_info = user.get_user_info(user_id)
        city = user_info.get("city", {}).get("title", "Unknown")
        age = user_info.get("bdate", "").split(".")[-1] if user_info.get("bdate") else 0
        db.user_insert(user_id, user_info["first_name"], user_info["last_name"], city, int(age) if age else 0, user_info["sex"])
    if not db.is_exist_searchuser(favorite_vk_id):
        user_info = user.get_user_info(favorite_vk_id)
        city = user_info.get("city", {}).get("title", "Unknown")
        age = user_info.get("bdate", "").split(".")[-1] if user_info.get("bdate") else 0
        db.searchuser_insert(favorite_vk_id, user_info["first_name"], user_info["last_name"], city, int(age) if age else 0, user_info["sex"])
    db.favorites_insert(favorite_vk_id, user_id)
    write_msg(user_id, "✅ Добавлено в избранное!", create_search_keyboard())

def handle_list_favorites(user_id):
    favorites = db.get_info_favorite(user_id)
    if not favorites:
        write_msg(user_id, "😔 У вас нет избранных.", create_main_keyboard())
        return
    message = "⭐ Ваши избранные:\n" + "\n".join(f"{i+1}. {name} ({url})" for i, (url, name) in enumerate(favorites))
    write_msg(user_id, message, create_main_keyboard())

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_id = event.user_id
                payload = event.message.get("payload")
                if payload:
                    payload = json.loads(payload)
                    command = payload.get("command")
                    if command == "find_person":
                        handle_find_person(user_id)
                    elif command == "add_favorite":
                        handle_add_favorite(user_id)
                    elif command == "list_favorites":
                        handle_list_favorites(user_id)
                    elif command == "next_person":
                        handle_next_person(user_id)
                    elif command == "back":
                        write_msg(user_id, "Возвращаемся в главное меню.", create_main_keyboard())
                    continue

                request = event.text.lower().strip()
                logging.info(f"Message from {user_id}: {request}")
                if not request:
                    write_msg(user_id, "Пожалуйста, введите команду или используйте кнопки!", create_main_keyboard())
                    continue

                if request == "привет":
                    write_msg(user_id, "Привет! Я бот для знакомств. 🚀\nНажми «Найти человека», чтобы начать.", create_main_keyboard())
                elif request == "найти человека":
                    handle_find_person(user_id)
                elif request == "добавить в избранное":
                    handle_add_favorite(user_id)
                elif request == "список избранных":
                    handle_list_favorites(user_id)
                elif request == "следующий":
                    handle_next_person(user_id)
                elif request == "помощь":
                    write_msg(user_id, "Доступные команды:\n1. Найти человека — поиск новых людей\n2. Добавить в избранное — сохранить пользователя\n3. Список избранных — посмотреть избранных\n4. Следующий — следующий пользователь\nИспользуйте кнопки ниже!", create_main_keyboard())
                else:
                    write_msg(user_id, "Команда не распознана. Попробуйте «помощь» или используйте кнопки.", create_main_keyboard())

    except Exception as e:
        logging.error(f"Longpoll error: {e}")
        time.sleep(5)
