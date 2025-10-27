import React from 'react';
import { fireEvent, waitFor } from '@testing-library/react-native';
import { RegisterScreen } from '../RegisterScreen';
import { renderWithProviders } from '../../../test-utils/renderWithProviders';

const mutateAsyncMock = jest.fn();

jest.mock('../../../services/api/auth', () => ({
  useRegister: () => ({
    mutateAsync: mutateAsyncMock,
    isLoading: false,
    isError: false,
  }),
}));

describe('RegisterScreen', () => {
  beforeEach(() => {
    mutateAsyncMock.mockResolvedValue({ token: 'registered-token' });
  });

  it('prevents submission when passwords do not match', async () => {
    const onSuccess = jest.fn();
    const onNavigate = jest.fn();
    const { getByLabelText, getByRole, getByText } = renderWithProviders(
      <RegisterScreen onSuccess={onSuccess} onNavigateToLogin={onNavigate} />
    );

    fireEvent.changeText(getByLabelText('name-input'), 'Marie');
    fireEvent.changeText(getByLabelText('email-input'), 'marie@example.com');
    fireEvent.changeText(getByLabelText('password-input'), 'password123');
    fireEvent.changeText(getByLabelText('confirmPassword-input'), 'password456');
    fireEvent.press(getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(getByText('Passwords must match')).toBeTruthy();
    });
    expect(mutateAsyncMock).not.toHaveBeenCalled();
  });

  it('submits registration details when valid', async () => {
    const onSuccess = jest.fn();
    const onNavigate = jest.fn();
    const { getByLabelText, getByRole } = renderWithProviders(
      <RegisterScreen onSuccess={onSuccess} onNavigateToLogin={onNavigate} />
    );

    fireEvent.changeText(getByLabelText('name-input'), 'Marie');
    fireEvent.changeText(getByLabelText('email-input'), 'marie@example.com');
    fireEvent.changeText(getByLabelText('password-input'), 'password123');
    fireEvent.changeText(getByLabelText('confirmPassword-input'), 'password123');
    fireEvent.press(getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        name: 'Marie',
        email: 'marie@example.com',
        password: 'password123',
      });
      expect(onSuccess).toHaveBeenCalledWith('registered-token');
    });
  });
});
