# Отчёт по Sprint 2 (Итерация 2)
**Проект:** Smart University Admissions Assistant (Интеллектуальный портал приёмной комиссии SDU)  
**Команда:** Arman, Saken, Collaborators  
**Период:** Октябрь 2026  
**Репозиторий:** [GitHub: QazaKod/PM](https://github.com/QazaKod/PM)  
**Статус тестов:** 79 / 79 PASS (100%)  

---

## 1. Цели и скоуп Спринта 2 (Sprint Goal)

Основная цель Спринта 2 — **переход от простого прототипа к полноценной enterprise-архитектуре**:
1. Перевод хранилища данных со статических JSON-файлов на реляционную СУБД (**SQLite + SQLAlchemy ORM**).
2. Реализация защищенной системы аутентификации, авторизации и ролевого доступа (**RBAC**, JWT, хеширование паролей bcrypt).
3. Разработка персонального кабинета абитуриента (профиль, история чатов, избранные программы).
4. Создание административной панели управления данными (**SQLAdmin**) с защищенным входом.
5. Реализация двухканальной системы сброса паролей (**Email / SMTP + официальный Telegram-бот @sdu_admissions_registration_bot**).
6. Внедрение улучшений в чат-бот: контекстная память, слот-филлинг, поддержка трех языков (EN, RU, KK).
7. Покрытие функционала сквозными тестами (**79 automated tests**).

---

## 2. Реализованные User Stories и задачи

### 👤 Модуль аутентификации и профилей (Account & Auth System)
* **Регистрация и Вход (JWT + RBAC):**
  - Поддержка ролей `applicant` и `admin`.
  - Валидация сложности паролей, подтверждение пароля (`confirm_password`), валидация корректности формата email.
  - Международная валидация телефонного номера (+7 / от 10 до 15 цифр).
  - Интерактивные кнопки «показать/скрыть пароль» (👁️ / 🙈) в модальных окнах интерфейса.
* **Профиль абитуриента:**
  - Поля: гражданство (`domestic` / `international`), уровень обучения (`undergraduate` / `graduate`), баллы ЕНТ (0–140), сертификат IELTS (0.0–9.0), номер телефона.
  - Связка с чат-ботом: бот автоматически подставляет параметры профиля в контекст диалога для персонализированных ответов по требованиям.
* **Закладки (Favorites) и сохранение сессий:**
  - Возможность отмечать программы звездочкой (★) с сохранением в БД.
  - Автоматическое сохранение истории переписки в `chat_sessions` и `chat_messages`.

---

### 🔑 Система восстановления пароля и Telegram-бот
* **Двухканальное восстановление:**
  - Генерация безопасных 6-значных кодов с ограничением времени действия (15 минут) и защитой от повторного использования.
  - **Канал Email (SMTP):** отправка кодов на почту пользователя.
  - **Канал Telegram:** мгновенная доставка через официального бота [@sdu_admissions_registration_bot](https://t.me/sdu_admissions_registration_bot).
* **Deep Linking и интеграция Telegram:**
  - Генерация ссылок прямого запуска: `https://t.me/sdu_admissions_registration_bot?start=reset_<CODE>`.
  - При нажатии кнопки на сайте открывается бот, после команды `/start` бот валидирует код в базе, связывает `telegram_chat_id` с аккаунтом и отправляет код подтверждения.
  - Фоновый асинхронный поллер (`start_telegram_polling`) встроен в `lifespan` FastAPI и запускается в едином процессе через `start.bat` (без необходимости сторонних сервисов вроде ngrok).
  - Поддержка вебхуков (`/auth/telegram-webhook`).
  - **Безопасность токена:** токен бота защищен и исключен из публичного репозитория GitHub; для членов команды реализован автоматический fallback при запуске `start.bat`.

---

### 🗄️ Миграция базы данных и панель управления (SQLAdmin)
* **ORM-модели (SQLAlchemy):**
  - `User`, `ApplicantProfile`, `SavedProgram`
  - `Program`, `FAQ`, `Requirement`
  - `PasswordResetToken`
  - `ChatSession`, `ChatMessage`
* **Панель SQLAdmin (`/admin`):**
  - Защищена сессионной авторизацией администратора (`AdminAuth`).
  - CRUD-интерфейсы с фильтрацией и поиском для всех ключевых сущностей.
  - Раздел «Logs Admin» для оперативного мониторинга событий сервера.

---

### 💬 Требования к поступлению и Чат-бот (US3, US4, US5)
* **US3 (Admission Requirements):** 
  - Разделение требований по матрице `Категория × Уровень × Тематика` (domestic/international × undergraduate/graduate × exams/prerequisites/language).
  - Мультиязычные тексты ответов (`text_en`, `text_ru`, `text_kk`).
  - Диалоговая память: слот-филлинг и удержание контекста при уточняющих вопросах.
* **US4 (Required Documents):** 
  - Интерактивный чеклист с подсчетом процента готовности документов и сохранением прогресса в `localStorage`.
* **US5 (Admission FAQ):**
  - Динамическая загрузка данных из СУБД с аккордеонами и фильтрацией по ключевым словам.
  - Быстрая кнопка «💬 Ask this in Chat» для мгновенной пересылки вопроса в диалог.
  - Исправлен баг функции экранирования `escapeJs` и добавлена кнопка повторной попытки «🔄 Try Again».

---

## 3. Архитектура системы

```mermaid
flowchart TD
    Client["Пользовательский браузер (SPA / HTML5 / CSS3 / JS)"]
    TGBot["Telegram App / @sdu_admissions_registration_bot"]
    
    subgraph Backend ["FastAPI Backend (Port 8000)"]
        RouterAuth["Auth Router (/auth/*)"]
        RouterChat["Chat Router (/chat)"]
        RouterAdmin["SQLAdmin Panel (/admin)"]
        TGService["Telegram Polling Service (Background Async Task)"]
        ChatbotEngine["Hybrid Chat Engine (Local Intent + Gemini Fallback)"]
    end
    
    subgraph DataLayer ["Слой данных"]
        DB[("SQLite Database: data/app.db")]
        LogFile["app.log (UTF-8 Logging)"]
    end
    
    Client -->|HTTP REST / JWT| RouterAuth
    Client -->|WebSocket/POST JSON| RouterChat
    Client -->|Admin Session| RouterAdmin
    
    TGBot <-->|Telegram Bot API (Long Polling / Webhook)| TGService
    TGService -->|Validate Code / Save Chat ID| DB
    
    RouterAuth --> DB
    RouterChat --> ChatbotEngine
    ChatbotEngine --> DB
    RouterAdmin --> DB
    Backend --> LogFile
```

---

## 4. Метрики тестирования и качества

Покрытие тестами в рамках Спринта 2 расширено более чем в **3 раза**:

| Модуль тестов | Количество тестов | Статус | Проверяемый функционал |
| :--- | :---: | :---: | :--- |
| `test_api.py` | 5 | **PASS** | Базовые эндпоинты программ, FAQ, healthcheck |
| `test_auth.py` | 15 | **PASS** | Регистрация, дубликаты, валидация полей, JWT, профиль, избранное, сброс паролей через Email и Telegram Webhook |
| `test_chatbot.py` | 8 | **PASS** | Распознавание интентов, fallback, фильтрация стоп-слов, акронимы программ |
| `test_requirements.py` | 51 | **PASS** | Мультиязычность (EN/RU/KK), слот-филлинг, матрица категорий и уровней обучения |
| **ИТОГО:** | **79** | **PASS** | **100% прохождение всех автоматических тестов** |

---

## 5. Достигнутые результаты (Deliverables)

1. **Рабочий сервис «под ключ»:** запуск одной командой через `start.bat` поднимает веб-сервер, базу данных, интерфейс и Telegram-бота без внешних зависимостей.
2. **Живой Telegram-бот:** зарегистрирован и функционирует официальный бот [@sdu_admissions_registration_bot](https://t.me/sdu_admissions_registration_bot).
3. **Безопасность:**
   - Хеширование паролей алгоритмом bcrypt с солью.
   - Защита токенов авторизации через JWT.
   - Изоляция секретных ключей от публичного репозитория GitHub.
4. **Чистый код и документация:**
   - Проект организован по стандартам FastAPI/SQLAlchemy.
   - Все изменения запушены в ветку `main` репозитория [GitHub: QazaKod/PM](https://github.com/QazaKod/PM).
