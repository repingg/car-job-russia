"""
ИИ-АГЕНТ для сайта car-job-russia.ru
=====================================
Что делает этот скрипт:
1. Заходит на hh.ru и ищет вакансии по ключевым словам
2. Проверяет каждую вакансию через ИИ (Claude)
3. Фильтрует: только Россия, не старше 30 дней, без дубликатов
4. Сохраняет подходящие вакансии в базу данных Supabase
"""

import requests          # для отправки запросов к сайтам
import json              # для работы с данными в формате JSON
import time              # для пауз между запросами
from datetime import datetime, timedelta  # для работы с датами

# =============================================
# НАСТРОЙКИ АГЕНТА
# Объяснение: здесь хранятся все ключи и параметры.
# В реальной работе они берутся из секретных переменных GitHub.
# =============================================

# Ключи доступа (берутся из переменных окружения GitHub)
import os
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')  # ключ Claude
SUPABASE_URL      = os.environ.get('SUPABASE_URL', '')       # адрес базы данных
SUPABASE_KEY      = os.environ.get('SUPABASE_KEY', '')       # ключ базы данных

# Ключевые слова для поиска на hh.ru
# Агент будет искать по каждому слову отдельно
KEYWORDS = [
    'детейлинг',
    'детейлер',
    'PPF плёнка',
    'оклейка автомобилей',
    'PDR мастер',
    'удаление вмятин без покраски',
    'покраска дисков',
    'тонировка автомобилей',
    'полировка кузова',
    'шумоизоляция автомобиля',
    'vinyl wrap',
    'керамическое покрытие автомобиль',
]

# Страны которые НЕ берём
EXCLUDED_COUNTRIES = ['Беларусь', 'Казахстан', 'Украина', 'Узбекистан', 'Армения']

# Максимальный возраст вакансии в днях
MAX_AGE_DAYS = 30


# =============================================
# ШАГ 1: ПОЛУЧАЕМ ВАКАНСИИ С HH.RU
# Объяснение: hh.ru имеет открытый API — специальный
# интерфейс для программ. Мы используем его чтобы
# получать вакансии в удобном формате (JSON).
# =============================================

def search_hh(keyword, page=0):
    """
    Ищет вакансии на hh.ru по ключевому слову.
    Возвращает список вакансий.
    """
    url = 'https://api.hh.ru/vacancies'
    
    params = {
        'text': keyword,          # ключевое слово поиска
        'area': 113,              # 113 = Россия в системе hh.ru
        'per_page': 20,           # сколько вакансий за один запрос
        'page': page,             # номер страницы
        'order_by': 'publication_time',  # сортировка по дате
        'date_from': (datetime.now() - timedelta(days=MAX_AGE_DAYS)).strftime('%Y-%m-%d'),
    }
    
    headers = {
        'User-Agent': 'CarJobRussia/1.0 (car-job-russia.ru)'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f'  Найдено по "{keyword}": {data["found"]} вакансий')
            return data.get('items', [])
        else:
            print(f'  Ошибка hh.ru: статус {response.status_code}')
            return []
            
    except Exception as e:
        print(f'  Ошибка запроса: {e}')
        return []


# =============================================
# ШАГ 2: ПОЛУЧАЕМ ДЕТАЛИ ВАКАНСИИ
# Объяснение: первый запрос даёт только краткую информацию.
# Нам нужно зайти на страницу каждой вакансии
# чтобы получить полное описание и требования.
# =============================================

def get_vacancy_details(vacancy_id):
    """
    Получает полную информацию о вакансии по её ID.
    Заодно проверяет что ссылка работает.
    """
    url = f'https://api.hh.ru/vacancies/{vacancy_id}'
    
    headers = {
        'User-Agent': 'CarJobRussia/1.0 (car-job-russia.ru)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()  # ссылка работает, данные получены
        elif response.status_code == 404:
            print(f'  Вакансия {vacancy_id} не найдена (удалена)')
            return None  # вакансия удалена
        else:
            print(f'  Ошибка получения вакансии {vacancy_id}: {response.status_code}')
            return None
            
    except Exception as e:
        print(f'  Ошибка: {e}')
        return None


# =============================================
# ШАГ 3: ПРОВЕРКА ЧЕРЕЗ ИИ (CLAUDE)
# Объяснение: мы отправляем описание вакансии Claude
# и спрашиваем: "Это авто-сфера? Отвечай только да/нет"
# Claude анализирует текст и даёт ответ.
# =============================================

def check_with_ai(title, description):
    """
    Спрашивает Claude: относится ли вакансия к авто-сфере?
    Возвращает True (да) или False (нет).
    """
    
    if not ANTHROPIC_API_KEY:
        print('  ИИ-проверка пропущена (нет ключа)')
        return True  # если нет ключа — пропускаем всё
    
    # Формируем вопрос для Claude
    prompt = f"""Ты помогаешь фильтровать вакансии для сайта по трудоустройству в автомобильной сфере.

Вакансия:
Название: {title}
Описание: {description[:500]}

Относится ли эта вакансия к автомобильной сфере? 
Подходящие направления: детейлинг, полировка, оклейка плёнкой (PPF/vinyl), 
удаление вмятин (PDR), покраска дисков, тонировка, шумоизоляция, 
керамическое покрытие, химчистка салона, антикоррозийная обработка.

Отвечай ТОЛЬКО одним словом: ДА или НЕТ"""

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-haiku-4-5-20251001',  # быстрая и дешёвая модель
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=15
        )
        
        if response.status_code == 200:
            answer = response.json()['content'][0]['text'].strip().upper()
            print(f'  ИИ говорит: {answer}')
            return 'ДА' in answer
        else:
            print(f'  Ошибка ИИ: {response.status_code}')
            return True  # если ошибка — не блокируем вакансию
            
    except Exception as e:
        print(f'  Ошибка ИИ: {e}')
        return True


# =============================================
# ШАГ 4: ПРОВЕРКА НА ДУБЛИКАТЫ
# Объяснение: спрашиваем нашу базу данных —
# есть ли уже вакансия с таким source_url?
# Если есть — пропускаем, не добавляем снова.
# =============================================

def is_duplicate(vacancy_url):
    """
    Проверяет есть ли уже такая вакансия в базе данных.
    Возвращает True если дубликат, False если новая.
    """
    try:
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/vacancies',
            params={'source_url': f'eq.{vacancy_url}', 'select': 'id'},
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return len(data) > 0  # если нашли — это дубликат
        return False
        
    except Exception as e:
        print(f'  Ошибка проверки дубликата: {e}')
        return False


# =============================================
# ШАГ 5: СОХРАНЯЕМ В БАЗУ ДАННЫХ
# Объяснение: отправляем данные вакансии в Supabase.
# После этого вакансия автоматически появится на сайте.
# =============================================

def save_to_database(vacancy_data):
    """
    Сохраняет вакансию в базу данных Supabase.
    """
    try:
        response = requests.post(
            f'{SUPABASE_URL}/rest/v1/vacancies',
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            },
            json=vacancy_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f'  ✅ Сохранено: {vacancy_data["title"]}')
            return True
        else:
            print(f'  ❌ Ошибка сохранения: {response.status_code} — {response.text}')
            return False
            
    except Exception as e:
        print(f'  ❌ Ошибка: {e}')
        return False


# =============================================
# ШАГ 6: ОПРЕДЕЛЯЕМ КАТЕГОРИЮ
# Объяснение: смотрим на название вакансии
# и определяем к какой категории она относится.
# =============================================

def get_category(title, description):
    """
    Определяет категорию вакансии по ключевым словам в названии.
    """
    text = (title + ' ' + description).lower()
    
    if any(w in text for w in ['детейлинг', 'детейлер', 'химчистка']):
        return 'Детейлинг'
    elif any(w in text for w in ['ppf', 'оклейк', 'vinyl', 'винил', 'плёнк', 'пленк']):
        return 'Оклейка / PPF'
    elif any(w in text for w in ['pdr', 'вмятин', 'рихтовк']):
        return 'PDR / Рихтовка'
    elif any(w in text for w in ['покраск', 'дисков', 'суппорт']):
        return 'Покраска дисков'
    elif any(w in text for w in ['тонировк', 'тониров']):
        return 'Тонировка'
    elif any(w in text for w in ['полировк', 'полиров']):
        return 'Полировка'
    elif any(w in text for w in ['шумоизол']):
        return 'Шумоизоляция'
    elif any(w in text for w in ['автоэлектр', 'электрик']):
        return 'Автоэлектрик'
    else:
        return 'Другое'


# =============================================
# ГЛАВНАЯ ФУНКЦИЯ — запускает всё по порядку
# =============================================

def main():
    print('🚀 Запускаем ИИ-агент Car Job Russia')
    print(f'📅 Время запуска: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
    print('=' * 50)
    
    saved_count = 0      # счётчик сохранённых вакансий
    checked_ids = set()  # уже проверенные ID вакансий (чтобы не дублировать внутри сессии)
    
    # Проходим по каждому ключевому слову
    for keyword in KEYWORDS:
        print(f'\n🔍 Ищем: "{keyword}"')
        
        vacancies = search_hh(keyword)
        
        for vacancy in vacancies:
            vacancy_id  = vacancy['id']
            vacancy_url = f'https://hh.ru/vacancy/{vacancy_id}'
            
            # Пропускаем если уже проверяли в этой сессии
            if vacancy_id in checked_ids:
                continue
            checked_ids.add(vacancy_id)
            
            print(f'\n  📋 Проверяем: {vacancy["name"]}')
            
            # ФИЛЬТР 1: Только Россия
            area = vacancy.get('area', {}).get('name', '')
            if any(country in area for country in EXCLUDED_COUNTRIES):
                print(f'  ⛔ Пропускаем — не Россия ({area})')
                continue
            
            # ФИЛЬТР 2: Проверка на дубликат
            if is_duplicate(vacancy_url):
                print(f'  ⛔ Пропускаем — уже есть в базе')
                continue
            
            # ФИЛЬТР 3: Получаем детали и проверяем ссылку
            details = get_vacancy_details(vacancy_id)
            if not details:
                print(f'  ⛔ Пропускаем — ссылка не работает')
                continue
            
            # Собираем описание
            description = ''
            if details.get('description'):
                # убираем HTML теги из описания
                import re
                description = re.sub('<[^<]+?>', ' ', details['description'])
                description = ' '.join(description.split())[:1000]
            
            # ФИЛЬТР 4: Проверка через ИИ
            if not check_with_ai(vacancy['name'], description):
                print(f'  ⛔ Пропускаем — не авто-сфера (ИИ)')
                continue
            
            # Всё проверено — готовим данные для сохранения
            salary      = details.get('salary') or {}
            salary_from = salary.get('from')
            salary_to   = salary.get('to')
            
            # Если зарплата в валюте — конвертируем примерно
            if salary.get('currency') == 'USD' and salary_from:
                salary_from = int(salary_from * 90)
                salary_to   = int(salary_to * 90) if salary_to else None
            
            # Требования из вакансии
            requirements = ''
            if details.get('key_skills'):
                requirements = '\n'.join([s['name'] for s in details['key_skills']])
            
            vacancy_data = {
                'title':        vacancy['name'],
                'company':      vacancy.get('employer', {}).get('name', ''),
                'salary_from':  salary_from,
                'salary_to':    salary_to,
                'city':         vacancy.get('area', {}).get('name', ''),
                'category':     get_category(vacancy['name'], description),
                'description':  description,
                'requirements': requirements,
                'source_url':   vacancy_url,
                'source_name':  'hh.ru',
                'is_active':    True,
            }
            
            # Сохраняем в базу данных
            if save_to_database(vacancy_data):
                saved_count += 1
            
            # Пауза между запросами — чтобы не перегружать серверы
            time.sleep(1)
        
        # Пауза между ключевыми словами
        time.sleep(2)
    
    print('\n' + '=' * 50)
    print(f'✅ Агент завершил работу')
    print(f'📊 Сохранено новых вакансий: {saved_count}')
    print(f'📅 Время: {datetime.now().strftime("%d.%m.%Y %H:%M")}')


# Запускаем главную функцию
if __name__ == '__main__':
    main()
