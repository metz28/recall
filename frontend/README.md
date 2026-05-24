# Recall Frontend

Modern React TypeScript web interface for the Recall knowledge base system.

## Features

- **Document Upload**: Drag-and-drop interface for uploading documents (PDF, DOCX, TXT, Markdown, HTML)
- **Semantic Search**: Vector-based search with similarity scores
- **Document Management**: View all uploaded documents with metadata
- **Responsive Design**: Clean, modern UI built with Tailwind CSS

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Fast build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **Axios** - HTTP client

## Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

## Installation

```bash
cd frontend
npm install
```

## Development

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

The Vite dev server is configured to proxy API requests to `http://localhost:8000`, so make sure your backend is running.

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

Preview the production build:

```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and HTTP utilities
│   │   └── client.ts     # Backend API methods
│   ├── components/       # React components
│   │   ├── Upload.tsx    # Document upload interface
│   │   └── Search.tsx    # Search interface
│   ├── types/            # TypeScript type definitions
│   │   └── index.ts      # Shared types
│   ├── App.tsx           # Main application component
│   ├── main.tsx          # Application entry point
│   └── index.css         # Global styles (Tailwind)
├── index.html            # HTML template
├── vite.config.ts        # Vite configuration
├── tailwind.config.js    # Tailwind CSS configuration
├── tsconfig.json         # TypeScript configuration
└── package.json          # Dependencies
```

## API Integration

The frontend communicates with the FastAPI backend through these endpoints:

- `POST /api/ingest/upload` - Upload documents
- `GET /api/ingest/documents` - List documents
- `DELETE /api/ingest/documents/{id}` - Delete document
- `GET /api/search` - Vector search (semantic similarity)
- `GET /api/search/hybrid` - Hybrid search (vector + knowledge graph)

## Configuration

### API Base URL

The API base URL is configured in Vite's proxy settings (vite.config.ts):

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

To change the backend URL, edit `vite.config.ts`.

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Troubleshooting

### Backend connection issues

Make sure the backend is running on `http://localhost:8000`. Check the console for CORS errors.

### Build errors

Clear node_modules and reinstall:
```bash
rm -rf node_modules package-lock.json
npm install
```

## Future Enhancements

- Chat interface for RAG queries
- Entity browser and knowledge graph visualization
- Document collections and tags
- Advanced filters and sorting
- Dark mode support
