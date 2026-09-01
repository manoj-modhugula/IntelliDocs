import { toast } from '@/components/ui/Toaster';
import { useAuthStore } from '@/store/authStore';

/** Toast, clear the session, and send the user to login. Returns true if handled. */
export function handleUnauthorized(status: number): boolean {
  if (status !== 401) return false;
  toast('error', 'Session expired. Please sign in again.');
  useAuthStore.getState().logout();
  if (typeof window !== 'undefined') {
    const path = window.location.pathname;
    if (path !== '/login' && path !== '/register') {
      window.location.assign('/login');
    }
  }
  return true;
}
