"""
S3 storage service for secure file storage with tenant isolation.
Handles document uploads, audio files, and provides presigned URLs for secure access.
"""
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import BinaryIO, Optional
import uuid
from datetime import datetime, timedelta
from app.config import settings
from app.obs.logging import get_logger

logger = get_logger(__name__)


class StorageException(Exception):
    """Base exception for storage operations."""
    pass


class StorageService:
    """
    S3 storage service with multi-tenant isolation.
    
    File structure:
    {bucket}/{tenant_id}/{file_type}/{uuid}/{filename}
    
    Example:
    otto-documents-prod/company_123/documents/abc-def-ghi/sales_script.pdf
    """
    
    def __init__(self):
        """Initialize S3 client with configured credentials."""
        if not settings.is_storage_configured():
            logger.warning("S3 storage not fully configured, service may not work")
            self.s3_client = None
            return
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket = settings.S3_BUCKET
            logger.info(f"S3 storage service initialized: bucket={self.bucket}, region={settings.AWS_REGION}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            self.s3_client = None
    
    def _check_initialized(self):
        """Verify S3 client is initialized."""
        if not self.s3_client:
            raise StorageException("S3 storage not configured. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and S3_BUCKET.")
    
    async def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        tenant_id: str,
        file_type: str = "documents",
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload file to S3 with tenant isolation.
        
        Args:
            file: File object or binary data
            filename: Original filename
            tenant_id: Company/tenant ID for isolation
            file_type: Category (documents, audio, images, etc.)
            content_type: MIME type (auto-detected if not provided)
        
        Returns:
            Public URL to the uploaded file
        
        Raises:
            StorageException: If upload fails
        """
        self._check_initialized()
        
        # Generate unique key with tenant isolation
        file_uuid = str(uuid.uuid4())
        s3_key = f"{tenant_id}/{file_type}/{file_uuid}/{filename}"
        
        try:
            # Upload file
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.upload_fileobj(
                file,
                self.bucket,
                s3_key,
                ExtraArgs=extra_args
            )
            
            # Generate URL
            file_url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            
            logger.info(f"File uploaded successfully",
                       extra={
                           "tenant_id": tenant_id,
                           "filename": filename,
                           "s3_key": s3_key,
                           "file_type": file_type
                       })
            
            return file_url
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}",
                        extra={
                            "tenant_id": tenant_id,
                            "filename": filename,
                            "error_code": e.response.get('Error', {}).get('Code')
                        })
            raise StorageException(f"Failed to upload file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {str(e)}")
            raise StorageException(f"Upload error: {str(e)}")
    
    async def delete_file(self, file_url: str, tenant_id: str) -> bool:
        """
        Delete file from S3 (for GDPR compliance).
        
        Args:
            file_url: Full URL to the file
            tenant_id: Tenant ID for validation (ensures cross-tenant deletion prevention)
        
        Returns:
            True if deleted successfully
        
        Raises:
            StorageException: If deletion fails or tenant mismatch
        """
        self._check_initialized()
        
        try:
            # Extract S3 key from URL
            s3_key = self._extract_key_from_url(file_url)
            
            # Verify tenant owns this file
            if not s3_key.startswith(f"{tenant_id}/"):
                raise StorageException(f"Tenant {tenant_id} does not own file {s3_key}")
            
            # Delete file
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            
            logger.info(f"File deleted successfully",
                       extra={
                           "tenant_id": tenant_id,
                           "s3_key": s3_key
                       })
            
            return True
            
        except ClientError as e:
            logger.error(f"S3 deletion failed: {str(e)}")
            raise StorageException(f"Failed to delete file: {str(e)}")
    
    async def delete_tenant_files(self, tenant_id: str) -> int:
        """
        Delete ALL files for a tenant (company offboarding/GDPR).
        
        WARNING: This is a destructive operation!
        
        Args:
            tenant_id: Company ID
        
        Returns:
            Number of files deleted
        """
        self._check_initialized()
        
        try:
            # List all objects with tenant prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket,
                Prefix=f"{tenant_id}/"
            )
            
            deleted_count = 0
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                # Batch delete (up to 1000 at a time)
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                
                if objects_to_delete:
                    response = self.s3_client.delete_objects(
                        Bucket=self.bucket,
                        Delete={'Objects': objects_to_delete}
                    )
                    deleted_count += len(response.get('Deleted', []))
            
            logger.warning(f"Deleted ALL files for tenant",
                          extra={
                              "tenant_id": tenant_id,
                              "files_deleted": deleted_count
                          })
            
            return deleted_count
            
        except ClientError as e:
            logger.error(f"Failed to delete tenant files: {str(e)}")
            raise StorageException(f"Tenant file deletion failed: {str(e)}")
    
    async def generate_presigned_url(
        self,
        file_url: str,
        expires_in: int = 3600,
        tenant_id: Optional[str] = None
    ) -> str:
        """
        Generate presigned URL for secure temporary access.
        
        Args:
            file_url: Full URL to the file
            expires_in: Expiration time in seconds (default 1 hour)
            tenant_id: Optional tenant ID for validation
        
        Returns:
            Presigned URL valid for expires_in seconds
        """
        self._check_initialized()
        
        try:
            # Extract S3 key from URL
            s3_key = self._extract_key_from_url(file_url)
            
            # Optional: Verify tenant owns file
            if tenant_id and not s3_key.startswith(f"{tenant_id}/"):
                raise StorageException(f"Tenant {tenant_id} does not own file")
            
            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': s3_key
                },
                ExpiresIn=expires_in
            )
            
            return presigned_url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise StorageException(f"Presigned URL generation failed: {str(e)}")
    
    async def file_exists(self, file_url: str) -> bool:
        """
        Check if file exists in S3.
        
        Args:
            file_url: Full URL to the file
        
        Returns:
            True if file exists
        """
        self._check_initialized()
        
        try:
            s3_key = self._extract_key_from_url(file_url)
            
            self.s3_client.head_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise StorageException(f"Error checking file existence: {str(e)}")
    
    async def get_file_size(self, file_url: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_url: Full URL to the file
        
        Returns:
            File size in bytes
        """
        self._check_initialized()
        
        try:
            s3_key = self._extract_key_from_url(file_url)
            
            response = self.s3_client.head_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            
            return response['ContentLength']
            
        except ClientError as e:
            raise StorageException(f"Error getting file size: {str(e)}")
    
    def _extract_key_from_url(self, file_url: str) -> str:
        """
        Extract S3 key from full URL.
        
        Args:
            file_url: Full S3 URL
        
        Returns:
            S3 key (path within bucket)
        """
        # Handle different URL formats:
        # https://bucket.s3.region.amazonaws.com/key
        # https://bucket.s3.amazonaws.com/key
        # s3://bucket/key
        
        if file_url.startswith("s3://"):
            # s3://bucket/key
            parts = file_url.replace("s3://", "").split("/", 1)
            return parts[1] if len(parts) > 1 else ""
        
        elif ".s3." in file_url or ".s3-" in file_url:
            # Extract key from HTTPS URL
            # Split on amazonaws.com/ and take everything after
            if "amazonaws.com/" in file_url:
                return file_url.split("amazonaws.com/", 1)[1]
        
        # If we can't parse it, raise error
        raise ValueError(f"Invalid S3 URL format: {file_url}")


# Global storage service instance
storage_service = StorageService()




