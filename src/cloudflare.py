from botocore.config import Config
from typing import Optional, List
from dotenv import load_dotenv
from uuid import UUID
import aioboto3
import asyncio
import os
import io

load_dotenv()


class CloudflareR2Bucket:
    """
    Async CloudflareR2 bucket wrapper using aioboto3.
    Optimized for fast uploads and concurrent operations.
    """
    _instance = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region: str = "auto",
    ):
        self.bucket_name = bucket_name
        self.prefix = os.getenv("CLOUDFLARE_PREFIX", "")
        self.endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self.region = region
        
        # Credentials for session
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        
        # Config for better performance
        self.config = Config(
            signature_version="s3v4",
            max_pool_connections=100,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        
        # aioboto3 session (created once)
        self.session = aioboto3.Session()
        self._initialized = True

    @classmethod
    async def get_instance(
        cls,
        account_id: str = os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        access_key_id: str = os.getenv("CLOUDFLARE_ACCESS_KEY"),
        secret_access_key: str = os.getenv("CLOUDFLARE_SECRET_ACCESS_KEY"),
        bucket_name: str = os.getenv("CLOUDFLARE_BUCKET_NAME"),
        region: str = "auto",
    ):
        """Thread-safe async singleton getter using double-checked locking"""
        if not cls._instance:
            async with cls._lock:
                if not cls._instance:
                    cls._instance = cls(
                        account_id,
                        access_key_id,
                        secret_access_key,
                        bucket_name,
                        region,
                    )
        return cls._instance

    async def _get_client(self):
        """Get an S3 client for use in async context"""
        return self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=self.config,
        )

    async def upload_file(
        self,
        key: str,
        file_path: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file from disk to R2.
        
        Args:
            key: S3 key/path in bucket
            file_path: Local file path
            content_type: MIME type (e.g., 'image/webp')
            
        Returns:
            Full URL to the uploaded file
        """
        extra = {"ContentType": content_type} if content_type else {}
        
        async with await self._get_client() as client:
            with open(file_path, "rb") as f:
                await client.upload_fileobj(f, self.bucket_name, key, ExtraArgs=extra)
        
        return self.prefix + key

    async def upload_bytes(
        self,
        key: str,
        data: io.BytesIO,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload bytes directly to R2.
        
        Args:
            key: S3 key/path in bucket
            data: BytesIO object containing file data
            content_type: MIME type
            
        Returns:
            Full URL to the uploaded file
        """
        extra = {"ContentType": content_type} if content_type else {}
        
        async with await self._get_client() as client:
            await client.upload_fileobj(data, self.bucket_name, key, ExtraArgs=extra)
        
        return self.prefix + key

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for direct access"""
        async with await self._get_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )

    async def list_files(self, prefix: str = "") -> List[str]:
        """List all files with a given prefix"""
        files = []
        
        async with await self._get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                contents = page.get("Contents", [])
                files.extend([item["Key"] for item in contents])
        
        return files

    async def delete_file(self, key: str) -> None:
        """Delete a single file from R2"""
        async with await self._get_client() as client:
            await client.delete_object(Bucket=self.bucket_name, Key=key)

    async def delete_by_prefix(self, prefix: str) -> int:
        """
        Delete all files with a given prefix.
        
        Args:
            prefix: S3 prefix to match
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        
        async with await self._get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                objects = page.get("Contents", [])
                if not objects:
                    continue
                
                delete_payload = {"Objects": [{"Key": obj["Key"]} for obj in objects]}
                response = await client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete=delete_payload
                )
                deleted_count += len(response.get("Deleted", []))
        
        print(f"{prefix} | DELETED {deleted_count}")
        return deleted_count

    async def delete_multiple(self, keys: List[str]) -> int:
        """Delete multiple files by key"""
        if not keys:
            return 0
        
        deleted_count = 0
        
        async with await self._get_client() as client:
            delete_payload = {"Objects": [{"Key": key} for key in keys]}
            response = await client.delete_objects(
                Bucket=self.bucket_name,
                Delete=delete_payload
            )
            deleted_count = len(response.get("Deleted", []))
        
        return deleted_count

    async def upload_multiple(
        self,
        files: List[tuple[str, str]],
        content_type: Optional[str] = None
    ) -> List[str]:
        """
        Upload multiple files concurrently.
        
        Args:
            files: List of (key, file_path) tuples
            content_type: MIME type for all files
            
        Returns:
            List of URLs for uploaded files
        """
        tasks = [
            self.upload_file(key, file_path, content_type)
            for key, file_path in files
        ]
        return await asyncio.gather(*tasks)

    def extract_key(self, url: str) -> str:
        """Extract the S3 key from a full URL"""
        return url.replace(self.prefix, "").strip()
    
    def get_chapter_cover_key(self, chapter_id: UUID | str) -> str:
        return f"ougi/thumbs/chapters/{chapter_id}.webp"