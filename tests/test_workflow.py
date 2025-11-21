"""
Unit tests for Main Workflow / Orchestrator.

Tests cover:
- End-to-end workflow integration
- Error handling and recovery
- State management
- Component coordination
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
from src.workflow import WorkflowOrchestrator, WorkflowStatus, WorkflowStep
from src.youtube.detector import Video
from src.ai.transcriber import TranscriptionResult
from src.ai.post_generator import GeneratedPost
from src.ai.moderator import ModerationResult, SafetyLevel
from src.social.threads_client import PublishResult


class TestWorkflowOrchestrator:
    """Test suite for WorkflowOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create WorkflowOrchestrator instance for testing."""
        return WorkflowOrchestrator(
            youtube_channel_id="UCtest123",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
            threads_access_token="test_threads_token",
            threads_user_id="test_threads_user",
            telegram_bot_token="test_telegram_token",
            telegram_admin_chat_id="123456789",
            db_url="sqlite:///:memory:"
        )

    @pytest.fixture
    def sample_video(self):
        """Sample video for testing."""
        return Video(
            video_id="test123",
            title="Test Medical Video",
            url="https://youtube.com/watch?v=test123",
            description="Test description",
            published_date=datetime.now(),
            thumbnail_url="https://i.ytimg.com/vi/test123/hq.jpg"
        )

    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript for testing."""
        return TranscriptionResult(
            text="Сегодня поговорим о витамине D. Это общая информация.",
            language="ru",
            source="youtube_captions"
        )

    @pytest.fixture
    def sample_generated_post(self):
        """Sample generated post for testing."""
        return GeneratedPost(
            platform='threads',
            content='🩺 Витамин D важен!\n\n⚠️ Это не медицинская рекомендация.',
            hashtags=['#здоровье'],
            emoji_count=2,
            char_count=100
        )

    def test_orchestrator_init(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator.youtube_channel_id == "UCtest123"
        assert orchestrator.youtube_detector is not None
        assert orchestrator.transcriber is not None
        assert orchestrator.post_generator is not None
        assert orchestrator.moderator is not None
        assert orchestrator.threads_client is not None
        assert orchestrator.telegram_bot is not None
        assert orchestrator.database is not None

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'check_for_new_videos')
    @patch.object(WorkflowOrchestrator, 'process_video')
    async def test_run_workflow_success(self, mock_process, mock_check, orchestrator, sample_video):
        """Test running full workflow successfully."""
        mock_check.return_value = [sample_video]
        mock_process.return_value = AsyncMock(return_value=WorkflowStatus.SUCCESS)

        result = await orchestrator.run_workflow()

        assert result.status == WorkflowStatus.SUCCESS
        mock_check.assert_called_once()
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'check_for_new_videos')
    async def test_run_workflow_no_new_videos(self, mock_check, orchestrator):
        """Test running workflow when no new videos."""
        mock_check.return_value = []

        result = await orchestrator.run_workflow()

        assert result.status == WorkflowStatus.NO_NEW_VIDEOS
        assert result.videos_processed == 0

    @patch('src.youtube.detector.YouTubeDetector.check_for_new_videos')
    def test_check_for_new_videos(self, mock_check, orchestrator, sample_video):
        """Test checking for new videos."""
        mock_check.return_value = [sample_video]

        videos = orchestrator.check_for_new_videos()

        assert len(videos) == 1
        assert videos[0].video_id == "test123"

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'transcribe_video')
    @patch.object(WorkflowOrchestrator, 'moderate_transcript')
    @patch.object(WorkflowOrchestrator, 'generate_post')
    @patch.object(WorkflowOrchestrator, 'moderate_post')
    @patch.object(WorkflowOrchestrator, 'send_for_approval')
    async def test_process_video_full_workflow(
        self,
        mock_approval,
        mock_moderate_post,
        mock_generate,
        mock_moderate_transcript,
        mock_transcribe,
        orchestrator,
        sample_video,
        sample_transcript,
        sample_generated_post
    ):
        """Test processing single video through all steps."""
        # Mock each step
        mock_transcribe.return_value = sample_transcript

        mock_moderate_transcript.return_value = ModerationResult(
            is_safe=True,
            safety_level=SafetyLevel.SAFE,
            violations=[]
        )

        mock_generate.return_value = sample_generated_post

        mock_moderate_post.return_value = ModerationResult(
            is_safe=True,
            safety_level=SafetyLevel.SAFE,
            violations=[],
            has_disclaimer=True
        )

        mock_approval.return_value = AsyncMock()

        result = await orchestrator.process_video(sample_video)

        assert result.status == WorkflowStatus.SUCCESS
        mock_transcribe.assert_called_once()
        mock_moderate_transcript.assert_called_once()
        mock_generate.assert_called_once()
        mock_moderate_post.assert_called_once()
        mock_approval.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'transcribe_video')
    @patch.object(WorkflowOrchestrator, 'moderate_transcript')
    async def test_process_video_unsafe_transcript(
        self,
        mock_moderate,
        mock_transcribe,
        orchestrator,
        sample_video,
        sample_transcript
    ):
        """Test processing video with unsafe transcript."""
        mock_transcribe.return_value = sample_transcript

        mock_moderate.return_value = ModerationResult(
            is_safe=False,
            safety_level=SafetyLevel.UNSAFE,
            violations=['Contains specific medical advice']
        )

        result = await orchestrator.process_video(sample_video)

        assert result.status == WorkflowStatus.BLOCKED_BY_GUARDRAILS
        assert 'unsafe transcript' in result.reason.lower()

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'transcribe_video')
    async def test_process_video_transcription_fails(
        self,
        mock_transcribe,
        orchestrator,
        sample_video
    ):
        """Test processing video when transcription fails."""
        mock_transcribe.side_effect = Exception("Transcription failed")

        result = await orchestrator.process_video(sample_video)

        assert result.status == WorkflowStatus.FAILED
        assert 'transcription' in result.reason.lower()

    def test_transcribe_video(self, orchestrator, sample_video, sample_transcript):
        """Test video transcription step."""
        with patch.object(orchestrator.transcriber, 'transcribe') as mock_transcribe:
            mock_transcribe.return_value = sample_transcript

            transcript = orchestrator.transcribe_video(sample_video)

            assert transcript.text is not None
            mock_transcribe.assert_called_once_with(
                video_id=sample_video.video_id,
                language="ru"
            )

    def test_moderate_transcript(self, orchestrator, sample_transcript):
        """Test transcript moderation step."""
        with patch.object(orchestrator.moderator, 'check_transcript') as mock_moderate:
            mock_moderate.return_value = ModerationResult(
                is_safe=True,
                safety_level=SafetyLevel.SAFE,
                violations=[]
            )

            result = orchestrator.moderate_transcript(sample_transcript.text)

            assert result.is_safe is True
            mock_moderate.assert_called_once()

    def test_generate_post(
        self,
        orchestrator,
        sample_video,
        sample_transcript,
        sample_generated_post
    ):
        """Test post generation step."""
        with patch.object(orchestrator.post_generator, 'generate_post') as mock_generate:
            mock_generate.return_value = sample_generated_post

            post = orchestrator.generate_post(
                transcript=sample_transcript.text,
                video=sample_video,
                platform='threads'
            )

            assert post.content is not None
            assert post.platform == 'threads'
            mock_generate.assert_called_once()

    def test_moderate_post(self, orchestrator, sample_generated_post):
        """Test post moderation step."""
        with patch.object(orchestrator.moderator, 'check_post') as mock_moderate:
            mock_moderate.return_value = ModerationResult(
                is_safe=True,
                safety_level=SafetyLevel.SAFE,
                violations=[],
                has_disclaimer=True
            )

            result = orchestrator.moderate_post(sample_generated_post)

            assert result.is_safe is True
            assert result.has_disclaimer is True
            mock_moderate.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_for_approval(
        self,
        orchestrator,
        sample_video,
        sample_generated_post
    ):
        """Test sending post for approval."""
        with patch.object(orchestrator.telegram_bot, 'send_approval_request') as mock_send:
            mock_send.return_value = AsyncMock(return_value=12345)

            message_id = await orchestrator.send_for_approval(
                video=sample_video,
                post=sample_generated_post
            )

            assert message_id == 12345
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_approved_post(
        self,
        orchestrator,
        sample_generated_post
    ):
        """Test publishing approved post."""
        with patch.object(orchestrator.threads_client, 'publish_post') as mock_publish:
            mock_publish.return_value = PublishResult(
                success=True,
                post_id='thread_123',
                post_url='https://threads.net/@user/post/thread_123',
                platform='threads'
            )

            result = await orchestrator.publish_post(sample_generated_post)

            assert result.success is True
            assert result.post_id is not None
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_post_failure(
        self,
        orchestrator,
        sample_generated_post
    ):
        """Test handling post publishing failure."""
        with patch.object(orchestrator.threads_client, 'publish_post') as mock_publish:
            mock_publish.side_effect = Exception("Publishing failed")

            with pytest.raises(Exception, match="Publishing failed"):
                await orchestrator.publish_post(sample_generated_post)

    def test_save_video_to_database(self, orchestrator, sample_video):
        """Test saving video to database."""
        with patch.object(orchestrator.database, 'add_video') as mock_add:
            mock_add.return_value = Mock(id=1, video_id="test123")

            video_record = orchestrator.save_video_to_database(sample_video)

            assert video_record.video_id == "test123"
            mock_add.assert_called_once()

    def test_save_transcript_to_database(self, orchestrator, sample_transcript):
        """Test saving transcript to database."""
        with patch.object(orchestrator.database, 'update_video_transcript') as mock_update:
            orchestrator.save_transcript_to_database(
                video_id=1,
                transcript=sample_transcript.text
            )

            mock_update.assert_called_once_with(1, sample_transcript.text)

    def test_save_post_to_database(
        self,
        orchestrator,
        sample_generated_post
    ):
        """Test saving post to database."""
        with patch.object(orchestrator.database, 'add_post') as mock_add:
            mock_add.return_value = Mock(id=1, platform='threads')

            post_record = orchestrator.save_post_to_database(
                video_id=1,
                post=sample_generated_post
            )

            assert post_record.platform == 'threads'
            mock_add.assert_called_once()

    def test_workflow_status_enum(self):
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.SUCCESS.value == "success"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.BLOCKED_BY_GUARDRAILS.value == "blocked_by_guardrails"
        assert WorkflowStatus.NO_NEW_VIDEOS.value == "no_new_videos"
        assert WorkflowStatus.PENDING_APPROVAL.value == "pending_approval"

    def test_workflow_step_enum(self):
        """Test WorkflowStep enum values."""
        assert WorkflowStep.CHECK_VIDEOS.value == "check_videos"
        assert WorkflowStep.TRANSCRIBE.value == "transcribe"
        assert WorkflowStep.MODERATE_TRANSCRIPT.value == "moderate_transcript"
        assert WorkflowStep.GENERATE_POST.value == "generate_post"
        assert WorkflowStep.MODERATE_POST.value == "moderate_post"
        assert WorkflowStep.SEND_APPROVAL.value == "send_approval"
        assert WorkflowStep.PUBLISH.value == "publish"

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'process_video')
    async def test_process_multiple_videos(
        self,
        mock_process,
        orchestrator,
        sample_video
    ):
        """Test processing multiple videos."""
        videos = [sample_video, sample_video]  # Two videos
        mock_process.return_value = AsyncMock(return_value=Mock(status=WorkflowStatus.SUCCESS))

        results = await orchestrator.process_multiple_videos(videos)

        assert len(results) == 2
        assert mock_process.call_count == 2

    def test_get_workflow_state(self, orchestrator):
        """Test getting current workflow state."""
        state = orchestrator.get_workflow_state()

        assert 'current_step' in state
        assert 'videos_in_queue' in state
        assert 'pending_approvals' in state

    def test_handle_error_logging(self, orchestrator):
        """Test error logging and handling."""
        error = Exception("Test error")
        video_id = "test123"

        with patch.object(orchestrator, 'log_error') as mock_log:
            orchestrator.handle_error(error, video_id=video_id, step="transcribe")

            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert "Test error" in str(call_args)

    @pytest.mark.asyncio
    async def test_retry_failed_video(self, orchestrator, sample_video):
        """Test retrying failed video processing."""
        with patch.object(orchestrator, 'process_video') as mock_process:
            mock_process.return_value = AsyncMock(return_value=Mock(status=WorkflowStatus.SUCCESS))

            result = await orchestrator.retry_video(sample_video.video_id)

            assert result.status == WorkflowStatus.SUCCESS
            mock_process.assert_called_once()

    def test_get_processing_statistics(self, orchestrator):
        """Test getting workflow processing statistics."""
        with patch.object(orchestrator.database, 'get_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_videos': 10,
                'total_posts': 10,
                'published_posts': 8
            }

            stats = orchestrator.get_statistics()

            assert stats['total_videos'] == 10
            assert stats['total_posts'] == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, orchestrator):
        """Test cleaning up old processed data."""
        with patch.object(orchestrator.database, 'delete_old_videos') as mock_delete:
            await orchestrator.cleanup_old_data(days=30)

            mock_delete.assert_called_once_with(days=30)

    def test_validate_configuration(self, orchestrator):
        """Test validating orchestrator configuration."""
        is_valid, errors = orchestrator.validate_configuration()

        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    @pytest.mark.asyncio
    @patch.object(WorkflowOrchestrator, 'check_for_new_videos')
    @patch.object(WorkflowOrchestrator, 'process_video')
    async def test_run_workflow_with_error_recovery(
        self,
        mock_process,
        mock_check,
        orchestrator,
        sample_video
    ):
        """Test workflow with error recovery."""
        mock_check.return_value = [sample_video]

        # First attempt fails, second succeeds
        mock_process.side_effect = [
            AsyncMock(return_value=Mock(status=WorkflowStatus.FAILED)),
            AsyncMock(return_value=Mock(status=WorkflowStatus.SUCCESS))
        ]

        result = await orchestrator.run_workflow_with_retry(max_retries=2)

        assert mock_process.call_count <= 2

    def test_calculate_workflow_duration(self, orchestrator):
        """Test calculating workflow execution duration."""
        start_time = datetime.now()
        # Simulate some processing
        end_time = datetime.now()

        duration = orchestrator.calculate_duration(start_time, end_time)

        assert duration >= 0
        assert isinstance(duration, float)
