# Shareable Links Feature

## Overview

The shareable links feature allows users to create public links for documents, search results, and collections. Anyone with the link can view the content without authentication.

## Features

- **Share Documents**: Create public links to individual documents
- **Share Searches**: Save and share search queries with results
- **Share Collections**: Share entire collections of documents
- **Expiration**: Set expiration dates (1, 7, 30, 90 days, or never)
- **Access Control**: View-only access for shared links
- **Revocation**: Revoke or delete shares at any time
- **Analytics**: Track view counts and last accessed timestamps

## Implementation Details

### Backend

#### Database Schema
- New `shared_links` table with:
  - Unique secure tokens (32-byte random strings)
  - Resource type (document/search/collection)
  - Owner tracking and expiration
  - View count and access analytics
  - Metadata for search parameters

#### API Endpoints

**Authenticated (require JWT token):**
- `POST /api/shares/` - Create a share
- `GET /api/shares/` - List user's shares
- `DELETE /api/shares/{share_id}` - Revoke a share
- `DELETE /api/shares/{share_id}/permanent` - Permanently delete a share

**Public (no authentication):**
- `GET /api/shares/public/{token}/metadata` - Get share info
- `GET /api/shares/public/{token}/document` - Access shared document
- `GET /api/shares/public/{token}/document/chunks` - Get document chunks
- `GET /api/shares/public/{token}/search` - Execute shared search
- `GET /api/shares/public/{token}/collection` - Get collection documents

#### Security Features
- Secure random token generation using `secrets.token_urlsafe()`
- Token validation with expiration checking
- Owner-based access control (users can only share their own content)
- Rate limiting on public endpoints (recommended for production)

### Frontend

#### Components
1. **ShareButton** - Trigger button for sharing
2. **ShareModal** - Configuration dialog for creating shares
3. **SharedView** - Public view for accessing shared content
4. **ShareManager** - Manage user's shared links

#### UI Integration
- Share button on search results page
- Share button on each document in upload/document list
- New "Shares" tab in main navigation
- Public route at `/shared/:token` for shared content

## Usage

### Creating a Share (Web UI)

1. Navigate to Search or Upload view
2. Click the "Share" button on a document or search results
3. Configure expiration (optional)
4. Click "Create Share Link"
5. Copy the generated URL
6. Share the URL with others

### Creating a Share (API)

```bash
curl -X POST "http://localhost:8000/api/shares/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "document",
    "resource_id": "doc-uuid",
    "expires_in_days": 7
  }'
```

### Accessing a Shared Link

Simply open the share URL in a browser:
```
http://localhost:5173/shared/AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

No authentication required!

### Managing Shares

1. Click the "Shares" tab in the navigation
2. View all your active shares
3. See view counts and last accessed times
4. Revoke or delete shares as needed

## Security Considerations

### Current Implementation
- View-only access for shared links
- Secure random tokens (32 bytes = 256 bits)
- Owner-based access control
- Optional expiration dates
- Revocation capability

### Recommended for Production
- Add rate limiting on public endpoints
- Implement IP-based access logs
- Add CAPTCHA for abuse prevention
- Consider password protection option
- Add download limits for documents
- Implement audit logging

## Database Migration

The feature includes automatic database migration. When you start the application, the `shared_links` table will be created automatically if it doesn't exist.

## Configuration

The feature uses the existing `FRONTEND_URL` setting from `.env`:

```env
FRONTEND_URL=http://localhost:5173
```

This is used to generate the full share URLs.

## Future Enhancements

Potential improvements for future versions:

- [ ] Password-protected shares
- [ ] Custom expiration dates (specific date/time)
- [ ] Edit access level (currently view-only)
- [ ] Batch sharing (multiple documents at once)
- [ ] Share permissions (who can reshare)
- [ ] Email notifications when shared content is accessed
- [ ] Embedded view mode (iframe support)
- [ ] Share analytics dashboard
- [ ] QR code generation for shares
- [ ] Share templates (pre-configured settings)

## Testing

To test the implementation:

1. Start the backend: `python local/recall.py run` or `docker-compose up`
2. Start the frontend: `cd frontend && npm run dev`
3. Register/login to the application
4. Upload a document or perform a search
5. Click the "Share" button
6. Create a share link
7. Open the share link in an incognito window (to test public access)

## Files Modified/Created

### Backend
- `backend/db/init_db.py` - Added shared_links table
- `backend/models/share.py` - Pydantic models for shares (NEW)
- `backend/services/share_service.py` - Share business logic (NEW)
- `backend/api/shares.py` - Share API endpoints (NEW)
- `backend/api/ingest.py` - Added user_id to Qdrant payload
- `backend/main.py` - Registered shares router

### Frontend
- `frontend/src/types/index.ts` - Added share TypeScript types
- `frontend/src/api/client.ts` - Added share API functions
- `frontend/src/components/ShareButton.tsx` - Share trigger button (NEW)
- `frontend/src/components/ShareModal.tsx` - Share configuration modal (NEW)
- `frontend/src/components/SharedView.tsx` - Public share view (NEW)
- `frontend/src/components/ShareManager.tsx` - Manage shares UI (NEW)
- `frontend/src/components/Search.tsx` - Added share button
- `frontend/src/components/Upload.tsx` - Added share button
- `frontend/src/App.tsx` - Added shares route and view

### Documentation
- `README.md` - Updated roadmap and added shareable links documentation
- `SHAREABLE_LINKS.md` - This file (NEW)

## API Examples

See the README.md file for comprehensive API examples and usage patterns.
