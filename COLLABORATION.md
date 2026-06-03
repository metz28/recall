# Multi-User Collaboration

## Overview

The collaboration feature enables multiple users to work together on documents and collections with granular permission controls and activity tracking.

## Features

- **Granular Permissions**: Read, write, and admin access levels
- **Activity Tracking**: Full audit log of all actions
- **Self-Service**: Users can leave shared resources
- **Permission Management**: Update collaborator permissions anytime
- **Shared With Me**: View all resources others have shared with you
- **Statistics**: Track collaboration metrics

## Permission Levels

### Read
- View document content
- Search within the document
- View metadata and tags
- See collaborators list

### Write
- Everything in Read, plus:
- Edit document metadata
- Add/remove tags
- Add/remove from collections
- Update document title

### Admin
- Everything in Write, plus:
- Add new collaborators
- Remove collaborators
- Update collaborator permissions
- View activity log

### Owner
- Everything in Admin, plus:
- Delete the document
- Transfer ownership (future)
- Cannot be removed as collaborator

## Database Schema

### Collaborators Table

```sql
CREATE TABLE collaborators (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,        -- 'document' or 'collection'
    resource_id TEXT NOT NULL,          -- Document/collection ID
    collaborator_id TEXT NOT NULL,      -- User ID of collaborator
    permission TEXT NOT NULL,           -- 'read', 'write', 'admin'
    added_by TEXT NOT NULL,             -- User ID who added them
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    FOREIGN KEY (collaborator_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE CASCADE
)
```

### Activity Log Table

```sql
CREATE TABLE activity_log (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    user_id TEXT NOT NULL,              -- Who performed the action
    action TEXT NOT NULL,               -- Action type (created, edited, shared, etc.)
    details TEXT,                       -- Optional details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
```

## API Endpoints

### Add Collaborator
**POST** `/api/collaboration/collaborators`

```json
{
  "resource_type": "document",
  "resource_id": "doc-uuid",
  "collaborator_email": "user@example.com",
  "permission": "write",
  "message": "Optional message"
}
```

### List Collaborators
**GET** `/api/collaboration/collaborators/{resource_type}/{resource_id}`

### Update Permission
**PUT** `/api/collaboration/collaborators/{collaborator_id}`

```json
{
  "permission": "admin"
}
```

### Remove Collaborator
**DELETE** `/api/collaboration/collaborators/{collaborator_id}`

### Shared With Me
**GET** `/api/collaboration/shared-with-me`

Returns all documents and collections shared with the current user.

### Activity Log
**GET** `/api/collaboration/activity/{resource_type}/{resource_id}?limit=50`

### Collaboration Stats
**GET** `/api/collaboration/stats`

Returns:
- Total resources shared by you
- Total resources shared with you
- Total collaborators on your resources
- Recent activity count (last 7 days)

### Check Permissions
**GET** `/api/collaboration/permissions/{resource_type}/{resource_id}`

Returns your permission level and capabilities.

## Usage Examples

### Adding a Collaborator

```bash
curl -X POST "http://localhost:8000/api/collaboration/collaborators" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "document",
    "resource_id": "abc-123",
    "collaborator_email": "colleague@example.com",
    "permission": "write"
  }'
```

### Viewing Shared Resources

```bash
curl "http://localhost:8000/api/collaboration/shared-with-me" \
  -H "Authorization: Bearer $TOKEN"
```

### Checking Your Permission

```bash
curl "http://localhost:8000/api/collaboration/permissions/document/abc-123" \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "has_access": true,
  "permission_level": "write",
  "can_read": true,
  "can_write": true,
  "can_admin": false,
  "is_owner": false
}
```

### Viewing Activity Log

```bash
curl "http://localhost:8000/api/collaboration/activity/document/abc-123?limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

## Activity Types

The system tracks these activity types:

- `created` - Document/collection created
- `edited` - Metadata or content updated
- `deleted` - Resource deleted
- `shared` - Shared with a collaborator
- `updated_permission` - Collaborator permission changed
- `removed_collaborator` - Collaborator removed
- `left` - User left as collaborator
- `tag_added` - Tag added
- `tag_removed` - Tag removed
- `collection_changed` - Moved to different collection

## Security Considerations

### Permission Checks

All operations verify permissions before execution:

1. **Read Operations**: User must have at least `read` permission
2. **Write Operations**: User must have at least `write` permission
3. **Admin Operations**: User must have `admin` or `owner` permission

### Self-Service Removal

Users can remove themselves from any shared resource, regardless of their permission level.

### Owner Protection

- The document owner cannot be removed as a collaborator
- The owner always has full permissions
- Owner status is determined by the `user_id` field on the document

### Audit Trail

All collaboration actions are logged in the activity log, providing a complete audit trail.

## Integration with Existing Features

### Search
Collaborators can search within documents they have access to. Search results respect permission levels.

### Collections
When sharing a collection, all documents within that collection are accessible to collaborators based on their permission level.

### Tags
Users with `write` permission or higher can add/remove tags on shared documents.

### Export/Import
Only the owner can export/import documents. Collaborators are not exported/imported.

### Shareable Links
Users with `admin` permission can create public shareable links.

## Future Enhancements

- [ ] Transfer ownership to another user
- [ ] Bulk add collaborators (multiple users at once)
- [ ] Collaborator groups/teams
- [ ] Email notifications when added as collaborator
- [ ] Real-time collaboration indicators (who's viewing)
- [ ] Comment threads on documents
- [ ] @mentions in comments
- [ ] Approval workflows for write operations
- [ ] Time-based access (temporary collaborators)
- [ ] External collaborators (invite by email, no account required)

## Testing

To test the collaboration feature:

1. Create two user accounts
2. Login as User A, upload a document
3. Add User B as a collaborator with `write` permission
4. Login as User B
5. View shared resources at `/api/collaboration/shared-with-me`
6. Verify User B can read and edit (based on permission)
7. Check activity log to see collaboration events

## Files Modified/Created

### Backend
- `backend/models/collaboration.py` - Pydantic models (NEW)
- `backend/services/collaboration_service.py` - Business logic (NEW)
- `backend/api/collaboration.py` - API endpoints (NEW)
- `backend/db/init_db.py` - Added collaborators and activity_log tables
- `backend/main.py` - Registered collaboration router

### Documentation
- `README.md` - Added collaboration API documentation
- `COLLABORATION.md` - This file (NEW)
