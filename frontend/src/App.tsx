import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CollectionProvider } from './contexts/CollectionContext';
import { TagProvider } from './contexts/TagContext';
import Login from './components/Login';
import Register from './components/Register';
import ProtectedRoute from './components/ProtectedRoute';
import Upload from './components/Upload';
import Search from './components/Search';
import Graph from './components/Graph';
import CollectionManager from './components/CollectionManager';

type View = 'upload' | 'search' | 'graph' | 'collections';

function MainApp() {
  const [currentView, setCurrentView] = useState<View>('search');
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <CollectionProvider>
      <TagProvider>
        <div className="min-h-screen bg-gray-100">
          {/* Header */}
          <header className="bg-white shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between items-center py-6">
                <div className="flex items-center space-x-3">
                  <div className="bg-blue-600 rounded-lg p-2">
                    <svg
                      className="h-8 w-8 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                      />
                    </svg>
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-gray-900">Recall</h1>
                    <p className="text-sm text-gray-500">Personal Knowledge Base</p>
                  </div>
                </div>

                <div className="flex items-center space-x-4">
                  <nav className="flex space-x-4">
                    <button
                      onClick={() => setCurrentView('search')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        currentView === 'search'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <svg
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                          />
                        </svg>
                        <span>Search</span>
                      </div>
                    </button>

                    <button
                      onClick={() => setCurrentView('graph')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        currentView === 'graph'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <svg
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
                          />
                        </svg>
                        <span>Graph</span>
                      </div>
                    </button>

                    <button
                      onClick={() => setCurrentView('upload')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        currentView === 'upload'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <svg
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                          />
                        </svg>
                        <span>Upload</span>
                      </div>
                    </button>

                    <button
                      onClick={() => setCurrentView('collections')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        currentView === 'collections'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <svg
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                          />
                        </svg>
                        <span>Collections</span>
                      </div>
                    </button>
                  </nav>

                  {/* User menu */}
                  <div className="flex items-center space-x-2 border-l pl-4">
                    <span className="text-sm text-gray-700">
                      {user?.username}
                    </span>
                    <button
                      onClick={handleLogout}
                      className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      Logout
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </header>

          {/* Main Content */}
          <main className="py-8">
            {currentView === 'search' && <Search />}
            {currentView === 'graph' && <Graph />}
            {currentView === 'upload' && <Upload />}
            {currentView === 'collections' && <CollectionManager />}
          </main>

          {/* Footer */}
          <footer className="bg-white border-t border-gray-200 mt-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <div className="flex justify-between items-center text-sm text-gray-500">
                <p>Powered by vector embeddings and knowledge graphs</p>
                <p>
                  Built with <span className="text-red-500">&hearts;</span> using React + FastAPI
                </p>
              </div>
            </div>
          </footer>
        </div>
      </TagProvider>
    </CollectionProvider>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <MainApp />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
