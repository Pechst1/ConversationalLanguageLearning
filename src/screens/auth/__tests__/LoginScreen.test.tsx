import React from 'react';
import { fireEvent, waitFor } from '@testing-library/react-native';
import { LoginScreen } from '../LoginScreen';
import { renderWithProviders } from '../../../test-utils/renderWithProviders';

const mutateAsyncMock = jest.fn();

jest.mock('../../../services/api/auth', () => ({
  useLogin: () => ({
    mutateAsync: mutateAsyncMock,
    isLoading: false,
    isError: false,
  }),
}));

describe('LoginScreen', () => {
  beforeEach(() => {
    mutateAsyncMock.mockResolvedValue({ token: 'token123' });
  });

  it('validates form fields before submitting', async () => {
    const onSuccess = jest.fn();
    const { getByText, getByRole } = renderWithProviders(
      <LoginScreen onSuccess={onSuccess} onForgotPassword={jest.fn()} />
    );

    fireEvent.press(getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(getByText('Email is required')).toBeTruthy();
      expect(getByText('Password is required')).toBeTruthy();
    });

    expect(mutateAsyncMock).not.toHaveBeenCalled();
  });

  it('submits credentials and notifies parent on success', async () => {
    const onSuccess = jest.fn();
    const { getByLabelText, getByRole } = renderWithProviders(
      <LoginScreen onSuccess={onSuccess} onForgotPassword={jest.fn()} />
    );

    fireEvent.changeText(getByLabelText('email-input'), 'learner@example.com');
    fireEvent.changeText(getByLabelText('password-input'), 'password123');
    fireEvent.press(getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        email: 'learner@example.com',
        password: 'password123',
      });
      expect(onSuccess).toHaveBeenCalledWith('token123');
    });
  });
});
