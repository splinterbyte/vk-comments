# parser.py

import time
import requests
import re

# --- Настройки ---
ACCESS_TOKEN = 'vk1.a.tq9Zm8PrUXYWGcmYlkdIsMmt2xW7vruGUWpc4ghwuwejLBJkDe9GhvlXrGiX8Mw5a0k1rW3jC1o5Kvi2kP6W-wC2d50JB9luFerjVOWWkYk8F-w_m-r3Qf-OjGaIR5kG3oKsvVnOKGuLzVh4Mu3gOdcuUDCIChzULxfwTN4E2r9_qM58BRjYr1mtmgVd2wk1lJEac1UPojQuCGvhM5gMyw'
VERSION = '5.199'

def get_latest_posts(owner_id, count=100, offset=0):
    print(f"[PARSER] Получаю {count} постов с offset={offset}")

    url = 'https://api.vk.com/method/wall.get'
    params = {
        'access_token': ACCESS_TOKEN,
        'owner_id': owner_id,
        'v': VERSION,
        'count': count,
        'offset': offset
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        if 'response' in data:
            post_count = len(data['response']['items'])
            print(f"[PARSER] Найдено постов: {post_count}")
            return data['response']['items']
        else:
            print(f"[ERROR] wall.get вернул ошибку: {data}")
            return []
    except Exception as e:
        print(f"[ERROR] Ошибка при получении постов: {e}")
        return []

def get_all_comments(owner_id, post_id, count=100):
    time.sleep(0.5)
    url = 'https://api.vk.com/method/wall.getComments' 
    params_base = {
        'access_token': ACCESS_TOKEN,
        'owner_id': owner_id,
        'post_id': post_id,
        'v': VERSION
    }

    all_comments = []
    limit_per_page = 20  # Максимум 20 комментариев за один запрос
    for offset in range(0, count, limit_per_page):
        params = params_base.copy()
        params['count'] = limit_per_page
        params['offset'] = offset

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if 'response' in data:
                items = data['response']['items']
                all_comments.extend(items)
                print(f"[PARSER] Найдено комментариев (пакет {offset}-{offset+limit_per_page}): {len(items)}")
            else:
                print(f"[ERROR] wall.getComments для post_id={post_id} вернул ошибку: {data}")
                break

              # Пауза между пакетами

        except Exception as e:
            print(f"[ERROR] Ошибка при получении комментариев (post_id={post_id}): {e}")
            break

    print(f"[PARSER] Всего комментариев к посту {post_id}: {len(all_comments)}")
    return all_comments

def get_thread_replies(owner_id, post_id, comment_id, count=100):
    """Получает ответы на конкретный комментарий"""
    print(f"[PARSER] Получаю ответы на комментарий ID={comment_id}")
    url = 'https://api.vk.com/method/wall.getComments'   
    params = {
        'access_token': ACCESS_TOKEN,
        'owner_id': owner_id,
        'post_id': post_id,
        'v': VERSION,
        'count': count,
        'comment_id': comment_id  # <-- Ответы к этому комментарию
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if 'response' in data and 'items' in data['response']:
            replies = data['response']['items']
            reply_count = len(replies)
            print(f"[PARSER] Найдено ответов на комментарий {comment_id}: {reply_count}")
            return replies
        else:
            print(f"[PARSER] Нет ответов на комментарий {comment_id}")
            return []
    except Exception as e:
        print(f"[ERROR] Ошибка при получении вложенных комментариев (comment_id={comment_id}): {e}")
        return []

def process_comment(comment, tags, seen_comments, owner_id, post_id):
    comment_id = comment.get('id')
    if not comment_id or comment_id in seen_comments:
        return None

    seen_comments.add(comment_id)

    text = comment.get('text', '')
    from_id = comment.get('from_id')

    if from_id == owner_id:
        print(f"[PARSER] Пропущен комментарий от владельца ({from_id})")
        return None

    matched_tags = []
    for tag in tags:
        pattern = r'\b' + re.escape(tag) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            print(f"[MATCH] Совпадение найдено: '{tag}' в тексте '{text[:50]}...'")
            matched_tags.append(tag)

    if matched_tags:
        post_link = f"https://vk.com/wall{owner_id}_{post_id}"
        comment_link = f"https://vk.com/wall{owner_id}_{post_id}?reply={comment_id}"

        result = {
            "text": text,
            "tags": ', '.join(matched_tags),
            "post_link": post_link,
            "comment_link": comment_link
        }
        print(f"[RESULT] Новое совпадение: {result}")
        return result
    return None

def run_parser():
    print("[PARSER] Запуск парсера...")
    owner_id = -33197055
    output = []

    with open('keywords.txt', 'r', encoding='utf-8') as file:
        tags = [line.strip() for line in file if line.strip()]
    print(f"[PARSER] Загружены теги: {tags}")

    seen_comments = set()

    # Получаем до 500 постов (по 100 за раз)
    total_posts = 100
    posts_per_page = 100
    all_posts = []

    for offset in range(0, total_posts, posts_per_page):
        print(f"[PARSER] Загрузка постов с offset={offset}")
        posts = get_latest_posts(owner_id, count=posts_per_page, offset=offset)
        if not posts:
            print(f"[PARSER] Больше нет постов, остановка на offset={offset}")
            break
        all_posts.extend(posts)

    print(f"[PARSER] Всего загружено постов: {len(all_posts)}")

    for i, post in enumerate(all_posts, 1):
        post_id = post['id']
        print(f"[PARSER] Обрабатывается пост #{i} (ID: {post_id})")

        comments = get_all_comments(owner_id, post_id, count=100)
        for comment in comments:
            res = process_comment(comment, tags, seen_comments, owner_id, post_id)
            if res:
                output.append(res)

            replies = get_thread_replies(owner_id, post_id, comment['id'], count=100)
            for reply in replies:
                res = process_comment(reply, tags, seen_comments, owner_id, post_id)
                if res:
                    output.append(res)

        # Пауза после обработки поста
        time.sleep(1)

    print(f"[PARSER] Парсер завершён. Найдено совпадений: {len(output)}")
    return output