import { api } from './client'
import type { User } from '../types'

export const authApi = {
  register: (email: string, name: string, password: string) =>
    api.post<{ user: User; message: string }>('/auth/register', { email, name, password }),

  login: (email: string, password: string) =>
    api.post<{ user: User; message: string }>('/auth/login', { email, password }),

  logout: () => api.post<{ message: string }>('/auth/logout'),

  me: () => api.get<User>('/auth/me'),
}
