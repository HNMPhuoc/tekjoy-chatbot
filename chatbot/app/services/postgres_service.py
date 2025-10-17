from ..db.database import get_session
from datetime import datetime
import json
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def delete_file_by_id(file_id: str):
    db_session = get_session()
    async with db_session as session:
        try:
            query = text("DELETE FROM files WHERE id = :file_id")
            await session.execute(query, {"file_id": file_id})
            await session.commit()
            return {"success": True}
        except Exception as e:
            await session.rollback()
            return {"success": False, "error": str(e)}

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class PostgresService:
    @staticmethod
    async def insert_file_data(
        original_file_name: str,
        file_extension: str,
        mime_type: str,
        file_size_bytes: int,
        storage_path: str,
        thumbnail_path: str = None,
        document_type: str = None,
        uploaded_by_user_id: str = None,
        processing_status: str = 'pending',
        error_message: str = None,
        project_code: str = None,
        project_name: str = None,
        document_date: datetime = None,
        vendor_name: str = None,
        contract_number: str = None,
        total_value: float = None,
        currency: str = None,
        warranty_period_months: int = None,
        is_template: bool = False,
        keywords: list = None,
        folder_id: str = None,
        folder_path: str = None,
        extracted_text: str = None,
        ai_summary: dict = None,
        ai_extracted_data: dict = None,
        download_link: str = None,
        char_count: int = None,
        word_count: int = None
    ):
        db_session = get_session()
        async with db_session as session:
            try:
                # Convert UUID strings to UUID objects if needed
                if uploaded_by_user_id and not isinstance(uploaded_by_user_id, UUID):
                    try:
                        uploaded_by_user_id = UUID(uploaded_by_user_id)
                    except ValueError:
                        pass
                        
                if folder_id and not isinstance(folder_id, UUID):
                    try:
                        folder_id = UUID(folder_id)
                    except ValueError:
                        pass
                
                # Convert dicts to JSON with custom encoder
                ai_summary_json = json.dumps(ai_summary, cls=CustomJSONEncoder) if ai_summary else None
                ai_extracted_data_json = json.dumps(ai_extracted_data, cls=CustomJSONEncoder) if ai_extracted_data else None
                
                # Ensure keywords is a list
                keywords_array = keywords if keywords else []
                
                query = text("""
                    INSERT INTO files (
                        original_file_name, file_extension, mime_type, file_size_bytes,
                        storage_path, thumbnail_path, document_type, uploaded_by_user_id,
                        processing_status, error_message, project_code, project_name,
                        document_date, vendor_name, contract_number, total_value,
                        currency, warranty_period_months, is_template, keywords,
                        folder_id, folder_path, extracted_text, ai_summary,
                        ai_extracted_data, download_link, char_count, word_count
                    ) VALUES (
                        :original_file_name, :file_extension, :mime_type, :file_size_bytes,
                        :storage_path, :thumbnail_path, :document_type, :uploaded_by_user_id,
                        :processing_status, :error_message, :project_code, :project_name,
                        :document_date, :vendor_name, :contract_number, :total_value,
                        :currency, :warranty_period_months, :is_template, :keywords,
                        :folder_id, :folder_path, :extracted_text, :ai_summary,
                        :ai_extracted_data, :download_link, :char_count, :word_count
                    )
                    RETURNING *
                """)
                
                result = await session.execute(
                    query,
                    {
                        "original_file_name": original_file_name,
                        "file_extension": file_extension,
                        "mime_type": mime_type,
                        "file_size_bytes": file_size_bytes,
                        "storage_path": storage_path,
                        "thumbnail_path": thumbnail_path,
                        "document_type": document_type,
                        "uploaded_by_user_id": uploaded_by_user_id,
                        "processing_status": processing_status,
                        "error_message": error_message,
                        "project_code": project_code,
                        "project_name": project_name,
                        "document_date": document_date,
                        "vendor_name": vendor_name,
                        "contract_number": contract_number,
                        "total_value": total_value,
                        "currency": currency,
                        "warranty_period_months": warranty_period_months,
                        "is_template": is_template,
                        "keywords": keywords_array,
                        "folder_id": folder_id,
                        "folder_path": folder_path,
                        "extracted_text": extracted_text,
                        "ai_summary": ai_summary_json,
                        "ai_extracted_data": ai_extracted_data_json,
                        "download_link": download_link,
                        "char_count": char_count,
                        "word_count": word_count
                    }
                )
                
                row = result.fetchone()
                await session.commit()
                
                # Convert the row to a dictionary
                file_data = dict(row._mapping)
                
                # Convert special types
                for key, value in file_data.items():
                    if isinstance(value, UUID):
                        file_data[key] = str(value)
                    elif isinstance(value, datetime):
                        file_data[key] = value.isoformat()
                
                return {
                    "success": True,
                    "file_info": file_data
                }

            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}

    @staticmethod
    async def update_file_data(file_id: str, update_data: dict):
        db_session = get_session()
        async with db_session as session:
            try:
                # Create SET clause and values
                set_clause = []
                values = {}
                for key, value in update_data.items():
                    set_clause.append(f"{key} = :{key}")
                    if isinstance(value, dict):
                        values[key] = json.dumps(value, cls=CustomJSONEncoder)
                    elif isinstance(value, (UUID, datetime)):
                        values[key] = str(value)
                    else:
                        values[key] = value
                
                values['file_id'] = file_id
                
                query = text(f"""
                    UPDATE files 
                    SET {', '.join(set_clause)}
                    WHERE id = :file_id
                    RETURNING *
                """)
                
                result = await session.execute(query, values)
                updated_file = result.fetchone()
                
                if not updated_file:
                    return {"success": False, "error": "File not found"}
                
                await session.commit()
                
                # Convert row to dictionary
                file_data = dict(updated_file._mapping)
                
                # Convert special types
                for key, value in file_data.items():
                    if isinstance(value, UUID):
                        file_data[key] = str(value)
                    elif isinstance(value, datetime):
                        file_data[key] = value.isoformat()
                
                return {"success": True, "file": file_data}

            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}

    @staticmethod
    async def get_file_by_id(file_id: str):
        db_session = get_session()
        async with db_session as session:
            try:
                query = text("SELECT * FROM files WHERE id = :file_id")
                result = await session.execute(query, {"file_id": file_id})
                file_data = result.fetchone()
                
                if not file_data:
                    return {"success": False, "error": "File not found"}
                
                # Convert row to dictionary
                file_dict = dict(file_data._mapping)
                
                # Convert special types
                for key, value in file_dict.items():
                    if isinstance(value, UUID):
                        file_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        file_dict[key] = value.isoformat()
                
                return {"success": True, "file": file_dict}

            except Exception as e:
                return {"success": False, "error": str(e)}

    @staticmethod
    async def get_visible_files_for_user(user_id: int):
        db_session = get_session()
        async with db_session as session:
            try:
                query = text("SELECT * FROM get_visible_files_for_user(:user_id)")
                result = await session.execute(query, {"user_id": user_id})
                rows = result.fetchall()
                
                files = []
                for row in rows:
                    file_dict = dict(row._mapping)
                    # Convert special types
                    for key, value in file_dict.items():
                        if isinstance(value, UUID):
                            file_dict[key] = str(value)
                        elif isinstance(value, datetime):
                            file_dict[key] = value.isoformat()
                    files.append(file_dict)
                
                return {"success": True, "files": files}

            except Exception as e:
                return {"success": False, "error": str(e)}


async def run_sql_query(sql_query: str):
    db_session = get_session()
    async with db_session as session:
        try:
            # Execute the query safely using SQLAlchemy text
            query = text(sql_query)
            result = await session.execute(query)
            rows = result.fetchall()
            
            results = []
            for row in rows:
                row_dict = dict(row._mapping)
                # Convert special types
                for key, value in row_dict.items():
                    if isinstance(value, UUID):
                        row_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                results.append(row_dict)
            return results

        except Exception as e:
            print(f"Error executing SQL query: {str(e)}")
            return []

# Create instance
postgres_service = PostgresService()