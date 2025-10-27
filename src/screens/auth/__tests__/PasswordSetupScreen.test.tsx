import React from 'react';
import { fireEvent, waitFor } from '@testing-library/react-native';
import { PasswordSetupScreen } from '../PasswordSetupScreen';
import { renderWithProviders } from '../../../test-utils/renderWithProviders';

const mutateAsyncMock = jest.fn();

jest.mock('../../../services/api/auth', () => ({
  usePasswordSetup: () => ({
    mutateAsync: mutateAsyncMock,
    isLoading: false,
    isError: false,
  }),
}));

describe('PasswordSetupScreen', () => {
  beforeEach(() => {
    mutateAsyncMock.mockResolvedValue({ success: true });
  });

  it('requires token and matching passwords', async () => {
    const onSuccess = jest.fn();
    const { getByRole, getByText } = renderWithProviders(<PasswordSetupScreen onSuccess={onSuccess} />);

    fireEvent.press(getByRole('button', { name: /save password/i }));

    await waitFor(() => {
      expect(getByText('Invite token is required')).toBeTruthy();
      expect(getByText('Password is required')).toBeTruthy();
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('submits password setup when valid', async () => {
    const onSuccess = jest.fn();
    const { getByLabelText, getByRole } = renderWithProviders(<PasswordSetupScreen onSuccess={onSuccess} />);

    fireEvent.changeText(getByLabelText('token-input'), 'invite-token');
    fireEvent.changeText(getByLabelText('password-input'), 'password123');
    fireEvent.changeText(getByLabelText('confirmPassword-input'), 'password123');
    fireEvent.press(getByRole('button', { name: /save password/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith({ token: 'invite-token', password: 'password123' });
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
