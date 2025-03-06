# Foodgram

# О проекте

Foodgram— сайт, на котором пользователи могут публиковать свои рецепты, добавлять чужие рецепты в избранное и подписываться на публикации других авторов. Зарегистрированным пользователям также доступен сервис «Список покупок». Он позволяет создавать список продуктов, которые нужно купить для приготовления выбранных блюд.


# Как развернуть локально

    1. Клонируйте репозиторий Foodgram на локальную машину:

git clone https://github.com/NaughtyRaccoon/foodgram.git

    2. Запустить оркестрацию контейнеров:

docker compose -f docker-compose.production.yml up

    3. Сразу же соберите статику:

docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic
docker compose -f docker-compose.production.yml exec backend cp -r /app/collected_static/. /backend_static/static/

    4. Выполните миграции:

docker compose -f docker-compose.production.yml exec backend python manage.py migrate

    5. Заполните .env файл по образцу .env.example

    6. Перейдите по адресу http://127.0.0.1:7000/ в вашем браузере,чтобы увидеть приложение в действии.

Проект также запущен по адресу https://foodgrams.publicvm.com

Автор

    @NaughtyRaccoon
