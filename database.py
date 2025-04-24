import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
DBNAME = os.getenv("NAME_DB")
if not DBNAME:
    raise ValueError("NAME_DB not found in environment variables")
USER = os.getenv("USER_DB")
if not USER:
    raise ValueError("USER_DB not found in environment variables")
PASSWORD = os.getenv("PASSWORD_DB")
if not PASSWORD:
    raise ValueError("PASSWORD_DB not found in environment variables")
HOST = os.getenv("HOST_DB")
if not HOST:
    raise ValueError("HOST_DB not found in environment variables")
PORT = os.getenv("PORT_DB")
if not PORT:
    raise ValueError("PORT_DB not found in environment variables")

#Установка соединения с базой данных
def get_db_connection():
    return psycopg2.connect(
        dbname=DBNAME,
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT
    )

# Функция для создания структуры БД
def create_database_structure():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Создание таблицы Users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        vk_id SERIAL PRIMARY KEY,
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255) NOT NULL,
        city VARCHAR(255) NOT NULL,
        age VARCHAR(255) NOT NULL,
        sex INT NOT NULL
    );
    ''')

    # Создание таблицы SearchUser
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SearchUser (
        vk_id SERIAL PRIMARY KEY,
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255) NOT NULL,
        city VARCHAR(255) NOT NULL,
        age INT NOT NULL,
        sex INT NOT NULL,
        photo1 VARCHAR,
        photo2 VARCHAR,
        photo3 VARCHAR,
        last_updated VARCHAR
    );
    ''')

    # Создание таблицы Favorites
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Favorites(
	    searchUserId INTEGER REFERENCES SearchUser(vk_id),
	    userId INTEGER REFERENCES Users(vk_id),
	    added_at VARCHAR,
	    CONSTRAINT pk1 PRIMARY KEY (searchUserId, userId)
	);
	''')

    conn.commit()
    cursor.close()
    conn.close()

#функция добавления нового пользователя в таблицу Users
def user_insert(vk_id: int, first_name: str, last_name: str, city: str, age: int, sex: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO Users (vk_id, first_name, last_name, city, age, sex) 
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING vk_id;
    ''', (vk_id, first_name, last_name, city, age, sex))

    user_vk_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return user_vk_id

#функция добавления нового подходящего пользователя из поиска в таблицу SearchUser
def searchUser_insert(vk_id: int, first_name: str, last_name: str, city: str, age: int,
                      sex: int, photo1: str, photo2: str, photo3: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_time = str(datetime.now())
    cursor.execute('''
    INSERT INTO SearchUser (vk_id, first_name, last_name, city, age, sex, photo1, photo2, photo3, last_updated) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING vk_id;
    ''', (vk_id, first_name, last_name, city, age, sex, photo1, photo2, photo3, now_time))

    serachUser_vk_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return serachUser_vk_id

#функция добавления избранного кандидата в таблицу Favorites
def favorites_insert(favorite_vk_id: int, user_vk_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_time = str(datetime.now())
    cursor.execute('''
    INSERT INTO Favorites (searchUserId, userId, added_at) 
    VALUES (%s, %s, %s);
    ''', (favorite_vk_id, user_vk_id, now_time))

    conn.commit()
    cursor.close()
    conn.close()

#Функция для получения списка избранных для одного пользователя, возраает url, имя и фамилию без фотографий
def get_info_favorite(vk_id_user: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT vk_id,first_name,last_name FROM SearchUser  
    WHERE vk_id IN (SELECT searchUserId FROM favorites WHERE userid= %s)
    ''', (vk_id_user,))

    favorite_users = cursor.fetchall()
    new_list = []
    for i in favorite_users:
        url = f'https://vk.com/id{i[0]}'
        new_name = f'{i[1]} {i[2]}'
        new_list.append([url, new_name])

    conn.commit()
    cursor.close()
    conn.close()

    return new_list