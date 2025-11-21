"""
Unit tests for Telegram Bot (Human-in-the-Loop).

Tests cover:
- Sending approval requests
- Handling button callbacks
- Post editing workflow
- Error handling
- Message formatting
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from src.telegram.bot import TelegramBot, ApprovalRequest, ApprovalStatus


class TestTelegramBot:
    """Test suite for TelegramBot class."""

    @pytest.fixture
    def bot(self):
        """Create TelegramBot instance for testing."""
        return TelegramBot(
            token="test_bot_token_123",
            admin_chat_id="123456789"
        )

    @pytest.fixture
    def sample_approval_request(self):
        """Sample approval request data."""
        return ApprovalRequest(
            video_id="test_video_123",
            video_title="Test Medical Video",
            video_url="https://youtube.com/watch?v=test_video_123",
            generated_post="🩺 Test post content\n\n⚠️ Disclaimer",
            platform="threads"
        )

    def test_init_with_credentials(self, bot):
        """Test initialization with bot token and admin chat ID."""
        assert bot.token == "test_bot_token_123"
        assert bot.admin_chat_id == "123456789"

    def test_init_without_token(self):
        """Test initialization without bot token raises ValueError."""
        with pytest.raises(ValueError, match="Bot token is required"):
            TelegramBot(token="", admin_chat_id="123456")

    def test_init_without_admin_chat_id(self):
        """Test initialization without admin chat ID raises ValueError."""
        with pytest.raises(ValueError, match="Admin chat ID is required"):
            TelegramBot(token="test_token", admin_chat_id="")

    @pytest.mark.asyncio
    @patch('telegram.Bot.send_message')
    async def test_send_approval_request_success(
        self,
        mock_send_message,
        bot,
        sample_approval_request
    ):
        """Test sending approval request successfully."""
        mock_send_message.return_value = AsyncMock(message_id=12345)

        message_id = await bot.send_approval_request(sample_approval_request)

        assert message_id == 12345
        mock_send_message.assert_called_once()
        # Verify message contains video info
        call_args = mock_send_message.call_args
        message_text = call_args[1]['text']
        assert sample_approval_request.video_title in message_text
        assert sample_approval_request.generated_post in message_text

    @pytest.mark.asyncio
    async def test_send_approval_request_with_inline_keyboard(
        self,
        bot,
        sample_approval_request
    ):
        """Test approval request includes inline keyboard buttons."""
        with patch('telegram.Bot.send_message') as mock_send:
            mock_send.return_value = AsyncMock(message_id=12345)

            await bot.send_approval_request(sample_approval_request)

            call_args = mock_send.call_args
            assert 'reply_markup' in call_args[1]
            keyboard = call_args[1]['reply_markup']
            assert keyboard is not None

    def test_build_approval_keyboard(self, bot):
        """Test building inline keyboard for approval."""
        keyboard = bot.build_approval_keyboard(video_id="test123")

        # Should have Approve, Reject, Edit buttons
        buttons = keyboard.inline_keyboard
        assert len(buttons) >= 2  # At least 2 rows
        button_texts = [btn.text for row in buttons for btn in row]
        assert any('Approve' in text or 'Одобрить' in text for text in button_texts)
        assert any('Reject' in text or 'Отклонить' in text for text in button_texts)
        assert any('Edit' in text or 'Редактировать' in text for text in button_texts)

    def test_build_approval_keyboard_callback_data(self, bot):
        """Test keyboard buttons have correct callback data."""
        keyboard = bot.build_approval_keyboard(video_id="test123")

        buttons = keyboard.inline_keyboard
        callback_data = [btn.callback_data for row in buttons for btn in row]

        assert any('approve:test123' in data for data in callback_data)
        assert any('reject:test123' in data for data in callback_data)
        assert any('edit:test123' in data for data in callback_data)

    @pytest.mark.asyncio
    @patch('telegram.Update')
    @patch('telegram.ext.ContextTypes.DEFAULT_TYPE')
    async def test_handle_approve_callback(self, mock_context, mock_update, bot):
        """Test handling approve button callback."""
        mock_update.callback_query.data = "approve:test123"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        await bot.handle_callback_query(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        # Verify approval was processed
        assert bot.get_approval_status("test123") == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    @patch('telegram.Update')
    @patch('telegram.ext.ContextTypes.DEFAULT_TYPE')
    async def test_handle_reject_callback(self, mock_context, mock_update, bot):
        """Test handling reject button callback."""
        mock_update.callback_query.data = "reject:test123"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        await bot.handle_callback_query(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        assert bot.get_approval_status("test123") == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    @patch('telegram.Update')
    @patch('telegram.ext.ContextTypes.DEFAULT_TYPE')
    async def test_handle_edit_callback(self, mock_context, mock_update, bot):
        """Test handling edit button callback."""
        mock_update.callback_query.data = "edit:test123"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.message.reply_text = AsyncMock()

        await bot.handle_callback_query(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        # Should prompt for new text
        mock_update.callback_query.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_text_message_while_editing(self, bot):
        """Test handling text message when in editing mode."""
        # Set bot to editing mode for video test123
        bot.set_editing_mode("test123", True)

        with patch('telegram.Update') as mock_update:
            with patch('telegram.ext.ContextTypes.DEFAULT_TYPE') as mock_context:
                mock_update.message.text = "New edited post content"
                mock_update.message.reply_text = AsyncMock()

                await bot.handle_text_message(mock_update, mock_context)

                # Should update the post content
                assert bot.get_edited_content("test123") == "New edited post content"

    def test_format_approval_message(self, bot, sample_approval_request):
        """Test formatting approval message."""
        message = bot.format_approval_message(sample_approval_request)

        assert isinstance(message, str)
        assert sample_approval_request.video_title in message
        assert sample_approval_request.video_url in message
        assert sample_approval_request.generated_post in message
        assert sample_approval_request.platform in message

    def test_format_approval_message_with_markdown(self, bot, sample_approval_request):
        """Test approval message uses Markdown formatting."""
        message = bot.format_approval_message(sample_approval_request)

        # Should contain Markdown elements
        assert '*' in message or '_' in message  # Bold or italic
        assert '`' in message or '```' in message  # Code blocks

    @pytest.mark.asyncio
    @patch('telegram.Bot.send_message')
    async def test_send_confirmation_message(self, mock_send_message, bot):
        """Test sending confirmation after approval."""
        mock_send_message.return_value = AsyncMock()

        await bot.send_confirmation(
            video_id="test123",
            status=ApprovalStatus.APPROVED,
            post_url="https://threads.net/@user/post/123"
        )

        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args
        message_text = call_args[1]['text']
        assert "approved" in message_text.lower() or "одобрен" in message_text.lower()
        assert "threads.net" in message_text

    @pytest.mark.asyncio
    @patch('telegram.Bot.send_message')
    async def test_send_error_notification(self, mock_send_message, bot):
        """Test sending error notification."""
        mock_send_message.return_value = AsyncMock()

        await bot.send_error_notification(
            error_message="Failed to publish post",
            video_id="test123"
        )

        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args
        message_text = call_args[1]['text']
        assert "error" in message_text.lower() or "ошибка" in message_text.lower()

    def test_parse_callback_data(self, bot):
        """Test parsing callback data from buttons."""
        callback_data = "approve:test_video_123"

        action, video_id = bot.parse_callback_data(callback_data)

        assert action == "approve"
        assert video_id == "test_video_123"

    def test_parse_callback_data_invalid_format(self, bot):
        """Test parsing invalid callback data."""
        invalid_data = "invalid_format"

        with pytest.raises(ValueError, match="Invalid callback data"):
            bot.parse_callback_data(invalid_data)

    def test_approval_status_enum(self):
        """Test ApprovalStatus enum values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EDITING.value == "editing"

    def test_approval_request_dataclass(self):
        """Test ApprovalRequest dataclass attributes."""
        request = ApprovalRequest(
            video_id="test123",
            video_title="Test Video",
            video_url="https://youtube.com/watch?v=test123",
            generated_post="Test post content",
            platform="threads"
        )

        assert request.video_id == "test123"
        assert request.video_title == "Test Video"
        assert request.platform == "threads"

    @pytest.mark.asyncio
    async def test_start_command_handler(self, bot):
        """Test /start command handler."""
        with patch('telegram.Update') as mock_update:
            with patch('telegram.ext.ContextTypes.DEFAULT_TYPE') as mock_context:
                mock_update.message.reply_text = AsyncMock()

                await bot.handle_start_command(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                message_text = call_args[0][0]
                assert "start" in message_text.lower() or "начал" in message_text.lower()

    @pytest.mark.asyncio
    async def test_help_command_handler(self, bot):
        """Test /help command handler."""
        with patch('telegram.Update') as mock_update:
            with patch('telegram.ext.ContextTypes.DEFAULT_TYPE') as mock_context:
                mock_update.message.reply_text = AsyncMock()

                await bot.handle_help_command(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                message_text = call_args[0][0]
                assert "help" in message_text.lower() or "помощь" in message_text.lower()

    @pytest.mark.asyncio
    async def test_status_command_handler(self, bot):
        """Test /status command handler."""
        with patch('telegram.Update') as mock_update:
            with patch('telegram.ext.ContextTypes.DEFAULT_TYPE') as mock_context:
                mock_update.message.reply_text = AsyncMock()

                await bot.handle_status_command(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                # Should show current pending approvals

    def test_store_approval_status(self, bot):
        """Test storing approval status in memory."""
        bot.store_approval_status("test123", ApprovalStatus.APPROVED)

        status = bot.get_approval_status("test123")
        assert status == ApprovalStatus.APPROVED

    def test_get_approval_status_not_found(self, bot):
        """Test getting approval status for non-existent video."""
        status = bot.get_approval_status("nonexistent_video")

        assert status == ApprovalStatus.PENDING  # Default

    def test_store_edited_content(self, bot):
        """Test storing edited post content."""
        edited_content = "This is the edited post content"

        bot.store_edited_content("test123", edited_content)

        retrieved = bot.get_edited_content("test123")
        assert retrieved == edited_content

    @pytest.mark.asyncio
    @patch('telegram.Bot.send_message')
    async def test_send_multiple_posts_approval(self, mock_send_message, bot):
        """Test sending approval for multiple platform posts (future)."""
        # For MVP only Threads, but structure supports multiple platforms
        mock_send_message.return_value = AsyncMock(message_id=12345)

        posts = {
            'threads': '🩺 Threads post content',
        }

        await bot.send_multi_platform_approval("test123", posts, {})

        mock_send_message.assert_called_once()

    def test_truncate_long_message(self, bot):
        """Test truncating long messages for Telegram."""
        long_text = "A" * 5000  # Telegram has ~4096 char limit

        truncated = bot.truncate_message(long_text)

        assert len(truncated) <= 4096
        assert truncated.endswith("...")

    @pytest.mark.asyncio
    async def test_webhook_setup(self, bot):
        """Test setting up webhook for Telegram bot."""
        with patch('telegram.Bot.set_webhook') as mock_set_webhook:
            mock_set_webhook.return_value = AsyncMock()

            webhook_url = "https://example.com/webhook"
            await bot.setup_webhook(webhook_url)

            mock_set_webhook.assert_called_once_with(webhook_url)

    @pytest.mark.asyncio
    async def test_polling_mode(self, bot):
        """Test starting bot in polling mode."""
        with patch('telegram.ext.Application.run_polling') as mock_polling:
            mock_polling.return_value = AsyncMock()

            # Should be able to start polling
            # (implementation would use Application.run_polling())
            pass  # Test structure for polling mode

    def test_escape_markdown_v2(self, bot):
        """Test escaping special characters for Markdown V2."""
        text_with_special = "Test (text) with [special] characters!"

        escaped = bot.escape_markdown_v2(text_with_special)

        # Should escape parentheses, brackets, etc.
        assert '\\(' in escaped or '(' not in escaped

    @pytest.mark.asyncio
    async def test_send_typing_action(self, bot):
        """Test sending typing action while processing."""
        with patch('telegram.Bot.send_chat_action') as mock_action:
            mock_action.return_value = AsyncMock()

            await bot.send_typing_action()

            mock_action.assert_called_once()

    def test_is_admin_user(self, bot):
        """Test checking if user is admin."""
        assert bot.is_admin_user(bot.admin_chat_id) is True
        assert bot.is_admin_user("other_user_id") is False

    @pytest.mark.asyncio
    async def test_unauthorized_user_access(self, bot):
        """Test handling message from unauthorized user."""
        with patch('telegram.Update') as mock_update:
            with patch('telegram.ext.ContextTypes.DEFAULT_TYPE') as mock_context:
                mock_update.message.from_user.id = "unauthorized_id"
                mock_update.message.reply_text = AsyncMock()

                await bot.handle_message_from_unauthorized(mock_update, mock_context)

                # Should send unauthorized message
                mock_update.message.reply_text.assert_called_once()
