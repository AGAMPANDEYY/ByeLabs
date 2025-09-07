"""
MinIO object storage client and utilities.

This module provides a client for interacting with MinIO (S3-compatible)
object storage for storing raw emails, attachments, and exported files.
"""

import hashlib
import logging
from typing import Optional, Union, BinaryIO
from datetime import datetime, timezone
from io import BytesIO

from minio import Minio
from minio.error import S3Error, InvalidResponseError
import structlog

from .config import settings

logger = structlog.get_logger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageClient:
    """
    MinIO client wrapper for object storage operations.
    
    This class provides a high-level interface for storing and retrieving
    objects from MinIO with proper error handling and logging.
    """
    
    def __init__(self):
        """Initialize the MinIO client."""
        self.client = Minio(
            endpoint=settings.s3_endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
            region=settings.s3_region
        )
        self.bucket_name = settings.s3_bucket
        self._ensure_bucket()
    
    def _ensure_bucket(self) -> None:
        """
        Ensure the bucket exists, create if it doesn't.
        
        Raises:
            StorageError: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                logger.info(f"Creating bucket: {self.bucket_name}")
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket created: {self.bucket_name}")
            else:
                logger.debug(f"Bucket exists: {self.bucket_name}")
        except S3Error as e:
            if "BucketAlreadyOwnedByYou" in str(e):
                logger.info(f"Bucket {self.bucket_name} already exists and is owned by us")
            else:
                logger.error(f"Failed to create bucket {self.bucket_name}: {e}")
                raise StorageError(f"Failed to create bucket: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating bucket: {e}")
            raise StorageError(f"Unexpected error: {e}")
    
    def put_bytes(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Store bytes data in MinIO.
        
        Args:
            key: Object key (path) in the bucket
            data: Bytes data or file-like object
            content_type: MIME type of the data
            metadata: Optional metadata dictionary
        
        Returns:
            URI of the stored object
        
        Raises:
            StorageError: If storage operation fails
        """
        try:
            # Convert bytes to BytesIO if needed
            if isinstance(data, bytes):
                data = BytesIO(data)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            # Add timestamp metadata
            metadata.update({
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "content_type": content_type
            })
            
            # Store the object
            logger.debug(f"Storing object: {key}")
            
            # Get the length of the data
            if hasattr(data, 'seek'):
                data.seek(0, 2)  # Seek to end
                length = data.tell()
                data.seek(0)  # Reset to beginning
            else:
                length = len(data)
            
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=key,
                data=data,
                length=length,
                content_type=content_type,
                metadata=metadata
            )
            
            # Generate URI
            uri = f"{self.bucket_name}/{key}"
            logger.info(f"Object stored successfully: {uri}")
            return uri
            
        except S3Error as e:
            logger.error(f"Failed to store object {key}: {e}")
            raise StorageError(f"Failed to store object: {e}")
        except Exception as e:
            logger.error(f"Unexpected error storing object: {e}")
            raise StorageError(f"Unexpected error: {e}")
    
    def get_bytes(self, key: str) -> bytes:
        """
        Retrieve bytes data from MinIO.
        
        Args:
            key: Object key (path) in the bucket
        
        Returns:
            Bytes data
        
        Raises:
            StorageError: If retrieval operation fails
        """
        try:
            logger.debug(f"Retrieving object: {key}")
            response = self.client.get_object(self.bucket_name, key)
            
            # Read all data
            data = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"Object retrieved successfully: {key} ({len(data)} bytes)")
            return data
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"Object not found: {key}")
                raise StorageError(f"Object not found: {key}")
            else:
                logger.error(f"Failed to retrieve object {key}: {e}")
                raise StorageError(f"Failed to retrieve object: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving object: {e}")
            raise StorageError(f"Unexpected error: {e}")
    
    def delete_object(self, key: str) -> None:
        """
        Delete an object from MinIO.
        
        Args:
            key: Object key (path) in the bucket
        
        Raises:
            StorageError: If deletion operation fails
        """
        try:
            logger.debug(f"Deleting object: {key}")
            self.client.remove_object(self.bucket_name, key)
            logger.info(f"Object deleted successfully: {key}")
            
        except S3Error as e:
            logger.error(f"Failed to delete object {key}: {e}")
            raise StorageError(f"Failed to delete object: {e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting object: {e}")
            raise StorageError(f"Unexpected error: {e}")
    
    def object_exists(self, key: str) -> bool:
        """
        Check if an object exists in MinIO.
        
        Args:
            key: Object key (path) in the bucket
        
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.client.stat_object(self.bucket_name, key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            else:
                logger.error(f"Error checking object existence {key}: {e}")
                raise StorageError(f"Error checking object existence: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking object existence: {e}")
            raise StorageError(f"Unexpected error: {e}")
    
    def get_object_info(self, key: str) -> dict:
        """
        Get metadata information about an object.
        
        Args:
            key: Object key (path) in the bucket
        
        Returns:
            Dictionary with object metadata
        
        Raises:
            StorageError: If operation fails
        """
        try:
            stat = self.client.stat_object(self.bucket_name, key)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified,
                "content_type": stat.content_type,
                "metadata": stat.metadata
            }
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageError(f"Object not found: {key}")
            else:
                logger.error(f"Failed to get object info {key}: {e}")
                raise StorageError(f"Failed to get object info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting object info: {e}")
            raise StorageError(f"Unexpected error: {e}")
    
    def list_objects(self, prefix: str = "", recursive: bool = True) -> list:
        """
        List objects in the bucket.
        
        Args:
            prefix: Object key prefix to filter by
            recursive: Whether to list recursively
        
        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=recursive
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"Failed to list objects: {e}")
            raise StorageError(f"Failed to list objects: {e}")
        except Exception as e:
            logger.error(f"Unexpected error listing objects: {e}")
            raise StorageError(f"Unexpected error: {e}")


# Utility functions

def calculate_checksum(data: Union[bytes, BinaryIO]) -> str:
    """
    Calculate SHA-256 checksum of data.
    
    Args:
        data: Bytes data or file-like object
    
    Returns:
        SHA-256 checksum as hexadecimal string
    """
    sha256_hash = hashlib.sha256()
    
    if isinstance(data, bytes):
        sha256_hash.update(data)
    else:
        # Reset file pointer to beginning
        data.seek(0)
        for chunk in iter(lambda: data.read(4096), b""):
            sha256_hash.update(chunk)
        data.seek(0)  # Reset again for potential future use
    
    return sha256_hash.hexdigest()


def generate_object_key(prefix: str, filename: str, timestamp: Optional[datetime] = None) -> str:
    """
    Generate a unique object key for storage.
    
    Args:
        prefix: Key prefix (e.g., "emails", "exports")
        filename: Original filename
        timestamp: Optional timestamp (defaults to now)
    
    Returns:
        Generated object key
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    # Format timestamp
    timestamp_str = timestamp.strftime("%Y/%m/%d/%H%M%S")
    
    # Generate unique key
    key = f"{prefix}/{timestamp_str}/{filename}"
    
    return key


def ensure_bucket(bucket_name: Optional[str] = None) -> None:
    """
    Ensure a bucket exists, create if it doesn't.
    
    Args:
        bucket_name: Bucket name (defaults to configured bucket)
    
    Raises:
        StorageError: If bucket creation fails
    """
    if bucket_name is None:
        bucket_name = settings.s3_bucket
    
    client = Minio(
        endpoint=settings.s3_endpoint.replace("http://", "").replace("https://", ""),
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=settings.s3_secure,
        region=settings.s3_region
    )
    
    try:
        if not client.bucket_exists(bucket_name):
            logger.info(f"Creating bucket: {bucket_name}")
            client.make_bucket(bucket_name)
            logger.info(f"Bucket created: {bucket_name}")
        else:
            logger.debug(f"Bucket exists: {bucket_name}")
    except S3Error as e:
        logger.error(f"Failed to create bucket {bucket_name}: {e}")
        raise StorageError(f"Failed to create bucket: {e}")
    except Exception as e:
        logger.error(f"Unexpected error creating bucket: {e}")
        raise StorageError(f"Unexpected error: {e}")


# Global storage client instance
storage_client = StorageClient()
