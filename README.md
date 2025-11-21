# YouTube to Threads MVP 🎬 → 🧵

Автоматизированная система для создания и публикации постов в Threads на основе YouTube Shorts с human-in-the-loop модерацией через Telegram.

> **📖 [Полная инструкция по настройке и запуску → SETUP_RU.md](./SETUP_RU.md)**

## 🚀 Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repository_url>
cd youtube-threads-mvp

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env
# Отредактируйте .env и добавьте ваши API ключи

# 5. Инициализировать базу данных
python -c "from src.database.db import Database; Database().create_tables()"

# 6. Запустить
python main.py --check  # Проверить новые видео
```

**Статус разработки:** ✅ MVP готов (88% тестов проходит)
- ✅ YouTube детектор, транскрибер, модератор, генератор постов, Threads клиент
- ⏳ Telegram бот и оркестратор (в разработке)

## 📋 Особенности

- ✅ **YouTube RSS мониторинг** - автоматическое обнаружение новых видео
- ✅ **AI транскрипция** - youtube-transcript-api (приоритет) с fallback на Whisper
- ✅ **AI генерация контента** - Claude 3.5 Sonnet для создания постов
- ✅ **Guardrails** - проверка качества контента (длина, повторения, спам)
- ✅ **Human-in-the-Loop** - утверждение через Telegram бота
- ✅ **Threads публикация** - автоматическая публикация после одобрения
- ✅ **SQLite database** - хранение истории и статусов

## 🏗️ Архитектура

```
YouTube RSS Feed
    ↓
[Detector] Новые видео
    ↓
[Transcriber] youtube-transcript-api → Транскрипция
    ↓
[Moderator] Level 1: Проверка транскрипции
    ↓
[PostGenerator] Claude → Генерация поста
    ↓
[Moderator] Level 2: Проверка поста
    ↓
[Telegram Bot] Human approval
    ↓
[Threads Client] Публикация
    ↓
[Database] Сохранение результата
```

## 📁 Структура проекта

```
youtube-threads-mvp/
├── config/
│   ├── prompts/
│   │   └── threads.yaml          # Промпт для Threads
│   └── guardrails.yaml            # Правила модерации
│
├── src/
│   ├── youtube/
│   │   └── detector.py            # YouTube RSS детектор
│   ├── ai/
│   │   ├── transcriber.py         # Транскрипция (youtube-transcript-api)
│   │   ├── post_generator.py      # Генерация постов (Claude)
│   │   └── moderator.py           # Guardrails проверка
│   ├── social/
│   │   └── threads_client.py      # Threads API клиент
│   ├── telegram/
│   │   └── bot.py                 # Telegram бот для approval
│   ├── database/
│   │   ├── models.py              # SQLAlchemy модели
│   │   └── db.py                  # Database управление
│   └── workflow.py                # Главный оркестратор
│
├── tests/
│   ├── test_youtube_detector.py   # Тесты YouTube детектора
│   ├── test_transcriber_v2.py     # Тесты транскрибера
│   ├── test_post_generator.py     # Тесты генератора постов
│   ├── test_moderator.py          # Тесты модератора
│   ├── test_threads_client.py     # Тесты Threads клиента
│   ├── test_telegram_bot.py       # Тесты Telegram бота
│   ├── test_database.py           # Тесты БД
│   └── test_workflow.py           # Тесты workflow
│
├── .env.example                    # Пример конфигурации
├── requirements.txt                # Python зависимости
├── pytest.ini                      # Pytest конфигурация
└── README.md                       # Этот файл
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Установить зависимости
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env с вашими API ключами
nano .env
```

**Необходимые API ключи:**
- YouTube Channel ID
- Anthropic API key (Claude)
- Threads Access Token + User ID
- Telegram Bot Token + Admin Chat ID
- (Опционально) OpenAI API key для Whisper fallback

### 3. Запуск тестов

```bash
# Запустить все тесты
pytest

# Запустить с подробным выводом
pytest -v

# Запустить с покрытием кода
pytest --cov=src --cov-report=html

# Запустить конкретный тест файл
pytest tests/test_youtube_detector.py

# Запустить конкретный тест
pytest tests/test_youtube_detector.py::TestYouTubeDetector::test_parse_rss_feed_valid

# Запустить только unit тесты (без integration)
pytest -m "not integration"

# Запустить с замером времени
pytest --durations=10
```

## 🧪 Test-Driven Development (TDD)

Проект следует методологии TDD:

### Red → Green → Refactor

1. **RED Phase** ✅ - Написаны все юнит-тесты (DONE)
2. **GREEN Phase** 🏗️ - Написать минимальный код для прохождения тестов (TODO)
3. **REFACTOR Phase** 🔨 - Улучшить код без изменения поведения (TODO)

### Покрытие тестами

Текущие test suites:
- `test_youtube_detector.py` - 19 тестов (YouTube RSS парсинг)
- `test_transcriber_v2.py` - 21 тест (youtube-transcript-api + fallback)
- `test_post_generator.py` - 22 теста (Claude генерация)
- `test_moderator.py` - 24 теста (Guardrails проверка)
- `test_threads_client.py` - 23 теста (Threads API)
- `test_telegram_bot.py` - 25 тестов (Telegram бот)
- `test_database.py` - 20 тестов (Database операции)
- `test_workflow.py` - 24 теста (End-to-end workflow)

**Всего: ~178 тестов**

## 📊 Запуск с покрытием

```bash
# Генерировать HTML отчет покрытия
pytest --cov=src --cov-report=html

# Открыть отчет
open htmlcov/index.html
```

Цель: **>80% покрытие кода**

## 🔍 Структура тестов

Каждый тест следует AAA паттерну:
- **Arrange** - подготовка (fixtures)
- **Act** - действие (вызов функции)
- **Assert** - проверка (assertions)

Пример:
```python
def test_parse_rss_feed_valid(self, detector, mock_rss_feed):
    # Arrange
    detector = YouTubeDetector(channel_id="UCtest123")

    # Act
    videos = detector.parse_rss_feed(mock_rss_feed)

    # Assert
    assert len(videos) == 1
    assert videos[0].video_id == "abc123"
```

## 🛠️ Следующие шаги (Green Phase)

### Phase 1: Core Components
1. Реализовать `YouTubeDetector` (src/youtube/detector.py)
2. Реализовать `Transcriber` с youtube-transcript-api (src/ai/transcriber.py)
3. Реализовать `PostGenerator` с Claude (src/ai/post_generator.py)
4. Реализовать `Moderator` (src/ai/moderator.py)

### Phase 2: Integration
5. Реализовать `ThreadsClient` (src/social/threads_client.py)
6. Реализовать `TelegramBot` (src/telegram/bot.py)
7. Реализовать `Database` models (src/database/*)

### Phase 3: Orchestration
8. Реализовать `WorkflowOrchestrator` (src/workflow.py)
9. Создать main entry point (main.py)
10. Добавить CLI интерфейс

## 📝 Конфигурация

### Prompts (config/prompts/threads.yaml)
Настройка промптов для генерации контента под Threads:
- System prompt с правилами
- User prompt template
- Model parameters (temperature, max_tokens)

### Guardrails (config/guardrails.yaml)
Правила проверки качества контента:
- Минимальная/максимальная длина транскрипции
- Проверка на повторяющийся контент
- Детекция спам-паттернов
- Лимиты платформ (длина, хештеги, эмодзи)
- Severity weights для violations

## 🔐 Безопасность & Качество

- ✅ Никогда не commit `.env` файл
- ✅ Все API ключи в переменных окружения
- ✅ Guardrails проверяют качество контента (длина, спам)
- ✅ Human-in-the-loop для финальной проверки
- ✅ Автоматическое исправление minor issues (truncate, trim whitespace)

## 🐛 Debugging

```bash
# Запустить тесты с pdb при ошибке
pytest --pdb

# Показать print statements
pytest -s

# Запустить только failed тесты
pytest --lf

# Verbose output с полными tracebacks
pytest -vv --tb=long
```

## 📚 Документация API

### YouTube Detector
```python
from src.youtube.detector import YouTubeDetector

detector = YouTubeDetector(channel_id="UCtest123")
new_videos = detector.check_for_new_videos(hours=24)
```

### Transcriber
```python
from src.ai.transcriber import Transcriber

transcriber = Transcriber()
transcript = transcriber.transcribe(video_id="abc123", language="ru")
```

### Post Generator
```python
from src.ai.post_generator import PostGenerator

generator = PostGenerator(api_key="sk-ant-...")
post = generator.generate_post(transcript="...", platform="threads")
```

## 🤝 Contribution Guidelines

1. Все новые фичи должны иметь тесты (TDD)
2. Код должен проходить `black`, `isort`, `flake8`
3. Покрытие тестами >80%
4. Документировать public методы

## 📄 Лицензия

MIT

## 👤 Автор

Создано с ❤️ для автоматизации медицинского контента

---

**Status:** 🏗️ В разработке (MVP)
**Phase:** ✅ RED (Tests Written) → 🔄 GREEN (Implementation) → ⏳ REFACTOR
