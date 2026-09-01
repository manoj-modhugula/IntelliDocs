"""Tests for configuration module."""

import pytest
from app.core.config import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_settings_has_database_url(self):
        """Test settings has DATABASE_URL."""
        settings = Settings()
        assert hasattr(settings, "DATABASE_URL")

    def test_settings_has_aws_region(self):
        """Test settings has AWS_REGION."""
        settings = Settings()
        assert hasattr(settings, "AWS_REGION")

    def test_settings_has_bedrock_model_id(self):
        """Test settings has BEDROCK_MODEL_ID."""
        settings = Settings()
        assert hasattr(settings, "BEDROCK_MODEL_ID")

    def test_settings_has_s3_bucket(self):
        """Test settings has S3_BUCKET_NAME."""
        settings = Settings()
        assert hasattr(settings, "S3_BUCKET_NAME")

    def test_settings_has_cors_origins(self):
        """Test settings has CORS_ORIGINS."""
        settings = Settings()
        assert hasattr(settings, "CORS_ORIGINS")
        assert isinstance(settings.CORS_ORIGINS, list)

    def test_settings_has_chunk_config(self):
        """Test settings has chunking configuration."""
        settings = Settings()
        assert hasattr(settings, "CHUNK_SIZE")
        assert hasattr(settings, "CHUNK_OVERLAP")
        assert settings.CHUNK_SIZE > 0
        assert settings.CHUNK_OVERLAP >= 0

    def test_settings_has_cache_config(self):
        """Test settings has cache configuration."""
        settings = Settings()
        assert hasattr(settings, "CACHE_TTL_SECONDS")
        assert hasattr(settings, "SEMANTIC_CACHE_THRESHOLD")


class TestSettingsDefaults:
    """Tests for settings default values."""

    def test_debug_is_boolean(self):
        """Test DEBUG is boolean."""
        settings = Settings()
        assert isinstance(settings.DEBUG, bool)

    def test_chunk_size_is_reasonable(self):
        """Test chunk size is reasonable."""
        settings = Settings()
        assert 100 <= settings.CHUNK_SIZE <= 10000

    def test_semantic_weight_is_valid(self):
        """Test semantic weight is between 0 and 1."""
        settings = Settings()
        assert 0 <= settings.SEMANTIC_WEIGHT <= 1
