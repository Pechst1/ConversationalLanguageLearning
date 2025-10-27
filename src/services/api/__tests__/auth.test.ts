import * as SecureStore from 'expo-secure-store';
import { apiClient } from '../client';
import { login, register, setupLearnerProfile, setupPassword } from '../auth';

let postSpy: jest.SpyInstance;

describe('auth API', () => {
  beforeEach(() => {
    postSpy = jest.spyOn(apiClient, 'post');
    jest.spyOn(SecureStore, 'setItemAsync').mockResolvedValue();
    jest.spyOn(SecureStore, 'deleteItemAsync').mockResolvedValue();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it('stores auth token on login', async () => {
    const token = 'login-token';
    postSpy.mockResolvedValue({ data: { token, user: { id: '1', email: 'e', name: 'n' } } });

    const response = await login({ email: 'learner@example.com', password: 'password123' });

    expect(postSpy).toHaveBeenCalledWith('/auth/login', {
      email: 'learner@example.com',
      password: 'password123',
    });
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(expect.any(String), token);
    expect(response.token).toEqual(token);
  });

  it('stores auth token on registration', async () => {
    const token = 'register-token';
    postSpy.mockResolvedValue({
      data: { token, user: { id: '2', email: 'test', name: 'Test' } },
    });

    const response = await register({ email: 'test@example.com', password: 'password123', name: 'Test' });

    expect(postSpy).toHaveBeenCalledWith('/auth/register', {
      email: 'test@example.com',
      password: 'password123',
      name: 'Test',
    });
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(expect.any(String), token);
    expect(response.token).toEqual(token);
  });

  it('sets learner profile with provided payload', async () => {
    const profile = { level: 'Beginner', goals: ['Travel'], updatedAt: new Date().toISOString() };
    postSpy.mockResolvedValue({ data: profile });

    const response = await setupLearnerProfile({ level: 'Beginner', goals: ['Travel'] });

    expect(postSpy).toHaveBeenCalledWith('/profile', { level: 'Beginner', goals: ['Travel'] });
    expect(response).toEqual(profile);
  });

  it('completes password setup', async () => {
    postSpy.mockResolvedValue({ data: { success: true } });

    const response = await setupPassword({ token: 'invite', password: 'password123' });

    expect(postSpy).toHaveBeenCalledWith('/auth/setup-password', {
      token: 'invite',
      password: 'password123',
    });
    expect(response).toEqual({ success: true });
  });
});
