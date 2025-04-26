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


class DataBase:
    def __init__(self):
        self.data_name = DBNAME
        self.data_user = USER
        self.data_password = PASSWORD
        self.data_host = HOST
        self.data_port = PORT


    #Установка соединения с базой данных
    def get_db_connection(self):
        return psycopg2.connect(
            dbname=self.data_name,
            user=self.data_user,
            password=self.data_password,
            host=self.data_host,
            port=self.data_port
        )

    # Функция для создания структуры БД
    def create_database_structure(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Создание таблицы Users
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            vk_id SERIAL PRIMARY KEY,
            first_name VARCHAR(255) NOT NULL,
            last_name VARCHAR(255) NOT NULL,
            city VARCHAR(255) NOT NULL,
            age INT NOT NULL,
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

        # Создание таблицы BlackList
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS BlackList(
	        ID SERIAL PRIMARY KEY,
	        user_ID INTEGER NOT NULL REFERENCES Users(vk_id),
	        blackuser_id INTEGER NOT NULL
        );
        ''')

        conn.commit()
        cursor.close()
        conn.close()

    #функция добавления нового пользователя в таблицу Users
    def user_insert(self, vk_id: int, first_name: str, last_name: str, city: str, age: int, sex: int):
        conn = self.get_db_connection()
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
    def searchuser_insert(self, vk_id: int, first_name: str, last_name: str, city: str, age: int,
                      sex: int):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        now_time = str(datetime.now())
        cursor.execute('''
        INSERT INTO SearchUser (vk_id, first_name, last_name, city, age, sex, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING vk_id;
        ''', (vk_id, first_name, last_name, city, age, sex, now_time))

        serachUser_vk_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return serachUser_vk_id

    #функция добавления избранного кандидата в таблицу Favorites
    def favorites_insert(self, favorite_vk_id: int, user_vk_id: int):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        now_time = str(datetime.now())
        cursor.execute('''
        INSERT INTO Favorites (searchUserId, userId, added_at)
        VALUES (%s, %s, %s);
        ''', (favorite_vk_id, user_vk_id, now_time))

        conn.commit()
        cursor.close()
        conn.close()

    #функция добавления нежелательного пользователя в таблицу BlackList
    def blacklist_insert(self, blacklist_vk_id: int, user_vk_id: int):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO BlackList (user_id, blackuser_id)
        VALUES (%s, %s);
        ''', (blacklist_vk_id, user_vk_id,))

        conn.commit()
        cursor.close()
        conn.close()

    #Функция для получения списка избранных для одного пользователя, возраает url, имя и фамилию без фотографий
    def get_info_favorite(self, vk_id_user: int):
        conn = self.get_db_connection()
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

    # функция обновления информации о пользователе в таблице SearchUser
    def update_searchuser(self, vk_id: int, first_name=None, last_name=None, city=None, age=None, sex=None):
        conn = self.get_db_connection()
        cursor = conn.cursor()

        list_param = [('first_name', first_name), ('last_name',last_name),
                    ('city',city), ('age',age), ('sex',sex)]

        for p in list_param:
            if p[1]:
                cursor.execute(f'UPDATE SearchUser SET {p[0]} = %s WHERE vk_id = %s;', (p[1], vk_id))

        now_time = str(datetime.now())
        cursor.execute('UPDATE SearchUser SET last_updated = %s WHERE vk_id = %s;', (now_time, vk_id))
        conn.commit()
        cursor.close()
        conn.close()

    # функция удаления избранного кандидата для пользователя из таблицы Favorites
    def delete_favorite(self, favorite_vk_id:int, user_vk_id: int):
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        DELETE FROM favorites
        WHERE searchUserId = %s AND userId = %s;
        ''', (favorite_vk_id, user_vk_id,))

        conn.commit()
        cursor.close()
        conn.close()

    # функция удаления найденного кандидата из таблицы SearchUser
    def delete_searchuser(self, vk_id:int):
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        DELETE FROM SearchUser
        WHERE vk_id = %s;
        ''', (vk_id,))

        conn.commit()
        cursor.close()
        conn.close()

    def delete_all_data(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        DELETE FROM Favorites;
        DELETE FROM Users;
        DELETE FROM SearchUser;
        DELETE FROM BlackList;
        ''')

        conn.commit()
        cursor.close()
        conn.close()


    #функция проверки наличия пользователя в таблице SearchUser
    def is_exist_searchuser(self, vk_id):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT TRUE FROM SearchUser WHERE vk_id = %s', (vk_id,))

        answer = cursor.fetchall()
        if answer:
            res = True
        else:
            res = False

        conn.commit()
        cursor.close()
        conn.close()

        return res

    #функция проверки наличия пользователя в таблице Favorites
    def is_exist_favorite(self, favorite_vk_id:int, user_vk_id: int):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT TRUE FROM Favorites 
        WHERE searchUserId = %s AND userId= %s
        ''', (favorite_vk_id, user_vk_id,))

        answer = cursor.fetchall()
        if answer:
            res = True
        else:
            res = False

        conn.commit()
        cursor.close()
        conn.close()

        return res

    #функция проверки наличия пользователя в таблице Users
    def is_exist_user(self, vk_id):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT TRUE FROM Users WHERE vk_id = %s', (vk_id,))

        answer = cursor.fetchall()
        if answer:
            res = True
        else:
            res = False

        conn.commit()
        cursor.close()
        conn.close()

        return res

    # функция проверки наличия пользователя в таблице BlackList
    def is_exist_blackuser(self, user_vk_id: int, blacklist_vk_id: int):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
           SELECT TRUE FROM BlackList
           WHERE user_id = %s AND blackuser_id= %s
           ''', (user_vk_id, blacklist_vk_id, ))

        answer = cursor.fetchall()
        if answer:
            res = True
        else:
            res = False

        conn.commit()
        cursor.close()
        conn.close()

        return res
