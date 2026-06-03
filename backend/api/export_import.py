"""
API endpoints for export/import functionality
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime

from models.export_import import (
    ExportRequest, ExportResponse, ImportRequest, ImportResponse
)
from models.user import User
from core.dependencies import get_current_user
from services import export_import_service

router = APIRouter()


@router.post("/export", response_model=ExportResponse)
async def export_data(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export documents, collections, or entire knowledge base.

    - **document**: Export a specific document by ID
    - **collection**: Export all documents in a collection
    - **all**: Export entire knowledge base
    """
    try:
        documents = []

        if export_request.export_type == "document":
            if not export_request.resource_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="resource_id is required for document export"
                )

            doc = await export_import_service.export_document(
                user_id=current_user.id,
                document_id=export_request.resource_id,
                include_embeddings=export_request.include_embeddings,
                include_graph=export_request.include_graph
            )

            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found or you don't have permission to export it"
                )

            documents = [doc]

        elif export_request.export_type == "collection":
            if not export_request.resource_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="resource_id is required for collection export"
                )

            documents = await export_import_service.export_collection(
                user_id=current_user.id,
                collection_name=export_request.resource_id,
                include_embeddings=export_request.include_embeddings,
                include_graph=export_request.include_graph
            )

            if not documents:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Collection not found or is empty"
                )

        elif export_request.export_type == "all":
            documents = await export_import_service.export_all(
                user_id=current_user.id,
                include_embeddings=export_request.include_embeddings,
                include_graph=export_request.include_graph
            )

            if not documents:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No documents found to export"
                )

        # Calculate statistics
        total_chunks = sum(len(doc.chunks) for doc in documents)
        total_entities = sum(len(doc.entities) if doc.entities else 0 for doc in documents)
        total_relationships = sum(len(doc.relationships) if doc.relationships else 0 for doc in documents)

        # Convert to JSON-serializable format
        export_data = {
            "version": "1.0",
            "export_type": export_request.export_type,
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": current_user.username,
            "include_embeddings": export_request.include_embeddings,
            "include_graph": export_request.include_graph,
            "total_documents": len(documents),
            "total_chunks": total_chunks,
            "total_entities": total_entities if export_request.include_graph else None,
            "total_relationships": total_relationships if export_request.include_graph else None,
            "documents": [doc.model_dump(mode='json') for doc in documents]
        }

        return ExportResponse(
            export_type=export_request.export_type,
            total_documents=len(documents),
            total_chunks=total_chunks,
            total_entities=total_entities if export_request.include_graph else None,
            total_relationships=total_relationships if export_request.include_graph else None,
            created_at=datetime.utcnow(),
            data=export_data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.post("/import", response_model=ImportResponse)
async def import_data(
    import_request: ImportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Import documents from exported data.

    - **skip**: Skip documents that already exist (default)
    - **replace**: Replace existing documents with imported versions
    - **merge**: Add imported data alongside existing documents
    """
    try:
        # Validate export data format
        if not isinstance(import_request.data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid import data format"
            )

        if "documents" not in import_request.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Import data must contain 'documents' field"
            )

        documents = import_request.data["documents"]
        if not isinstance(documents, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'documents' must be a list"
            )

        # Perform import
        stats = await export_import_service.import_documents(
            user_id=current_user.id,
            documents=documents,
            import_mode=import_request.import_mode,
            regenerate_embeddings=import_request.regenerate_embeddings,
            target_collection=import_request.target_collection
        )

        return ImportResponse(
            total_documents=len(documents),
            imported_documents=stats["imported"],
            skipped_documents=stats["skipped"],
            replaced_documents=stats["replaced"],
            total_chunks=stats["total_chunks"],
            total_entities=stats["total_entities"] if stats["total_entities"] > 0 else None,
            total_relationships=stats["total_relationships"] if stats["total_relationships"] > 0 else None,
            errors=stats["errors"],
            completed_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


@router.get("/export/document/{document_id}")
async def quick_export_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    include_embeddings: bool = False,
    include_graph: bool = True
):
    """Quick export endpoint for a single document (GET request)"""
    doc = await export_import_service.export_document(
        user_id=current_user.id,
        document_id=document_id,
        include_embeddings=include_embeddings,
        include_graph=include_graph
    )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    export_data = {
        "version": "1.0",
        "export_type": "document",
        "exported_at": datetime.utcnow().isoformat(),
        "exported_by": current_user.username,
        "include_embeddings": include_embeddings,
        "include_graph": include_graph,
        "total_documents": 1,
        "documents": [doc.model_dump(mode='json')]
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=recall-export-{document_id}.json"
        }
    )
