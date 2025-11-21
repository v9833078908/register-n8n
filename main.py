#!/usr/bin/env python3
"""
YouTube to Threads MVP - Main Entry Point

Автоматическая система для кросспостинга YouTube Shorts в Threads.
"""
import os
import sys
import time
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()

# Импорт компонентов
from src.database.db import Database
from src.youtube.detector import YouTubeDetector
from src.ai.transcriber import Transcriber
from src.ai.moderator import Moderator
from src.ai.post_generator import PostGenerator
from src.social.threads_client import ThreadsClient

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'youtube_threads.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class YouTubeThreadsBot:
    """Главный класс бота для автоматизации YouTube → Threads."""

    def __init__(self):
        """Инициализация компонентов бота."""
        logger.info("🚀 Инициализация YouTube→Threads MVP...")

        # Проверка переменных окружения
        self._validate_env_vars()

        # Инициализация компонентов
        self.db = Database(os.getenv('DATABASE_URL', 'sqlite:///./youtube_threads_mvp.db'))
        self.youtube = YouTubeDetector(os.getenv('YOUTUBE_CHANNEL_ID'))
        self.transcriber = Transcriber(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            use_youtube_captions=os.getenv('USE_YOUTUBE_CAPTIONS', 'true').lower() == 'true',
            enable_whisper_fallback=os.getenv('ENABLE_WHISPER_FALLBACK', 'false').lower() == 'true'
        )
        self.moderator = Moderator(config_path='config/guardrails.yaml')
        self.post_generator = PostGenerator(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            prompts_dir='config/prompts'
        )
        self.threads_client = ThreadsClient(
            access_token=os.getenv('THREADS_ACCESS_TOKEN'),
            user_id=os.getenv('THREADS_USER_ID')
        )

        # Создание таблиц БД
        self.db.create_tables()
        logger.info("✅ Все компоненты инициализированы")

    def _validate_env_vars(self):
        """Проверка обязательных переменных окружения."""
        required_vars = [
            'YOUTUBE_CHANNEL_ID',
            'ANTHROPIC_API_KEY',
            'THREADS_ACCESS_TOKEN',
            'THREADS_USER_ID'
        ]

        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            logger.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing)}")
            logger.error("Скопируйте .env.example в .env и заполните данные!")
            sys.exit(1)

    def process_video(self, video_url: str) -> None:
        """
        Обработать конкретное видео.

        Args:
            video_url: URL видео YouTube
        """
        logger.info(f"📹 Обработка видео: {video_url}")

        try:
            # Извлечь video_id
            video_id = self.transcriber.extract_video_id(video_url)
            logger.info(f"Video ID: {video_id}")

            # Получить транскрипцию
            logger.info("📝 Извлечение транскрипции...")
            transcript_result = self.transcriber.transcribe(video_id)
            logger.info(f"✅ Транскрипция получена: {transcript_result.word_count} слов")

            # Проверка качества транскрипции
            logger.info("🛡️ Проверка качества контента...")
            moderation_result = self.moderator.check_transcript(transcript_result.text)

            if not moderation_result.is_safe:
                logger.warning(f"⚠️ Транскрипция не прошла модерацию: {moderation_result.reason}")
                print(f"\n❌ Видео не прошло модерацию:")
                for violation in moderation_result.violations:
                    print(f"  - {violation}")
                return

            logger.info("✅ Транскрипция прошла проверку качества")

            # Генерация постов
            logger.info("🤖 Генерация постов через Claude...")
            video_metadata = {
                'title': f'Video {video_id}',
                'video_id': video_id,
                'url': video_url
            }

            post = self.post_generator.generate_post(
                transcript=transcript_result.text,
                platform='threads',
                video_metadata=video_metadata
            )

            logger.info(f"✅ Пост сгенерирован: {len(post.content)} символов")

            # Проверка поста
            post_moderation = self.moderator.check_post(post.content, platform='threads')

            if not post_moderation.is_safe:
                logger.warning(f"⚠️ Пост не прошёл модерацию: {post_moderation.reason}")
                print(f"\n⚠️ Пост не прошёл модерацию:")
                for violation in post_moderation.violations:
                    print(f"  - {violation}")

            # Вывод результата
            print("\n" + "="*60)
            print("📱 СГЕНЕРИРОВАННЫЙ ПОСТ ДЛЯ THREADS")
            print("="*60)
            print(post.content)
            print("="*60)
            print(f"\n📊 Статистика:")
            print(f"  • Длина: {post.char_count} символов")
            print(f"  • Хештеги: {len(post.hashtags)} ({', '.join(post.hashtags[:3])}...)")
            print(f"  • Эмодзи: {post.emoji_count}")
            print(f"  • Статус модерации: {'✅ Безопасно' if post_moderation.is_safe else '⚠️ Требует проверки'}")

            # Подтверждение публикации
            if self._confirm_publish():
                logger.info("📤 Публикация в Threads...")
                result = self.threads_client.publish_post(post.content)

                if result.success:
                    logger.info(f"✅ Пост опубликован: {result.post_url}")
                    print(f"\n✅ Успешно опубликовано!")
                    print(f"🔗 Ссылка: {result.post_url}")
                else:
                    logger.error(f"❌ Ошибка публикации: {result.error_message}")
                    print(f"\n❌ Ошибка: {result.error_message}")
            else:
                logger.info("❌ Публикация отменена пользователем")
                print("\n❌ Публикация отменена")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки видео: {e}", exc_info=True)
            print(f"\n❌ Ошибка: {e}")

    def _confirm_publish(self) -> bool:
        """Запросить подтверждение публикации у пользователя."""
        print("\n📤 Опубликовать в Threads? (y/n): ", end='')
        response = input().strip().lower()
        return response in ['y', 'yes', 'д', 'да']

    def check_new_videos(self) -> None:
        """Проверить новые видео на канале."""
        logger.info("🔍 Проверка новых видео на YouTube...")

        try:
            check_interval = float(os.getenv('CHECK_INTERVAL_HOURS', '6'))
            videos = self.youtube.check_for_new_videos(hours=check_interval)

            if not videos:
                logger.info("📭 Новых видео не найдено")
                print("📭 Новых видео нет")
                return

            logger.info(f"📹 Найдено {len(videos)} новых видео")
            print(f"\n📹 Найдено новых видео: {len(videos)}")

            for i, video in enumerate(videos, 1):
                print(f"\n{i}. {video.title}")
                print(f"   🔗 {video.url}")
                print(f"   📅 {video.published_date}")

                # Проверка, не обработано ли уже
                existing = self.db.get_video_by_video_id(video.video_id)
                if existing:
                    logger.info(f"⏭️ Видео {video.video_id} уже обработано")
                    print(f"   ⏭️ Уже обработано")
                    continue

                # Добавление в БД
                self.db.add_video(
                    video_id=video.video_id,
                    title=video.title,
                    url=video.url,
                    published_date=video.published_date,
                    description=video.description,
                    thumbnail_url=video.thumbnail_url
                )

                print(f"   ✅ Добавлено в очередь обработки")

            print(f"\n💾 Добавлено в базу данных. Используйте команду для обработки:")
            print(f"   python main.py --process-pending")

        except Exception as e:
            logger.error(f"❌ Ошибка проверки видео: {e}", exc_info=True)
            print(f"❌ Ошибка: {e}")

    def process_pending_videos(self) -> None:
        """Обработать все видео в статусе NEW."""
        logger.info("🔄 Обработка видео из очереди...")

        videos = self.db.get_videos_by_status('NEW')

        if not videos:
            print("📭 Нет видео для обработки")
            return

        print(f"\n📹 Найдено видео в очереди: {len(videos)}")

        for i, video in enumerate(videos, 1):
            print(f"\n{'='*60}")
            print(f"Видео {i}/{len(videos)}: {video.title}")
            print('='*60)

            self.process_video(video.url)

            # Обновление статуса
            if self._should_continue():
                continue
            else:
                break

    def _should_continue(self) -> bool:
        """Спросить пользователя продолжать ли обработку."""
        print("\n▶️ Продолжить обработку следующего видео? (y/n): ", end='')
        response = input().strip().lower()
        return response in ['y', 'yes', 'д', 'да']

    def show_stats(self) -> None:
        """Показать статистику."""
        all_videos = self.db.get_all_videos()

        print("\n" + "="*60)
        print("📊 СТАТИСТИКА")
        print("="*60)
        print(f"Всего видео в базе: {len(all_videos)}")

        # Группировка по статусам
        from collections import Counter
        statuses = Counter(v.processing_status.value for v in all_videos)

        for status, count in statuses.items():
            print(f"  • {status}: {count}")

        # Последние видео
        print("\n📹 Последние 5 видео:")
        for video in all_videos[-5:]:
            print(f"  • {video.title[:50]}... [{video.processing_status.value}]")

    def run_auto_mode(self) -> None:
        """Запуск в автоматическом режиме (бесконечный цикл)."""
        logger.info("🤖 Запуск в автоматическом режиме...")
        check_interval_hours = float(os.getenv('CHECK_INTERVAL_HOURS', '6'))

        print(f"\n🤖 Автоматический режим запущен")
        print(f"⏰ Интервал проверки: каждые {check_interval_hours} ч")
        print(f"Нажмите Ctrl+C для остановки\n")

        try:
            while True:
                self.check_new_videos()
                # TODO: Автоматическая обработка (после реализации Telegram бота)

                # Ожидание
                logger.info(f"😴 Ожидание {check_interval_hours} часов до следующей проверки...")
                time.sleep(check_interval_hours * 3600)

        except KeyboardInterrupt:
            logger.info("🛑 Остановка по запросу пользователя")
            print("\n\n🛑 Остановлено")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description='YouTube to Threads MVP - Автоматический кросспостинг',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Обработать конкретное видео
  python main.py --video-url "https://www.youtube.com/watch?v=VIDEO_ID"

  # Проверить новые видео на канале
  python main.py --check

  # Обработать видео из очереди
  python main.py --process-pending

  # Показать статистику
  python main.py --stats

  # Автоматический режим (проверка каждые N часов)
  python main.py --auto
        """
    )

    parser.add_argument(
        '--video-url',
        help='URL видео для обработки'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Проверить новые видео на канале'
    )
    parser.add_argument(
        '--process-pending',
        action='store_true',
        help='Обработать видео из очереди'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Показать статистику'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Автоматический режим (бесконечный цикл)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Проверить один раз и выйти'
    )

    args = parser.parse_args()

    # Баннер
    print("""
╔═══════════════════════════════════════════════════════════╗
║     🎬 YouTube → Threads Automation MVP                  ║
║     Автоматический кросспостинг с AI                     ║
╚═══════════════════════════════════════════════════════════╝
    """)

    try:
        bot = YouTubeThreadsBot()

        if args.video_url:
            bot.process_video(args.video_url)

        elif args.check or args.once:
            bot.check_new_videos()

        elif args.process_pending:
            bot.process_pending_videos()

        elif args.stats:
            bot.show_stats()

        elif args.auto:
            bot.run_auto_mode()

        else:
            parser.print_help()
            print("\n💡 Для начала используйте: python main.py --check")

    except KeyboardInterrupt:
        print("\n\n👋 До свидания!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
