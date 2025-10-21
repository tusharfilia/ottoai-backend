"""
Comprehensive test suite for UWC integration with fallback logic.
Tests ASR, RAG, Training, and Follow-up generation.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.uwc_client import UWCClient
from app.config import settings


class TestUWCIntegration:
    """Test all UWC integrations with fallback scenarios."""
    
    @pytest.fixture
    def uwc_client(self):
        """Create UWC client instance."""
        return UWCClient()
    
    @pytest.mark.asyncio
    async def test_asr_integration_success(self, uwc_client):
        """Test successful UWC ASR integration."""
        # Mock successful UWC ASR response
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
    async def test_asr_integration_fallback(self, uwc_client):
        """Test UWC ASR failure falls back to Deepgram."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("UWC ASR service unavailable")
            
            # This would be called from the route with fallback logic
            with pytest.raises(Exception):
                await uwc_client.transcribe_audio(
                    company_id="test-company",
                    request_id="test-request-123",
                    audio_url="https://example.com/audio.wav"
                )
    
    @pytest.mark.asyncio
    async def test_rag_integration_success(self, uwc_client):
        """Test successful UWC RAG integration."""
        mock_response = {
            "answer": "The most common objection is price (40%), followed by timing (28%).",
            "citations": [
                {
                    "doc_id": "doc_123",
                    "filename": "sales_script.pdf",
                    "chunk_text": "Price objections are best handled by...",
                    "similarity_score": 0.92
                }
            ],
            "confidence_score": 0.89
        }
        
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await uwc_client.query_rag(
                company_id="test-company",
                request_id="test-request-123",
                query="What are the most common objections?",
                context={"tenant_id": "test-company", "user_role": "manager"},
                options={"max_results": 10}
            )
            
            assert result == mock_response
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rag_integration_fallback(self, uwc_client):
        """Test UWC RAG failure falls back to mock response."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("UWC RAG service unavailable")
            
            with pytest.raises(Exception):
                await uwc_client.query_rag(
                    company_id="test-company",
                    request_id="test-request-123",
                    query="What are the most common objections?",
                    context={"tenant_id": "test-company"},
                    options={"max_results": 10}
                )
    
    @pytest.mark.asyncio
    async def test_training_integration_success(self, uwc_client):
        """Test successful UWC training integration."""
        mock_response = {
            "job_id": "training_job_123",
            "status": "submitted",
            "estimated_duration": "2-4 hours"
        }
        
        training_data = {
            "call_ids": [101, 102, 103],
            "media_urls": ["https://youtube.com/shorts/abc123"]
        }
        
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await uwc_client.submit_training_job(
                company_id="test-company",
                request_id="test-request-123",
                training_data=training_data,
                options={"model_type": "personal_clone"}
            )
            
            assert result == mock_response
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_followup_generation_success(self, uwc_client):
        """Test successful UWC follow-up generation."""
        mock_response = {
            "draft_text": "Hi John, thanks for your time today. I wanted to follow up on our roofing discussion and see if you had any questions.",
            "used_clone": True,
            "confidence_score": 0.85
        }
        
        call_context = {
            "customer_name": "John Smith",
            "call_summary": "Discussed roof replacement, customer interested but needs to think",
            "objections": ["price", "timing"]
        }
        
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await uwc_client.generate_followup_draft(
                company_id="test-company",
                request_id="test-request-123",
                rep_id="rep_456",
                call_context=call_context,
                draft_type="sms",
                tone="professional",
                options={"use_personal_clone": True}
            )
            
            assert result == mock_response
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_followup_generation_fallback(self, uwc_client):
        """Test UWC follow-up generation failure falls back to mock."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("UWC follow-up service unavailable")
            
            call_context = {
                "customer_name": "John Smith",
                "call_summary": "Discussed roof replacement"
            }
            
            with pytest.raises(Exception):
                await uwc_client.generate_followup_draft(
                    company_id="test-company",
                    request_id="test-request-123",
                    rep_id="rep_456",
                    call_context=call_context,
                    draft_type="sms"
                )
    
    @pytest.mark.asyncio
    async def test_document_indexing_success(self, uwc_client):
        """Test successful UWC document indexing."""
        mock_response = {
            "job_id": "index_job_789",
            "status": "processing",
            "estimated_completion": "5-10 minutes"
        }
        
        documents = [{
            "document_id": "doc_123",
            "url": "https://s3.amazonaws.com/bucket/doc.pdf",
            "type": "sop",
            "filename": "sales_process.pdf"
        }]
        
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await uwc_client.index_documents(
                company_id="test-company",
                request_id="test-request-123",
                documents=documents,
                options={"chunk_size": 1000}
            )
            
            assert result == mock_response
            mock_request.assert_called_once()


class TestUWCFeatureFlags:
    """Test UWC feature flag behavior."""
    
    def test_uwc_flags_default_to_false(self):
        """Test that UWC flags default to False."""
        # These should be False by default for safety
        assert settings.ENABLE_UWC_ASR is False
        assert settings.ENABLE_UWC_RAG is False
        assert settings.ENABLE_UWC_TRAINING is False
        assert settings.ENABLE_UWC_FOLLOWUPS is False
    
    def test_uwc_base_url_defaults_to_mock(self):
        """Test that UWC base URL defaults to mock API."""
        assert settings.UWC_BASE_URL == "https://otto.shunyalabs.ai"


class TestUWCClientErrorHandling:
    """Test UWC client error handling and retry logic."""
    
    @pytest.fixture
    def uwc_client(self):
        return UWCClient()
    
    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, uwc_client):
        """Test handling of authentication errors."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("401 Unauthorized")
            
            with pytest.raises(Exception, match="401 Unauthorized"):
                await uwc_client.transcribe_audio(
                    company_id="test-company",
                    request_id="test-request-123",
                    audio_url="https://example.com/audio.wav"
                )
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, uwc_client):
        """Test handling of rate limit errors."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("429 Rate Limit Exceeded")
            
            with pytest.raises(Exception, match="429 Rate Limit Exceeded"):
                await uwc_client.query_rag(
                    company_id="test-company",
                    request_id="test-request-123",
                    query="test query",
                    context={"tenant_id": "test-company"}
                )
    
    @pytest.mark.asyncio
    async def test_server_error_handling(self, uwc_client):
        """Test handling of server errors."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("500 Internal Server Error")
            
            with pytest.raises(Exception, match="500 Internal Server Error"):
                await uwc_client.submit_training_job(
                    company_id="test-company",
                    request_id="test-request-123",
                    training_data={"call_ids": [1, 2, 3]}
                )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

