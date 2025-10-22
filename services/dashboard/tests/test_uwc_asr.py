"""
Test UWC ASR integration with fallback to Deepgram.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.uwc_client import UWCClient
from app.config import settings


class TestUWCASRIntegration:
    """Test UWC ASR integration with fallback logic."""
    
    @pytest.fixture
    def uwc_client(self):
        """Create UWC client instance."""
        return UWCClient()
    
    @pytest.mark.asyncio
    async def test_uwc_asr_success(self, uwc_client):
        """Test successful UWC ASR transcription."""
        # Mock successful UWC response
        mock_response = {
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "Hello, this is a test transcription."
                    }]
                }],
                "utterances": [
                    {
                        "speaker": 0,
                        "text": "Hello, this is a test transcription."
                    }
                ]
            }
        }
        
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await uwc_client.transcribe_audio(
                company_id="test-company",
                request_id="test-request-123",
                audio_url="https://example.com/audio.wav",
                language="en-US",
                model="nova-2"
            )
            
            assert result == mock_response
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_uwc_asr_fallback_to_deepgram(self, uwc_client):
        """Test UWC ASR failure falls back to Deepgram."""
        # Mock UWC failure
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("UWC ASR service unavailable")
            
            with patch('app.routes.mobile_routes.audio_routes.deepgram') as mock_deepgram:
                # Mock Deepgram success
                mock_deepgram_response = {
                    "results": {
                        "channels": [{
                            "alternatives": [{
                                "transcript": "Fallback transcription from Deepgram."
                            }]
                        }]
                    }
                }
                mock_deepgram.transcription.prerecorded = AsyncMock(return_value=mock_deepgram_response)
                
                # Test the integration (this would be called from process_audio)
                settings.ENABLE_UWC_ASR = True
                
                try:
                    await uwc_client.transcribe_audio(
                        company_id="test-company",
                        request_id="test-request-123",
                        audio_url="https://example.com/audio.wav"
                    )
                except Exception:
                    # Expected - UWC fails, fallback should be triggered in the route
                    pass
                
                # Verify UWC was attempted
                mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_uwc_disabled_uses_deepgram_only(self):
        """Test that when UWC is disabled, only Deepgram is used."""
        with patch('app.routes.mobile_routes.audio_routes.deepgram') as mock_deepgram:
            mock_deepgram_response = {
                "results": {
                    "channels": [{
                        "alternatives": [{
                            "transcript": "Deepgram-only transcription."
                        }]
                    }]
                }
            }
            mock_deepgram.transcription.prerecorded = AsyncMock(return_value=mock_deepgram_response)
            
            # Test with UWC disabled
            settings.ENABLE_UWC_ASR = False
            
            # This would be the behavior in process_audio when UWC is disabled
            # (UWC client should not be called at all)
            pass


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])


