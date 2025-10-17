from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.models import Folder, File, UserAccessFile
from app.schemas.autocomplete_schema import AutocompleteItem


class AutocompleteService:
    async def get_all_keywords(self, db: AsyncSession) -> List[dict]:
        """
        Get all keywords from the database.

        Args:
            db: Database session

        Returns:
            List of keyword dictionaries
        """
        # Implementation goes here
        return []


    async def get_folder_contents(
        self,
        db: AsyncSession,
        user_id: UUID,
        folder_id: Optional[UUID] = None,
        keyword: Optional[str] = None,
        prefix: str = "",
        limit: int = 50
    ) -> List[AutocompleteItem]:
        """
        Get contents of a folder (both files and subfolders) that user has access to.

        Args:
            db: Database session
            user_id: ID of the user
            folder_id: Optional folder ID to get contents from
            keyword: Optional keyword to find root folder
            prefix: Filter items by name prefix (case-insensitive contains)
            limit: Maximum number of items to return

        Returns:
            List of AutocompleteItem objects
        """
        items: List[AutocompleteItem] = []
        
        # If searching by keyword, find the root folder first
        if keyword and folder_id is None:
            root_folder = await db.execute(
                select(Folder).where(Folder.keyword == keyword)
            )
            root_folder = root_folder.scalars().first()
            if root_folder:
                folder_id = root_folder.id
        
        # Build base folder query
        folder_query = select(Folder)
        
        # Add where conditions for folders
        if folder_id is not None:
            folder_query = folder_query.where(Folder.parent_id == folder_id)
        else:
            folder_query = folder_query.where(Folder.parent_id.is_(None))
        
        # Add prefix filter if provided
        if prefix:
            folder_query = folder_query.where(Folder.name.ilike(f"%{prefix}%"))
        
        # Execute folder query
        folders = await db.execute(folder_query)
        
        # Process folders
        for folder in folders.scalars().all():
            items.append(AutocompleteItem(
                type="folder",
                id=folder.id,
                name=folder.name,
                parent_id=folder.parent_id
            ))
        
        # Build base file query with join to UserAccessFile
        file_query = select(File).join(
            UserAccessFile,
            and_(
                UserAccessFile.file_id == File.id,
                UserAccessFile.user_id == user_id
            )
        )
        
        # Add folder condition
        if folder_id is not None:
            file_query = file_query.where(File.folder_id == folder_id)
        else:
            file_query = file_query.where(File.folder_id.is_(None))
        
        # Add prefix filter if provided
        if prefix:
            file_query = file_query.where(File.original_file_name.ilike(f"%{prefix}%"))
        
        # Limit total results
        remaining_limit = limit - len(items)
        if remaining_limit > 0:
            file_query = file_query.limit(remaining_limit)
            
            # Execute file query
            files = await db.execute(file_query)
            
            # Process files
            for file in files.scalars().all():
                items.append(AutocompleteItem(
                    type="file",
                    id=file.id,
                    name=file.original_file_name,
                    parent_id=file.folder_id
                ))
        
        return items