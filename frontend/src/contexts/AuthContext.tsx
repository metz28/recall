import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, AuthResponse, RegisterRequest } from '../types';
import { login as apiLogin, register as apiRegister, getCurrentUser, logout as apiLogout } from '../api/client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load token and user from localStorage on mount
  useEffect(() => {
    const loadUser = async () => {
      const storedToken = localStorage.getItem('authToken');
      const storedUser = localStorage.getItem('user');

      if (storedToken) {
        setToken(storedToken);

        // Try to fetch current user
        try {
          const currentUser = await getCurrentUser();
          setUser(currentUser);
          localStorage.setItem('user', JSON.stringify(currentUser));
        } catch (error) {
          // Token is invalid, clear it
          localStorage.removeItem('authToken');
          localStorage.removeItem('user');
          setToken(null);
          setUser(null);
        }
      } else if (storedUser) {
        // Clear stale user data if no token
        localStorage.removeItem('user');
      }

      setIsLoading(false);
    };

    loadUser();
  }, []);

  const login = async (email: string, password: string) => {
    const response: AuthResponse = await apiLogin(email, password);

    setToken(response.access_token);
    setUser(response.user);

    localStorage.setItem('authToken', response.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));
  };

  const register = async (data: RegisterRequest) => {
    const response = await apiRegister(data);

    // After registration, log the user in
    await login(data.email, data.password);
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch (error) {
      // Ignore errors during logout
      console.error('Logout error:', error);
    }

    setUser(null);
    setToken(null);

    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
  };

  const value: AuthContextType = {
    user,
    token,
    isLoading,
    isAuthenticated: !!user && !!token,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
