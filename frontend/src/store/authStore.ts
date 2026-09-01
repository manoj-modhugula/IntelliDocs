import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: string;
  email: string;
  name?: string;
  workspace_id?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  hasHydrated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  setDefaultWorkspace: (workspaceId: string | null) => Promise<void>;
  clearError: () => void;
}

const AUTH_API = '/api/auth';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      hasHydrated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch(`${AUTH_API}/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
          });
          
          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
          }
          
          const data = await response.json();
          
          set({
            user: data.user,
            token: data.access_token,
            isAuthenticated: true,
            hasHydrated: true,
            isLoading: false,
            error: null,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Login failed';
          const friendlyMessage = message.includes('fetch') || message.includes('network')
            ? 'Cannot reach server. Is the backend running on port 8000?'
            : message;
          set({
            isLoading: false,
            error: friendlyMessage,
          });
          throw error;
        }
      },

      register: async (email: string, password: string, name?: string) => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch(`${AUTH_API}/register`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password, name }),
          });
          
          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
          }
          
          const data = await response.json();
          
          set({
            user: data.user,
            token: data.access_token,
            isAuthenticated: true,
            hasHydrated: true,
            isLoading: false,
            error: null,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Registration failed';
          const friendlyMessage = message.includes('fetch') || message.includes('network')
            ? 'Cannot reach server. Is the backend running on port 8000?'
            : message;
          set({
            isLoading: false,
            error: friendlyMessage,
          });
          throw error;
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          hasHydrated: true,
          error: null,
        });
      },

      setDefaultWorkspace: async (workspaceId: string | null) => {
        const token = get().token;
        if (!token) return;
        try {
          const response = await fetch(`${AUTH_API}/me`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ workspace_id: workspaceId }),
          });
          if (!response.ok) return;
          const data = await response.json();
          // Backend returns user object directly, not wrapped in { user: ... }
          set((s) => ({
            user: data.id ? { ...s.user!, ...data, workspace_id: data.workspace_id } : s.user,
          }));
        } catch (err) {
          console.error('Failed to update default workspace:', err);
        }
      },

      refreshToken: async () => {
        const token = get().token;
        if (!token) return;
        
        try {
          const response = await fetch(`${AUTH_API}/refresh`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
          
          if (!response.ok) {
            // Token expired, logout
            set({
              user: null,
              token: null,
              isAuthenticated: false,
              hasHydrated: true,
            });
            return;
          }
          
          const data = await response.json();
          
          set({
            token: data.access_token,
            user: data.user,
            isAuthenticated: Boolean(data.access_token),
            hasHydrated: true,
          });
        } catch (error) {
          console.error('Token refresh failed:', error);
        }
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'intellidocs-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
      }),
      merge: (persisted, current) => {
        const p = (persisted as Partial<AuthState> | undefined) ?? {};
        const token = p.token ?? current.token;
        return {
          ...current,
          ...p,
          token,
          isAuthenticated: Boolean(token),
          hasHydrated: true,
        };
      },
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.isAuthenticated = Boolean(state.token);
          state.hasHydrated = true;
        }
      },
    }
  )
);

export function useAuthHeaders(): HeadersInit {
  const token = useAuthStore((state) => state.token);
  
  if (token) {
    return {
      'Authorization': `Bearer ${token}`,
    };
  }
  
  return {};
}
